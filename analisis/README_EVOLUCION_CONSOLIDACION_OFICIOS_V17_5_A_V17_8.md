# Consolidación de oficios judiciales — Informe de evolución V17.5 → V17.8

**Fecha:** 23 de noviembre de 2026  
**Versión más reciente:** V17.8 (`consolidacion_oficios_v17_8_refuerzos.py`)  
**Base:** extracción GLiNER2 sobre fragmentos de oficios.  
**Propósito:** documentar las modificaciones, cuantificar los cambios efectivos y comprobar que las nuevas expresiones contextuales no alteraron indebidamente las identidades ya consolidadas.

> **Alcance fundamental.** Las decisiones de la consolidación se calculan con `resultados[].fragmento` o, cuando falta, `resultados[].texto_entrada_modelo`, junto con las predicciones de GLiNER2. `texto_completo` se conserva en la salida para un eventual fallback posterior, pero **no se inspecciona para consolidar identidades**. `suficiente=True` significa que la etapa no requiere fallback según sus reglas; **no equivale a exactitud certificada contra un gold**.

---

## 1. Resumen ejecutivo

La evolución **V17.5 → V17.8** no pretende sustituir GLiNER2, ampliar los fragmentos ni clasificar automáticamente a todas las personas mencionadas. Busca aprovechar mejor las identidades y relaciones que **ya aparecen dentro de los fragmentos**.

- **V17.5:** consolidó las mejoras acumuladas V17.1–V17.5: reconstrucción de apellidos con DNI/CUIT/CUIL, relación local entre persona y requerimiento, deduplicación de evidencias, auditoría de roles y recuperación de una razón social vinculada al CUIT. En los 20 casos nuevos alcanzó **16 suficientes** frente a **11 de la V16**.
- **V17.6:** incorporó una salida específica de **identidades estructuradas recuperadas para revisión manual**, sin promoverlas automáticamente como personas objeto del oficio. Cambió el diagnóstico del documento **`790081`**, pero mantuvo **16/20 suficientes**.
- **V17.7:** añadió detección complementaria de relaciones contextualizadas (p. ej., **cuentas pertenecientes a una persona**, **operaciones realizadas por** y **facturación atribuida a**). Protegió los casos previos: **sin cambios de aceptación/suficiencia**. En el caso nuevo **`790085`** aumentó el score contextual **7,419 → 8,919**, sin modificar su aceptación.
- **V17.8 — foco de este informe:** amplió el análisis a **seis familias lingüísticas**, permitió un **refuerzo de +1,5 puntos** incluso para candidatos que ya tenían contexto positivo, con exclusión de relaciones duplicadas, terceros y enlaces de identificadores dudosos. En los 120 documentos principales mantuvo las decisiones y reforzó **un caso histórico** (`496887`, Ángela del Buono, **9,977 → 11,477**). **No incorporó nuevos sujetos ni resolvió documentos adicionales** en el lote probado.

### Indicadores comparativos de los 20 nuevos documentos

| Indicador | V17.5 | V17.6 | V17.7 | V17.8 |
|---|---:|---:|---:|---:|
| Documentos evaluados | 20 | 20 | 20 | 20 |
| Resueltos y suficientes | **16** | **16** | **16** | **16** |
| No resueltos / insuficientes | 4 | 4 | 4 | 4 |
| Documentos con identidad estructurada provisional recuperada | 0 | **1** | **1** | **1** |
| Cambios de identidades aceptadas respecto a V17.5 | — | 0 | 0 | 0 |
| Cambios de suficiencia respecto a V17.5 | — | 0 | 0 | 0 |
| Cambios de score contextual observados en el lote respecto de la versión anterior | — | 0 | **1 (`790085`)** | **0** |

> Los conteos de recuperaciones provisionales se refieren al caso observado `790081`; no representan identidades automáticamente aceptadas. Los scores pueden variar entre versiones sin que cambie el estado o la suficiencia.

