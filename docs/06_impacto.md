# 06 · Impacto

## Beneficios para el negocio

### 1. Detección temprana de oportunidades
Cada alerta se procesa en cuanto llega el correo: el flujo lee, enriquece y evalúa sin intervención humana. En procesos de mínima cuantía, que pueden cerrar en 2 a 5 días hábiles, **ganar uno o dos días de preparación** puede definir si la empresa alcanza a presentarse.

### 2. Foco en lo que vale la pena
El filtro de afinidad y los castigos por objetos no relacionados (automotor, obra civil, papelería…) reducen el ruido. El equipo comercial **recibe en Teams solo las oportunidades con alto puntaje**, con la justificación y el desglose de puntajes a la vista.

### 3. Criterio único, explicable y ajustable
La decisión ya no depende de quién lea el correo. Los pesos y las tablas son **decisiones de negocio documentadas** que se ajustan en un solo lugar, y cada evaluación deja una justificación escrita.

### 4. Experiencia acreditable verificada desde el inicio
El cruce automático UNSPSC-RUP anticipa si la empresa **puede habilitarse** y qué contratos usar como soporte, antes de invertir horas en la propuesta.

### 5. Preparación documental desde el día uno
El botón **"Cargar anexos"** convierte la alerta en una tarea: un formulario pre-llenado con responsable y checklist de habilitantes. La recolección de documentos empieza en paralelo al análisis del pliego, en lugar de al final.

### 6. Trazabilidad y datos para decidir
La matriz registra **todos** los procesos, incluidos los descartados, con fechas, entidad, valor, UNSPSC, cronograma y evaluación. Con esa base se pueden:
- auditar falsos negativos y calibrar el umbral;
- analizar el mercado: entidades que más contratan, montos, regiones y épocas del año;
- medir la tasa de presentación y de adjudicación por tipo de proceso;
- revisar a los competidores en las columnas `proponentes` y `ganadores`.

## Indicadores (KPIs)

Plantilla de medición. Los valores de línea base y resultado se completan con datos reales de la operación.

| KPI | Definición | Fuente | Línea base | Resultado |
|---|---|---|---|---|
| Tiempo de detección | Horas entre la publicación del proceso y su evaluación | `fechaPublicacionAPI` vs. `fechaRecepcionISO` | _[completar]_ | _[completar]_ |
| Días útiles para preparar | Días entre la alerta y el cierre | Cronograma | _[completar]_ | _[completar]_ |
| Procesos evaluados por mes | Filas nuevas en la matriz | Matriz | _[completar]_ | _[completar]_ |
| Tasa de alertas | % de procesos con `alerta_enviada = true` | Matriz | n/a | _[completar]_ |
| Precisión de la alerta | % de alertas que el equipo decide presentar | Matriz + decisión comercial | n/a | _[completar]_ |
| Falsos negativos | Procesos no alertados que el equipo sí habría presentado (muestreo mensual) | Revisión manual | n/a | _[completar]_ |
| Horas de revisión ahorradas | (procesos × minutos de revisión manual) − minutos de revisión de alertas | Estimación | _[completar]_ | _[completar]_ |
| Ofertas presentadas | Procesos presentados por mes | Comercial | _[completar]_ | _[completar]_ |
| Tasa de adjudicación | Adjudicados / presentados | Comercial | _[completar]_ | _[completar]_ |
| Costo por evaluación | Costo del LLM y la infraestructura / procesos evaluados | Facturación | n/a | _[completar]_ |

### Fórmula sugerida para el ahorro de tiempo

```text
horas_ahorradas_mes = (N_procesos × t_revisión_manual − N_alertas × t_revisión_alerta) / 60
```
donde `t_revisión_manual` es el tiempo que tomaba leer, abrir el portal y cruzar UNSPSC por proceso, y `t_revisión_alerta` es el tiempo de leer una tarjeta de Teams ya analizada.

## Impacto organizacional

- **De reactivo a proactivo:** el equipo pasa de buscar oportunidades a **gestionar un embudo** de oportunidades priorizadas.
- **Conocimiento institucionalizado:** el criterio de quien más sabe de licitaciones queda en reglas y en un prompt versionado, y no depende de una sola persona.
- **Base para escalar:** el mismo motor puede sumar nuevas fuentes (otros agregadores, SECOP II directo), nuevas líneas de negocio o nuevos países ajustando la configuración.
