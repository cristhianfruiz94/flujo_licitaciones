"""
ETAPA 5 — Carga de la experiencia acreditada (RUP)
==================================================
Equivale a «Descargar archivo» (OneDrive) + «Extraer de archivo».

El Registro Único de Proponentes (RUP) resume los contratos ejecutados por la
empresa con sus códigos UNSPSC. Es la base para medir si la empresa tiene
experiencia acreditable en lo que pide la entidad. En producción se descarga
un respaldo del RUP desde OneDrive; aquí se lee `datos_ejemplo/rup_historico.json`
(datos ficticios).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

COLUMNAS_RUP = {
    "consecutivo": "NÚMERO CONSECUTIVO DEL REPORTE DEL CONTRATO EJECUTADO",
    "contratante": "NOMBRE DEL CONTRATANTE",
    "valor_smmlv": "VALOR DEL CONTRATO EJECUTADO EXPRESADO SMMLV",
    "segmento": "SEGMENTO",
    "familia": "FAMILIA",
    "clase": "CLASE",
    "producto": "PRODUCTO",
    "unspsc": "UNSPSC",
}


def texto_corrupto(texto: str) -> bool:
    """Marca el respaldo como corrupto si está vacío o >5 % de caracteres ilegibles."""
    if not texto or len(texto) < 50:
        return True
    return texto.count("�") / len(texto) > 0.05


def cargar_rup(ruta: Path | None = None) -> tuple[list[dict], bool]:
    ruta = ruta or (config.DATOS_EJEMPLO / "rup_historico.json")
    texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    corrupto = texto_corrupto(texto)
    try:
        crudo = json.loads(texto) if texto else []
    except json.JSONDecodeError:
        return [], True
    contratos = []
    for fila in crudo if isinstance(crudo, list) else []:
        # tolera encabezados con espacios (" FAMILIA") como en el archivo real
        f = {k.strip(): v for k, v in fila.items()}
        contratos.append({
            "consecutivo": f.get(COLUMNAS_RUP["consecutivo"]),
            "contratante": f.get(COLUMNAS_RUP["contratante"]),
            "valor_smmlv": float(f.get(COLUMNAS_RUP["valor_smmlv"]) or 0),
            "segmento": int(f.get(COLUMNAS_RUP["segmento"]) or 0),
            "familia": int(f.get(COLUMNAS_RUP["familia"]) or 0),
            "clase": int(f.get(COLUMNAS_RUP["clase"]) or 0),
            "producto": int(f.get(COLUMNAS_RUP["producto"]) or 0),
            "unspsc": str(f.get(COLUMNAS_RUP["unspsc"]) or ""),
        })
    return contratos, corrupto
