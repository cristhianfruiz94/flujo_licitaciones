"""
ETAPA 7 — Decisión, alerta en Microsoft Teams y preparación documental
======================================================================
Equivale a «If (match_final > umbral)» → «Prellenar formulario» →
«Crear mensaje en Teams» → «Actualizar Excel»; y en la rama negativa,
«Actualizar Excel» sin alerta.

* Si el `match_final` supera el umbral (80 en producción), se publica una
  tarjeta en el canal «Alertas licitaciones» con los datos del proceso, los
  puntajes y dos botones: «Ver proceso» y «Cargar anexos».
* «Cargar anexos» abre un formulario pre-llenado (código, entidad, valor,
  match, decisión) donde el equipo comercial adjunta los documentos
  habilitantes; así arranca la preparación de la oferta el mismo día.
* En ambos casos la fila del proceso se actualiza en la matriz con la
  evaluación (trazabilidad completa, también de lo descartado).
"""
from __future__ import annotations

import html
import json
import time
import urllib.parse
import urllib.request

from . import config

# Checklist base de documentos habilitantes en contratación pública colombiana.
# Se ajusta por proceso según el pliego (aquí: genérico + reglas simples).
CHECKLIST_BASE = [
    "Carta de presentación de la oferta firmada",
    "Certificado de existencia y representación legal (≤ 30 días)",
    "RUT actualizado",
    "RUP vigente y en firme",
    "Certificados de experiencia (códigos UNSPSC exigidos)",
    "Estados financieros / indicadores de capacidad financiera",
    "Certificado de pago de seguridad social y parafiscales",
    "Antecedentes: Procuraduría, Contraloría, Policía",
    "Garantía de seriedad de la oferta (póliza)",
    "Propuesta económica",
]


def checklist_documental(registro: dict, evaluacion: dict) -> list[str]:
    items = list(CHECKLIST_BASE)
    if evaluacion.get("linea_negocio") == 2:
        items.append("Fichas técnicas y certificados de origen/importación de los bienes")
    else:
        items.append("Hojas de vida del personal técnico y relación de equipos (succión-presión, inspección)")
    from .utilidades import normalizar
    if "minima cuantia" in normalizar(registro.get("tipoContrato", "")):
        items.remove("Garantía de seriedad de la oferta (póliza)")  # suele no exigirse en mínima cuantía
    return items


def construir_url_formulario(registro: dict, ev: dict) -> str:
    codigo = registro.get("codigoProceso", "")
    params = {
        "codigo": codigo,
        "entidad": registro.get("entidadContratante", ""),
        "valor": str(registro.get("valor", "")),
        "match": str(ev.get("match_final", 0)),
        "decision": ev.get("decision", ""),
        "process_id": f"{codigo.replace(' ', '_')}_{int(time.time() * 1000)}",
    }
    return f"{config.FORM_ANEXOS_URL}?{urllib.parse.urlencode(params)}"


def _formato_pesos(valor) -> str:
    from .utilidades import a_numero
    v = a_numero(valor)
    return f"$ {v:,.0f}".replace(",", ".") if v else "No informado"


def tarjeta_teams_html(registro: dict, ev: dict, form_url: str) -> str:
    e = lambda x: html.escape(str(x or "No disponible"))  # noqa: E731
    return f"""<div style="font-family:Segoe UI, Arial, sans-serif; font-size:14px; color:#323130; line-height:1.5; max-width:640px">
  <h2 style="color:#d83b01; margin-bottom:12px;">🚨 Nueva oportunidad licitatoria detectada</h2>
  <p><b>📌 Proceso:</b><br>{e(registro.get('codigoProceso'))}</p>
  <p><b>🏢 Entidad:</b><br>{e(registro.get('entidadContratante'))}</p>
  <p><b>📝 Objeto:</b><br>{e(registro.get('objeto'))}</p>
  <p><b>📍 Ubicación:</b><br>{e(registro.get('ubicacion'))}</p>
  <p><b>💰 Valor:</b><br>{_formato_pesos(registro.get('valor'))}</p>
  <p><b>🔢 Clase UNSPSC:</b><br>{e(registro.get('Clase'))}</p>
  <p><b>🏷️ Actividad detectada:</b><br>{e(registro.get('actividad_filter'))}</p>
  <hr style="margin:15px 0; border:none; border-top:1px solid #ddd;">
  <h3 style="color:#0078D4;">🤖 Evaluación IA</h3>
  <p><b>Match final:</b> {ev.get('match_final', 0)} / 100</p>
  <p><b>Decisión:</b> {e(ev.get('decision'))}</p>
  <p><b>Justificación:</b><br>{e(ev.get('justificacion'))}</p>
  <p><b>Scores:</b><br>
    • Fit objeto: {ev.get('fit_objeto', 0)}<br>
    • Entidad: {ev.get('score_entidad', 0)}<br>
    • Geografía: {ev.get('score_geografia', 0)}<br>
    • Presupuesto: {ev.get('score_presupuesto', 0)}{' (excluido)' if ev.get('presupuesto_eliminado_de_ponderacion') else ''}<br>
    • Tiempo: {ev.get('score_tiempo', 0)}<br>
    • Experiencia UNSPSC (RUP): {ev.get('score_frecuencia_unspsc', 0)}</p>
  <hr style="margin:15px 0; border:none; border-top:1px solid #ddd;">
  <p>
    <a href="{html.escape(registro.get('link') or '#')}" style="background:#0078D4;color:white;padding:10px 14px;text-decoration:none;border-radius:6px;">🔗 Ver proceso licitatorio</a>
    &nbsp;
    <a href="{html.escape(form_url)}" style="background:#107C10;color:white;padding:10px 14px;text-decoration:none;border-radius:6px;">📂 Cargar anexos</a>
  </p>
</div>"""


def publicar_en_teams(html_mensaje: str) -> bool:
    """Publica vía Incoming Webhook / Workflows de Teams si TEAMS_WEBHOOK_URL existe."""
    if not config.TEAMS_WEBHOOK_URL:
        return False
    cuerpo = json.dumps({"text": html_mensaje}).encode("utf-8")
    req = urllib.request.Request(config.TEAMS_WEBHOOK_URL, data=cuerpo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return 200 <= r.status < 300
