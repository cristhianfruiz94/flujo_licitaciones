"""
Orquestador del prototipo — reproduce el flujo de producción de punta a punta.

Uso:
    python -m prototipo.pipeline                 # modo demo con datos de ejemplo
    python -m prototipo.pipeline --imap --api    # fuentes reales (requiere .env)
    python -m prototipo.pipeline --llm           # evaluación con LLM + guardrail
    python -m prototipo.pipeline --umbral 70     # cambia el umbral de alerta
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from . import config
from .etapa_01_correo import leer_correos_demo, leer_correos_imap, parsear_correo
from .etapa_02_api import ClienteAPI, ClienteAPIDemo, primer_proceso
from .etapa_03_unspsc import descargar_html, identificar_unspsc
from .etapa_04_registro import MatrizOportunidades, consolidar
from .etapa_05_experiencia import cargar_rup
from .etapa_06_evaluacion import evaluar, preparar_insumo
from .etapa_07_alertas import (
    checklist_documental,
    construir_url_formulario,
    publicar_en_teams,
    tarjeta_teams_html,
)


def _rel(ruta) -> str:
    try:
        return str(Path(ruta).relative_to(config.RAIZ))
    except ValueError:
        return str(ruta)


def procesar_correo(item: dict, *, cliente, matriz, rup, rup_corrupto, demo_portal, usar_llm, umbral) -> dict:
    # 1. Correo
    correo = parsear_correo(item)
    codigo = correo["numeroProceso"]
    # 2. API
    proceso = primer_proceso(cliente.consultar(codigo)) if codigo else {}
    # 3. Portal + UNSPSC
    unspsc = identificar_unspsc(descargar_html(correo["enlaceProceso"], codigo, demo=demo_portal))
    # 4. Registro
    registro = consolidar(correo, proceso, unspsc)
    registro["tipoContrato"] = correo.get("tipoContrato", "")
    matriz.agregar(registro)
    # 5-6. Experiencia + evaluación
    ev = evaluar(preparar_insumo(registro, rup, rup_corrupto), usar_llm=usar_llm)
    # 7. Decisión
    resultado = {"codigo": codigo, "entidad": registro["entidadContratante"], "evaluacion": ev, "alerta": False}
    columnas_eval = {k: v for k, v in ev.items() if not isinstance(v, (dict, list))}
    if ev["match_final"] > umbral:
        form_url = construir_url_formulario(registro, ev)
        tarjeta = tarjeta_teams_html(registro, ev, form_url)
        destino = config.SALIDA / "alertas_teams" / f"{codigo}.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(f"<!doctype html><meta charset='utf-8'><body style='background:#f3f2f1;padding:24px'>{tarjeta}</body>", encoding="utf-8")
        enviado = publicar_en_teams(tarjeta)
        checklist = checklist_documental(registro, ev)
        resultado.update(alerta=True, tarjeta=str(destino), form_url=form_url, publicado_teams=enviado, checklist=checklist)
        matriz.upsert({**registro, **columnas_eval, "alerta_enviada": True, "form_url": form_url})
    else:
        matriz.upsert({**registro, **columnas_eval, "alerta_enviada": False})
    return resultado


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(description="Prototipo del flujo de alertas de licitaciones")
    ap.add_argument("--imap", action="store_true", help="leer correos UNSEEN por IMAP")
    ap.add_argument("--api", action="store_true", help="usar la API real del agregador")
    ap.add_argument("--portal", action="store_true", help="descargar el portal real (scraping)")
    ap.add_argument("--llm", action="store_true", help="evaluar con LLM (OpenRouter) + guardrail")
    ap.add_argument("--umbral", type=int, default=config.UMBRAL_ALERTA)
    ap.add_argument("--correos", type=Path, help="carpeta con archivos .eml")
    ap.add_argument("--limpiar", action="store_true", help="borra la carpeta salida/ antes de correr")
    a = ap.parse_args(argv)

    if a.limpiar and config.SALIDA.exists():
        shutil.rmtree(config.SALIDA)
    correos = leer_correos_imap() if a.imap else leer_correos_demo(a.correos)
    cliente = ClienteAPI() if a.api else ClienteAPIDemo()
    rup, rup_corrupto = cargar_rup()
    matriz = MatrizOportunidades()

    print(f"\n📥 {len(correos)} correo(s) de alerta · 📚 {len(rup)} contratos en RUP · umbral de alerta > {a.umbral}\n")
    resultados = []
    for item in correos:
        r = procesar_correo(item, cliente=cliente, matriz=matriz, rup=rup, rup_corrupto=rup_corrupto,
                            demo_portal=not a.portal, usar_llm=a.llm, umbral=a.umbral)
        ev = r["evaluacion"]
        icono = "🚨" if r["alerta"] else "🗂️ "
        print(f"{icono} {r['codigo']:<22} match {ev['match_final']:>3}/100  {ev['decision']:<16} {r['entidad'][:48]}")
        print(f"   objeto {ev['fit_objeto']} · entidad {ev['score_entidad']} · geografía {ev['score_geografia']} · "
              f"presupuesto {ev['score_presupuesto']} · tiempo {ev['score_tiempo']} · UNSPSC/RUP {ev['score_frecuencia_unspsc']}")
        if r["alerta"]:
            print(f"   → tarjeta Teams: {_rel(r['tarjeta'])}")
            print(f"   → checklist documental: {len(r['checklist'])} ítems")
        print()
        resultados.append(r)

    config.SALIDA.mkdir(parents=True, exist_ok=True)
    resumen = config.SALIDA / "resumen_ejecucion.json"
    resumen.write_text(json.dumps(resultados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"📊 Matriz: {_rel(matriz.ruta)} · Resumen: {_rel(resumen)}")
    return resultados


if __name__ == "__main__":
    main()
