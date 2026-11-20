# Evaluación GLiNER2 + Consolidación V16 — 20 casos nuevos

**Proyecto:** Identificación de personas objeto de oficios — Pasantía UNNE / SEGEM / CECONEA  
**Fecha del análisis:** 20/11/2026  
**Estado:** diagnóstico de referencia; **no se implementaron cambios en la consolidación**.  
**Objetivo:** establecer una línea base verificable antes de implementar mejoras generales, sin ajustar reglas a los nombres o redacciones particulares de esta muestra.

## 1. Fuentes y configuración

- **Extracción:** `outputs/por_documento/20261120_013152_multi_v1_oficios_fragmentos_thr50_20_casos/predicciones_por_documento.json` (copia analizada: `predicciones_por_documento(20261120-044012).json`).
- **Consolidación:** `consolidacion(20261120-045242).json`.
- **Resumen:** `resumen(20261120-045243).json`.
- **Subconjuntos:** `suficientes(20261120-045243).json` e `insuficientes(20261120-045243).json`.
- **Experimento:** `multi_v1_oficios_fragmentos_thr50_20_casos`; modelo `gliner2_multi`, esquema `schema_v1_persona_objeto_oficio_fragmentos`, modo `fragmentos`, umbral general 0,50; campos: nombre 0,50, DNI 0,30, CUIT/CUIL 0,30 y rol 0,50.

**Política de alcance:** las propuestas de recuperación y todas las decisiones de consolidación deben utilizar **solo `fragmento` / `texto_entrada_modelo` y predicciones asociadas**, nunca `texto_completo`. Este último se consultó **exclusivamente para evaluación manual** y para describir la falta de cobertura de fragmentación, no como insumo de la solución.

> **Definición de “persona objeto del oficio”:** individuo o entidad cuya identidad, cuenta u operaciones son directamente materia de la solicitud dirigida al destinatario del oficio. No equivale necesariamente a “demandado”: puede ser causante, actor/a, imputado/a, titular u otra persona. Los terceros mencionados y autorizados para diligenciar no se aceptan solo por aparecer en el documento.

## 2. Resumen cuantitativo de la ejecución

| Métrica | Resultado registrado |
|---|---:|
| Documentos | 20 |
| Documentos RESUELTO | 11 |
| Documentos RESUELTO_MULTIPLE | 0 |
| Documentos NO_RESUELTO | 9 |
| Documentos SUFICIENTES | 11 (55 %) |
| Documentos INSUFICIENTES | 9 (45 %) |
| Personas aceptadas en el conjunto | 11 |
| Documentos para revisión | 9 |
| Conflictos de identificador detectados | 0 |
| Documentos sin fragmentos de entrada útiles | 3: 16, 17, 20 |

**Interpretación importante:** `suficiente=true` es la decisión **del programa**, no una prueba de precisión contra etiquetas *gold*. El conteo de 11 resueltos no implica que los otros nueve estén correctamente rechazados. Hay **cuatro falsos descartes claros** (2, 6, 10 y 13), un caso de entidad jurídica no recuperada (1), un anexo comercial ambiguo (5) y tres documentos sin fragmentos (16, 17, 20).

## 3. Tabla completa: GLiNER → comportamiento esperado → V16 → diagnóstico

En la columna **“Esperado”** se registra el resultado deseable *con la evidencia disponible en fragmentos*, no una predicción de que la V16 ya pueda producirlo. **“V16”** describe literalmente el resultado observado.