---

## 2. ¿Cómo funciona la consolidación?

1. **Recibe fragmentos** previamente seleccionados y las predicciones de GLiNER2 (`nombre_persona`, `dni_persona`, `cuit_cuil_persona`, `rol_persona`).
2. **Recupera campos inequívocos** que aparecen literalmente en esos fragmentos, por ejemplo un apellido anterior al nombre o un DNI adyacente, según condiciones específicas.
3. **Agrupa evidencias** y conserva sus variantes, identificadores, roles, fragmentos y trazabilidad.
4. **Evalúa contexto y vinculación**: si una petición, una cuenta, una operación o un dato se refiere realmente a la persona candidata; separa terceros y conflictos.
5. **Decide** si aceptar o descartar cada grupo y determina `estado`, `suficiente`, `requiere_revision` y motivos de insuficiencia.
6. **Conserva recuperaciones provisionales** cuando el fragmento contiene datos útiles, pero no prueba que la identidad sea el objeto principal del oficio.

**Principio de diseño:** detectar una expresión positiva no alcanza por sí solo para aceptar una persona. La decisión también depende de las relaciones locales, la identidad y las protecciones existentes.

---

## 3. Evolución técnica de las versiones

### 3.1. V17.5 — Base funcional de comparación

Esta versión acumuló cambios desarrollados en V17.1–V17.5:

| Mejora | Comportamiento | Ejemplos de los 20 nuevos |
|---|---|---|
| Reconstrucción de apellido omitido | Recupera una estructura literal `APELLIDO, NOMBRE` cuando el identificador cercano confirma la asociación. Considera DNI y CUIT/CUIL; **dos palabras pueden formar un nombre válido**. | `789454` UNGAR; `790085` SORIA |
| Relación directa con el requerimiento | Reconoce fórmulas locales que vinculan al sujeto con operaciones bancarias o peticiones. No exige siempre rol procesal ni repetición. | `790094` Arcadio; `790106` Nancy |
| Recuperación de razón social | Puede recuperar la denominación de una empresa cuando GLiNER detectó su CUIT y el fragmento contiene una relación explícita. | `788347` Caledonia |
| Evidencias independientes | Evita que cuatro predicciones repetidas de un mismo fragmento se computen como cuatro pruebas independientes. | `790072` González |
| Auditoría de roles | Conserva el rol original predicho por GLiNER y registra el rol literal encontrado en el fragmento cuando hay contradicción. | `790097` Romero |
| Recuperaciones históricas preservadas | No pierde identidades cuya reconstrucción ya funcionaba antes. | `790129` López |

**Resultado del lote nuevo:** **16/20 suficientes**, con cuatro casos que requieren revisión o mejor fragmentación (`790081`, `790115`, `790122`, `790138`).

### 3.2. V17.6 — Recuperación provisional sin aceptación automática

La función `_recuperar_identidades_estructuradas_revision()` identifica registros del tipo:

```text
Nombre: PIZZERIA - Apellido: NAPOLES - Tipo de Documento: CUIT - Número de documento: 20288024554
```

Para el documento `790081`, V17.6 guarda:

```json
{
  "nombre_persona": "PIZZERIA NAPOLES",
  "cuit_cuil_persona": "20288024554",
  "tipo_identidad": "NO_DETERMINADO",
  "estado_validacion_identidad": "REQUIERE_REVISION_MANUAL",
  "origen_recuperacion": "campos_estructurados_en_fragmento"
}
```

La identidad se guarda en **`identidades_recuperadas_revision_manual`**; `personas_objeto_oficio` sigue vacío. El documento continúa **`NO_RESUELTO`, `suficiente=false` y `requiere_revision=true`**. Esta distinción evita descartar información útil sin afirmar que el oficio consulte necesariamente a esa persona o entidad.

