"""
ETAPA 3 — Lectura del portal e identificación UNSPSC
====================================================
Equivale a «Scraping del sitio» + «Identifica UNSPSC».

Se descarga la página de detalle del proceso (enlace que viene en el correo) y
se extraen:
  * la clasificación UNSPSC principal (Segmento / Grupo / Clase / actividad),
    embebida en el HTML como un atributo `contrato="{...json...}"`;
  * todos los códigos UNSPSC secundarios (patrón «8 dígitos - descripción»);
  * el número oficial del proceso.

En modo demo, el HTML se lee de `datos_ejemplo/portal/<codigo>.html`.
"""
from __future__ import annotations

import html as html_lib
import json
import re
import urllib.request

from . import config


def descargar_html(url: str, codigo_proceso: str, demo: bool = True) -> str:
    if demo:
        ruta = config.DATOS_EJEMPLO / "portal" / f"{codigo_proceso}.html"
        return ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    if not url:
        return ""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8", "replace")


def _limpiar_descripcion(texto: str) -> str:
    t = re.sub(r"<[^>]+>", " ", texto or "")
    t = re.sub(r'type="[^"]+"|text/javascript|function\s*\(.+', "", t, flags=re.I)
    t = html_lib.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def identificar_unspsc(html: str) -> dict:
    principal: dict = {}
    m = re.search(r'contrato="(\{.*?\})"', html or "", re.S)
    if m:
        try:
            principal = json.loads(html_lib.unescape(m.group(1)))
        except json.JSONDecodeError:
            principal = {}

    vistos, secundarios = set(), []
    for cod, desc in re.findall(r"(\d{8})\s*-\s*([^<,\n\r]+)", html or ""):
        if cod not in vistos:
            vistos.add(cod)
            secundarios.append({"codigo": cod, "descripcion": _limpiar_descripcion(desc)})

    id_contrato = ""
    plano = re.sub(r"<[^>]+>", " ", html or "")
    mp = re.search(r"N[uú]mero\s+del\s+proceso[:\s]+([A-Za-z0-9\-_.]+)", plano, re.I)
    if mp:
        id_contrato = mp.group(1).strip()

    return {
        "idContrato": id_contrato,
        "Clase": principal.get("Clase", ""),
        "Grupo": principal.get("Grupo", ""),
        "Segmento": principal.get("Segmento", ""),
        "actividad_filter": principal.get("actividad_filter", ""),
        "unspsc_principal": principal.get("Clase", ""),
        "unspsc_secundarios": secundarios,
    }
