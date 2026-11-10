# Diccionario de datos · Matriz de oportunidades (hoja *Procesos*)

Una fila por proceso. Clave única: `idContrato`.

## Identificación y origen

| Columna | Tipo | Fuente | Descripción |
|---|---|---|---|
| `idContrato` | texto | API › portal › correo | Identificador único (clave del upsert) |
| `codigoProceso` | texto | API › correo | Código oficial del proceso |
| `nombreProceso` | texto | API › correo | Nombre corto del proceso |
| `link` | URL | API › correo | Detalle del proceso en el agregador |
| `nombre_fuente` | texto | API › correo | Portal de origen (SECOP I, SECOP II, privado) |
| `tipoContrato` | texto | correo | Modalidad (mínima cuantía, selección abreviada…) |
| `estado` | texto | API | Estado agrupado del proceso |

## Proceso

| Columna | Tipo | Descripción |
|---|---|---|
| `entidadContratante` | texto | Entidad que contrata |
| `objeto` | texto | Objeto contractual completo |
| `valor` | número/texto | Presupuesto oficial (vacío si no se informa) |
| `ubicacion` | texto | `Departamento : Municipio` |
| `fechaPublicacionAPI` / `fechaVencimientoAPI` | fecha | Fechas oficiales |
| `fechaRecepcionCorreo`, `horaRecepcionCorreo`, `fechaRecepcionISO` | fecha/hora | Recepción de la alerta (hora de Colombia) |
| `<evento>_fecha`, `<evento>_hora` | texto | Una pareja por evento del cronograma (p. ej. `fecha_y_hora_de_cierre_del_proceso_fecha`) |
| `doc_<nombre>` | URL | Una columna por documento del proceso |
| `totalDocumentos`, `tieneAdjuntos` | número, booleano | Conteo y bandera de documentos |
| `proponentes`, `ganadores`, `totalProponentes` | texto, número | Competidores (separados por `\|`) |

## Clasificación UNSPSC

| Columna | Descripción |
|---|---|
| `unspsc_principal`, `Clase`, `Grupo`, `Segmento`, `actividad_filter` | Clasificación principal del portal |
| `unspsc_1` … `unspsc_5` (+ `_descripcion`) | Primeros cinco códigos secundarios |
| `unspsc_secundarios`, `unspsc_descripciones` | Todos los secundarios, separados por `\|` |
| `total_unspsc_secundarios` | Cantidad de secundarios |
| `todos_unspsc` | Principal + secundarios sin duplicados |

## Evaluación (se completa en la etapa 7)

| Columna | Rango | Descripción |
|---|---|---|
| `linea_negocio` | 1 / 2 | Línea detectada |
| `fit_objeto`, `score_entidad`, `score_geografia`, `score_presupuesto`, `score_tiempo`, `score_frecuencia_unspsc` | 0–100 | Puntajes por criterio |
| `presupuesto_eliminado_de_ponderacion` | booleano | `true` si se aplicó el escenario B |
| `descarte_temprano`, `evidencia_insuficiente`, `backup_corrupto` | booleano | Banderas de calidad |
| `match_final` | 0–100 | Puntaje ponderado |
| `decision` | texto | PARTICIPAR / REVISIÓN MANUAL / NO PARTICIPAR / ERROR |
| `justificacion` | texto | Explicación con conteos UNSPSC-RUP |
| `alerta_enviada` | booleano | Si se publicó en Teams |
| `form_url` | URL | Formulario de anexos pre-llenado |
| `motor` | texto | `reglas` o `llm+guardrail` (prototipo) |