**Cambio real frente a V17.5:** un documento con una recuperación **provisional** adicional; **ninguna aceptación automática nueva**.

### 3.3. V17.7 — Primera ampliación contextual

La V17.7 introduce `_v17_7_relacion_contextual()` y familias complementarias de contexto positivo para reconocer, entre otras, estas construcciones:

- Operaciones bancarias realizadas **por** una persona.
- Cuentas o fondos **pertenecientes a**, **de titularidad de** o **a nombre de** una persona.
- Requerimientos de información **respecto de** o **acerca de** un sujeto.
- Importes facturados, vínculos comerciales y otras solicitudes relacionadas.

La señal se combina con `_score_contexto()` y **solo se incorpora cuando la puntuación contextual previa no era positiva** y se verifican condiciones de vinculación local. Se preservan los descartes por terceros y la comprobación de identificadores.

**Ejemplo medido:** en el documento nuevo **`790085`**, `SORIA, MARÍA FERNANDA` mantiene `RESUELTO/suficiente`, mientras el `score_total` aumenta de **7,419 (V17.6)** a **8,919 (V17.7)** por una relación contextual local adicional. La V17.8 conserva **8,919** en ese documento; no vuelve a sumarle la misma relación.

**Resultado:** no cambian personas aceptadas, descartes ni suficiencia en las 220 ejecuciones de regresión; se reconoce información contextual adicional.

---

## 4. V17.8 — Ampliación y refuerzo del contexto positivo (mejora principal)

### 4.1. Objetivo

**Reconocer más formas de expresar que un oficio solicita información sobre una persona o entidad, sin confundir al sujeto de la solicitud con firmantes, representantes, autorizados, destinatarios ni otras contrapartes.**

La V17.8 es **aditiva**: mantiene los patrones y las reglas de aceptación anteriores. No impone un nuevo requisito universal, porque eso habría rechazado muchos casos que ya funcionaban.

### 4.2. Seis familias de contexto positivo

La constante **`_V17_8_FAMILIAS`** agrupa patrones compuestos que se examinan **antes del nombre del candidato**, en una ventana acotada:

| Familia en el código | Relación que intenta reconocer | Ejemplos orientativos de construcciones (no todas observadas literalmente en la muestra) |
|---|---|---|
| `pedido_persona` | Introducción de una solicitud dirigida a un sujeto. | `sírvase informar ... respecto de`, `se requiere ... acerca de`, `referente a la señora` |
| `titularidad_productos` | Pertenencia o titularidad de productos financieros. | `cuentas pertenecientes a`, `fondos de titularidad de`, `productos a nombre de` |
| `registro_historico` | Registro presente o pasado de cuentas y productos. | `registra ... cuentas de`, `mantuvo ... cuentas pertenecientes a`, `es o fue titular` |
| `operacion_sujeto` | Relación entre una operación y quien la realiza o percibe. | `operaciones realizadas por`, `movimientos efectuados por`, `transferencias recibidas por` |
| `comercial_fiscal_laboral` | Solicitudes comerciales, tributarias y laborales. | `importes facturados a`, `contratos celebrados con`, `información tributaria correspondiente a`, `haberes percibidos por` |
| `datos_identificacion` | Datos identificatorios, domicilio u otra información personal vinculada. | `domicilio registrado correspondiente a`, `datos personales respecto de`, `información acerca de` |

**Nota de generalización:** estas son familias con variantes lingüísticas esperables; una frase de ejemplo no se considera automáticamente “observada en los 120” salvo que se haya constatado en sus fragmentos. Los patrones no se convierten en una lista de palabras sueltas con puntuación automática.

### 4.3. Nueva función y salvaguardas

La función **`_v17_8_relacion_refuerzo(evidencia)`** comprueba las relaciones de forma localizada. El procedimiento resumido es:

