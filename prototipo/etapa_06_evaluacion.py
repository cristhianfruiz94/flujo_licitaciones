"""
ETAPA 6 — Evaluación de la oportunidad (agente de IA + motor de reglas)
=======================================================================
Equivale a «Preparar agente IA» → «Agente IA (LLM vía OpenRouter)» →
«Parsear respuesta IA».

En producción, un LLM recibe la licitación normalizada, el análisis geográfico
y el histórico RUP, y devuelve un JSON con seis puntajes, el `match_final`, la
decisión y una justificación.

Este prototipo implementa las MISMAS reglas de forma determinística
(`MotorReglas`) para que el proceso sea auditable y reproducible sin llaves de
API. Si se configura `OPENROUTER_API_KEY` y se usa `--llm`, se llama al modelo y
el motor de reglas actúa como *guardrail*: recalcula `match_final` con los
pesos oficiales y marca discrepancias.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime

from . import config
from .utilidades import a_numero, normalizar, parsear_fecha_es

CAPITALES = {
    "leticia", "medellin", "arauca", "barranquilla", "cartagena", "tunja", "manizales",
    "florencia", "yopal", "popayan", "valledupar", "quibdo", "monteria", "bogota",
    "inirida", "san jose del guaviare", "neiva", "riohacha", "santa marta",
    "villavicencio", "pasto", "cucuta", "mocoa", "armenia", "pereira", "san andres",
    "bucaramanga", "sincelejo", "ibague", "cali", "mitu", "puerto carreno",
}


# ---------------------------------------------------------------------------
# Preparación del insumo del agente
# ---------------------------------------------------------------------------
def analisis_geografico(ubicacion: str) -> dict:
    res = {"departamento": None, "municipio": None, "clasificacion": "Otros Municipios", "interes_prioritario": False}
    if ubicacion and ":" in ubicacion:
        dep, mun = [p.strip() for p in ubicacion.split(":", 1)]
        res["departamento"], res["municipio"] = dep, mun
        m = normalizar(mun).replace(" d.c.", "")
        if m in ("cali", "bogota"):
            res.update(clasificacion="Mayor Interés", interes_prioritario=True)
        elif m in CAPITALES:
            res.update(clasificacion="Capital de Departamento", interes_prioritario=True)
        else:
            res.update(clasificacion="Municipio Ordinario")
    return res


def preparar_insumo(registro: dict, rup: list[dict], rup_corrupto: bool) -> dict:
    lic = {k: v for k, v in registro.items()}
    lic["analisis_geografico"] = analisis_geografico(registro.get("ubicacion", ""))
    return {"licitacion": lic, "backup_rup": rup, "backup_corrupto": rup_corrupto}


# ---------------------------------------------------------------------------
# Motor de reglas (réplica determinística del prompt de producción)
# ---------------------------------------------------------------------------
class MotorReglas:
    def __init__(self, perfil: config.PerfilNegocio = config.PERFIL) -> None:
        self.p = perfil

    # --- Línea de negocio ---------------------------------------------------
    def linea_negocio(self, objeto: str) -> int:
        o = normalizar(objeto)
        es_suministro = any(o.startswith(v) or f" {v}" in o[:60] for v in self.p.verbos_suministro)
        tiene_bien = any(k in o for k in self.p.palabras_linea2)
        return 2 if (es_suministro and tiene_bien) else 1

    # --- 1. Fit del objeto (80 % afinidad + 20 % filtro negativo) ------------
    def fit_objeto(self, objeto: str) -> tuple[int, list[str], list[str]]:
        o = normalizar(objeto)
        positivos = [k for k in self.p.palabras_linea1 + self.p.palabras_linea2 if k in o]
        negativos = [k for k in self.p.palabras_negativas if k in o]
        afinidad = min(100, 35 * len(positivos)) if positivos else 0
        castigo = 100 if negativos else 0
        score = round(0.8 * afinidad + 0.2 * (100 - castigo))
        if negativos and len(positivos) <= 1:
            score = min(score, 15)  # «castigar fuertemente»
        return max(0, min(100, score)), positivos, negativos

    # --- 2. Geografía --------------------------------------------------------
    def score_geografia(self, geo: dict, linea: int) -> int:
        dep = normalizar(geo.get("departamento") or "").replace(" d.c.", "")
        mun = normalizar(geo.get("municipio") or "").replace(" d.c.", "")
        tabla = self.p.geografia_linea1 if linea == 1 else self.p.geografia_linea2
        for llave in ((dep, mun), (dep, "*"), ("*", "*")):
            if llave in tabla:
                return tabla[llave]
        return 30

    # --- 3. Presupuesto ------------------------------------------------------
    def score_presupuesto(self, valor: float, geo: dict, linea: int) -> int | None:
        if valor <= 0:
            return None  # se elimina de la ponderación
        millones = valor / 1_000_000
        en_valle = normalizar(geo.get("departamento") or "") == "valle del cauca"
        if millones < 20:
            if 10 <= millones < 20 and en_valle:
                return 85
            base = 20
            if linea == 1 and not en_valle:
                base = max(0, base - 30)
            return base
        if millones < 80:
            return 80
        if millones <= 500:
            return 95
        return 100

    # --- 4. Entidad ----------------------------------------------------------
    def score_entidad(self, entidad: str, objeto: str) -> int:
        e = normalizar(entidad)
        if any(k in e for k in self.p.entidades_tier1):
            return 100
        if any(k in e for k in self.p.entidades_tier3):
            return 60
        if any(k in e for k in ("alcaldia", "municipio", "gobernacion", "departamento")):
            return 85 if any(k in normalizar(objeto) for k in self.p.palabras_saneamiento) else 60
        return 50

    # --- 5. Tiempo disponible para preparar la oferta -----------------------
    def score_tiempo(self, registro: dict) -> tuple[int, float | None]:
        recibido = datetime.fromisoformat(registro["fechaRecepcionISO"]).replace(tzinfo=None)
        cierre = None
        for ev in registro.get("_cronograma", []):
            if re.search(r"cierre|presentaci[oó]n de ofertas|vencimiento", ev.get("nombre", ""), re.I):
                fecha = ev.get("fecha", "")
                partes = fecha.split(" - ")
                cierre = parsear_fecha_es(partes[0], partes[1] if len(partes) > 1 else "")
                if cierre:
                    break
        if not cierre and registro.get("fechaVencimientoAPI"):
            cierre = parsear_fecha_es(str(registro["fechaVencimientoAPI"]))
        if not cierre:
            return 60, None
        dias = (cierre - recibido).total_seconds() / 86400
        return (100 if dias > 4 else 60 if dias >= 2 else 20), round(dias, 1)

    # --- 6. Frecuencia UNSPSC en el RUP --------------------------------------
    @staticmethod
    def score_frecuencia(todos_unspsc: str, rup: list[dict]) -> tuple[int, dict]:
        codigos = [c.strip()[:6] for c in (todos_unspsc or "").split("|") if c.strip()]
        rup6 = [str(c.get("unspsc", ""))[:6] for c in rup]
        conteo = {c: rup6.count(c) for c in dict.fromkeys(codigos)}
        if not codigos:
            return 20, conteo
        hallados = [c for c, n in conteo.items() if n > 0]
        if len(hallados) == len(conteo):
            return 100, conteo
        if hallados:
            return 85, conteo
        return 20, conteo

    # --- Ponderación ----------------------------------------------------------
    @staticmethod
    def ponderar(scores: dict) -> tuple[int, bool]:
        sin_presupuesto = scores.get("score_presupuesto") is None
        pesos = config.PESOS_SIN_PRESUPUESTO if sin_presupuesto else config.PESOS_CON_PRESUPUESTO
        total = sum((scores.get(k) or 0) * w for k, w in pesos.items())
        return max(0, min(100, round(total))), sin_presupuesto

    @staticmethod
    def decidir(match: int) -> str:
        if match >= 85:
            return "PARTICIPAR"
        if match >= 60:
            return "REVISIÓN MANUAL"
        return "NO PARTICIPAR"

    def evaluar(self, insumo: dict) -> dict:
        lic = insumo["licitacion"]
        geo = lic["analisis_geografico"]
        linea = self.linea_negocio(lic.get("objeto", ""))
        fit, pos, neg = self.fit_objeto(lic.get("objeto", ""))
        valor = a_numero(lic.get("valor"))
        tiempo, dias = self.score_tiempo(lic)
        frec, conteo = self.score_frecuencia(lic.get("todos_unspsc", ""), insumo["backup_rup"])
        scores = {
            "fit_objeto": fit,
            "score_entidad": self.score_entidad(lic.get("entidadContratante", ""), lic.get("objeto", "")),
            "score_geografia": self.score_geografia(geo, linea),
            "score_presupuesto": self.score_presupuesto(valor, geo, linea),
            "score_tiempo": tiempo,
            "score_frecuencia_unspsc": frec,
        }
        match, sin_ppto = self.ponderar(scores)
        decision = self.decidir(match)

        frec_txt = "; ".join(f"código {c} hallado {n} veces en el RUP" for c, n in conteo.items()) or "sin códigos UNSPSC"
        just = (
            f"Línea {linea}. Afinidad del objeto: {', '.join(pos) or 'ninguna palabra clave'}"
            f"{'; filtros negativos: ' + ', '.join(neg) if neg else ''}. "
            f"Geografía: {geo.get('municipio') or 'N/D'} ({geo.get('departamento') or 'N/D'}). "
            f"Presupuesto: {'no informado (excluido de la ponderación)' if sin_ppto else f'${valor:,.0f}'.replace(',', '.')}. "
            f"Tiempo al cierre: {dias if dias is not None else 'N/D'} días. Frecuencia UNSPSC: {frec_txt}."
        )
        return {
            "idContrato": lic.get("idContrato"),
            "codigoProceso": lic.get("codigoProceso"),
            "linea_negocio": linea,
            **{k: (0 if v is None else v) for k, v in scores.items()},
            "presupuesto_eliminado_de_ponderacion": sin_ppto,
            "descarte_temprano": bool(neg) and fit <= 15,
            "evidencia_insuficiente": not lic.get("objeto"),
            "backup_corrupto": insumo.get("backup_corrupto", False),
            "match_final": match,
            "decision": decision,
            "justificacion": just,
            "motor": "reglas",
        }


# ---------------------------------------------------------------------------
# Agente LLM (opcional)
# ---------------------------------------------------------------------------
PLANTILLA_PROMPT = """Eres un motor de evaluación automática dentro de un flujo de automatización.
NO eres un chatbot. Tu respuesta FINAL debe ser SOLO un JSON válido, sin markdown ni texto adicional.
Si falta información, no pidas datos: continúa con la mejor evidencia. Todos los scores son enteros 0–100.

