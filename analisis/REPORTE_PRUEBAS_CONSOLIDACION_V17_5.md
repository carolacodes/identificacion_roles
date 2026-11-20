# Consolidación de oficios — Pruebas de V17.1 a V17.5

**Fecha:** 20/11/2026  
**Base:** `consolidacion_oficios(5).py` (V16)  
**Versión final evaluada:** V17.5  
**Alcance:** decisiones basadas exclusivamente en fragmentos; `texto_completo` conservado como metadato.

---

## 1. Objetivo de las mejoras

El objetivo de las versiones V17.1 a V17.5 fue corregir problemas detectados durante la evaluación de 20 nuevos oficios judiciales, sin perjudicar los resultados de documentos que la consolidación V16 ya resolvía correctamente.

Los principales problemas identificados fueron:

- Nombres incompletos que podían reconstruirse desde el fragmento.
- Solicitudes de información que no eran reconocidas por los patrones contextuales existentes.
- Predicciones duplicadas que aumentaban artificialmente las puntuaciones.
- Roles jurídicos incorrectos predichos por GLiNER2.
- Dificultades para diferenciar sujetos consultados de terceros administrativos.
- Razones sociales que no podían recuperarse aunque estuvieran asociadas a un CUIT.
- Limitaciones de las reglas contextuales para documentos con distintas estructuras.

### Principios de implementación

1. Utilizar exclusivamente los fragmentos disponibles.
2. No inventar nombres ni identificadores.
3. No modificar un nombre válido por tener solamente dos palabras.
4. Asociar nombres e identificadores mediante evidencia local verificable.
5. No aceptar automáticamente personas mencionadas como firmantes, abogados o terceros.
6. Conservar las predicciones originales de GLiNER2 para auditoría.
7. Mantener compatibilidad con las corridas históricas.
8. Priorizar reglas generales frente a soluciones específicas para determinados documentos.

**Importante:** una persona puede tener un nombre y un apellido. La cantidad de palabras no debe utilizarse como criterio para exigir que tenga dos nombres propios.

Por ejemplo, `ROMERO HECTOR`, `ANDRADE NORA` y `JUAN PEREZ` son estructuras nominales válidas.

---

## 2. Comparación acumulativa de versiones

| Versión      | Nueva corrida (suficientes / 20) | Cambios en las cuatro corridas anteriores (200 ejecuciones) | Mejoras                                                                                                                           |
| ------------ | -------------------------------: | ----------------------------------------------------------: | --------------------------------------------------------------------------------------------------------------------------------- |
| V16 original |                               11 |                                                           — | Referencia inicial                                                                                                                |
| V17.1        |                               12 |                                                           0 | Recuperación de apellidos con CUIT/CUIL además de DNI. Recupera Soria, pero todavía no Ungar.                                     |
| V17.2        |                               15 |                                                           0 | Reconocimiento de relaciones locales entre persona y requerimiento. Recupera Ungar, Arcadio y Nancy.                              |
| V17.3        |                               15 |                                                           0 | Una evidencia independiente por fragmento e identidad, manteniendo las predicciones originales para auditoría.                    |
| V17.4        |                               15 |                                                           0 | Auditoría del rol textual frente al rol predicho por GLiNER. Detecta la contradicción de Romero.                                  |
| V17.5        |                               16 |                                                           0 | Recuperación contextual de razón social y CUIT. Recupera Caledonia y agrega una comprobación genérica de pedidos internacionales. |

**Detalle de regresiones:**

Las cuatro corridas anteriores corresponden a:

- Corrida histórica de 80 documentos.
- Segunda corrida histórica de 80 documentos.
- Corrida anterior de 20 documentos.
- Corrida internacional de 20 documentos.

En total se compararon 200 ejecuciones por documento.

La comparación comprobó igualdad para:

- Estado de consolidación.
- Suficiencia.
- `requiere_revision`.
- Identidades aceptadas.
- Grupos descartados y sus motivos.

**Estas 200 ejecuciones no representan necesariamente 200 documentos diferentes ni constituyen un conjunto gold de exactitud.**

---

## 3. Resultados generales: V16 frente a V17.5