1. Localizar el nombre del candidato **dentro del fragmento**.
2. Detectar una familia contextual en la ventana previa al nombre.
3. Exigir un **DNI/CUIT/CUIL del mismo candidato asociado localmente**, mediante `_identificador_cerca_nombre()`.
4. Rechazar reconstrucciones todavía parciales en listados (`_nombre_parcial_en_lista()`).
5. Excluir contexto de firmas, autorizaciones, representación profesional y otras menciones administrativas.
6. Verificar vocabulario de **requerimiento** y **objeto** dentro del propio fragmento.
7. Evitar atribuir automáticamente una transferencia a ambos participantes cuando aparecen señales de contraparte.
8. Devolver una **familia de relación** o `None` si no hay evidencia suficiente para aplicar el refuerzo.

**Límite:** las expresiones regulares y ventanas implementadas son salvaguardas de ingeniería, no una comprensión semántica infalible. Pueden perder asociaciones correctas o no detectar todos los terceros de documentos desconocidos.

### 4.4. Modificación de `_score_contexto()`

Hasta V17.7, la señal adicional de esa versión operaba, de forma conservadora, cuando el score previo era cero o negativo. La V17.8 introduce un cambio puntual:

- Permite un **refuerzo adicional `+1.5`** aunque el candidato ya tenga contexto positivo **si la nueva relación cumple las validaciones**.
- **No vuelve a premiar** una relación que ya activó la señal complementaria V17.7 en esa evaluación.
- **No aumenta** la puntuación por una mera coincidencia de `titular`, `transferencia`, `respecto de` o cualquier palabra aislada.
- **No altera** las reglas base de aceptación, deduplicación por fragmento, recuperación de identidad ni revisión manual.

Esquema conceptual (explicativo, no reemplazo literal de las funciones):

```text
Score contextual existente
       +
Señal V17.7, solo si corresponde y no había contexto positivo
       +
Refuerzo V17.8 (+1,5), si es una relación independiente,
localmente verificable y sin alertas de terceros
       =
Score contextual de la evidencia
```

**¿Por qué sumar puntos no es malo?** Porque el score permite reflejar respaldo textual adicional. El riesgo sería asignar puntos a personas no consultadas o duplicar la misma relación. Además, el sistema **no acepta personas únicamente por alcanzar un score**: utiliza señales de contexto, rol, identificador, repetición, evidencia vinculante y descartes fuertes. Aun así, una nueva señal contextual positiva *puede* alterar decisiones; por eso se probaron las regresiones completas.

### 4.5. Mejora cuantitativa comprobada — `496887`

| Aspecto | V17.7 | V17.8 | Interpretación |
|---|---:|---:|---|
| Documento histórico | `496887` | `496887` | Misma entrada |
| Identidad | ANGELA DEL BUONO | ANGELA DEL BUONO | No cambia |
| DNI | `14124313` | `14124313` | No cambia |
| `score_total` | **9,977** | **11,477** | **+1,5** por relación contextual adicional |
| Decisión y suficiencia | Se conservan | Se conservan | No es una aceptación nueva |

El refuerzo se relaciona con una **cuenta a nombre del sujeto**. Se refleja tanto en la puntuación serializada como en su detalle diagnóstico.

En una primera prueba más permisiva también aumentaron las puntuaciones de **`497726`** y **`790085`**, pero esas activaciones **duplicaban relaciones que ya reconocía V17.7**. La versión final las excluyó: **tres posibles refuerzos iniciales → uno adicional independiente** en la prueba principal.

**Balance real de V17.8:** mayor capacidad de reconocer tipos de contexto y **una mejora de puntuación comprobada**, sin nuevos sujetos ni nuevos documentos suficientes en los 120 evaluados.

### 4.6. Archivos y funciones implicadas

