"""
ETAPA 1 — Recepción y lectura del correo de alerta
==================================================
Equivale a los pasos «Disparador IMAP» + «Obtener datos del correo» del flujo.

1. Se leen los correos NO LEÍDOS de la bandeja que recibe las alertas del
   agregador de contratación pública (modo IMAP) o, en modo demo, los archivos
   .eml de `datos_ejemplo/correos/`.
2. Del asunto y el cuerpo se extraen: entidad, modalidad, número de proceso,
   objeto, valor, localización, portal de origen, cronograma, documentos y el
   enlace al detalle del proceso.
"""
from __future__ import annotations

import email
import imaplib
import re
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import config
from .utilidades import clave

PATRONES_MODALIDAD = [
    r"^Selecci[oó]n", r"^Selec\.", r"^Licitaci[oó]n", r"^Concurso",
    r"^Contrataci[oó]n", r"^M[ií]nima Cuant[ií]a", r"^Invitaci[oó]n", r"^Subasta",
]

# Ordenados de más específico a más general (igual que en producción)
PATRONES_PROCESO = [
    r"\b[A-Z]{2,}(?:-[A-Z0-9]+){2,}-\d{4}\b",          # PSMC-031-LM-CAU-2026
    r"\b[A-Z]{2,}(?:-[A-Z]{1,10})+-\d{2,6}-\d{4}\b",   # MC-PS-051-2026
    r"\b[A-Z]{2,}-\d{2,6}-\d{4}\b",                    # MC-065-2026
    r"\b[a-z0-9]+(?:-[a-z0-9]+){2,}\b",                # ws578...-solped-100...
    r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b",                   # LP001-2026
]

EXT_DOCUMENTOS = (".pdf", ".rar", ".zip", ".doc", ".docx", ".xls", ".xlsx")


# ---------------------------------------------------------------------------
# Fuentes de correo
# ---------------------------------------------------------------------------
def _mensaje_a_dict(msg: email.message.Message) -> dict:
    texto, html = "", ""
    for parte in msg.walk():
        tipo = parte.get_content_type()
        if parte.is_multipart():
            continue
        try:
            contenido = parte.get_content()
        except Exception:  # noqa: BLE001
            contenido = parte.get_payload(decode=True).decode("utf-8", "replace")
        if tipo == "text/plain" and not texto:
            texto = contenido
        elif tipo == "text/html" and not html:
            html = contenido
    return {
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
        "from": str(msg.get("From", "")),
        "text": texto,
        "html": html,
    }


def leer_correos_demo(carpeta: Path | None = None) -> list[dict]:
    carpeta = carpeta or (config.DATOS_EJEMPLO / "correos")
    correos = []
    for ruta in sorted(carpeta.glob("*.eml")):
        msg = email.message_from_bytes(ruta.read_bytes(), policy=policy.default)
        d = _mensaje_a_dict(msg)
        d["_origen"] = ruta.name
        correos.append(d)
    return correos


def leer_correos_imap(marcar_leidos: bool = True) -> list[dict]:
    """Lee los correos UNSEEN (igual que el disparador de producción)."""
    if not (config.IMAP_HOST and config.IMAP_USER and config.IMAP_PASSWORD):
        raise RuntimeError("Configure IMAP_HOST, IMAP_USER e IMAP_PASSWORD en .env")
    correos = []
    with imaplib.IMAP4_SSL(config.IMAP_HOST) as imap:
        imap.login(config.IMAP_USER, config.IMAP_PASSWORD)
        imap.select(config.IMAP_FOLDER)
        _, ids = imap.search(None, "UNSEEN")
        for num in ids[0].split():
            _, datos = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(datos[0][1], policy=policy.default)
            correos.append(_mensaje_a_dict(msg))
            if marcar_leidos:
                imap.store(num, "+FLAGS", "\\Seen")
    return correos


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _limpiar(texto: str) -> str:
    return str(texto or "").replace("*", "").replace("\r", "").strip()


def _extraer_entidad(subject: str, lineas: list[str], texto: str) -> str:
    entidad = ""
    # 1. Línea inmediatamente anterior a la modalidad de contratación
    idx = next(
        (i for i, l in enumerate(lineas)
         if any(re.match(p, l, re.I) for p in PATRONES_MODALIDAD)),
        -1,
    )
    if idx > 0:
        candidata = lineas[idx - 1]
        if len(candidata) > 8 and not re.search(r"Objeto:|Valor:|Portal|Localizaci", candidata, re.I):
            entidad = candidata
    # 2. Desde el asunto
    if not entidad:
        m = re.match(r"^(.*?)\s+(Selec\.|Selecci[oó]n|Licitaci[oó]n|Concurso|Contrataci[oó]n|M[ií]nima)", subject, re.I)
        if m:
            entidad = m.group(1)
    # 3. Desde la localización
    if not entidad:
        m = re.search(r"Localizaci[oó]n:\s*([^\n]+)", texto, re.I)
        if m:
            entidad = re.sub(r"\s*:\s*", " - ", m.group(1))
    entidad = re.sub(r"^(Enlace directo a|Contrataci[oó]n|Proceso)", "", entidad, flags=re.I)
    return re.sub(r"\s+", " ", entidad).strip()