| Doc. (ID) | Qué extrajo GLiNER2 | Qué se esperaba que pudiera resolver/filtrar la consolidación | Qué devolvió la V16 | Diagnóstico / mejora |
|---|---|---|---|---|
| **1** (`788347`) | Solo CUIT `3050003967-8`, sin nombre. Fragmento: `Caledonia Argentina Compañía de Seguros SA (CUIT: ...)`. | Reconocer la **razón social y CUIT** asociados a la consulta, si se admite persona jurídica y hay asociación textual inequívoca. | **NO_RESUELTO**; 0 aceptados; 1 incompleto `sin_nombre_persona`. | Falta recuperación controlada de entidades jurídicas, no aceptación ciega de CUIT aislado. |
| **2** (`789454`) | `NORBERTO HORACIO` + CUIT `20-10041809-7` (omisión de `UNGAR`); también `MARIA VIRGINIA RAFFO` (firmante). | Reconstruir **`UNGAR, NORBERTO HORACIO`** desde el fragmento; aceptar al sujeto y descartar a la firmante. | **NO_RESUELTO**; Ungar descartado `nombre_parcial_en_lista`; Raffo descartada `tercero_fuerte`. | **Falso descarte**; recuperar apellido contiguo sin relajar indiscriminadamente validaciones. El descarte de la firmante es correcto. |
| **3** (`790063`) | Dos predicciones `Marta Elisa PUGLIESE`, DNI `4756818`, CUIL `27-04756818-3`, rol `causante`, en **dos fragmentos distintos**. | Unificar dos apariciones y conservar identificadores/rol. | **RESUELTO**, 1 persona, 2 fragmentos y 2 evidencias. | **Correcto**. Caso de regresión positivo. |
| **4** (`790072`) | Cuatro predicciones **idénticas** de `GONZALEZ DAVID AVELINO` + DNI `33903621` en un fragmento; CUIT aislado `30-50098787-8` de una entidad oficiada; `Alejandro Luis Alberto Siliano` + DNI y rol `actor` incorrecto; `Sra. RODRIGUEZ MAIRA ALEJANDRA` + DNI. | Aceptar solo a González; excluir terceros administrativos y destinatarios de otros oficios; **deduplicar evidencia**, no solo persona. | **RESUELTO**, González aceptado; terceros descartados; CUIT aislado incompleto. **4 evidencias para 1 fragmento**, score `46.31`. | **Identidad final correcta**, pero evidencia y score inflados. Los terceros se descartaron por falta de señales, no por una explicación explícita de autorización. |
| **5** (`790081`) | `PIZZERIA` sin ID; fragmento estructurado `Nombre: PIZZERIA - Apellido: NAPOLES - Tipo de Documento: CUIT - Número de documento: 20288024554`. | Detectar formato de **anexo comercial** y conservar el vínculo entre denominación y CUIT como dato estructurado, **sin inventar persona física** ni asumir que el anexo es un oficio convencional. | **NO_RESUELTO**; `PIZZERIA` descartado `nombre_no_valido`. | **Pendiente de alcance/definición funcional**: separar persona jurídica/comercio/anexo de una identidad personal común. No tratar automáticamente como falso descarte. |
| **6** (`790085`) | `MARÍA FERNANDA` + CUIT `27-34953534-9`; el fragmento dice `SORIA, MARÍA FERNANDA`; otro candidato solo `rol=titular`, sin nombre ni ID. | Reconstruir **`SORIA, MARÍA FERNANDA`**, aceptar a la titular consultada y no convertir `titular` aislado en persona. | **NO_RESUELTO**; nombre descartado `nombre_parcial_en_lista`. | **Falso descarte**; contexto `se le requiere... cuentas pertenecientes a` es fuerte. Mantener rechazo de candidatos sin identidad. |
| **7** (`790089`) | `Martin Ignacio Galvan` + DNI `39054617`. | Reconocer pedido explícito sobre él. | **RESUELTO**, 1 persona. | **Correcto**. |
| **8** (`790091`) | `Horacio Guillermo PÉREZ` + DNI `22.513.908`, rol `demandado`. | Aceptar sujeto e identificador asociados a solicitud. | **RESUELTO**, 1 persona. | **Correcto**. |
| **9** (`790092`) | `Franco Eduardo Cárdenas` + DNI `32.851.047` + CUIL `20-32851047-3`. | Asociar dos identificadores a la misma persona. | **RESUELTO**, 1 persona. | **Correcto**. |
| **10** (`790094`) | `Arcadio Samuel Hamil García` + DNI `37433769`; el fragmento incluye `operaciones bancarias ... por el ciudadano` y CVU. | Aceptar si la construcción evidencia que las operaciones solicitadas corresponden a esa persona, **sin exigir rol judicial ni repetición**. | **NO_RESUELTO**; `senales_insuficientes`, `sin_rol_juridico_fuerte`, `sin_contexto_juridico`, `sin_repeticion`. | **Falso descarte** por señales demasiado acotadas; generalizar vínculo entre *operación solicitada* y *persona identificada*. |
| **11** (`790097`) | `Romero Hector` + DNI `34.472.193`; rol GLiNER `actor`, aunque el fragmento dice `el accionado`. | Aceptar la persona y conservar/corregir el rol solo con evidencia inequívoca; detectar contradicción. | **RESUELTO**, persona correcta; `roles_detectados=["actor"]` permanece. | **Acierto de identidad, error de rol**; comparar predicción del modelo con evidencia textual localizada. **`Romero Hector` (dos palabras) es nombre válido**. |
| **12** (`790102`) | `ENDARA MARIANO ADRIÁN` + DNI `38.804.970` + CUIL `20-38804970-8`. | Aceptar sujeto e identificadores. | **RESUELTO**, 1 persona. | **Correcto**. |
| **13** (`790106`) | `NANCY SILVANA GRACIANO` + DNI `27017871` + CUIT `27-27017871-0`; en otro fragmento `nombrada` sin ID. | Aceptar a Nancy por la construcción `respecto de la señora [nombre], DNI..., CUIT..., lo siguiente:`. Rechazar `nombrada` como nueva identidad; usarlo, si se puede enlazar con seguridad, solo como referencia contextual. | **NO_RESUELTO**; Nancy descartada por falta de rol/contexto/repetición; `nombrada` descartada `nombre_no_valido`. | **Falso descarte** por no entender una introducción de solicitud. No forzar resolución de referencias anafóricas entre fragmentos sin evidencia explícita. |
| **14** (`790111`) | `Susana Esther Gigerey` + DNI `44.379.117`. | Aceptar persona consultada. | **RESUELTO**, 1 persona. | **Correcto**. |
| **15** (`790114`) | `ARIAS MARIA BELEN` + DNI `37.128.726`, rol `demandada`; otro fragmento de URL sin detecciones. | Aceptar sujeto sin aceptar texto administrativo. | **RESUELTO**, 1 persona. | **Correcto**. |
| **16** (`790115`) | Ningún candidato: **fragmento vacío**. El texto completo, solo para revisión manual, habla de ID/nombre de vendedor. | **No inventar sujeto**; señalar ausencia de fragmento. | **NO_RESUELTO**, `sin_fragmentos_para_gliner`, revisión. | **Límite del fragmentador**, no error reparable por la consolidación con el input actual. Requerirá otra etapa futura. |
| **17** (`790122`) | Ningún candidato: **fragmento vacío**. El texto completo menciona a Mariano Fabián Ferro, CVU y alias. | **No recuperar desde texto completo**; señalar falta de evidencia de entrada. | **NO_RESUELTO**, sin fragmentos, revisión. | **Límite del fragmentador**; no imputar omisión al modelo sobre texto que nunca recibió. |
| **18** (`790129`) | `JOSE LEONARDO` + DNI `30500719`; fragmento `LOPEZ, JOSE LEONARDO`. | Recuperar apellido faltante y aceptar sin añadir identidades ajenas. | **RESUELTO**, `LOPEZ, JOSE LEONARDO` + DNI. | **Correcto**: la V16 ya tiene recuperación parcial en algunos contextos. Usar como prueba de regresión para 2/6. |
| **19** (`790136`) | `ANDRADE NORA` + DNI `18223729`. **No** extrajo a `KEVIN EZEQUIEL SLAVIN` + DNI `45304486`, aunque ambos aparecen en el mismo fragmento de transferencias. | Aceptar Andrade como titular de origen vinculado a Mercado Pago. **Revisar criterio de alcance** sobre Slavin (titular de destino) antes de declararlo objeto del pedido. No inventar un candidato sin extracción. | **RESUELTO**, solo Andrade Nora. | Resultado **razonable con el alcance actual**; la omisión de Slavin es de extracción y/o definición funcional, no necesariamente error de consolidación. **`ANDRADE NORA` (dos palabras) es nombre válido**. |
| **20** (`790138`) | Ningún candidato: **fragmento vacío**. El texto completo, solo para auditoría, identifica a Juan José Cesario y DNI. | No inventar identidad; marcar insuficiencia por falta de fragmentos. | **NO_RESUELTO**, sin fragmentos, revisión. | **Límite del fragmentador**. |