| Elemento | Situación en V17.8 |
|---|---|
| `PATRONES_CONTEXTO_POSITIVO` | Se conserva; **no** se le agregan todas las frases indiscriminadamente. |
| `_V17_8_FAMILIAS` | Nuevo catálogo de seis familias de expresiones compuestas. |
| `_V17_8_REQ`, `_V17_8_OBJ` | Filtros que requieren vocabulario de petición y objeto en el fragmento. |
| `_V17_8_NEG`, `_V17_8_CONTRAPARTE` | Exclusiones de contextos administrativos y operaciones ambiguas. |
| `_v17_8_relacion_refuerzo()` | Nueva comprobación local de una relación contextual verificable. |
| `_score_contexto()` | Mantiene lógica previa y suma `+1.5` en los casos verificados que no duplican la señal V17.7. |
| `_evaluar_grupo_oficio()` | **Sin sustitución de los criterios generales de aceptación**. |
| `_recuperar_identidades_estructuradas_revision()` | **Sin cambios funcionales**: se conserva la mejora V17.6. |

---

## 5. Comparación detallada de los últimos 20 documentos — V17.5 → V17.8

**Fuente de verificación:** el mismo JSON `predicciones_por_documento(20261120-044012).json` ejecutado directamente con los cuatro archivos Python: V17.5, V17.6, V17.7 y V17.8. Se verificaron estados, suficiencia, revisión, identidades aceptadas e identidades provisionales. Las observaciones de V16 se mantienen como contexto histórico cuando ayuda a explicar el origen de la recuperación, pero la tabla solicitada empieza en V17.5.

**Convenciones:** `R/S` = `RESUELTO` y suficiente; `NR/I` = `NO_RESUELTO` e insuficiente; `RM` = recuperación exclusivamente para revisión manual; `=` = conserva la identidad, aceptación y suficiencia de la columna anterior (si cambia el score, se indica explícitamente).