| Métrica                                                  |  V16 | V17.5 |              Diferencia |
| -------------------------------------------------------- | ---: | ----: | ----------------------: |
| Total de documentos                                      |   20 |    20 |                       0 |
| Documentos suficientes                                   |   11 |    16 |                      +5 |
| Documentos insuficientes                                 |    9 |     4 |                      -5 |
| Porcentaje de suficiencia                                | 55 % |  80 % | +25 puntos porcentuales |
| Documentos con una identidad aceptada                    |   11 |    16 |                      +5 |
| Documentos resueltos con múltiples personas              |    0 |     0 |                       0 |
| Regresiones detectadas en las cuatro corridas anteriores |    — |     0 |  Sin cambios detectados |

**Interpretación:**

La V17.5 aumentó la suficiencia de los 20 documentos nuevos del 55 % al 80 %.

Este aumento se debe a que cinco documentos que anteriormente eran descartados pudieron resolverse mediante mejoras generales de recuperación e interpretación contextual.

No obstante, `suficiente=true` no garantiza exactitud frente a etiquetas gold. Significa que la consolidación considera que existe evidencia suficiente para no solicitar una extracción adicional.

---

## 4. Tabla completa: comportamiento V16 frente a V17.5

Esta tabla compara el comportamiento anterior y posterior de la consolidación para cada uno de los 20 documentos evaluados.

La columna **V16** describe el resultado observado con la versión original.

La columna **V17.5** describe el comportamiento obtenido después de implementar las cinco etapas de mejora.

La columna **Mejora / diagnóstico** explica qué se corrigió, qué se conservó y qué continúa pendiente.

