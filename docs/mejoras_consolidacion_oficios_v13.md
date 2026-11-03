# Evolución de la consolidación de personas objeto de oficio — V3 a V13

**Proyecto:** Pasantía universitaria SEGEM / CECONEA — agentes de IA para el análisis de oficios.  
**Corte documentado:** V13, noviembre de 2026.  
**Base de evaluación:** 80 oficios; extracción GLiNER2 por fragmentos del 01/11/2026 (carpeta `20261101_204459_multi_v1_oficios_fragmentos_thr50_todos`).

## 1. Objetivo y arquitectura

El objetivo de la consolidación es transformar las predicciones independientes de GLiNER2, producidas sobre fragmentos OCR, en **identidades consolidadas de sujetos directamente vinculados al requerimiento**. Una identidad puede ser una persona física o jurídica. La consolidación intenta evitar tres errores: omitir sujetos explícitos, asociar a una persona el identificador de otra y aceptar como sujeto a un profesional, firmante o tercero meramente mencionado.

El flujo actual es:

```text
Documento judicial / administrativo (OCR)
       ↓
Selección de fragmentos relevantes
       ↓
GLiNER2 (nombre, DNI, CUIT/CUIL y rol)
       ↓
Consolidación Python V13
  ├─ Recuperación local de campos omitidos
  ├─ Reconstrucción de apellidos y listas estructuradas
  ├─ Normalización, agrupación y verificación de identidad
  ├─ Detección y tratamiento de conflictos de identificadores
  └─ Decisión explicable: aceptado / descartado / insuficiente
       ↓
JSON con evidencias y motivos + eventual fallback
```

**Principio:** GLiNER2 propone candidatos; la consolidación no replica sin más sus decisiones. Comprueba qué nombre e identificador están vinculados por el texto, qué papel tiene el sujeto en el pedido y si hay indicios contradictorios. Puede recuperar campos mediante patrones **sobre los fragmentos literales recibidos**, pero no debe inferir datos ausentes ni inventar sujetos.

## 2. Progresión de versiones

| Versión | Mejora principal |
|---|---|
| V3 | Base de consolidación de candidatos, grupos y decisión sobre sujetos. |
| V4 | Tratamiento conservador de DNI deteriorados por OCR, condicionado a evidencia. |
| V5 | Mejor trazabilidad de evidencias, decisiones e identificadores. |
| V6 | Priorización diagnóstica del identificador que aparece en el pedido principal; inicialmente **no resolvía** conflictos automáticamente. |
| V7 | Excepción para **homónimos explícitos**: mismo nombre, DNI distintos, dos personas diferentes cuando el oficio las individualiza. |
| V8 | Recuperación del apellido que GLiNER2 omite cuando está inmediatamente antes de los nombres detectados. |
| V9 | Reasociación de nombres y DNI en listas de filas separadas. |
| V10 | Reconstrucción y cobertura de **listas numeradas**: recuperación de filas omitidas cuando son literales y verificables. |
| V11 | Reconstrucción de **listas extensas con múltiples registros por línea**; corrección de asignaciones desplazadas. |
| V12 | Recuperación local de **razones sociales y DNI**; contexto comercial/fiscal; validación reforzada; decisión controlada sobre conflictos por prioridad del pedido. |
| V13 | Reconocimiento de **codemandados** para recuperar razón social y aceptar sujetos identificados en ese contexto. |

> Esta tabla sintetiza el propósito de cada versión. Los detalles y límites operativos siguientes se contrastaron con el código de `consolidacion_oficios_v13_codemandados.py`.

## 3. Recuperación local de datos que GLiNER2 no extrajo

### 3.1. Función central: `_v12_recuperar_campos_locales()`

Esta función se ejecuta dentro de `_extraer_evidencias_documento()`, **antes de convertir los candidatos en objetos de evidencia**. Recibe una lista de candidatos GLiNER2 y el fragmento exacto que vio el modelo. Devuelve copias de los candidatos, eventualmente enriquecidas con nombre o DNI recuperados. En la V13 se amplió el patrón para incluir `codemandada` y `codemandado`.

**Caso A — Persona jurídica con CUIT, pero sin nombre.**