ROL: experto en contratación pública colombiana (SECOP), análisis comercial B2G, clasificación UNSPSC
y matching técnico-comercial. Evalúa si la empresa debe participar en la licitación.

PERFIL DE LA EMPRESA:
{perfil}
CASTIGAR FUERTEMENTE: {negativos}.

CRITERIOS:
1. score_frecuencia_unspsc: compara los 6 primeros dígitos de los UNSPSC del proceso con backup_rup.
   Todos hallados = 100; alguno = 85; ninguno = 20. Incluye los conteos en la justificación.
2. score_geografia según la línea de negocio (tabla del perfil).
3. score_presupuesto: <20M=20; 20–80M=80; 80–500M=95; >500M=100. Si valor es 0/null, exclúyelo.
4. fit_objeto: 80 % afinidad con las líneas de negocio + 20 % filtros negativos.
5. score_entidad: Tier 1 empresas de servicios públicos de agua=100; Tier 2 alcaldías/gobernaciones
   con objeto de agua/saneamiento=85; Tier 3 puertos/petroleras=60.
   score_tiempo: >4 días al cierre=100; 2–4=60; <2=20.

PESOS con presupuesto: geografía 25 %, objeto 35 %, tiempo 5 %, UNSPSC 15 %, entidad 15 %, presupuesto 5 %.
PESOS sin presupuesto: geografía 27 %, objeto 38 %, tiempo 15 %, UNSPSC 15 %, entidad 5 %.
DECISIÓN: >=85 PARTICIPAR; 60–84 REVISIÓN MANUAL; <60 NO PARTICIPAR.

