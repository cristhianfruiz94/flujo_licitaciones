"""
ETAPA 2 — Enriquecimiento vía API del agregador de licitaciones
===============================================================
Equivale a «Solicitar token» → «Usar token» → «Consultar licitación».

1. Se autentica contra la API del agregador (POST /auth-token) y obtiene un
   token Bearer.
2. Consulta el proceso por su código (POST /contratos/consultar) pidiendo los
   campos adicionales `fechas` y `documentos`: cronograma oficial, documentos
   del proceso, proponentes, ganadores, estado, fecha de vencimiento, etc.

En modo demo, la respuesta se lee de `datos_ejemplo/api/<codigo>.json`.
"""
from __future__ import annotations

import json
import urllib.request

from . import config


class ClienteAPIDemo:
    """Devuelve respuestas grabadas, con la misma forma que la API real."""

    def consultar(self, codigo_proceso: str) -> dict:
        ruta = config.DATOS_EJEMPLO / "api" / f"{codigo_proceso}.json"
        if not ruta.exists():
            return {"data": []}
        return json.loads(ruta.read_text(encoding="utf-8"))


class ClienteAPI:
    """Cliente real. Requiere LICITACIONES_API_* en el archivo .env."""

    def __init__(self) -> None:
        if not (config.API_BASE_URL and config.API_EMAIL and config.API_PASSWORD):
            raise RuntimeError("Configure LICITACIONES_API_BASE_URL, _EMAIL y _PASSWORD en .env")
        self._token: str | None = None

    def _post(self, ruta: str, cuerpo: dict, token: str | None = None) -> dict:
        req = urllib.request.Request(
            f"{config.API_BASE_URL.rstrip('/')}/{ruta.lstrip('/')}",
            data=json.dumps(cuerpo).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))

    def token(self) -> str:
        if not self._token:
            resp = self._post("auth-token", {"email": config.API_EMAIL, "password": config.API_PASSWORD})
            self._token = (resp.get("token") or {}).get("accessToken")
        return self._token or ""

    def consultar(self, codigo_proceso: str) -> dict:
        cuerpo = {
            "perfiles": config.API_PERFIL,
            "page": 1,
            "limit": 30,
            "query": json.dumps({"CodigoProceso": codigo_proceso}),
            "campos_adicionales": "fechas,documentos",
        }
        return self._post("contratos/consultar", cuerpo, self.token())


def primer_proceso(respuesta: dict | list) -> dict:
    """La API puede responder lista, {data: []} o {body: {data: []}}."""
    if isinstance(respuesta, list):
        return respuesta[0] if respuesta else {}
    for camino in (("data",), ("body", "data")):
        nodo = respuesta
        for k in camino:
            nodo = nodo.get(k, {}) if isinstance(nodo, dict) else {}
        if isinstance(nodo, list):
            return nodo[0] if nodo else {}
    return respuesta if isinstance(respuesta, dict) and respuesta.get("CodigoProceso") else {}
