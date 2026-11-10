"""Funciones auxiliares compartidas por las etapas."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

MESES = {
    "ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5,
    "jun": 6, "jul": 7, "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10,
    "nov": 11, "dic": 12, "dec": 12,
}


def normalizar(texto: str | None) -> str:
    """Minúsculas sin tildes, espacios colapsados."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFD", str(texto))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.lower()).strip()


def clave(texto: str) -> str:
    """Convierte un texto en clave snake_case (para columnas de Excel)."""
    t = normalizar(texto)
    t = re.sub(r"[^a-z0-9]", "_", t)
    return re.sub(r"_+", "_", t).strip("_")


def a_numero(valor) -> float:
    """'$33.333.333' -> 33333333.0 ; valores vacíos -> 0."""
    if valor in (None, ""):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    limpio = re.sub(r"[^\d,]", "", str(valor)).replace(",", ".")
    try:
        return float(limpio) if limpio else 0.0
    except ValueError:
        return 0.0


def parsear_fecha_es(fecha: str, hora: str = "") -> datetime | None:
    """
    Interpreta fechas del correo de alerta: '02/Nov/26 10:10 am', '2026-11-02',
    '02-11-2026 - 10:10' etc.
    """
    if not fecha:
        return None
    f = fecha.strip()
    h = (hora or "").strip().lower()
    m = re.match(r"(\d{1,2})[/-]([A-Za-z]{3,9})[/-](\d{2,4})", f)
    try:
        if m:
            dia, mes_txt, anio = m.groups()
            mes = MESES.get(normalizar(mes_txt)[:3])
            if not mes:
                return None
            anio_i = int(anio) + (2000 if len(anio) == 2 else 0)
            dt = datetime(anio_i, mes, int(dia))
        elif re.match(r"\d{4}-\d{2}-\d{2}", f):
            dt = datetime.strptime(f[:10], "%Y-%m-%d")
        elif re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", f):
            dt = datetime.strptime(re.sub(r"-", "/", f[:10]), "%d/%m/%Y")
        else:
            return None
    except ValueError:
        return None

    mh = re.match(r"(\d{1,2}):(\d{2})\s*([ap]m)?", h)
    if mh:
        hh, mm, ampm = int(mh.group(1)), int(mh.group(2)), mh.group(3)
        if ampm == "pm" and hh < 12:
            hh += 12
        if ampm == "am" and hh == 12:
            hh = 0
        dt = dt.replace(hour=hh, minute=mm)
    return dt