INSUMO:
{insumo}

SALIDA (estructura exacta):
{{"idContrato": "", "codigoProceso": "", "fit_objeto": 0, "score_entidad": 0, "score_geografia": 0,
"score_presupuesto": 0, "presupuesto_eliminado_de_ponderacion": false, "score_tiempo": 0,
"score_frecuencia_unspsc": 0, "descarte_temprano": false, "evidencia_insuficiente": false,
"backup_corrupto": false, "match_final": 0, "decision": null, "justificacion": null}}
"""


def construir_prompt(insumo: dict, perfil: config.PerfilNegocio = config.PERFIL) -> str:
    lic = {k: v for k, v in insumo["licitacion"].items() if not k.startswith("_")}
    lic["cronograma"] = insumo["licitacion"].get("_cronograma", [])
    datos = {"licitacion": lic, "backup_rup": insumo["backup_rup"][:200]}
    return PLANTILLA_PROMPT.format(
        perfil=perfil.descripcion,
        negativos=", ".join(perfil.palabras_negativas),
        insumo=json.dumps(datos, ensure_ascii=False, default=str),
    )


def parsear_respuesta_ia(raw: str) -> dict:
    """Port de 'Parsear_Respuesta_AI': tolera fences de markdown y texto extra."""
    if not raw:
        return {"parse_error": True, "error_message": "Sin salida del modelo", "match_final": 0, "decision": "ERROR"}
    limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw).strip(), flags=re.I)
    for candidato in (limpio, (re.search(r"\{[\s\S]*\}", limpio) or [None])[0]):
        if not candidato:
            continue
        try:
            return {**json.loads(candidato), "parse_error": False}
        except json.JSONDecodeError:
            continue
    return {"parse_error": True, "raw_output": limpio, "match_final": 0, "decision": "ERROR"}


def llamar_llm(prompt: str) -> str:
    if not config.LLM_API_KEY:
        raise RuntimeError("Configure OPENROUTER_API_KEY en .env para usar el modo LLM")
    cuerpo = {"model": config.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    req = urllib.request.Request(
        config.LLM_URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        return json.loads(r.read())["choices"][0]["message"]["content"]


def evaluar(insumo: dict, usar_llm: bool = False) -> dict:
    motor = MotorReglas()
    reglas = motor.evaluar(insumo)
    if not usar_llm:
        return reglas
    ia = parsear_respuesta_ia(llamar_llm(construir_prompt(insumo)))
    if ia.get("parse_error"):
        reglas["advertencia"] = "La respuesta del LLM no fue JSON válido; se usó el motor de reglas."
        return reglas
    # Guardrail: recalcular match con pesos oficiales a partir de los scores del LLM
    scores = {k: ia.get(k) for k in config.PESOS_CON_PRESUPUESTO}
    if ia.get("presupuesto_eliminado_de_ponderacion"):
        scores["score_presupuesto"] = None
    recalculado, _ = MotorReglas.ponderar(scores)
    ia["match_final_llm"] = ia.get("match_final")
    ia["match_final"] = recalculado
    ia["decision"] = MotorReglas.decidir(recalculado)
    ia["discrepancia_vs_reglas"] = abs(recalculado - reglas["match_final"])
    ia["motor"] = "llm+guardrail"
    return ia