## 4. Diagnóstico causal (separar responsabilidades)

### 4.1 Errores o limitaciones de GLiNER2

1. **Extracción de nombres parciales:** docs. 2, 6, 18 (en 18 la consolidación sí reparó).
2. **Nombre o identificador omitido en estructura comercial:** docs. 1 y 5.
3. **Predicciones múltiples iguales en un mismo fragmento:** doc. 4.
4. **Rol incorrecto:** doc. 11 (`actor` en vez de `accionado`); doc. 4 (`actor` para autorizado).
5. **Referencias genéricas confundidas con personas:** doc. 13 (`nombrada`), doc. 6 (`titular` como único campo).
6. **Omisión de segundo interviniente:** doc. 19 (Slavin). Su clasificación como sujeto requerido es todavía discutible.
7. **Falta de fragmentos:** docs. 16, 17, 20, **problema anterior a GLiNER2**, no inferencia incorrecta del modelo.

### 4.2 Fallos observados de la consolidación actual

- **Falsos descartes confirmados** de sujetos relevantes: **2, 6, 10, 13**.
- **Deduplicación incompleta de evidencias:** doc. 4, cuatro evidencias de un único fragmento para González; score `46.31`. Agrupar una persona no equivale a eliminar evidencia repetida.
- **Rol semántico contradictorio conservado sin aviso:** doc. 11.
- **Justificación negativa poco específica:** doc. 4 excluye correctamente autorizados, pero por ausencia de otras señales en vez de detectar de forma robusta su función administrativa.
- **Recuperación/soporte de personas jurídicas no establecido:** doc. 1; posible caso comercial doc. 5.
- **Reglas contextuales acotadas:** doc. 10 carece de verbos reconocidos en la ventana de su fragmento; doc. 13 introduce el requerimiento con `respecto de ... lo siguiente:` y queda fuera.

