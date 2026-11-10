"""
Configuración del prototipo.

Todo lo sensible (usuarios, contraseñas, tokens, URLs de webhooks) se lee de
variables de entorno. Nunca escriba credenciales en el código: use un archivo
`.env` local (ignorado por git) a partir de `.env.example`.

El perfil de negocio (líneas, palabras clave, geografías prioritarias) está
parametrizado para que el mismo motor sirva a cualquier empresa del sector.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS_EJEMPLO = RAIZ / "datos_ejemplo"
SALIDA = RAIZ / "salida"


def _cargar_dotenv(ruta: Path = RAIZ / ".env") -> None:
    """Carga un .env sencillo (CLAVE=valor) sin dependencias externas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_dotenv()


def env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto)


# ---------------------------------------------------------------------------
# Integraciones (todas opcionales: sin ellas el prototipo corre en modo demo)
# ---------------------------------------------------------------------------
IMAP_HOST = env("IMAP_HOST")
IMAP_USER = env("IMAP_USER")
IMAP_PASSWORD = env("IMAP_PASSWORD")
IMAP_FOLDER = env("IMAP_FOLDER", "INBOX")

API_BASE_URL = env("LICITACIONES_API_BASE_URL")          # p. ej. https://<proveedor>/api/client
API_EMAIL = env("LICITACIONES_API_EMAIL")
API_PASSWORD = env("LICITACIONES_API_PASSWORD")
API_PERFIL = env("LICITACIONES_API_PERFIL")              # id del perfil de búsqueda

LLM_API_KEY = env("OPENROUTER_API_KEY")
LLM_MODEL = env("LLM_MODEL", "openai/gpt-4.1")
LLM_URL = env("LLM_URL", "https://openrouter.ai/api/v1/chat/completions")

TEAMS_WEBHOOK_URL = env("TEAMS_WEBHOOK_URL")              # canal "Alertas licitaciones"
FORM_ANEXOS_URL = env("FORM_ANEXOS_URL", "https://ejemplo.invalid/webhook/cargar-anexos")

UMBRAL_ALERTA = int(env("UMBRAL_ALERTA", "80"))           # producción: match_final > 80


# ---------------------------------------------------------------------------
# Perfil de negocio
# ---------------------------------------------------------------------------
@dataclass
class PerfilNegocio:
    descripcion: str
    palabras_linea1: list[str]
    palabras_linea2: list[str]
    verbos_suministro: list[str]
    palabras_negativas: list[str]
    entidades_tier1: list[str]
    entidades_tier3: list[str]
    palabras_saneamiento: list[str]
    geografia_linea1: dict = field(default_factory=dict)
    geografia_linea2: dict = field(default_factory=dict)


PERFIL = PerfilNegocio(
    descripcion=(
        "Empresa colombiana con dos líneas de negocio. "
        "LÍNEA 1 — Servicios especializados: consultoría, mantenimiento, limpieza, "
        "diagnóstico, rehabilitación y operación de infraestructura de acueducto, "
        "alcantarillado y aguas residuales; detección de fugas; inspección de redes; "
        "hidrosucción con equipos de succión-presión (tipo Vactor/Vaccon). "
        "LÍNEA 2 — Importación y comercialización de bienes y repuestos ligados a la "
        "Línea 1: boquillas, mangueras industriales de presión-succión, varillas "
        "flexométricas / rotosonda para limpieza de alcantarillado y tapones."
    ),
    palabras_linea1=[
        "alcantarillado", "acueducto", "aguas residuales", "hidrosuccion",
        "hidro succion", "succion-presion", "succion presion", "vactor", "vaccon",
        "deteccion de fugas", "fugas", "inspeccion de redes", "cctv", "sumideros",
        "pozos de inspeccion", "colectores", "limpieza de redes", "desobstruccion",
        "red sanitaria", "saneamiento", "rehabilitacion de redes", "redes hidrosanitarias",
    ],
    palabras_linea2=[
        "boquilla", "manguera", "varilla", "rotosonda", "rota sonda", "flexometric",
        "tapon", "accesorios", "herramientas consumibles", "repuestos para equipo de succion",
        "equipos de succion",
    ],
    verbos_suministro=["suministro", "adquisicion", "compra", "compraventa", "dotacion"],
    palabras_negativas=[
        "repuestos automotrices", "reparacion de vehiculos", "mantenimiento automotor",
        "mantenimiento vehicular", "parque automotor", "pavimentacion", "construccion de vias",
        "obra civil", "papeleria", "muestreo", "planta de tratamiento", "ptar",
        "instalacion de tuberia de drenaje", "videovigilancia", "camaras de seguridad",
        "software", "alimentacion escolar",
    ],
    entidades_tier1=[
        "empresas publicas", "acueducto y alcantarillado", "e.s.p", "esp ",
        "aguas de", "acuaductos", "empresa de servicios publicos",
    ],
    entidades_tier3=["puerto", "portuaria", "petrol", "hidrocarburos", "refineria"],
    palabras_saneamiento=["agua", "acueducto", "alcantarillado", "saneamiento", "residuales"],
    # (departamento, municipio) normalizados -> score; "*" = cualquier municipio
    geografia_linea1={
        ("valle del cauca", "cali"): 100,
        ("valle del cauca", "*"): 90,
        ("bogota", "*"): 90,
        ("cundinamarca", "bogota"): 90,
        ("cundinamarca", "*"): 80,
        ("quindio", "armenia"): 80,
        ("risaralda", "pereira"): 80,
        ("caldas", "manizales"): 80,
        ("atlantico", "barranquilla"): 80,
        ("*", "*"): 30,
    },
    geografia_linea2={
        ("valle del cauca", "cali"): 100,
        ("bogota", "*"): 100,
        ("cundinamarca", "bogota"): 100,
        ("valle del cauca", "*"): 95,
        ("*", "*"): 85,
    },
)

# Pesos de la matriz de decisión
PESOS_CON_PRESUPUESTO = {
    "score_geografia": 0.25,
    "fit_objeto": 0.35,
    "score_tiempo": 0.05,
    "score_frecuencia_unspsc": 0.15,
    "score_entidad": 0.15,
    "score_presupuesto": 0.05,
}
PESOS_SIN_PRESUPUESTO = {
    "score_geografia": 0.27,
    "fit_objeto": 0.38,
    "score_tiempo": 0.15,
    "score_frecuencia_unspsc": 0.15,
    "score_entidad": 0.05,
}
