# Consolidación experimental con Jev — JEV-V1

Camino independiente para consolidar las extracciones originales de GLiNER2 usando el modelo Jev de TypeSafe AI. No modifica ni importa la consolidación determinística, ni ejecuta GLiNER2. La línea base sirve para comparar métodos; no es ground truth.

La implementación se validó localmente sin enviar documentos a TypeSafe. Todavía no se evaluó la precisión de Jev sobre estos casos.

## Fuente y línea base verificadas

Desde la raíz del repositorio:

```text
outputs/por_documento/20261009_160006_multi_v7_fragmentos_thr50/predicciones_por_documento.json
outputs/consolidacion/20261009_160505_consolidacion_multi_v7_fragmentos_thr50_20261009_160006/consolidacion.json
```

`outputs/logs/consolidacion.log`, líneas 137–140, registra que esa consolidación consumió exactamente ese archivo de predicciones. Se inspeccionaron `src/run_consolidacion.py`, `src/consolidacion_embargado.py`, `src/exporter.py`, las dependencias y los tests existentes antes de implementar el adaptador.

La fuente es una lista de 79 documentos con campos `id`, `numero_archivo`, `nombre`, `texto_completo` y `resultados`. Contiene 163 resultados por fragmento y 239 candidatos. La numeración va de 1 a 80 y no incluye el archivo 36; no se crean documentos para cubrir esa ausencia.

Cada resultado conserva `contador_interno`, `palabra_clave`, `categoria`, `tipo_entrada_modelo`, `texto_entrada_modelo`, `fragmento`, `contexto_embargado`, posiciones, estado y `candidates`. Los candidatos incluyen campos canónicos, alias, `fields`, roles, confidencias y spans. Todos se mantienen literalmente, incluidos los valores `null`, nombres parciales y candidatos de baja confianza.

El `state` tiene esta forma:

```text
state.documento = documento original sin el campo superior texto_completo
state.referencias_candidatos = IDs técnicos → punteros a resultados/candidates
```

La única exclusión es `texto_completo`, porque JEV-V1 no añade el OCR completo. `contexto_embargado` se conserva tal como ya aparece en los resultados originales; no se genera ni amplía contexto nuevo. Si una futura entrada incluye `texto_completo` dentro de un resultado, se rechaza la estructura para evitar enviarlo por accidente. Los IDs `f0001.c0001`, etc., reflejan índices, sin modificar los objetos originales. Los checkpoints identifican cada documento por el hash de `[id, numero_archivo]`.

No hay filtrado, normalización, corrección, puntuación jurídica, selección de fragmentos ni agrupación previa. La consolidación de referencia solo interviene en la comparación posterior y en metadatos de procedencia; nunca se incluye en el `state` o en las preguntas.

La línea base comprobada tiene 71 `RESUELTO`, 5 `RESUELTO_MULTIPLE`, 3 `NO_RESUELTO`, 81 identidades aceptadas, 75 documentos suficientes y 4 insuficientes. Esas cifras no son resultados de Jev.

## Archivos

```text
jev_experimentos/
  __init__.py
  config.py
  run_experiment.py
  requirements.txt
  .gitignore
  src/
    __init__.py
    loader.py
    jev_client.py
    decision_engine.py
    result_builder.py
    comparison.py
    storage.py
  tests/
    __init__.py
    conftest.py
    test_loader.py
    test_jev_client.py
    test_decision_engine.py
    test_result_builder.py
    test_integration.py
  outputs/
  README.md
  changelog.txt
```

`loader.py` valida estructura y conserva evidencia; `jev_client.py` encapsula el SDK; `decision_engine.py` prepara preguntas y valida respuestas; `result_builder.py` proyecta decisiones a valores originales; `comparison.py` genera el CSV posterior; `storage.py` escribe JSON de forma atómica. El runner selecciona documentos, controla costos y persiste cada lote.

## Instalación y API oficial

Requiere Python 3.10 o posterior. Verificado en el entorno `.venv` existente, con Python 3.14.3 y **typesafe-sdk 0.7.4**. Las dependencias experimentales están separadas de `requirements.txt` del sistema actual:

```powershell
python -m pip install -r jev_experimentos/requirements.txt
```