### 4.3 Comportamientos correctos que deben preservarse

- Identidades aceptadas en docs. **3, 4, 7, 8, 9, 11, 12, 14, 15, 18, 19** (en 4, 11, 19 existen observaciones específicas).
- Descarte de firmante en doc. **2**.
- Descarte de autorizados en doc. **4**.
- Descarte de pseudonombre `nombrada` en doc. **13**.
- Recuperación del apellido en doc. **18**.
- Estado de revisión para documentos **16, 17, 20** sin fragmentos.

## 5. Mejoras propuestas (para implementar después de aprobar este diagnóstico)

### M1 — Reconstrucción segura de nombres parciales **SIN exigir más de dos palabras** (prioridad alta)

**Regla funcional esencial:** **un nombre y un apellido son suficientes** para representar una identidad completa. Por ejemplo, `Romero Hector`, `ANDRADE NORA` o `SORIA FERNANDA` pueden ser nombres perfectamente válidos. **Nunca descartar una persona por tener solo dos palabras** ni exigir dos nombres de pila y un apellido, o dos apellidos. Lo que se debe detectar es **la omisión comprobable de una parte ya presente en el mismo fragmento**.

**Flujo deseado:**

1. Conservar el nombre extraído por GLiNER como evidencia original.
2. Localizar su aparición exacta en `fragmento`, empleando offsets si son confiables.
3. Detectar si hay **continuidad nominal verificable** inmediatamente antes o después, por ejemplo `APELLIDO, NOMBRE` o una variante de puntuación/OCR, sin cruzar cláusulas/listas ajenas.
4. Reconstruir únicamente con texto presente en el fragmento, conservando `nombre_original`, `nombre_recuperado`, `origen_recuperacion` y la evidencia utilizada.
5. Si no hay evidencia clara de una omisión, **conservar el nombre de dos palabras como válido** y continuar con las demás validaciones; no cambiarlo ni descartarlo por estructura.
6. Si hay indicios contradictorios (dos nombres vecinos, separadores ambiguos, varias personas), no unir por fuerza; marcar revisión.

**Pruebas positivas:** 2 → `UNGAR, NORBERTO HORACIO`; 6 → `SORIA, MARÍA FERNANDA`; 18 → `LOPEZ, JOSE LEONARDO`.  
**Pruebas de no regresión:** 11 → conservar `Romero Hector`; 19 → conservar `ANDRADE NORA`; además probar nombres sintéticos legítimos de dos palabras con DNI y sin nombres adyacentes.

> **Importante:** `nombre_parcial_en_lista` debe indicar evidencia objetiva de truncamiento, **no mera longitud**. La presencia de coma por sí sola no autoriza unir nombres de personas diferentes.

### M2 — Contexto positivo orientado a la relación identidad–pedido (alta)

Añadir **familias de construcciones generales**, no nombres de empresas ni frases de un archivo:

- Solicitud explícita: `informe si`, `se requiere que`, `solicitar ... respecto de`.
- Introducción de objeto: `respecto de [persona] ... lo siguiente:`, `respecto a`, `en relación con`.
- Relación con datos solicitados: `operaciones ... por [persona]`, `cuentas pertenecientes a`, `saldo/cuenta a nombre de`, `datos asociados a`.
- Reconocimiento de sujetos sin rol procesal explícito: admitir evidencia de **vínculo directo con la consulta** si está localizada en el fragmento, incluso sin repetición.