| Doc. (ID)         | Comportamiento anterior — V16                                                                                                                                                            | Comportamiento actual — V17.5                                                                                                                                                                                                                                                                                              | Mejora implementada / diagnóstico                                                                                                                                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1** (`788347`)  | **NO_RESUELTO**. GLiNER extrajo únicamente el CUIT `3050003967-8`. La consolidación no recuperó la razón social.                                                                         | **RESUELTO / suficiente**. Recupera `Caledonia Argentina Compañía de Seguros SA` y el CUIT `3050003967-8`.                                                                                                                                                                                                                 | **Recuperación de personas jurídicas.** Reconoce una razón social vinculada localmente con su CUIT y el requerimiento. No acepta cualquier CUIT aislado.                                                                                                   |
| **2** (`789454`)  | **NO_RESUELTO**. Descarta `NORBERTO HORACIO` por `nombre_parcial_en_lista`. El apellido `UNGAR` estaba disponible en el fragmento.                                                       | **RESUELTO / suficiente**. Reconstruye `UNGAR, NORBERTO HORACIO`, CUIT `20-10041809-7`. Mantiene descartada a la firmante María Virginia Raffo.                                                                                                                                                                            | **Reconstrucción segura de nombres.** Recupera el apellido omitido mediante el CUIT y conserva el filtrado de terceros.                                                                                                                                    |
| **3** (`790063`)  | **RESUELTO**. Unifica dos apariciones de `Marta Elisa PUGLIESE`, DNI `4756818`, CUIL `27-04756818-3` y rol `causante`.                                                                   | **RESUELTO**. Conserva la misma identidad y la evidencia de dos fragmentos distintos.                                                                                                                                                                                                                                      | **Sin regresiones.** Mantiene la agrupación correcta de identidades repetidas en fragmentos diferentes.                                                                                                                                                    |
| **4** (`790072`)  | **RESUELTO**. Acepta `GONZALEZ DAVID AVELINO` y descarta terceros. Sin embargo, contabiliza cuatro predicciones idénticas del mismo fragmento como cuatro evidencias, con score `46.31`. | **RESUELTO**. Mantiene a González como única persona aceptada. Conserva cuatro predicciones originales, pero identifica una sola evidencia independiente y corrige su peso en el score.                                                                                                                                    | **Deduplicación de evidencias.** Evita que varias predicciones del mismo fragmento aumenten artificialmente el score sin perder trazabilidad.                                                                                                              |
| **5** (`790081`)  | **NO_RESUELTO**. GLiNER extrae únicamente `PIZZERIA`, que es descartado por `nombre_no_valido`.                                                                                          | **NO_RESUELTO**. NO_RESUELTO / insuficiente / revisión manual. Recupera PIZZERIA NAPOLES, CUIT 20288024554, mediante los campos estructurados del fragmento. Guarda la identidad en identidades_recuperadas_revision_manual, con tipo_identidad="NO_DETERMINADO" y estado_validacion_identidad="REQUIERE_REVISION_MANUAL". | Recuperación de identidades estructuradas (V17.6). Reconoce y asocia Nombre, Apellido y CUIT aunque GLiNER no haya extraído todos los campos. Conserva la información útil para revisión, sin aceptar automáticamente la identidad como sujeto del oficio. |
| **6** (`790085`)  | **NO_RESUELTO**. Descarta `MARÍA FERNANDA`, CUIT `27-34953534-9`, por `nombre_parcial_en_lista`.                                                                                         | **RESUELTO / suficiente**. Reconstruye `SORIA, MARÍA FERNANDA` y conserva su CUIT.                                                                                                                                                                                                                                         | **Reconstrucción de apellido.** Reconoce la identidad completa en la expresión `cuentas pertenecientes a SORIA, MARÍA FERNANDA`.                                                                                                                           |
| **7** (`790089`)  | **RESUELTO**. Acepta `Martin Ignacio Galvan`, DNI `39054617`.                                                                                                                            | **RESUELTO**. Conserva la misma identidad.                                                                                                                                                                                                                                                                                 | **Sin regresiones.** Mantiene la aceptación de solicitudes explícitas sin exigir rol jurídico.                                                                                                                                                             |
| **8** (`790091`)  | **RESUELTO**. Acepta `Horacio Guillermo PÉREZ`, DNI `22.513.908`, rol `demandado`.                                                                                                       | **RESUELTO**. Mantiene identidad, DNI y rol.                                                                                                                                                                                                                                                                               | **Sin regresiones.** Conserva el reconocimiento de sujetos procesales identificados.                                                                                                                                                                       |
| **9** (`790092`)  | **RESUELTO**. Acepta `Franco Eduardo Cárdenas`, DNI `32.851.047` y CUIL `20-32851047-3`.                                                                                                 | **RESUELTO**. Mantiene la misma identidad y ambos identificadores.                                                                                                                                                                                                                                                         | **Sin regresiones.** Conserva la asociación entre DNI y CUIT/CUIL.                                                                                                                                                                                         |
| **10** (`790094`) | **NO_RESUELTO**. Descarta `Arcadio Samuel Hamil García`, DNI `37433769`, por `senales_insuficientes`, `sin_rol_juridico_fuerte`, `sin_contexto_juridico` y `sin_repeticion`.             | **RESUELTO / suficiente**. Acepta a Arcadio mediante la relación entre operaciones bancarias solicitadas, nombre, DNI y contexto financiero.                                                                                                                                                                               | **Ampliación del contexto positivo.** Reconoce solicitudes financieras sin depender de un rol procesal ni de la repetición del sujeto.                                                                                                                     |
| **11** (`790097`) | **RESUELTO**. Acepta `Romero Hector`, DNI `34.472.193`, pero conserva el rol incorrecto `actor` predicho por GLiNER.                                                                     | **RESUELTO**. Mantiene la identidad y registra la contradicción entre el rol `actor` de GLiNER y `accionado` en el fragmento.                                                                                                                                                                                              | **Auditoría de roles.** Detecta contradicciones sin sobrescribir la predicción original. Se conserva la validez del nombre de dos palabras.                                                                                                                |
| **12** (`790102`) | **RESUELTO**. Acepta `ENDARA MARIANO ADRIÁN`, DNI `38.804.970`, CUIL `20-38804970-8`.                                                                                                    | **RESUELTO**. Mantiene identidad e identificadores.                                                                                                                                                                                                                                                                        | **Sin regresiones.** Preserva la asociación de los identificadores.                                                                                                                                                                                        |
| **13** (`790106`) | **NO_RESUELTO**. Descarta `NANCY SILVANA GRACIANO`, DNI `27017871`, CUIT `27-27017871-0`, por señales insuficientes. Descarta también `nombrada` como identidad.                         | **RESUELTO / suficiente**. Acepta a Nancy mediante `respecto de la señora ... lo siguiente:`. Continúa descartando `nombrada` como identidad independiente.                                                                                                                                                                | **Mejora de contexto positivo.** Reconoce introducciones de requerimientos y mantiene el rechazo de referencias genéricas como nombres propios.                                                                                                            |
| **14** (`790111`) | **RESUELTO**. Acepta `Susana Esther Gigerey`, DNI `44.379.117`.                                                                                                                          | **RESUELTO**. Mantiene la misma identidad.                                                                                                                                                                                                                                                                                 | **Sin regresiones.** Conserva el reconocimiento del sujeto consultado.                                                                                                                                                                                     |
| **15** (`790114`) | **RESUELTO**. Acepta `ARIAS MARIA BELEN`, DNI `37.128.726`, rol `demandada`.                                                                                                             | **RESUELTO**. Conserva la identidad y el rol.                                                                                                                                                                                                                                                                              | **Sin regresiones.** Mantiene el filtrado de fragmentos administrativos sin identidades.                                                                                                                                                                   |
| **16** (`790115`) | **NO_RESUELTO**. GLiNER no recibió fragmentos útiles.                                                                                                                                    | **NO_RESUELTO**. Continúa indicando ausencia de fragmentos y necesidad de revisión.                                                                                                                                                                                                                                        | **Pendiente del fragmentador.** No es posible recuperar una identidad desde fragmentos inexistentes.                                                                                                                                                       |
| **17** (`790122`) | **NO_RESUELTO**. No existen fragmentos útiles, aunque el texto completo menciona a Mariano Fabián Ferro.                                                                                 | **NO_RESUELTO**. Mantiene el diagnóstico de fragmentación insuficiente.                                                                                                                                                                                                                                                    | **Pendiente del fragmentador.** La consolidación no consulta `texto_completo`.                                                                                                                                                                             |
| **18** (`790129`) | **RESUELTO**. Reconstruye `LOPEZ, JOSE LEONARDO`, DNI `30500719`, a partir de una extracción parcial de GLiNER.                                                                          | **RESUELTO**. Conserva la recuperación del apellido con la lógica ampliada.                                                                                                                                                                                                                                                | **Regresión positiva preservada.** La mejora mantiene un caso que V16 ya resolvía correctamente.                                                                                                                                                           |
| **19** (`790136`) | **RESUELTO**. Acepta `ANDRADE NORA`, DNI `18223729`. GLiNER no recuperó a Kevin Ezequiel Slavin.                                                                                         | **RESUELTO**. Mantiene a Andrade como sujeto aceptado, sin agregar automáticamente al titular de la cuenta de destino.                                                                                                                                                                                                     | **Sin regresiones.** Evita incorporar terceros financieros sin evidencia suficiente. `ANDRADE NORA` continúa siendo un nombre válido.                                                                                                                      |
| **20** (`790138`) | **NO_RESUELTO**. No hay fragmentos para identificar a Juan José Cesario.                                                                                                                 | **NO_RESUELTO**. Mantiene la necesidad de revisión.                                                                                                                                                                                                                                                                        | **Pendiente del fragmentador.** No utiliza el texto completo para generar identidades.                                                                                                                                                                     |

