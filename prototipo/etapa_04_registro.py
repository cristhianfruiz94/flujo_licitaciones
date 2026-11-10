"""
ETAPA 4 — Consolidación y registro en la matriz de oportunidades
================================================================
Equivale a «Preparar registro» + «Agregar fila en Excel».

Fusiona tres fuentes con prioridad API > portal (UNSPSC) > correo, aplana el
cronograma y los documentos en columnas y agrega la fila a la hoja «Procesos»
del libro `Oportunidades_Licitacion.xlsx` (en producción: Excel en OneDrive /
SharePoint vía Microsoft Graph). Después del análisis de IA la misma fila se
actualiza (upsert por `idContrato`) con los puntajes y la decisión.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .utilidades import clave

TZ = ZoneInfo("America/Bogota")


def _split_fecha_hora(valor: str) -> tuple[str, str]:
    partes = (valor or "").split(" - ")
    return partes[0] if partes else "", partes[1] if len(partes) > 1 else ""


def consolidar(correo: dict, proceso_api: dict, unspsc: dict) -> dict:
    p = dict(proceso_api or {})
    for k in ("cronogramas", "documentos_proceso", "proponentes", "ganadores"):
        p.setdefault(k, [])

    try:
        recibido = datetime.fromisoformat(correo.get("fechaRecepcionISO")) if correo.get("fechaRecepcionISO") else datetime.now(TZ)
    except ValueError:
        recibido = datetime.now(TZ)
    recibido = recibido.astimezone(TZ)

    secundarios = unspsc.get("unspsc_secundarios") or []
    principal = unspsc.get("unspsc_principal") or ""
    todos = [principal] if principal else []
    todos += [s["codigo"] for s in secundarios if s["codigo"] not in todos]

    reg = {
        "idContrato": p.get("idContrato") or correo.get("numeroProceso") or unspsc.get("idContrato") or "",
        "codigoProceso": p.get("CodigoProceso") or correo.get("numeroProceso") or "",
        "nombreProceso": p.get("Nombre") or correo.get("objeto") or "",
        "link": p.get("link") or correo.get("enlaceProceso") or "",
        "nombre_fuente": p.get("nombre_fuente") or correo.get("portalOrigen") or "",
        "fechaPublicacionAPI": p.get("FechaPublicacion") or correo.get("cronogramaPlano", {}).get("fecha_de_publicacion_fecha", ""),
        "fechaVencimientoAPI": p.get("FechaVencimiento") or "",
        "entidadContratante": p.get("EntidadContratante") or correo.get("entidad") or "",
        "objeto": p.get("Objeto") or correo.get("objeto") or "",
        "valor": p.get("Valor") or correo.get("valor") or "",
        "ubicacion": p.get("TextoDepartamento") or correo.get("localizacion") or "",
        "estado": p.get("estado_agrupado") or "",
        "fechaRecepcionCorreo": recibido.strftime("%d/%m/%Y"),
        "horaRecepcionCorreo": recibido.strftime("%H:%M:%S"),
        "fechaRecepcionISO": recibido.isoformat(),
        "unspsc_principal": principal,
        "Clase": unspsc.get("Clase", ""),
        "Grupo": unspsc.get("Grupo", ""),
        "Segmento": unspsc.get("Segmento", ""),
        "actividad_filter": unspsc.get("actividad_filter", ""),
        "total_unspsc_secundarios": len(secundarios),
        "unspsc_secundarios": " | ".join(s["codigo"] for s in secundarios),
        "unspsc_descripciones": " | ".join(s["descripcion"] for s in secundarios),
        "todos_unspsc": " | ".join(todos),
    }
    for i in range(5):
        s = secundarios[i] if i < len(secundarios) else {}
        reg[f"unspsc_{i + 1}"] = s.get("codigo", "")
        reg[f"unspsc_{i + 1}_descripcion"] = s.get("descripcion", "")

    # Cronograma oficial de la API; si no hay, el del correo
    if p["cronogramas"]:
        for ev in p["cronogramas"]:
            f, h = _split_fecha_hora(ev.get("fecha", ""))
            reg[f"{clave(ev.get('nombre', ''))}_fecha"] = f
            reg[f"{clave(ev.get('nombre', ''))}_hora"] = h
    else:
        reg.update(correo.get("cronogramaPlano", {}))

    for doc in p["documentos_proceso"]:
        reg[f"doc_{clave(doc.get('nombre', ''))}"] = doc.get("ruta", "")

    reg["proponentes"] = " | ".join(x.get("nombreEntidad", "") for x in p["proponentes"])
    reg["ganadores"] = " | ".join(x.get("nombreEntidad", "") for x in p["ganadores"])
    reg["totalDocumentos"] = len(p["documentos_proceso"]) or len(correo.get("documentosClasificados", []))
    reg["totalProponentes"] = len(p["proponentes"])
    reg["tieneAdjuntos"] = reg["totalDocumentos"] > 0
    reg["_cronograma"] = p["cronogramas"] or [
        {"nombre": e["evento"], "fecha": f"{e['fecha']} - {e['hora']}".strip(" -")} for e in correo.get("cronograma", [])
    ]
    return reg


# ---------------------------------------------------------------------------
# Almacenamiento: Excel (openpyxl) con respaldo CSV
# ---------------------------------------------------------------------------
class MatrizOportunidades:
    HOJA = "Procesos"

    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = ruta or (config.SALIDA / "Oportunidades_Licitacion.xlsx")
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        try:
            import openpyxl  # noqa: F401
            self._xlsx = True
        except ImportError:
            self._xlsx = False
            self.ruta = self.ruta.with_suffix(".csv")

    def _leer(self) -> list[dict]:
        if not self.ruta.exists():
            return []
        if self._xlsx:
            import openpyxl
            ws = openpyxl.load_workbook(self.ruta)[self.HOJA]
            filas = list(ws.iter_rows(values_only=True))
            if not filas:
                return []
            enc = [str(c) for c in filas[0]]
            return [{enc[i]: v for i, v in enumerate(f) if v is not None} for f in filas[1:]]
        with self.ruta.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def _escribir(self, filas: list[dict]) -> None:
        columnas: list[str] = []
        for f in filas:
            columnas += [k for k in f if k not in columnas and not k.startswith("_")]
        if self._xlsx:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = self.HOJA
            ws.append(columnas)
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="1F4E79")
            for f in filas:
                ws.append([f.get(c, "") if not isinstance(f.get(c), (list, dict)) else str(f.get(c)) for c in columnas])
            ws.freeze_panes = "A2"
            wb.save(self.ruta)
        else:
            with self.ruta.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=columnas, extrasaction="ignore")
                w.writeheader()
                w.writerows(filas)

    def agregar(self, registro: dict) -> None:
        """Equivale a 'Actualizar_Excel' (append)."""
        filas = self._leer()
        filas.append({k: v for k, v in registro.items() if not k.startswith("_")})
        self._escribir(filas)

    def upsert(self, registro: dict, columna: str = "idContrato") -> None:
        """Equivale a 'Append or update' / 'Update sheet' por idContrato."""
        filas = self._leer()
        for f in filas:
            if str(f.get(columna)) == str(registro.get(columna)):
                f.update({k: v for k, v in registro.items() if not k.startswith("_")})
                break
        else:
            filas.append(registro)
        self._escribir(filas)

    def filas(self) -> list[dict]:
        return self._leer()