**Control:** no aceptar a todos los nombres cercanos a `informe`, y no hacer que `respecto de` aislado implique aceptación automática.

**Casos guía:** 10 y 13; conservar 7, 9 y demás resueltos.

### M3 — Deduplicar evidencias, no solo personas (alta)

- Definir clave estable por `(documento, fragmento/contador, identidad normalizada, tipo+valor de identificador, span si aporta una mención distinta)`.
- Combinar campos complementarios y elegir confianza máxima válida sin sumar 4 veces el mismo texto.
- Distinguir **número de predicciones**, **menciones únicas** y **fragmentos independientes**, para que el `score_total` no quede inflado.
- Recalcular contadores de evidencia y scoring de modo trazable.

**Caso guía:** doc. 4. **Control:** doc. 3 debe seguir contando **dos fragmentos independientes**.

### M4 — Validar roles predichos contra evidencia local (alta)

- Comparar `rol_persona` de GLiNER con expresiones **vinculadas al candidato** en el mismo fragmento.
- Normalizar equivalencias (`accionado`/`demandado`) sin confundirlas con `actor`.
- Ante contradicción clara, registrar el conflicto y, solo si el contexto lo permite inequívocamente, corregir el rol. En caso ambiguo, revisión.
- No tratar `actor` como razón automática para excluir: una parte actora también puede ser objeto de un oficio (doc. 13).

**Caso guía:** doc. 11.

### M5 — Señales negativas localizadas a cada candidato (media-alta)

- Detectar `firmado por`, `autorizado para diligenciar`, `facultado para`, `secretario/a`, `juez`, `perito`, `letrado` cuando el contexto indica función administrativa.
- Considerar listas de autorizados y referencias `y/o quienes ... autoricen`, **sin aplicar el descarte a una persona consultada en otra parte**.
- No convertir palabras como `titular`, `destinatario` o `actor` en negativas globales: dependen de su relación con el pedido.

**Casos guía:** docs. 2 y 4. El objetivo es mejorar la **justificación y robustez** de los descartes, no cambiar resultados correctos.

### M6 — Entidades jurídicas y formatos comerciales (media; requiere definición funcional)

- Permitir reconocimiento de razón social junto a CUIT desde el fragmento si el **tipo de entidad** está admitido.
- Distinguir razón social, nombre comercial, persona física y destinatario de otro oficio.
- Evaluar anexos estructurados (`Nombre:`, `Apellido:`, `Tipo de Documento:`, `Número de documento:`) con reglas de asociación por campos, **sin suponer automáticamente persona física**.
- No aceptar CUIT aislados de organismos mencionados como terceros.

**Casos guía:** 1 y 5; control negativo: CUIT aislado de destinatario adicional en doc. 4.

### M7 — Cobertura de fragmentación, fuera del alcance inmediato de consolidación (futura)

- A posteriori evaluar por qué faltaron fragmentos en 16, 17 y 20.
- Considerar señales adicionales de generación de fragmentos (CVU, alias, ID vendedor, nombre de cuenta), **en etapa distinta**.
- Por ahora: **no activar fallback automático a `texto_completo`**. `requiere_fallback_documento_completo=true` es una **bandera diagnóstica histórica**; no autoriza usar ese campo para extraer ni consolidar durante esta fase.

## 6. Requisitos de caja negra y aceptación de cambios

1. **Independencia del caso:** prohibido incorporar nombres concretos, CUIT concretos, documentos concretos, destinatarios fijos (p. ej. `MERCADO PAGO`) o expresiones exclusivas de un país/caso como atajos de aceptación.
2. **Entrada restringida:** decisiones basadas únicamente en fragmentos y predicciones GLiNER; `texto_completo` puede conservarse por compatibilidad y auditoría, pero no alimentar reglas ni puntajes.
3. **Separación de niveles:** no confundir identidad válida, pertenencia al requerimiento y suficiencia global del documento.
4. **No inventar:** reconstruir solo cadenas efectivamente respaldadas en el fragmento; ante ambigüedad preservar estado de revisión.
5. **Dos palabras válidas:** aceptar nombre + apellido cuando es coherente y está asociado a la evidencia. No exigir tres o cuatro tokens.
6. **Deduplicación robusta:** no sumar varias veces predicciones repetidas sobre una misma mención.
7. **Trazabilidad:** registrar evidencia textual, transformaciones, contradicciones y motivo concreto de aceptación/descarte.
8. **Regresión:** comparar nueva versión vs. V16 en los 20 presentes, los **20 anteriores** y los **80 históricos**; preservar todos los casos correctos, permitir cambios solo si están justificados por revisión manual/ground truth.
9. **Casos extranjeros:** mantener soporte de RUT/CI y evitar reglas que dependan de un solo oficio chileno o uruguayo.
10. **Métricas honestas:** informar `RESUELTO/SUFICIENTE` separados de precisión, recall y F1; estas últimas exigen un gold validado. No presentar 55 % como exactitud.