---

## 5. Documentos recuperados respecto de V16

De los 20 documentos nuevos, cinco cambiaron de `NO_RESUELTO` a `RESUELTO`.

| Doc. | ID       | V16         | V17.5                 | Resultado recuperado                                            |
| ---- | -------- | ----------- | --------------------- | --------------------------------------------------------------- |
| 1    | `788347` | NO_RESUELTO | RESUELTO / suficiente | Caledonia Argentina Compañía de Seguros SA, CUIT `3050003967-8` |
| 2    | `789454` | NO_RESUELTO | RESUELTO / suficiente | UNGAR, NORBERTO HORACIO, CUIT `20-10041809-7`                   |
| 6    | `790085` | NO_RESUELTO | RESUELTO / suficiente | SORIA, MARÍA FERNANDA, CUIT `27-34953534-9`                     |
| 10   | `790094` | NO_RESUELTO | RESUELTO / suficiente | Arcadio Samuel Hamil García, DNI `37433769`                     |
| 13   | `790106` | NO_RESUELTO | RESUELTO / suficiente | NANCY SILVANA GRACIANO, DNI `27017871`, CUIT `27-27017871-0`    |

### Resultados conservados

Los 11 documentos que V16 ya consideraba suficientes continúan aceptados en V17.5 con las mismas identidades.

