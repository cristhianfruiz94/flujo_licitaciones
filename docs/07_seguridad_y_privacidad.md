# 07 · Seguridad y privacidad

## Qué NO contiene este repositorio

- El flujo original de n8n (export JSON).
- El nombre de la empresa, de sus empleados o de sus clientes.
- Credenciales, tokens, IDs de tenant, de equipos o canales de Teams, IDs de archivos de OneDrive ni URLs de SharePoint.
- Datos reales del RUP ni de procesos en curso.

Todas las entidades, códigos de proceso, valores y contratos de `datos_ejemplo/` son **ficticios**. Los dominios usados (`agregador.ejemplo`, `ejemplo.invalid`) están reservados y no resuelven.

## Buenas prácticas aplicadas en el prototipo

| Riesgo | Mitigación |
|---|---|
| Credenciales en el código | Todo se lee de variables de entorno (`.env`), y `.env` está en `.gitignore`. Se incluye solo `.env.example` sin valores. |
| Credenciales en el flujo de n8n | En producción, usar siempre el **gestor de credenciales de n8n**, nunca valores en el cuerpo de un nodo HTTP. Si alguna credencial quedó escrita en un nodo o en un export, **hay que rotarla**. |
| Exportar flujos con datos | Los exports de n8n pueden incluir *pinData* (correos reales de prueba) y URLs internas. Hay que limpiarlos antes de compartir. |
| Inyección vía contenido del correo o del portal | El contenido externo solo se usa como **dato** en el prompt. El agente devuelve JSON con un esquema fijo, el parser descarta todo lo demás y la decisión se recalcula en código. |
| HTML en la tarjeta de Teams | El prototipo escapa todos los campos (`html.escape`) antes de insertarlos. |
| Datos personales en la matriz | La matriz solo guarda datos públicos de procesos de contratación. Los proponentes y ganadores son personas jurídicas publicadas en SECOP. |
| Columnas de depuración | Evitar escribir objetos de *debug* en la matriz de producción, porque pueden filtrar respuestas completas de la API. |

## Recomendaciones para producción

1. Usar un buzón dedicado y una **contraseña de aplicación** para IMAP.
2. Dar a la app de Microsoft Graph **permisos mínimos**: solo el archivo de la matriz, la carpeta del RUP y el canal de alertas.
3. **Rotar periódicamente** la contraseña de la API del agregador y la API key del LLM.
4. Restringir quién puede editar y exportar el flujo en n8n, y activar el registro de ejecuciones con retención limitada.
5. Proteger el webhook del formulario de anexos con un token firmado en el `process_id`.