### Matriz mínima de pruebas a crear antes de cambiar el código

| Prueba | Entrada | Resultado esperado |
|---|---|---|
| Nombre parcial con apellido previo | `Sr. UNGAR, NORBERTO HORACIO, CUIT...` + `NORBERTO HORACIO` | Reconstruye `UNGAR, NORBERTO HORACIO`, si asociación es inequívoca. |
| Nombre parcial tras mención de titularidad | `cuentas pertenecientes a SORIA, MARÍA FERNANDA (CUIT...)` + `MARÍA FERNANDA` | Reconstruye `SORIA, MARÍA FERNANDA`. |
| Recuperación ya existente | `Sr. LOPEZ, JOSE LEONARDO, DNI...` + `JOSE LEONARDO` | Mantiene `LOPEZ, JOSE LEONARDO`. |
| Nombre legítimo de **dos palabras** | `el accionado, Sr. Romero Hector, DNI...` | **No descarta** por número de palabras. |
| Nombre legítimo de **dos palabras** | `cuenta de ANDRADE NORA DNI...` | **No descarta** por número de palabras. |
| Separador entre dos personas | `JUAN PEREZ, MARIA LOPEZ`, IDs diferentes | No fusiona nombres sin asociación fiable. |
| Introducción de requerimiento | `respecto de la señora NANCY SILVANA GRACIANO, DNI..., CUIT..., lo siguiente:` | Acepta con evidencia contextual; sin exigir rol ni repetición. |
| Operación consultada | `operaciones ... por el ciudadano Arcadio Samuel Hamil García con DNI...` | Reconoce vínculo con operaciones; controla falso positivo. |
| Predicción repetida | 4 predicciones idénticas de González en un fragmento | 1 identidad, 1 evidencia independiente, score sin cuadruplicar. |
| Repetición genuina | Marta Elisa Pugliese en 2 fragmentos | 1 identidad, **2 evidencias independientes**. |
| Rol contradictorio | `el accionado Sr. Romero Hector` + GLiNER `actor` | Señala/corrige contradicción; mantiene identidad. |
| Firmantes/autorizados | `Firmado por Maria Virginia Raffo`; lista de autorizados | No acepta por sola aparición/ID. |
| Sin fragmentos | Docs. 16, 17, 20 | No resuelto; sin lectura de `texto_completo` para decidir. |

## 7. Plan de trabajo posterior a este README

1. **Congelar línea base:** guardar JSON de GLiNER, consolidación V16, resumen y esta revisión.
2. **Inspeccionar la implementación actual** (`src/consolidacion_oficios.py`) para localizar recuperación de apellidos, `nombre_parcial_en_lista`, reglas de contexto, scoring, deduplicación y tratamiento de rol.
3. **Crear tests de regresión primero**, especialmente los de nombres de dos palabras y los 80 + 20 documentos históricos.
4. Implementar primero **M1 (reconstrucción segura)** y **M3 (deduplicación)**; luego **M2 (relación petición–sujeto)** y **M4/M5**.
5. Discutir el alcance funcional de **M6** (personas jurídicas/anexos) antes de ampliar salidas.
6. Ejecutar nuevamente los 20 casos con la versión candidata, comparar identidad por identidad y aprobar solo cambios generales que no provoquen regresiones.

---

**Conclusión:** la V16 obtuvo 11 documentos suficientes según sus propias reglas, pero los docs. **2, 6, 10 y 13** exhiben rechazos que deben corregirse mediante reglas generales. La reconstrucción de nombres **no debe castigar nombres completos de dos palabras**: debe comprobar si el fragmento ofrece evidencia concreta de material omitido. Esta evaluación es la referencia para la siguiente fase; **todavía no se cambió código**.