1. Se examinan candidatos con `nombre_persona` vacío y `cuit_cuil_persona` presente.
2. Se busca en el **mismo fragmento** una expresión compatible con razón social (por ejemplo `S.A.`, `S.R.L.` o `S.A.S.`), junto a un CUIT explícito y un contexto reconocido (`informe si`, `contribuyente`, `firma`, `empresa`, `codemandada`, `codemandado`).
3. El CUIT hallado se normaliza y se compara con el CUIT que devolvió GLiNER2. La coincidencia debe ser exacta tras eliminar separadores.
4. Se exige **una sola coincidencia** de ese CUIT en el patrón, una longitud de nombre acotada (entre 2 y 8 palabras) y estructura de nombre válida.
5. Se completa `nombre_persona`, sin inventar una confianza del modelo. El registro de auditoría lleva `origen_recuperacion_v12 = "razon_social_cuit_local"`.
6. La identidad recuperada todavía debe pasar por agrupación, análisis contextual y reglas de aceptación; **recuperar un nombre no equivale a aceptarlo automáticamente**.

Ejemplos verificados:

| Oficio | Entrada observada | Recuperación / resultado |
|---|---|---|
| **46 — 507163** | `Telefónica Móviles Argentina S.A. (TMA), C.U.I.T. 30-67881435-7`; GLiNER dio solo CUIT | Recuperación local de la razón social, asociada al CUIT. |
| **76 — 513005** | `contribuyente ALIMENTOS Y BEBIDAS DEL SUR S.A., CUIT N° 30-70984125-8`; GLiNER dio CUIT y rol | Recuperación de la razón social como sujeto de fiscalización. |
| **75 — 513004** | `por la codemandada LOGISTICA OESTE S.A., CUIT 30-71884521-9`; GLiNER dio solo CUIT | V13 añade `codemandada` al contexto admitido y recupera la sociedad. |
| **37 — 503821** | `Contribuyente NATURA COSMETICOS SA, CUIT. 30-67775729-5` | **GLiNER2 actualizado sí extrajo el nombre**. Aquí la mejora relevante fue reconocer el rol y contexto fiscal para aceptar el candidato, no recuperar por regex un nombre ausente. |

**Caso B — Nombre detectado, pero DNI omitido.**

1. Se examinan candidatos con nombre y sin DNI.
2. Se localiza literalmente el nombre en el fragmento.
3. Se inspeccionan hasta **55 caracteres inmediatamente posteriores** al nombre.
4. Se exige un rótulo `DNI` (con puntuación y separador admitidos) seguido de un número de 7 u 8 dígitos, con separadores opcionales.
5. Se copia el DNI literal y se registra `origen_recuperacion_v12 = "dni_local_adyacente"`.

**Ejemplo 49 — 507226:** `Maximiliano Arnaldo GOMEZ DNI-33.943.547`. GLiNER devolvió el nombre sin DNI; el recuperador local completó `33.943.547` al comprobar la adyacencia. Esto es distinto de ampliar el validador regex del esquema: **un validador de valores no crea el campo cuando GLiNER devuelve `null`**.

**Protecciones y límites:** no se fabrica el nombre a partir del número de CUIT; no se consulta una base externa; no se utiliza cercanía arbitraria entre varias personas; si la vinculación no es inequívoca, se conserva el candidato incompleto para auditoría. La recuperación de sociedades se limita a los sufijos y contextos implementados: no es un extractor universal de todas las figuras societarias.

### 3.2. Recuperación de apellidos omitidos

La función `_recuperar_apellido_antes_nombre()` utiliza el texto literal para reconstruir casos como:

```text
GOMEZ, FACUNDO HERNAN, DNI N° 27.845.120
        ↓ GLiNER2
FACUNDO HERNAN
        ↓ consolidación
GOMEZ, FACUNDO HERNAN
```

El proceso conserva `nombre_original_gliner` y `motivo_recuperacion_nombre = "apellido_literal_recuperado_del_fragmento"`. La recuperación no supone que cualquier palabra anterior sea un apellido: exige una estructura verificable en el fragmento. También se aplicó a **BUSTAMANTE, SERGIO ARIEL** (oficio 74) y a nombres de listas como **PEREYRA, Mario Ezequiel** (oficio 63).

## 4. Recuperación de múltiples personas en listas