| Doc. (ID) | V17.5 — referencia | V17.6 — recuperación provisional | V17.7 — contexto ampliado | V17.8 — resultado final | Qué cambió / qué se mantuvo |
|:---|:---|:---|:---|:---|:---|
| **1 (`788347`)** | **R/S**. Caledonia Argentina Compañía de Seguros SA; CUIT `3050003967-8`. | **=** | **=** | **=** | La razón social recuperada desde el fragmento en V17.5 permanece aceptada; no se asocia un CUIT aislado a un tercero. |
| **2 (`789454`)** | **R/S**. `UNGAR, NORBERTO HORACIO`; CUIT `20-10041809-7`. Firmante descartada. | **=** | **=** | **=** | Se conserva la reconstrucción del apellido omitido y la separación de María Virginia Raffo como tercero. |
| **3 (`790063`)** | **R/S**. Marta Elisa PUGLIESE; DNI `4756818`; CUIL `27-04756818-3`. | **=** | **=** | **=** | Se mantiene una sola identidad con sus dos identificadores y evidencia en dos fragmentos. |
| **4 (`790072`)** | **R/S**. GONZALEZ DAVID AVELINO; DNI `33903621`; cuatro predicciones originales, una evidencia independiente. | **=** | **=** | **=** | Persiste la deduplicación incorporada antes: no se premian artificialmente las cuatro predicciones del mismo fragmento. |
| **5 (`790081`)** | **NR/I**. GLiNER detecta `PIZZERIA`; descartado por `nombre_no_valido`. Sin identidad recuperada. | **NR/I + RM**. Recupera **PIZZERIA NAPOLES**, CUIT `20288024554`, en `identidades_recuperadas_revision_manual`. | **=** | **=** | **Único cambio funcional nuevo del lote entre V17.5 y V17.8**: V17.6 guarda una identidad estructurada con `tipo_identidad=NO_DETERMINADO` y validación manual. **Nunca la acepta automáticamente.** |
| **6 (`790085`)** | **R/S**. `SORIA, MARÍA FERNANDA`; CUIT `27-34953534-9`; `score_total=7,419`. | **=**. Mantiene el score. | **R/S**, misma identidad; `score_total=8,919`. | **=**. Score `8,919`. | **Mejora diagnóstica V17.7 (+1,5)** por contexto de cuentas pertenecientes al sujeto; la V17.8 **no duplica** la puntuación. |
| **7 (`790089`)** | **R/S**. Martin Ignacio Galvan; DNI `39054617`. | **=** | **=** | **=** | No se exige un rol procesal adicional para conservar el pedido explícito. |
| **8 (`790091`)** | **R/S**. Horacio Guillermo PÉREZ; DNI `22.513.908`. | **=** | **=** | **=** | Identidad y contexto de demandado preservados. |
| **9 (`790092`)** | **R/S**. Franco Eduardo Cárdenas; DNI `32.851.047`; CUIL `20-32851047-3`. | **=** | **=** | **=** | Se mantiene la asociación de dos identificadores al mismo sujeto. |
| **10 (`790094`)** | **R/S**. Arcadio Samuel Hamil García; DNI `37433769`. | **=** | **=** | **=** | Continúa funcionando la relación entre las operaciones bancarias solicitadas y la persona, lograda en V17.2. |
| **11 (`790097`)** | **R/S**. Romero Hector; DNI `34.472.193`; GLiNER indicó `actor`, el fragmento `accionado`. | **=** | **=** | **=** | Se conserva la auditoría de contradicción `actor` / `demandado`, sin sobrescribir el rol predicho. Un nombre de dos palabras sigue siendo válido. |
| **12 (`790102`)** | **R/S**. ENDARA MARIANO ADRIÁN; DNI `38.804.970`; CUIL `20-38804970-8`. | **=** | **=** | **=** | Sin cambios en identidad ni asociación de identificadores. |
| **13 (`790106`)** | **R/S**. NANCY SILVANA GRACIANO; DNI `27017871`; CUIT `27-27017871-0`. | **=** | **=** | **=** | Mantiene el reconocimiento de `respecto de la señora ... lo siguiente:` y el descarte de `nombrada` como entidad. |
| **14 (`790111`)** | **R/S**. Susana Esther Gigerey; DNI `44.379.117`. | **=** | **=** | **=** | Identidad aceptada y suficiencia preservadas. |
| **15 (`790114`)** | **R/S**. ARIAS MARIA BELEN; DNI `37.128.726`. | **=** | **=** | **=** | Se conserva el reconocimiento de la demandada y el filtrado de terceros administrativos. |
| **16 (`790115`)** | **NR/I**. Sin fragmentos útiles para identificar al sujeto. | **=** | **=** | **=** | Pendiente de fragmentación. Las expresiones contextuales no pueden recuperar información que no aparece en el input fragmentado. |
| **17 (`790122`)** | **NR/I**. Sin fragmentos útiles; no se identifica al sujeto desde la entrada de GLiNER. | **=** | **=** | **=** | Pendiente de fragmentación. No se recurre al `texto_completo` para suplir el fragmento ausente. |
| **18 (`790129`)** | **R/S**. `LOPEZ, JOSE LEONARDO`; DNI `30500719`. | **=** | **=** | **=** | Se conserva la reconstrucción literal del apellido que ya funcionaba en V16. |
| **19 (`790136`)** | **R/S**. ANDRADE NORA; DNI `18223729`. | **=** | **=** | **=** | No se incorpora automáticamente a Kevin Ezequiel Slavin, vinculado a la cuenta de destino, sin confirmar el alcance del pedido. |
| **20 (`790138`)** | **NR/I**. No hay fragmentos útiles para recuperar la identidad. | **=** | **=** | **=** | Sigue pendiente el fragmentador; ninguna versión utiliza el documento completo para completar la identidad. |

### Lectura de la tabla