def _extraer_numero_proceso(texto_busqueda: str) -> str:
    for patron in PATRONES_PROCESO:
        flags = re.I if patron.startswith(r"\b[a-z0-9]") else 0
        m = re.search(patron, texto_busqueda, flags)
        if m:
            return re.sub(r"\s*\[\d+\].*$", "", m.group(0)).strip()
    return ""


def _extraer_links(texto: str, html: str) -> list[dict]:
    links = []
    for m in re.finditer(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html or "", re.I | re.S):
        links.append({"texto": re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip(), "url": m.group(1)})
    # En texto plano los enlaces vienen como "- NOMBRE\n[https://...]"
    for m in re.finditer(r"-\s*([^\n\[]+)\n\s*\[(https?://[^\]]+)\]", texto):
        links.append({"texto": m.group(1).strip(), "url": m.group(2).strip()})
    for m in re.finditer(r"(https?://\S*detalle-contrato\S*)", texto):
        links.append({"texto": "Detalle del proceso", "url": m.group(1).strip("[]")})
    return links


def _clasificar_documento(nombre: str) -> str:
    n = nombre.lower()
    if "estudios" in n:
        return "Estudios Previos"
    if "cdp" in n:
        return "CDP"
    if "invitaci" in n:
        return "Invitación"
    if "cronograma" in n:
        return "Cronograma"
    if "anexo" in n:
        return "Anexos"
    if "riesgo" in n:
        return "Matriz de riesgos"
    if "pliego" in n:
        return "Pliego de condiciones"
    return "Otro"


def parsear_correo(item: dict) -> dict:
    """Port del nodo 'Obtener_datos_correo'. Devuelve un dict plano."""
    subject = item.get("subject", "")
    texto = _limpiar(item.get("text") or item.get("textPlain") or "")
    html = item.get("html") or item.get("textHtml") or ""
    texto_busqueda = f"{subject}\n{texto}"
    lineas = [l.strip() for l in texto_busqueda.split("\n") if l.strip()]

    # Fecha de recepción
    fecha_iso = ""
    try:
        if item.get("date"):
            fecha_iso = parsedate_to_datetime(item["date"]).isoformat()
    except (TypeError, ValueError):
        pass

    # Modalidad: línea que empieza con la modalidad y trae " : <código>"
    m_tipo = next((re.match(r".+", l) for l in lineas
                   if any(re.match(p, l, re.I) for p in PATRONES_MODALIDAD) and ":" in l), None)
    m_obj = re.search(r"Objeto:\s*([\s\S]*?)Valor:", texto, re.I)
    m_val = re.search(r"Valor:\s*\$?\s*([\d.,]+)", texto, re.I)
    m_loc = re.search(r"Localizaci[oó]n:\s*(.+)", texto, re.I)
    m_portal = re.search(r"Portal de Origen:\s*(.+)", texto, re.I)

    localizacion = m_loc.group(1).strip() if m_loc else ""
    departamento, municipio = "", ""
    if ":" in localizacion:
        departamento, municipio = [p.strip() for p in localizacion.split(":", 1)]

    # Cronograma: "Evento: 02/Nov/26 10:10 am"
    cronograma = []
    regex_fecha = re.compile(
        r"([^:\n]+):\s*(\d{2}[/-][A-Za-z]{3,9}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\s*(\d{1,2}:\d{2}\s*[ap]m)?",
        re.I,
    )
    for m in regex_fecha.finditer(texto):
        cronograma.append({"evento": m.group(1).strip(), "fecha": m.group(2).strip(), "hora": (m.group(3) or "").strip()})
    cronograma_plano = {}
    for ev in cronograma:
        k = clave(ev["evento"])
        cronograma_plano[f"{k}_fecha"] = ev["fecha"]
        cronograma_plano[f"{k}_hora"] = ev["hora"]

    links = _extraer_links(texto, html)
    enlace_proceso = next((l["url"] for l in links if "detalle-contrato" in l["url"]), "")
    documentos = [
        {"tipo": _clasificar_documento(l["texto"]), "nombre": l["texto"].lstrip("- ").strip(), "url": l["url"]}
        for l in links
        if "detalle-contrato" not in l["url"]
        and ("descarga-documentos" in l["url"] or "secop" in l["url"].lower()
             or l["texto"].lower().endswith(EXT_DOCUMENTOS))
    ]

    return {
        "entidad": _extraer_entidad(subject, lineas, texto),
        "tipoContrato": m_tipo.group(0).strip() if m_tipo else "",
        "numeroProceso": _extraer_numero_proceso(texto_busqueda),
        "objeto": re.sub(r"\s+", " ", m_obj.group(1)).strip() if m_obj else "",
        "valor": m_val.group(1) if m_val else "",
        "fechaRecepcionISO": fecha_iso,
        "localizacion": localizacion,
        "departamento": departamento,
        "municipio": municipio,
        "portalOrigen": m_portal.group(1).strip() if m_portal else "",
        "enlaceProceso": enlace_proceso,
        "cronograma": cronograma,
        "cronogramaPlano": cronograma_plano,
        "documentosClasificados": documentos,
    }