En algunos casos se modificaron campos de auditoría o el cálculo de evidencias, pero no la decisión final de aceptación.

### Documentos pendientes

| Doc. | ID       | Motivo principal                                   | Etapa a mejorar                    |
| ---- | -------- | -------------------------------------------------- | ---------------------------------- |
| 5    | `790081` | Identidad estructurada no recuperada completamente | Recuperación de campos etiquetados |
| 16   | `790115` | Ausencia de fragmentos útiles                      | Fragmentación                      |
| 17   | `790122` | Ausencia de fragmentos útiles                      | Fragmentación                      |
| 20   | `790138` | Ausencia de fragmentos útiles                      | Fragmentación                      |

Los documentos 16, 17 y 20 requieren trabajar sobre la generación de fragmentos, no sobre la aceptación de personas dentro de la consolidación.

---

## 6. Comparación técnica de las mejoras implementadas

| Mejora                                  | Comportamiento V16                                                                                 | Comportamiento V17.5                                                                                | Beneficio                                                                   |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Reconstrucción de nombres parciales** | Recuperación limitada principalmente a apellido seguido de nombre y DNI.                           | Recupera apellidos omitidos mediante DNI y CUIT/CUIL, con asociación textual verificable.           | Reduce falsos descartes.                                                    |
| **Validación de nombres**               | Exige estructura plausible de persona física o jurídica.                                           | Conserva la validación de dos componentes; no exige dos nombres propios.                            | Evita rechazar nombres válidos de dos palabras.                             |
| **Contexto del requerimiento**          | Algunas solicitudes sin rol jurídico reconocido eran descartadas.                                  | Reconoce relaciones adicionales entre operaciones, cuentas, movimientos, identidad e identificador. | Mejora la aceptación de sujetos consultados.                                |
| **Deduplicación de evidencias**         | Puede sumar varias predicciones idénticas del mismo fragmento.                                     | Diferencia predicciones originales de evidencias independientes.                                    | Evita inflar el score.                                                      |
| **Validación de roles**                 | Conserva roles incorrectos sin detectar contradicciones.                                           | Contrasta roles de GLiNER con expresiones del fragmento y registra inconsistencias.                 | Mejora trazabilidad semántica.                                              |
| **Terceros administrativos**            | Puede descartar terceros por falta de señales positivas sin identificar explícitamente su función. | Mejora la evaluación contextual de autorizaciones y terceros.                                       | Reduce el riesgo de aceptar personas ajenas al pedido.                      |
| **Personas jurídicas**                  | Algunas razones sociales no se recuperaban cuando GLiNER extraía únicamente CUIT.                  | Recupera determinadas razones sociales vinculadas localmente con CUIT.                              | Amplía la cobertura de entidades jurídicas.                                 |
| **Contexto internacional**              | Reglas específicas para Chile y Uruguay.                                                           | Conserva las reglas originales y agrega comprobación genérica de pedidos como complemento.          | Amplía parcialmente la cobertura sin reemplazar los validadores existentes. |
| **Regresiones**                         | Versión de referencia.                                                                             | Sin cambios de decisiones detectados en las cuatro corridas anteriores.                             | Conserva compatibilidad con casos conocidos.                                |

---

## 7. Descripción de cada versión

### 7.1. V17.1 — Reconstrucción segura de nombres

**Problema detectado:**

GLiNER podía identificar solamente los nombres propios y omitir el apellido que aparecía inmediatamente antes, separado por una coma.

Ejemplo:

```text
SORIA, MARÍA FERNANDA (CUIT N.° 27-34953534-9)
```

GLiNER:

```json
{
  "nombre_persona": "MARÍA FERNANDA",
  "cuit_cuil_persona": "27-34953534-9"
}
```

V16 descartaba el candidato por:

```text
nombre_parcial_en_lista
```

**Mejora implementada:**

Se amplió la recuperación de apellidos para contemplar identificadores CUIT/CUIL además de DNI.

