# 08 · Lecciones aprendidas y hoja de ruta

## Lecciones aprendidas

| # | Hallazgo | Aprendizaje | Cómo lo aborda el prototipo |
|---|---|---|---|
| 1 | El LLM calcula la ponderación y aplica la regla de decisión | Los LLM pueden equivocarse en aritmética y en límites (84 vs. 85) | El motor de reglas recalcula `match_final` y la decisión (*guardrail*) |
| 2 | Umbral de alerta (> 80) distinto del umbral de "PARTICIPAR" (≥ 85) | Es intencional, pero debe documentarse para que nadie se confunda | Documentado y configurable (`--umbral`) |
| 3 | Los formatos de la API varían (`[]`, `{data}`, `{body: {data}}`) | Normalizar en un solo punto | `primer_proceso()` |
| 4 | El correo, la API y el portal tienen datos incompletos y distintos | Fusionar campo por campo con prioridades claras | `consolidar()`: API > portal > correo |
| 5 | Las referencias entre nodos por nombre se rompen al renombrar nodos | Pasar los datos explícitamente entre etapas | Las funciones reciben y devuelven diccionarios |
| 6 | La extracción por regex del correo es frágil ante cambios de formato | Cubrir con pruebas usando correos reales anonimizados | `tests/test_flujo.py` |
| 7 | El encabezado "Alertas de contratación…" podía confundirse con la modalidad | Anclar la búsqueda a la línea de modalidad | Corregido en `etapa_01_correo.py` |
| 8 | La respuesta del LLM a veces llega con markdown o texto extra | Parser tolerante y valor seguro por defecto (`match_final = 0`) | `parsear_respuesta_ia()` |

## Hoja de ruta

### Corto plazo
- [ ] Pasar el cálculo de `match_final` a un nodo de código en n8n (guardrail en producción).
- [ ] Mover todas las credenciales al gestor de credenciales y rotarlas.
- [ ] Quitar las columnas de *debug* de la matriz.
- [ ] Notificar errores de ejecución (parse error, API caída) en un canal técnico.

### Mediano plazo
- [ ] **Lectura del pliego con IA:** descargar los estudios previos y el pliego, y extraer requisitos habilitantes (experiencia mínima en SMMLV, indicadores financieros, UNSPSC exigidos) para generar el checklist exacto del proceso.
- [ ] **Validación de requisitos vs. RUP:** comparar la experiencia exigida con los contratos del RUP (suma de SMMLV por código) y señalar brechas.
- [ ] **Carpeta del proceso en SharePoint:** al dar clic en "Cargar anexos", crear la carpeta con plantillas (carta de presentación, anexos) pre-diligenciadas.
- [ ] **Recordatorios de cronograma:** avisar en Teams 48 y 24 horas antes del cierre o de la fecha de observaciones.

### Largo plazo
- [ ] **Aprendizaje con resultados:** usar las decisiones del equipo y las adjudicaciones para recalibrar pesos y umbral.
- [ ] **Tablero de mercado:** entidades, montos, regiones, competidores y tasa de éxito.
- [ ] **Nuevas fuentes:** consulta directa a los datos abiertos de SECOP II, además del agregador.