La implementación utiliza `typesafe_sdk.TypeSafeClient.system_one(state=..., questions=..., model=..., timeout=...)`. Se verificaron las firmas del paquete instalado, los constructores públicos `Noul` y `Choice` y la serialización Pydantic de `SystemOneResponse`. Se usan diccionarios de preguntas, admitidos oficialmente por el SDK. Las respuestas se leen desde `answers`; `noul` es la probabilidad de respuesta afirmativa, mientras que `Choice` devuelve `choice`, `probabilities` y `confidence`.

El modelo predeterminado está fijado en `jev-1.13.0`, para evitar cambios silenciosos de un alias. `--model jev-latest` es posible y se registra también el modelo efectivamente informado por cada respuesta. El SDK de otra versión se rechaza para ejecución real hasta verificar su compatibilidad.

Fuentes oficiales consultadas el 11/10/2026:

- [SDK Python](https://docs.typesafe.ai/sdk/python) y [repositorio oficial](https://github.com/typesafe-ai/typesafe-sdk-python).
- [Cliente síncrono y firmas](https://docs.typesafe.ai/sdk/python/api/clients/sync).
- [Preguntas](https://docs.typesafe.ai/sdk/python/api/types/questions), [respuestas](https://docs.typesafe.ai/sdk/python/api/types/responses) y [reintentos](https://docs.typesafe.ai/sdk/python/api/retries).
- [API HTTP](https://docs.typesafe.ai/api) y [modelos y límites](https://docs.typesafe.ai/models).

La URL del blog `typesafe-ai.com/blog/introducing-system-one-models-and-jev` provista en la tarea no fue accesible durante la consulta. La integración se verificó mediante la documentación oficial vigente y el SDK instalado. No se usa un servicio sustituto ni un LLM convencional.

## Preguntas y política de decisiones

Hay dos estrategias, seleccionadas con `--estrategia simple|completa`. La predeterminada es **`completa`**, que conserva las preguntas y el comportamiento originales de JEV-V1. Ambas utilizan exactamente el mismo `state`, con todos los resultados, fragmentos, candidatos y metadatos originales. La estrategia solo modifica las preguntas y la interpretación posterior de sus respuestas.

La política de esta sección describe la estrategia **`completa`**.

Para **cada candidato original** se preguntan cuatro cosas:

1. `Noul`: si sus fondos, cuentas o bienes son objeto del embargo en las evidencias del documento.
2. `Choice`: su función real: embargado, actora, profesional, funcionario, autorizado a diligenciar, destinataria del oficio, otro tercero o información insuficiente.
3. `Noul`: si su nombre o razón social original es completo, sin agregar palabras.
4. `Noul`: si sus datos identificatorios son contradictorios o están asociados de forma incierta.

Para **cada par de candidatos**, sin preselección, se hacen dos preguntas `Noul`: equivalencia de identidad y conflicto de identificadores. Esto permite que Jev vincule nombres completos y parciales, o detecte un mismo identificador atribuido a personas distintas. No se decide equivalencia mediante DNI, confianza o parecido del nombre en Python.

Con `n` candidatos se generan `4n + n(n−1)` preguntas. La estrategia es cuadrática; no se reduce el conjunto de pares con heurísticas. Las preguntas incluyen IDs explícitos en sus instrucciones, porque el proveedor no usa la clave del mapa de preguntas como contexto de inferencia.

Cada pregunta se evalúa contra el mismo contexto completo del documento. `--preguntas-por-solicitud` fija un máximo técnico propio de 64 preguntas por lote, no un supuesto límite del proveedor. También se divide el mapa de preguntas según una estimación conservadora del presupuesto total. No se divide ni recorta el `state`.

La política experimental predeterminada es:

- Aceptar un candidato únicamente si `acepta.noul >= 0.8` (`--umbral`). Descartarlo si es `<= 0.2`; entre ambos límites, registrar incertidumbre sin aceptarlo. Un valor ausente o inválido nunca se convierte en aceptación.
- Unir candidatos aceptados únicamente si Jev confirma su equivalencia con `noul >= 0.9` (`--umbral-equivalencia`). Una componente debe tener confirmación para **todos sus pares**. Si A=B y B=C, pero A=C no está confirmado, conservar candidatos por separado y registrar equivalencia no transitiva.
- El rol no reemplaza la decisión de aceptación. Un desacuerdo entre un rol seguro y la aceptación se registra como conflicto para revisión.
- Elegir como representante el primer candidato aceptado del grupo cuyo nombre Jev considere completo con probabilidad al menos igual al umbral. Si ninguno cumple, conservar el valor original del primer candidato, incluso `null`, y marcar revisión. No se concatenan palabras ni se completan nombres.
- Conservar todas las variantes originales. Si un grupo presenta varios valores literales de DNI o CUIT/CUIL, dejar el campo consolidado en `null`, listar las alternativas y registrar divergencia. Diferencias de formato también generan esta advertencia técnica; no se afirma que prueben una contradicción jurídica.
- Registrar incertidumbre de equivalencia, rol y conflictos. Los conflictos de identificadores informados por Jev pueden afectar candidatos no aceptados y quedan visibles. Equivalencia entre un aceptado y un no aceptado también se registra como inconsistencia.
- La cantidad final puede ser cero, uno o varios grupos. Sus estados son `NO_RESUELTO`, `RESUELTO` y `RESUELTO_MULTIPLE`. `RESUELTO` describe la cantidad de identidades aceptadas; `requiere_revision` y `procesamiento` expresan la calidad y completitud de la respuesta.

Esta es una conversión técnica de probabilidades, no una nueva regla jurídica. No se copia la suficiencia determinística: `evaluacion_suficiencia` siempre es `NO_EVALUADA_EN_JEV_V1`. Ninguna probabilidad garantiza que la identidad sea correcta. No se calcula una probabilidad combinada para el grupo; se muestran la del representante y todas las probabilidades de aceptación por candidato.

### Estrategia simple

Genera **una única pregunta `Noul` por candidato original**, con sus IDs técnicos en las instrucciones:

> Considerando todas las extracciones y fragmentos originales de este documento, ¿este candidato representa a una persona o entidad cuyos fondos, cuentas o bienes son objeto de la medida de embargo?

No formula preguntas de rol, nombre completo, contradicciones, equivalencia ni pares. Con `n` candidatos produce exactamente `n` preguntas. Se mantienen los umbrales de aceptación: `p >= umbral` acepta, `p <= 1−umbral` descarta y el intervalo intermedio es incierto y no se acepta. Las respuestas ausentes o inválidas tampoco se aceptan automáticamente.

Cada extracción aceptada se conserva como una entrada independiente en `personas_embargadas`, incluso si coincide literalmente en nombre, DNI o CUIT con otra. No hay fusiones por reglas ni por transitividad. Se mantienen sus campos originales, valores nulos, referencias y evidencias.

Los resultados y el resumen registran `deduplicacion: NO_EVALUADA` y `unidad_conteo: candidatos_aceptados_sin_deduplicar`. Por eso `cantidad_embargados` y `total_personas_embargadas` cuentan **extracciones aceptadas**, no identidades distintas verificadas; `RESUELTO_MULTIPLE` puede incluir apariciones repetidas de la misma persona.

Los resultados explicitan también que no se evaluaron rol, completitud del nombre ni conflictos de identificadores. Un listado de conflictos vacío no certifica ausencia de contradicciones. `requiere_revision` se conserva en `true` por esas evaluaciones omitidas, mientras que `incertidumbre` refleja respuestas de aceptación inciertas o incompletas; la ausencia de preguntas adicionales no se trata como error de respuesta.

Desde Bash en macOS, en la raíz del repositorio, para preparar los cuatro documentos **sin usar la API**:

```bash
.venv/bin/python -m jev_experimentos.run_experiment \
  --experiment 20261009_160006_multi_v7_fragmentos_thr50 \
  --solo-archivos 9 11 30 79 \
  --estrategia simple \
  --dry-run
```

Para validar la estrategia anterior, reemplazar `simple` por `completa` o quitar `--estrategia`. La selección de estrategia no habilita el envío de datos: siguen vigentes `--dry-run`, la autorización explícita y los controles de costos existentes.

## Ejecución sin API

Activar el entorno del proyecto y ejecutar desde la raíz:

```powershell
python -m jev_experimentos.run_experiment --experiment 20261009_160006_multi_v7_fragmentos_thr50 --dry-run
python -m jev_experimentos.run_experiment --experiment 20261009_160006_multi_v7_fragmentos_thr50 --solo-archivos 9 11 30 79 --dry-run
```

`--dry-run` prepara todos los planes y escribe los cinco outputs. Retorna antes de construir un cliente SDK, incluso si hay una clave o se combina con la opción de autorización. No necesita clave ni SDK instalado. `consolidacion_jev.json` queda vacío, `comparacion.csv` contiene solo encabezados y los documentos figuran pendientes: no se fabrican decisiones.

Se puede añadir `--limite-documentos 4`, `--output-dir RUTA` o cambiar los umbrales y el máximo técnico de preguntas. Un número de archivo inexistente se rechaza. `--output-dir` debe ser una carpeta nueva; no sobreescribe una ejecución anterior.

## Primera prueba real, solo después de autorizar el envío

No se ejecutaron estos comandos durante la implementación. Cuando se confirme el acceso y la autorización de tratamiento, configurar `TYPESAFE_API_KEY` en el entorno. La presencia de la clave por sí sola no habilita el envío.

Prueba limitada a Claudia Marcela Ledo (9), Santiago Nicolás González (11), Diego Fabián Fretes (30) y el caso múltiple con conflicto (79):

```powershell
python -m jev_experimentos.run_experiment --experiment 20261009_160006_multi_v7_fragmentos_thr50 --solo-archivos 9 11 30 79 --max-solicitudes 20 --autorizar-envio-datos
```

Se prevén 5 solicitudes iniciales. El límite de 20 cuenta también reintentos y llamadas de una reanudación; no es una estimación de facturación monetaria.

Para intentar los 79 documentos, manteniendo íntegra la evidencia de los tres casos que superan la estimación local por bytes:

```powershell
python -m jev_experimentos.run_experiment --experiment 20261009_160006_multi_v7_fragmentos_thr50 --max-solicitudes 300 --permitir-contexto-estimado --autorizar-envio-datos
```

`--permitir-contexto-estimado` permite que la API valide el tamaño real por tokens. No amplía los límites del proveedor, no elimina evidencia y no activa el envío sin la autorización separada. Si se omite, los documentos bloqueados por la estimación quedan pendientes y la ejecución real retorna código 1. Otra opción futura es implementar medición con un tokenizer oficial confirmado, antes de habilitar esos casos.

## Límites, errores y reanudación

La documentación del modelo consultada indica 64k tokens para el contexto total de la solicitud y 32k para `state` más la pregunta más larga. No se encontró un tokenizer oficial público en las referencias consultadas. Se usa **un proxy conservador de un token por byte UTF-8, más 2.048 de reserva**, con presupuestos internos de 32.000/64.000. No es una medición exacta ni una garantía frente a la tokenización del proveedor. Los metadatos distinguen `excede_estimacion`, `bloqueado_por_estimacion` y `tokenizacion_confirmada: false`.

No se afirma que un documento que supere ese proxy exceda realmente los límites. Dividir preguntas resuelve el presupuesto total; no resuelve un `state` que realmente supere el máximo con una sola pregunta. En ese caso JEV-V1 debe registrar el rechazo de la API; no recorta fragmentos. Confirmar los límites vigentes y la tokenización sigue pendiente para la ejecución completa.

El timeout por operación HTTP es de 30 segundos y se permiten dos reintentos adicionales. Se deshabilitan los reintentos internos del SDK para contar cada intento. Se reintentan conexiones, timeouts y los estados 429, 500, 502, 503, 504 y 529 con espera exponencial; se respeta `retry_after_ms` cuando existe y no supera 30 segundos. Un `Retry-After` mayor termina la llamada para que pueda retomarse después. Los errores 401/403 detienen el lote completo. Las respuestas inválidas no generan una sustitución del modelo ni aceptación automática.

Cada lote y respuesta se guarda atómicamente en `documentos/<hash>.json`, antes de reconstruir los outputs agregados. El contador de intentos se guarda **antes** de la llamada. Si el proceso se interrumpe entre escrituras, el conteo puede ser conservador. El bloqueo de ejecución impide dos escritores simultáneos y el sistema operativo lo libera si el proceso termina abruptamente.

Para reanudar, repetir los mismos argumentos de selección, modelo, umbrales, lotes y modo, añadiendo `--resume`:

```powershell
python -m jev_experimentos.run_experiment --experiment 20261009_160006_multi_v7_fragmentos_thr50 --solo-archivos 9 11 30 79 --resume jev_experimentos/outputs/ID_EJECUCION --max-solicitudes 20 --autorizar-envio-datos
```

Se verifican hash de entrada, selección, planes, configuración, modo y hash de línea base. El presupuesto máximo de solicitudes puede aumentarse al reanudar, sin reiniciar el contador. Si la corrida completa usó `--permitir-contexto-estimado`, repetir esa opción. Un dry-run se puede reanudar como dry-run; no se convierte en una corrida real sobre la misma carpeta.

Los lotes `RESPONDIDO` jamás se vuelven a consultar, incluso si faltan respuestas a algunas preguntas; esas ausencias se marcan para revisión. Los lotes `ERROR` se conservan y no se reintentan automáticamente. Para reintentarlos usar `--reintentar-errores`. Si quedó un lote `EN_CURSO` sin respuesta guardada, se exige esa opción tras revisar el caso: el servidor pudo procesar la llamada y podría repetirse el consumo. No se promete ejecución exactamente una vez frente a una desconexión.

## Outputs y auditoría

Cada ejecución crea su propia carpeta en `jev_experimentos/outputs/`. Los nombres automáticos incluyen la estrategia, por ejemplo `<timestamp>_simple_dry_run` y `<timestamp>_completa_dry_run`. Una ruta explícita debe ser nueva y no puede reutilizarse para sobreescribir otra corrida. `metadata.json`, `resumen_jev.json`, los planes, los checkpoints, `decisiones_jev.json` y el mensaje de consola registran la estrategia utilizada.

El contrato de reanudación incluye la estrategia: una ejecución `simple` no puede reanudarse como `completa`, ni a la inversa. Al reanudar una corrida simple, repetir `--estrategia simple`. Las ejecuciones anteriores a esta opción se reconocen como `completa`, preservando su compatibilidad.

Archivos generados:

- `decisiones_jev.json`: documentos, contexto original por fragmentos, preguntas, IDs y referencias, lotes, hashes de solicitud, respuestas originales serializables del SDK, probabilidades y errores estructurados.
- `consolidacion_jev.json`: documentos con respuestas disponibles, estado, personas aceptadas, valores originales, evidencias, decisiones por candidato, incertidumbre, conflictos generales y de identificadores. `procesamiento: RESPUESTA_INCOMPLETA` distingue respuestas incompletas. Los documentos con fallos de API o lotes pendientes no se presentan como decisiones de Jev.
- `resumen_jev.json`: documentos de origen/seleccionados/procesados/pendientes, estados, personas, incertidumbre, conflictos, errores, candidatos, fragmentos, preguntas y dimensiones de cada plan.
- `comparacion.csv`: comparación posterior por `(id, numero_archivo)`, estados, nombres comunes/exclusivos, valores y diferencias de identificadores, conflictos y revisión. Las diferencias incluyen conjuntos globales y asociaciones por nombre compartido, para detectar identificadores intercambiados entre personas. Usa igualdad literal y las variantes conservadas por ambos métodos; no aplica emparejamiento heurístico. Para otros experimentos, proporcionar `--baseline RUTA`; no se selecciona una línea base por semejanza del nombre.
- `metadata.json`: procedencia y SHA-256, versión de preguntas, SDK/Python, configuración y umbrales, modelo solicitado y modelos respondidos, fechas con UTC−03:00, intentos acumulados, errores y consumo informado por respuesta, estado de comparación y verificación del hash al terminar.
- `documentos/`: checkpoints de cada documento para reanudación. `.run.lock` es el archivo técnico de bloqueo.

`comparacion.csv` solo tiene filas después de obtener respuestas de Jev y disponer de la línea base. La coincidencia entre ambos métodos no demuestra corrección. Los valores nulos se mantienen nulos; la salida no inventa nombres o identificadores faltantes.

Las salidas contienen datos personales y están excluidas de Git por el `.gitignore` del módulo. Los JSON y CSV se crean con permisos privados mediante temporales. No se almacena la clave, no se registran headers de autenticación ni mensajes arbitrarios de excepciones, y se redacta cualquier eco de la clave en respuestas. El cliente fija `https://api.typesafe.ai`; no acepta una sustitución mediante `TYPESAFE_BASE_URL`. El logging del SDK se deshabilita durante la inicialización real.

## Validación realizada

```powershell
python -m pytest jev_experimentos/tests tests -q
```

La validación inicial del 11/10/2026 aprobó **135 tests: 50 del módulo experimental y 85 existentes**. Los tests experimentales bloquean conexiones de red y usan documentos sintéticos. Cubren preservación de nulls y baja confianza, roles de terceros, nombres parciales, identificadores sin nombre, cero/uno/múltiples embargados, equivalencias, conflictos, respuestas inválidas/incompletas, timeouts y reintentos, presupuesto global, reanudación e interrupciones. La comparación también detecta identificadores intercambiados entre nombres compartidos. El contrato HTTP del SDK instalado se verificó con `httpx2.MockTransport`, sin conexiones. También se validaron las 2.784 preguntas reales con los constructores públicos del SDK, sin cliente ni API.

La actualización del 12/10/2026 agregó 16 casos de prueba para la estrategia simple y la compatibilidad: **151 tests aprobados en total**, 66 experimentales y 85 del sistema original. Incluyen duplicados independientes, nulls, umbral configurable, incertidumbre, respuestas incompletas, integración simulada, estrategia en outputs, reanudación de simple, rechazo de estrategias distintas, carpetas independientes y compatibilidad con checkpoints antiguos de completa.

Se ejecutaron además dos dry-runs desde la consola sobre los archivos 9, 11, 30 y 79:

| Estrategia | Documentos | Fragmentos | Candidatos | Preguntas | Solicitudes previstas | Llamadas reales |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `simple` | 4 | 8 | 15 | 15 Noul | 4 | 0 |
| `completa` | 4 | 8 | 15 | 144 | 5 | 0 |

Las carpetas de esta validación son `outputs/20261012_233644_931282_simple_dry_run/` y `outputs/20261012_233645_069344_completa_dry_run/`. Se verificó igualdad profunda del `state` entre estrategias y de las preguntas de completa con las guardadas antes del cambio. Simple no contiene preguntas por pares. El SHA-256 de entrada permaneció igual al de la validación inicial.

Se conservan las dos validaciones iniciales sobre datos reales, sin API, con la estrategia completa:

| Validación | Documentos | Fragmentos | Candidatos | Preguntas | Solicitudes previstas | Llamadas reales |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `outputs/validacion_jev_v1_completa/` | 79 | 163 | 239 | 2.784 | 166 | 0 |
| `outputs/validacion_jev_v1_cuatro_archivos/` | 4 | 8 | 15 | 144 | 5 | 0 |

La división del caso 79 genera dos solicitudes con el mismo contexto. Los archivos 9 y 30 generan una cada uno y el 11 una. Las estimaciones de `state` para 9/11/30/79 son 3.309/11.195/4.100/20.480 bytes. Ninguno de esos cuatro está bloqueado por el proxy local.

Los archivos **14, 15 y 31** superan el proxy de contexto por pregunta, con `state` de 48.548, 47.125 y 40.960 bytes. Se preparan sus preguntas sin perder evidencia, pero quedan bloqueados para una ejecución real predeterminada. Las 166 solicitudes previstas incluyen esos tres documentos; sin habilitarlos quedarían 77 solicitudes iniciales ejecutables y tres documentos pendientes. Es una limitación de estimación, no un rechazo confirmado de la API.

SHA-256 de entrada antes y después de la validación:

```text
420d8e2f2cedfffe4591de2876af8bdbdd46d7daf3c8671354900af4c6e9322d
```

Se verificó por igualdad profunda que todos los `resultados` originales reaparecen completos en el `state`. No se modificó el JSON de entrada ni ningún archivo del sistema existente.

## Pendientes experimentales

Confirmar acceso y autorización de tratamiento para la primera prueba real; comprobar tokenización y límites efectivos para los tres casos señalados; evaluar el comportamiento en español jurídico; ajustar umbrales con ground truth independiente y medir errores, duplicados y costo observado. No hay resultados reales de Jev para comparar todavía, ni evidencia de que mejore la línea base.