La recuperación se realiza cuando existe evidencia explícita de que una parte del nombre quedó omitida.

**Restricción importante:**

No se considera incompleto un nombre solamente porque contenga dos palabras.

La reconstrucción debe basarse en la estructura literal del fragmento.

**Resultado:** 12/20 documentos suficientes.

### 7.2. V17.2 — Reconocimiento contextual del requerimiento

**Problema detectado:**

V16 rechazaba personas correctamente identificadas cuando el fragmento no contenía determinadas palabras jurídicas, aunque existiera una solicitud financiera claramente vinculada con ellas.

Ejemplo:

```text
operaciones bancarias realizadas ... por el ciudadano
Arcadio Samuel Hamil García con DNI N° 37433769
```

**Mejora implementada:**

Se amplió el reconocimiento de relaciones entre:

- Solicitudes de información.
- Operaciones financieras.
- Personas mencionadas.
- Identificadores.
- Cuentas, movimientos y productos financieros.

También se incorporó el reconocimiento de construcciones como:

```text
respecto de la señora NANCY SILVANA GRACIANO,
DNI 27017871, CUIT 27-27017871-0, lo siguiente:
```

**Resultado:** 15/20 documentos suficientes.

### 7.3. V17.3 — Deduplicación de evidencias

**Problema detectado:**

GLiNER podía devolver varias predicciones equivalentes desde el mismo fragmento.

En el documento 4 se habían contabilizado cuatro evidencias para González David Avelino, aunque todas procedían de un único fragmento.

**Mejora implementada:**

Se separaron dos conceptos:

- `cantidad_evidencias`: cantidad de predicciones originales conservadas.
- `cantidad_evidencias_independientes`: cantidad de evidencias distintas consideradas para el cálculo.

Para el documento 4:

```json
{
  "cantidad_evidencias": 4,
  "cantidad_evidencias_independientes": 1
}
```

Se corrigió el cálculo del score para evitar que predicciones repetidas tengan un peso artificialmente elevado.

**Resultado:** 15/20 documentos suficientes, con cambios en la auditoría y puntuación, sin cambios adicionales de suficiencia.

### 7.4. V17.4 — Auditoría de roles

**Problema detectado:**

GLiNER podía asociar un rol jurídico incorrecto a una persona.

En el documento 11:

```text
el accionado, Sr. Romero Hector, DNI N° 34.472.193
```

GLiNER devolvió:

```json
{
  "nombre_persona": "Romero Hector",
  "rol_persona": "actor"
}
```

**Mejora implementada:**

Se incorporó una comparación entre los roles predichos por GLiNER y los roles respaldados por el fragmento.

El resultado conserva la predicción original y agrega campos de auditoría.

```json
{
  "roles_detectados": ["actor"],
  "roles_validados_fragmento": ["demandado"],
  "contradiccion_rol_gliner": true
}
```

No se sobrescribe automáticamente el rol original.

**Resultado:** 15/20 documentos suficientes, con mejora de trazabilidad.

### 7.5. V17.5 — Personas jurídicas y complemento internacional

**Problema detectado:**

GLiNER podía extraer el CUIT de una empresa sin identificar su razón social.

Ejemplo:

```text
Caledonia Argentina Compañía de Seguros SA
(CUIT: 3050003967-8)
```

GLiNER devolvió únicamente:

```json
{
  "nombre_persona": null,
  "cuit_cuil_persona": "3050003967-8"
}
```

**Mejora implementada:**

Se amplió la recuperación contextual de razones sociales asociadas localmente a un CUIT.

La recuperación no se basa únicamente en la presencia del identificador: también debe existir evidencia de asociación con la entidad y el requerimiento.

Se agregó además una comprobación genérica de pedidos como complemento de la lógica internacional existente.

**Resultado:** 16/20 documentos suficientes.

---

## 8. Pruebas especiales y verificación de regresiones

### 8.1. Nombres de dos palabras

Se verificó que los siguientes nombres continúan siendo válidos:

```text
JUAN PEREZ
ROMERO HECTOR
ANDRADE NORA
```

La consolidación no exige que una persona tenga dos nombres propios.

### 8.2. Recuperación histórica conservada