GLiNER2 tiene dificultades cuando un solo fragmento concentra numerosas personas y DNI: puede omitir nombres, tomar únicamente los nombres de pila, repetir candidatos o atribuir el DNI de la fila anterior a la siguiente. Para resolverlo, se añadieron **tres mecanismos complementarios**.

### 4.1. Filas separadas: `_parejas_lista_estructurada()` (V9)

Identifica filas completas, en mayúsculas, con estructura inequívoca `NOMBRE COMPLETO DNI NÚMERO`. Para cada nombre recupera su pareja de DNI tal como figura en **esa misma fila**. Si GLiNER asoció otro DNI —que a su vez pertenece a la lista—, la consolidación puede reasociarlo y registrar la modificación. Esto es más seguro que emparejar por distancia textual libre.

**Ejemplo:** oficio **72**, lista de 14 personas con asociaciones cruzadas; la recuperación por estructura de filas permitió corregir vínculos.

### 4.2. Listas numeradas: `_filas_numeradas_verificadas()` (V10)

Admite, por ejemplo:

```text
1. BENITEZ, HUGO ORLANDO - DNI 12.345.678
2. ALMADA, GISELA PAOLA - DNI 23.456.789
3. TOLEDO, MONICA BEATRIZ - DNI 34.567.890
```

*Los números del ejemplo son ilustrativos, no datos del oficio.*

El patrón requiere apellido y nombres en mayúsculas, numeración **consecutiva**, al menos **tres filas**, sin nombres ni DNI repetidos. Solo amplía la lista si hay candidatos originales de GLiNER2 asociados al fragmento. Puede reconstruir un apellido faltante o agregar una fila que el modelo omitió, conservando `origen_recuperacion_lista = "fila_numerada_literal_verificada"`.

**Ejemplo:** oficio **73**, lista de 16 personas. Se recuperaron entradas omitidas y nombres parciales, incluyendo BENÍTEZ, ALMADA y TOLEDO.

### 4.3. Listas extensas en una misma línea: `_parejas_lista_extensa_en_linea()` (V11)

Este fue uno de los cambios más importantes. Algunos documentos OCR presentan múltiples registros concatenados:

```text
TAUZY CARLOS IGNACIO DNI 29.240.482. VILLALBA VALERIA GISELE DNI 33.040.021 GONZALEZ SANDRA NOEMI DNI 33.390.010 ...
```

La función no depende de saltos de línea. Detecta sucesivos rótulos `DNI` y exige que **todo el tramo previo a cada DNI sea exactamente un nombre completo en mayúsculas**. Su activación exige:

- Encabezado literal `PERSONAL POLICIAL A VERIFICAR:`.
- **Al menos 8** DNI en el fragmento.
- Segmentos entre DNI compatibles con nombres; sin contenido extraño intercalado.
- Nombres y DNI únicos en el conjunto reconstruido.
- **Al menos 5 nombres coincidentes** con los candidatos originales del modelo, como prueba de que el listado pertenece a la extracción analizada.

Cuando se activa, el consolidado recorre los candidatos originales. Si un nombre coincide con una fila literal, **sustituye el DNI desplazado por el de esa fila** y conserva el valor previo en `dni_original_gliner_recuperacion` con el motivo `dni_reasociado_lista_extensa`. Elimina duplicados espurios de ese nombre y crea candidatos para los nombres verificados que GLiNER omitió (`origen_recuperacion_lista = "lista_extensa_pareja_literal"`).

**Ejemplo crítico — oficio 9:**

| Concepto | Antes (V10) | Después (V11) |
|---|---:|---:|
| Personas aceptadas | 14 | **37** |
| Conflictos de identificadores | 1 | **0** |
| Suficiente | No | **Sí** |

GLiNER2 había atribuido a **GONZALEZ SANDRA NOEMI** el DNI `33.040.021`, perteneciente a **VILLALBA VALERIA GISELE**. El listado literal permitió reconstruir:

- **VILLALBA VALERIA GISELE → DNI 33.040.021**.
- **GONZALEZ SANDRA NOEMI → DNI 33.390.010**.

Se corrigió el emparejamiento y se recuperaron las entradas que el modelo había omitido, en lugar de limitarse a ignorar el conflicto. **Límite:** la implementación V11 es deliberadamente específica para el encabezado de personal policial; no debe describirse como un parser genérico de cualquier lista extensa.