- **16 documentos** permanecen `RESUELTO/suficiente` desde V17.5 hasta V17.8 con **las mismas identidades aceptadas**.
- **4 documentos** continúan `NO_RESUELTO/insuficiente`: `790081`, `790115`, `790122`, `790138`.
- **`790081`** es el único caso de este lote que **gana una identidad nueva recuperada para revisión manual** (V17.6). El estado no cambia.
- **`790085`** gana **+1,5 de score** en V17.7; V17.8 no vuelve a aumentarlo, para evitar duplicación.
- **V17.8 no cambia ninguna salida del lote nuevo respecto de V17.7** (incluidos scores y datos provisionales).

---

## 6. Regresión ampliada: documentos históricos e internacionales

Además de los 20 nuevos, se revisó la compatibilidad sobre otras corridas ya utilizadas en el desarrollo. Estas cifras son **ejecuciones por documento**, no 220 documentos necesariamente únicos.

| Corrida | Cantidad | Suficientes V17.7 | Suficientes V17.8 | Cambios en aceptación / suficiencia | Cambios diagnósticos V17.8 |
|---|---:|---:|---:|---:|---:|
| Históricos 01/11 | 80 | 76 | 76 | 0 | `496887`: +1,5 |
| Históricos 30/10 | 80 | 75 | 75 | 0 | `496887`: +1,5 |
| 20 anteriores | 20 | 16 | 16 | 0 | 0 |
| 20 internacionales | 20 | 1 | 1 | 0 | 0 |
| 20 nuevos | 20 | 16 | 16 | 0 | 0 |
| **Total de ejecuciones** | **220** | **184** | **184** | **0** | **Una identidad histórica en dos corridas** |

**Pruebas dirigidas V17.8: 7/7 correctas**, con dos señales positivas (domicilio y contratos) y cinco negativas (firmante repetido, tercero autorizado, DNI de otra persona, falta de identificador, falta de solicitud). Se comprobó también que sustituir `texto_completo` por contenido ajeno no altera los campos de decisión.

**Importante:** `0 cambios en aceptación` no significa `salidas idénticas byte a byte`. El refuerzo de `496887` sí modifica `score_total`, `score_contextual` y datos diagnósticos relacionados. Las demás estructuras de identidad y decisiones se conservan.

### Diferencia entre mejora observada y precisión real

| Pregunta | Respuesta sustentada por la prueba |
|---|---|
| ¿Se perdieron identidades aceptadas? | **No** en los 220 pases comparados. |
| ¿Se aceptaron terceros nuevos por la ampliación? | **No** en las corridas comparadas ni en las siete pruebas dirigidas. |
| ¿Cambió algún DNI/CUIT aceptado? | **No** en las comparaciones realizadas. |
| ¿Mejoró la puntuación contextual? | **Sí**, un caso histórico independiente (`496887`) con +1,5. |
| ¿Se recuperaron nuevos sujetos gracias a V17.8? | **No** en esta muestra. |
| ¿Se demostró mejor precisión/recall general en documentos desconocidos? | **Todavía no**. Hace falta un conjunto independiente y etiquetado. |

---

## 7. Restricciones que se mantienen

1. **Solo fragmentos:** no se permite completar contexto, nombres o identificadores con `texto_completo` durante la consolidación.
2. **Una expresión positiva no equivale a sujeto confirmado:** la coincidencia se debe asociar a un nombre y, para estas nuevas señales, a su identificador local.
3. **Los terceros no se aceptan por proximidad:** firmantes, funcionarios, autorizados y contrapartes deben evaluarse en relación con el pedido concreto.
4. **No se duplican refuerzos:** varias expresiones sobre la misma relación no implican evidencias independientes adicionales.
5. **Los nombres de dos palabras son válidos**, siempre que se cumplan las demás condiciones de identidad.
6. **Se conserva trazabilidad:** predicciones originales, roles, fragmentos, conflictos, motivos de aceptación y motivos de revisión.
7. **El fallback está señalado, no ejecutado:** `requiere_fallback_documento_completo` indica que otra etapa debería revisar el documento completo; esta consolidación no lo consume.