El documento 18 conserva la recuperación:

```text
LOPEZ, JOSE LEONARDO
```

La mejora de V17.1 no perjudica este comportamiento.

### 8.3. Evidencias duplicadas

En el documento 4 se verificó:

```text
cantidad_evidencias = 4
cantidad_evidencias_independientes = 1
```

La identidad aceptada permanece igual y las predicciones originales siguen disponibles para auditoría.

### 8.4. Contradicción de rol

En el documento 11 se verificó:

```json
{
  "roles_detectados": ["actor"],
  "roles_validados_fragmento": ["demandado"],
  "contradiccion_rol_gliner": true
}
```

La consolidación acepta a la persona correcta y registra la inconsistencia.

### 8.5. Independencia de texto_completo

Se sustituyó `texto_completo` por texto arbitrario en los 20 documentos nuevos.

Las siguientes salidas permanecieron idénticas:

- Estados.
- Decisiones de aceptación.
- Personas aceptadas.
- Grupos descartados.

Esto verifica que las decisiones evaluadas se construyen exclusivamente a partir de los fragmentos disponibles.

### 8.6. Comparación con corridas anteriores

Se compararon las decisiones de V17.5 con la V16 en las cuatro corridas anteriores.

**Resultado:** cero diferencias detectadas en las decisiones comparadas de los 200 casos.

Archivo de pruebas:

```text
test_v17_5_regresion.py
```

Las pruebas se ejecutaron con los cinco archivos JSON de GLiNER y el baseline de referencia.

---

## 9. Limitaciones y pasos pendientes

### 9.1. Reglas internacionales

Las reglas específicas de Chile y Uruguay de V16 permanecen por compatibilidad.

Entre ellas:

- `_int_contexto_chile_fragmento()`
- `_int_pedidos_uruguay()`
- Validadores de RUT/RUN.
- Validadores de CI uruguaya.
- Activadores por país.

V17.5 incorpora una comprobación genérica de pedido como complemento, pero **todavía no reemplaza toda la lógica específica**.

No existe suficiente evidencia internacional nueva para garantizar generalización a otros países o formulaciones desconocidas.

### 9.2. Interpretación contextual

La consolidación continúa utilizando patrones explícitos y ventanas de contexto limitadas.

Por lo tanto, no garantiza la resolución de todos los documentos futuros.

Los cinco documentos recuperados deben considerarse mejoras observadas en esta prueba, no una medida definitiva de precisión.

### 9.3. Validación contra gold

Los resultados de suficiencia deben contrastarse con etiquetas gold para calcular métricas como:

- Precisión.
- Recall.
- F1.
- Falsos positivos.
- Falsos negativos.
- Exactitud de asociación entre nombre e identificador.

### 9.4. Fragmentación

Los documentos 16, 17 y 20 no contaban con fragmentos útiles.

La consolidación no puede resolver correctamente esos documentos con la información de entrada disponible.

Será necesario mejorar posteriormente la estrategia de fragmentación.

### 9.5. Recuperación de campos estructurados

El documento 5 (`790081`) contiene:

```text
Nombre: PIZZERIA
Apellido: NAPOLES
Tipo de Documento: CUIT
Número de documento: 20288024554
```

V17.5 todavía no recupera estos campos como una identidad estructurada.

**Mejora posterior prevista:** recuperar la denominación y el identificador, pero mantener revisión manual cuando no exista evidencia suficiente para confirmar que se trata del sujeto del requerimiento.

Esta funcionalidad corresponde a V17.6 provisional y no se contabiliza como resultado de V17.5.

### 9.6. Pruebas fuera de las corridas disponibles

Aunque no se detectaron regresiones en las corridas evaluadas, una mejora podría modificar resultados de documentos diferentes.

Por eso se recomienda:

1. Conservar una copia de V16.
2. Ejecutar pruebas de regresión con cada cambio.
3. Comparar las salidas completas.
4. Revisar manualmente nuevas identidades aceptadas.
5. Ejecutar una prueba sombra antes de producción.

### 9.7. Fallback

El campo:

```text
requiere_fallback_documento_completo
```

es una marca heredada de la salida.

**V17.5 no ejecuta automáticamente una extracción desde `texto_completo`.**