## 5. Conflictos de identificadores: tres situaciones diferentes

### 5.1. Mismo nombre, distintos DNI: homónimos reales (V7)

La función `_detectar_conflictos_identificadores()` identifica nombres equivalentes con conjuntos de DNI o CUIT incompatibles. **No los fusiona**. Después consulta `_homonimos_enumerados_explicitamente()` para comprobar si ambos identificadores están ligados a entradas distintas del mismo nombre dentro de una enumeración plural explícita.

**Oficio 80 — 513009:** `Roberto Carlos ÁLVAREZ`, DNI `17.842.109` (**padre**) y DNI `40.125.684` (**hijo**). El texto distingue dos personas. No corresponde elegir un único DNI ni descartar a uno: ambos deben conservarse. También se aplicó esta lógica a los homónimos del oficio **58**.

Cuando la evidencia confirma homónimos, el conflicto queda registrado con `resolucion_conflicto = "homonimos_enumerados_explicitamente"` y `conflicto_bloqueante = false`.

### 5.2. Error de asociación entre personas de una lista (V9–V11)

Si el modelo une `nombre A` con el `DNI de B`, la solución es **corregir la pareja literal** mediante estructura de filas o secuencia inequívoca. No se debe asumir que son homónimos. El oficio **9** ejemplifica esta categoría.

### 5.3. Mismo sujeto con DNI contradictorios: prioridad documental (V6 + V12)

**Oficio 42 — 504981:** el texto atribuye al mismo `Leandro Anibal Jesús Rubin` los DNI `23.591.508` y `29.697.608` en pasajes diferentes. La V6 implementó `_prioridad_pedido_principal()` como **diagnóstico**: favorece la evidencia con nombre e identificador dentro del pedido explícito. **La V6 no descartaba ni resolvía automáticamente el conflicto.**

En la V12, después de evaluar los grupos, se aplica una resolución limitada cuando:

1. Hay conflicto por **mismo nombre y distintos identificadores**.
2. No se ha reconocido una enumeración de homónimos.
3. Un candidato tiene prioridad alta por pedido explícito con identificador local y el otro solamente evidencia complementaria.
4. Se identifica de forma unívoca el grupo secundario que corresponde descartar.

La salida acepta al candidato preferido (`23.591.508`) y retira el otro de `personas_objeto_oficio`, registrando `resolucion_conflicto = "prioridad_pedido_principal_con_alerta"`. El segundo candidato permanece visible en descartados o evidencia de auditoría.

**Advertencia esencial:** esta regla prioriza un identificador para el procesamiento, **no demuestra cuál es el DNI real**. El documento mantiene la alerta de contradicción y sigue requiriendo revisión humana. Por diseño, no se aplica a los oficios 58 y 80 porque allí hay homónimos explícitos.

## 6. Decisión sobre sujetos: más que un score

La función `_evaluar_grupo_oficio()` considera, separadamente, `tiene_identificador`, `rol_juridico_fuerte`, `contexto_juridico_positivo`, `repeticion`, `identificador_local_verificado`, `requerimiento_explicito`, además de descartar terceros fuertes, estructuras de nombre inválidas e identidades inconsistentes.

El score es útil para diagnóstico, **no sustituye** a las reglas de evidencia. Las mejoras V12–V13 añadieron:

- `_pedido_comercial_fiscal_explicito()`: reconoce nombres y CUIT vinculados a **facturación** y **fiscalización** (oficios 22 y 37).
- `_grupo_evidencia_vinculante()`: exige una solicitud o lista verificable, identificador cercano al nombre y ausencia de evidencia fuerte de tercero.
- Inclusión de `contribuyente` entre los roles considerados, sin aceptar automáticamente toda sociedad mencionada.
- Reconocimiento de `codemandada` y `codemandado` en el pedido explícito y en el patrón de razones sociales (oficio 75).
- Evitar que un rol jurídico y un contexto favorable, por sí solos, permitan resolver una persona sin DNI ni CUIT/CUIL (problema observado inicialmente en el oficio 49).