---

## 8. Limitaciones y próximos pasos

### 8.1. Cobertura

Las 6 familias de V17.8 amplían la capacidad potencial para documentos nuevos, pero en la muestra disponible solo se verificó un aumento de score histórico. **No es correcto presentar V17.8 como una mejora en documentos resueltos o en precisión medida**.

### 8.2. Identidades faltantes por fragmentación

Los documentos `790115`, `790122` y `790138` carecen de fragmentos útiles para este flujo. Deben investigarse en el **fragmentador o etapa de selección**, no mediante reglas de recuperación basadas en información ausente.

### 8.3. Recuperación provisional

El caso `790081` conserva datos estructurados útiles en revisión manual, pero sigue pendiente confirmar la naturaleza de `PIZZERIA NAPOLES` y su papel en el requerimiento. La recuperación provisional de V17.6 no debe confundirse con una aceptación válida.

### 8.4. Generalización

Antes de ampliar nuevamente la lista positiva, conviene crear un conjunto **nuevo y etiquetado** de oficios con relaciones de personas principales, terceros, operaciones con múltiples participantes y documentos internacionales. Evaluar por separado: sujetos correctamente aceptados, sujetos omitidos, terceros aceptados por error y asociaciones DNI/CUIT incorrectas.

---

## 9. Reproducción y referencias de la prueba

**Archivos de versión:**

```text
consolidacion_oficios_v17_5.py
consolidacion_oficios_v17_6_provisional.py
consolidacion_oficios_v17_7.py
consolidacion_oficios_v17_8_refuerzos.py
```

**Entrada de los 20 nuevos:**

```text
predicciones_por_documento(20261120-044012).json
```

**Informes y registros previos:**

```text
REPORTE_PRUEBAS_CONSOLIDACION_V17_5.md
INFORME_PRUEBA_CONTEXTO_POSITIVO_V17_7.md
RESULTADOS_INTEGRACION_V17_7.json
INFORME_PRUEBA_V17_8_120.md
INFORME_SEGUNDA_PRUEBA_V17_8_REFUERZOS.md
RESULTADOS_SEGUNDA_PRUEBA_E_INTEGRACION_V17_8.json
verificar_v17_8_refuerzos_120.py
```

La comparación de los 20 nuevos de este informe se recalculó directamente cargando las cuatro versiones en Python sobre el **mismo JSON de predicciones**. Las métricas ampliadas V17.7/V17.8 se contrastaron con los registros de regresión existentes.

Si se desea implementar V17.8 en el repositorio, conservar una copia de la versión previa antes de reemplazar `src/consolidacion_oficios.py` y ejecutar nuevamente la regresión sobre los JSON originales.

---

## 10. Conclusión general

**La mejora más reciente, V17.8, está orientada a generalizar el reconocimiento del lenguaje del requerimiento judicial, no a sumar puntos de forma indiscriminada.** Incorpora seis familias de relaciones entre **requerimiento, objeto e identidad**; exige comprobaciones locales; evita duplicar contexto ya reconocido; y mantiene las protecciones contra terceros e identificadores mal asociados.

En los **20 documentos nuevos**, la transición **V17.5 → V17.8** conserva **16 suficientes y 4 insuficientes**; V17.6 agregó la recuperación provisional de `790081`, V17.7 reforzó el contexto de `790085`, y V17.8 **mantuvo ambas mejoras sin modificar las decisiones**. En los **80 históricos**, V17.8 añadió un refuerzo independiente de **+1,5** a `496887` sin cambiar su identidad ni aceptación.

**Resultado demostrado:** mayor expresividad contextual y una mejora de evidencia diagnóstica controlada, **sin regresiones detectadas** en las 220 ejecuciones examinadas. **Resultado todavía pendiente:** comprobar si el vocabulario ampliado permite recuperar más sujetos correctamente en oficios futuros etiquetados.