---

## 10. Instalación

Guardar una copia del archivo original V16:

```text
src/consolidacion_oficios.py
```

Reemplazarlo por:

```text
consolidacion_oficios_v17_5.py
```

manteniendo el nombre esperado dentro del repositorio:

```text
src/consolidacion_oficios.py
```

El punto de entrada `consolidar_documentos` y el ejecutor habitual se conservan.

### Activar el entorno virtual

Desde PowerShell:

```powershell
& "C:\venvs\identroles\Scripts\Activate.ps1"
```

### Ejecutar la consolidación sobre los 20 documentos nuevos

Desde la raíz del proyecto `identificacion_roles`:

```powershell
python -m src.run_consolidacion_oficios --input "outputs/por_documento/20261120_013152_multi_v1_oficios_fragmentos_thr50_20_casos/predicciones_por_documento.json" --name consolidacion_20_casos_v17_5
```

### Resultado esperado

```text
Total documentos: 20

RESUELTO: 16
RESUELTO_MULTIPLE: 0
NO_RESUELTO: 4

SUFICIENTES: 16
INSUFICIENTES: 4
```

---

## 11. Conclusión general

La consolidación V17.5 mejoró los resultados de la corrida de 20 documentos nuevos, pasando de **11 documentos suficientes (55 %) a 16 documentos suficientes (80 %)**.

Esto representa:

- Cinco documentos adicionales resueltos.
- Una mejora de 25 puntos porcentuales en suficiencia.
- Recuperación de apellidos omitidos por GLiNER2.
- Reconocimiento de nuevas estructuras de solicitudes.
- Reducción del efecto de predicciones duplicadas.
- Mayor trazabilidad de contradicciones de roles.
- Recuperación de personas jurídicas vinculadas a CUIT.
- Conservación de las decisiones de las cuatro corridas anteriores utilizadas para regresión.

Las mejoras no se diseñaron exclusivamente para estos 20 documentos, sino para ampliar las capacidades generales de la consolidación.

**El objetivo principal es recuperar la mayor cantidad posible de información correctamente asociada, sin aceptar automáticamente identidades que carezcan de evidencia suficiente.**

Los casos que no pueden confirmarse deben conservarse para revisión manual cuando exista información útil, manteniendo una separación clara entre:

1. Identidades aceptadas como objeto del oficio.
2. Identidades recuperadas con evidencia insuficiente.
3. Candidatos descartados por corresponder a terceros o referencias inválidas.
4. Documentos sin información de entrada suficiente.

Esta separación permite mejorar la utilidad operativa del sistema sin comprometer la trazabilidad ni la confiabilidad de sus decisiones.

**Estado final:** V17.5 implementada y evaluada con cinco corridas conocidas. La recuperación estructurada provisional corresponde a la etapa posterior V17.6.

### Recuperación de información sin evidencia suficiente — V17.6

La consolidación incorpora un mecanismo para recuperar identidades desde campos estructurados, incluso cuando GLiNER2 no extrae todos sus componentes.

En el documento `790081`, GLiNER2 detectó únicamente `PIZZERIA`. Sin embargo, el fragmento contenía los campos `Nombre: PIZZERIA`, `Apellido: NAPOLES` y `Tipo de Documento: CUIT - Número de documento: 20288024554`.

La V17.6 recuperó:

- **Nombre:** `PIZZERIA NAPOLES`
- **CUIT:** `20288024554`
- **Tipo de identidad:** `NO_DETERMINADO`
- **Estado de validación:** `REQUIERE_REVISION_MANUAL`

La información se almacena en `identidades_recuperadas_revision_manual`, sin incorporarla a `personas_objeto_oficio`.

El documento mantiene `estado="NO_RESUELTO"`, `suficiente=false` y `requiere_revision=true`.

**Esta mejora no aumenta la cantidad de documentos suficientes, pero sí mejora la recuperación y disponibilidad de información para la revisión humana.**

La estrategia consiste en separar dos decisiones: **recuperar información verificable en los fragmentos** y **determinar si existe evidencia suficiente para aceptar esa identidad como objeto del oficio**.

De esta manera, la falta de evidencia para una aceptación automática no provoca la pérdida de información potencialmente útil.