**Oficio 75 — 513004:** la V13 recupera y acepta **LOGISTICA OESTE S.A.**, CUIT `30-71884521-9`, y **GOMEZ, FACUNDO HERNAN**, DNI `27.845.120` y CUIT `20-27845120-7`. Conserva además a **PERALTA, MARCOS GABRIEL**, contraparte de las transferencias, porque la definición actual de `persona_objeto_oficio` abarca sujetos directamente mencionados en el requerimiento, no exclusivamente codemandados. Si se necesitara solo a los remitentes investigados, se requeriría un campo o filtro semántico adicional.

## 7. Auditoría y trazabilidad

La salida separa:

- `personas_objeto_oficio`: grupos aceptados, con nombre, DNI/CUIT, roles, variantes, puntuación y fragmentos soporte.
- `grupos_descartados`: candidatos con evidencia pero sin aceptación y con motivos explícitos.
- `candidatos_incompletos`: campos aislados que GLiNER2 sí produjo, como un CUIT sin razón social; no deben desaparecer silenciosamente.
- `conflictos_identificador`: diferencias entre grupos, prioridad, carácter bloqueante y resolución.
- `motivos_insuficiencia`, `requiere_revision`, `requiere_fallback_documento_completo` y `suficiente`.

Los valores de procedencia documentan **qué creó el modelo y qué recuperó Python**: `nombre_original_gliner`, `motivo_recuperacion_nombre`, `dni_original_gliner_recuperacion`, `motivo_correccion_lista_extensa`, `origen_recuperacion_lista` y `origen_recuperacion_v12`.

## 8. Resultados de las pruebas y precauciones

En el conjunto de **80 oficios**, usando la misma extracción nueva para V11, V12 y V13:

| Versión | Documentos suficientes | Identidades aceptadas | Lectura |
|---|---:|---:|---|
| V11 | **70/80 (87,5 %)** | **143** | Lista extensa del oficio 9 ya recuperada. |
| V12 | **76/80 (95 %)** | **146** | Se recuperaron los oficios 22, 37, 42, 46, 49 y 76. |
| V13 | **76/80 (95 %)** | **148** | Se añadieron dos identidades aceptadas en el oficio 75, que ya figuraba como suficiente. |

Las comparaciones de V11→V12 y V12→V13 registraron cambios de identidad únicamente en los documentos objetivo, sin regresiones observadas de aceptación en los demás oficios de ese conjunto. **Estas cifras son resultados de las pruebas locales descritas; la corrida definitiva en el repositorio debe reproducirlas.**

**No confundir suficiencia con exactitud:** `suficiente = true` solo significa que, según las reglas implementadas, hay evidencia suficiente para **no repetir la extracción sobre texto completo**. No equivale a 95 % de precisión, recall ni exactitud contra etiquetas gold. La validación final requiere evaluación humana o un conjunto de referencia, sobre todo para falsos positivos y sujetos omitidos en oficios ya suficientes.

Persisten **4 documentos insuficientes: 45, 52, 78 y 79**. En los oficios 45, 78 y 79 la identidad solicitada no está individualizada en el texto. El oficio 52 contiene datos útiles en el texto completo, pero no llegaron mediante los fragmentos utilizados; es candidato para un fallback dirigido y auditado.

## 9. Recomendaciones para el siguiente ciclo

1. **Congelar V13 y el input de GLiNER2** para disponer de una base comparativa reproducible.
2. Incorporar pruebas unitarias sobre 9, 22, 37, 42, 46, 49, 58, 72, 73, 74, 75, 76 y 80, con verificaciones tanto de personas correctas como de personas que **no** deben aceptarse.
3. Medir precisión, recall y calidad de emparejamiento **nombre ↔ identificador** con una muestra gold independiente.
4. Implementar fallback dirigido para documentos sin fragmentos relevantes, distinguiendo `sin_identidad_en_documento` de `extraccion_fallida`.
5. Evaluar con coordinación funcional si corresponde distinguir `sujeto_principal`, `codemandado`, `contribuyente`, `contraparte_de_transaccion` y `destinatario_del_oficio`; esto resolvería ambigüedades como los oficios 75 y 80 sin perder evidencia.

---

**Archivos de referencia:** `consolidacion_oficios_v10_listas_numeradas.py`, `consolidacion_oficios_v11_listas_extensas.py`, `consolidacion_oficios_v12_recuperacion_local.py`, `consolidacion_oficios_v13_codemandados.py`, los JSON de extracción y consolidación de las corridas indicadas y la comparación V11–V12.
