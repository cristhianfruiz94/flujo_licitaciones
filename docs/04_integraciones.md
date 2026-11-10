# 04 · Integraciones

| # | Sistema | Uso en el flujo | Autenticación | Variable(s) en el prototipo | Flag CLI |
|---|---|---|---|---|---|
| 1 | **Buzón de correo (IMAP)** | Disparador: correos de alerta no leídos | Usuario y contraseña de aplicación | `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_FOLDER` | `--imap` |
| 2 | **API del agregador de licitaciones** | Token, y consulta del proceso con cronograma y documentos | Email y contraseña → token Bearer | `LICITACIONES_API_BASE_URL`, `_EMAIL`, `_PASSWORD`, `_PERFIL` | `--api` |
| 3 | **Portal de detalle del proceso** | Scraping de la clasificación UNSPSC | Ninguna (página pública) | — | `--portal` |
| 4 | **Microsoft Excel (OneDrive / SharePoint)** | Matriz de oportunidades: append, update y upsert por `idContrato` | OAuth2 de Microsoft Graph | Archivo local `salida/Oportunidades_Licitacion.xlsx` | — |
| 5 | **Microsoft OneDrive** | Descarga del respaldo del RUP | OAuth2 de Microsoft Graph | Archivo local `datos_ejemplo/rup_historico.json` | — |
| 6 | **OpenRouter (LLM)** | Agente evaluador (modelo `openai/gpt-4.1`) | API key | `OPENROUTER_API_KEY`, `LLM_MODEL` | `--llm` |
| 7 | **Microsoft Teams** | Publicación de la tarjeta en el canal *Alertas licitaciones* | OAuth2 de Microsoft Graph (en el prototipo: webhook) | `TEAMS_WEBHOOK_URL` | automático si existe |
| 8 | **Formulario "Cargar anexos"** | Webhook que recibe los parámetros del proceso | URL con parámetros | `FORM_ANEXOS_URL` | — |

## Detalle por integración

### 1. Correo (IMAP)
- **Producción:** nodo *Email Trigger (IMAP)* con filtro `UNSEEN`, reconexión forzada cada 45 min y seguimiento del último ID de mensaje.
- **Prototipo:** `leer_correos_imap()` usa `imaplib` y marca como leídos los correos procesados. Sin `--imap`, lee los `.eml` de `datos_ejemplo/correos/`.
- **Recomendación:** un buzón dedicado solo a alertas y una contraseña de aplicación, no la contraseña personal.

### 2. API del agregador
```http
POST {base}/auth-token
{"email": "...", "password": "..."}            →  {"token": {"accessToken": "..."}}

POST {base}/contratos/consultar
Authorization: Bearer <token>
{"perfiles": "<id perfil>", "page": 1, "limit": 30,
 "query": "{\"CodigoProceso\":\"SA-ACU-014-2026\"}",
 "campos_adicionales": "fechas,documentos"}     →  {"data": [ {...proceso...} ]}
```
La respuesta puede venir como lista, como `{data: []}` o como `{body: {data: []}}`. La función `primer_proceso()` normaliza los tres casos.

### 3. Portal del proceso
Petición `GET` con `User-Agent` de navegador. La clasificación principal viene en un atributo `contrato="{…}"` con entidades HTML escapadas, y los secundarios como texto `NNNNNNNN - Descripción`.
> Conviene respetar los términos de uso del portal y limitar la frecuencia de peticiones. El flujo hace una sola petición por alerta.

### 4–5. Microsoft 365 (Excel y OneDrive)
- **Libro:** *Oportunidades_Licitación*, hoja *Procesos*, con mapeo automático de columnas (*autoMap*).
- **Operaciones:** `append` al registrar el proceso, y `upsert`/`update` con columna de coincidencia `idContrato` al terminar la evaluación.
- **Archivos en OneDrive:** el respaldo del RUP (exportado a JSON/texto) y un documento de soporte reservado para futuras reglas.
- **Prototipo:** `MatrizOportunidades` escribe un `.xlsx` local con `openpyxl` (o un CSV de respaldo) y aplica la misma semántica de append y upsert.

### 6. LLM (OpenRouter)
- Nodo *AI Agent* de LangChain en n8n, conectado a *OpenRouter Chat Model* con `openai/gpt-4.1`.
- **Prototipo:** `llamar_llm()` hace la misma llamada vía la API compatible con OpenAI, con `temperature = 0`. La plantilla del prompt está en `etapa_06_evaluacion.PLANTILLA_PROMPT`, sin el nombre de la empresa (el perfil se inyecta desde `config.PERFIL`).

### 7. Microsoft Teams
- **Producción:** nodo *Create message* (recurso `channelMessage`, contenido HTML) en el equipo *Automatización de procesos*, canal *Alertas licitaciones*.
- **Prototipo:** genera la misma tarjeta HTML en `salida/alertas_teams/<código>.html` y, si existe `TEAMS_WEBHOOK_URL`, la publica en el canal.

### 8. Formulario de anexos
La URL lleva `codigo`, `entidad`, `valor`, `match`, `decision`, `process_id` y `justificacion`. En producción la recibe un webhook de n8n. El prototipo trae una versión estática (`prototipo/web/formulario_anexos.html`) que lee esos parámetros.

## Configuración

```bash
cp .env.example .env     # completa solo lo que vayas a usar
python -m prototipo.pipeline --imap --api --portal --llm
```
