# Reporte técnico — Consolidación de oficios V15: recuperación internacional

**Proyecto:** Identificación de personas objeto de oficios judiciales — SEGEM / CECONEA  
**Fecha de actualización:** 17 de noviembre de 2026  
**Archivo principal:** `consolidacion_oficios_v15_integrada.py`  
**Versión de referencia:** consolidación V14 con extensión internacional V15 integrada en **un único archivo Python**.

## 1. Objetivo de la actualización

Ampliar la consolidación de personas objeto de oficios judiciales para reconocer **identificadores extranjeros en fragmentos complementarios** sin modificar el esquema de GLiNER2 ni las reglas argentinas que ya habían sido validadas.

El alcance inicial se limita a:

- **Chile:** Rol Único Tributario / Rol Único Nacional (**RUT/RUN**).
- **Uruguay:** cédula de identidad (**CI/C.I.**).

Los documentos exclusivamente argentinos continúan procesándose con los métodos de la V14. El documento 16 (persona de nacionalidad peruana con DNI argentino) **no se incorpora a esta ampliación** porque no tiene fragmentos internacionales útiles en el conjunto de prueba.

## 2. Decisión de diseño: un único archivo de consolidación

No se creó una versión del consolidador que dependa de un módulo internacional adicional para ejecutar las reglas nuevas. La entrega principal es **`consolidacion_oficios_v15_integrada.py`**, que conserva las funciones anteriores e incluye, al final, la nueva sección `EXTENSION INTERNACIONAL V15 (CHILE Y URUGUAY)`.

Se utiliza una estrategia de **extensión optativa**:

1. La referencia `_consolidar_documentos_argentinos` conserva el comportamiento original de `consolidar_documentos` antes de redefinir su interfaz pública.
2. Los métodos nuevos con prefijo `_int_` realizan la recuperación internacional de manera separada.
3. La función pública `consolidar_documentos(documentos, documentos_internacionales=None)` permite recibir un segundo conjunto de predicciones, opcional.
4. Cuando no se pasan predicciones internacionales, se ejecuta únicamente la lógica histórica. Cuando se pasan, **primero se consolida normalmente** y después se incorporan los resultados extranjeros verificados, vinculando documentos por `id`.

> **Alcance importante:** el archivo consolidador contiene ambas lógicas. No obstante, el *runner* existente del repositorio aún debe adaptarse para leer y pasar el segundo JSON. Esa integración del CLI general **no está realizada** en esta entrega.

## 3. Entradas del procesamiento

La ampliación utiliza **dos fuentes complementarias**, no intercambiables:

| Fuente | Propósito | Ejemplo de entrada |
|---|---|---|
| Predicciones originales | Mantener la extracción y consolidación de casos argentinos | `predicciones_por_documento(20261113-051954).json` |
| Predicciones internacionales | Aportar fragmentos disparados por RUT/RUN/CI para los casos atípicos | `predicciones_por_documento(20261117-043211).json` |

El nuevo CSV `data/fragmentos_internacional.csv` se procesa **previamente** mediante GLiNER2 usando el mismo modelo, esquema y umbrales del experimento original. **La consolidación no ejecuta GLiNER ni lee directamente el CSV**: recibe el JSON de predicciones que produce esa etapa.

La ampliación no exige cambiar estos campos de GLiNER2:

- `nombre_persona`
- `dni_persona`
- `cuit_cuil_persona`
- `rol_persona`

En la prueba, GLiNER2 recuperó los nombres extranjeros, pero dejó vacíos los campos argentinos de identificadores. La nueva capa recupera RUT/RUN/CI desde el **mismo fragmento** donde el modelo detectó cada nombre.

## 4. Métodos nuevos incorporados

Todas las siguientes funciones están implementadas dentro de `consolidacion_oficios_v15_integrada.py` y usan el prefijo `_int_` para diferenciarlas de los métodos existentes.

| Método | Responsabilidad |
|---|---|
| `_int_normalizar` | Normaliza mayúsculas, tildes y espacios para comparaciones de texto. |
| `_int_nombre` | Normaliza nombres y elimina tratamientos iniciales como `don`/`doña`. |
| `_int_nombre_visible` | Limpia tratamientos del nombre preservando su presentación textual. |
| `_int_rut_valido` | Verifica el dígito verificador de RUT/RUN chileno mediante módulo 11. |
| `_int_ci_uy_valida` | Verifica el dígito verificador de la cédula uruguaya. |
| `_int_candidatos_gliner` | Reúne nombres detectados por GLiNER2 con su fragmento, palabra clave y confianza. |
| `_int_buscar_identificador_local` | Busca un identificador explícitamente etiquetado después del nombre y a corta distancia; evita apropiarse del ID de otra persona. |
| `_int_es_pedido_a_mercadopago_chile` | Verifica, para un candidato ya detectado, si el texto completo contiene un pedido dirigido a Mercado Pago asociado con ese nombre y RUT. |
| `_int_pedidos_uruguay` | Comprueba que el fragmento pertenezca a una lista expresa de personas vinculada con información financiera. |
| `_int_es_perito` | Identifica a peritos mediante su contexto profesional próximo al nombre. |
| `_int_nueva_persona` | Construye la estructura serializable de una persona extranjera con su identificador y trazabilidad. |
| `_int_recuperar_personas_internacionales` | Selecciona la estrategia por país, valida identidad y contexto, agrupa duplicados y registra descartes y alertas. |
| `_consolidar_documentos_con_fuente_internacional` | Ejecuta primero la consolidación histórica y combina solamente las recuperaciones extranjeras correspondientes. |
| `consolidar_documentos` (interfaz pública final) | Acepta opcionalmente `documentos_internacionales`; sin esa entrada mantiene la ruta V14. |

### 4.1. Patrones especializados

Se añadieron dos expresiones regulares internas:

- `_int_RUT`: reconoce menciones etiquetadas `RUT` o `RUN`, con el número y su dígito verificador (incluida la letra `K`).
- `_int_CI`: reconoce etiquetas `CI`, `C.I.` y variantes de puntuación, seguidas de una cédula con formato compatible.

**No basta la palabra clave `CI` aislada:** en la fragmentación complementaria aparecen coincidencias accidentales dentro de otras palabras. Para procesar una identidad se requieren además etiqueta y formato del identificador, nombre detectado por GLiNER, país compatible, contexto pertinente y validación del dígito verificador.

## 5. Flujo de decisión

```text
Predicciones GLiNER2 originales
             |
             v
Consolidación V14 (sin alterar sus reglas)
             |
             +-------------------------------+
                                             |
Predicciones GLiNER2 internacionales         |
             |                               |
             v                               |
Identificar documento por ID y país          |
             |                               |
             v                               |
Revisar candidatos y palabra_clave           |
             |                               |
             v                               |
Asociar nombre + RUT/RUN/CI en fragmento      |
             |                               |
             v                               |
Validar dígito verificador                   |
             |                               |
             v                               |
Verificar contexto y excluir terceros        |
             |                               |
             +-------------------------------+
                                             |
                                             v
                      Resultado consolidado unificado
```

**Chile:** se exige que el nombre y el RUT estén juntos en un fragmento complementario y que, en el texto completo, aparezcan asociados a una solicitud explícita dirigida a Mercado Pago. El texto completo solo se utiliza para **confirmar el pedido de un candidato ya detectado**, no para inventar nuevas personas o identificadores. Los peritos se descartan.

**Uruguay:** se exige una lista explícita de personas con contexto financiero; cada nombre detectado por GLiNER debe tener su CI etiquetada inmediatamente después. Se valida cada CI individualmente.

**Agrupación y conflictos:** las repeticiones de un mismo nombre e identificador se agrupan. Si un nombre tiene identificadores extranjeros diferentes dentro del mismo documento, la recuperación evita aceptarlo automáticamente y registra una alerta.

## 6. Estructura de salida

La salida mantiene los campos generales históricos (`estado`, `suficiente`, `personas_objeto_oficio`, `grupos_descartados`, etc.). Para las personas incorporadas por la capa internacional se agregan:

| Campo | Descripción |
|---|---|
| `pais_identificador` | `CL` o `UY`. |
| `tipo_identificador` | `RUT` o `CI`. |
| `identificador_extranjero` | Valor textual recuperado del fragmento. |
| `identificador_validado` | Indica si superó la validación implementada. |
| `evidencias` | Fragmento, palabra clave, nombre detectado y origen de recuperación. |
| `decision_consolidacion` | Motivos de aceptación y método aplicado. |

Los campos `dni_persona` y `cuit_cuil_persona` permanecen **vacíos** para las nuevas personas internacionales: **un RUT o CI no se presenta como si fuera un DNI o CUIT argentino**.

En los documentos ampliados también se incorpora `recuperacion_internacional`, con el país, fuente, cantidad de personas recuperadas, cantidad de descartes y alertas. La ampliación actual puede modificar el estado y la suficiencia cuando encuentra identidades extranjeras confirmadas, pero conserva la salida anterior en documentos sin una recuperación internacional aplicable.

## 7. Resultados experimentales

### Documento 2 — Chile

- **ID:** `780532`.
- **Resultado anterior:** `NO_RESUELTO`.
- **Resultado V15:** `RESUELTO`.
- **Persona aceptada:** Ana José Chacón Aguirre.
- **Identificador:** RUT `16.416.075-0`.
- **Descartes internacionales:** Dexter Johnson Chacón (hijo), Dwight Ronald Johnson Calcagno (sujeto de pedidos a otras entidades), Marta Andrea Vives González (perito) y Carolina Bustamante Troncoso (perito).

La distinción determinante es **ser objeto del pedido dirigido a Mercado Pago**, no limitarse a figurar como parte procesal o tener RUT.

### Documento 5 — Uruguay

- **ID:** `780763`.
- **Resultado anterior:** `NO_RESUELTO`.
- **Resultado V15:** `RESUELTO_MULTIPLE`.
- **Personas aceptadas:** **7 de 7** detectadas por GLiNER2 en el listado financiero.

| Persona | CI uruguaya recuperada |
|---|---|
| Yanet Gisela Suarez Ledesma | `5.442.723-8` |
| William Rafael Suarez Ledesma | `5.323.763-4` |
| Amadeo Alves Costa | `3.078.846-8` |
| Anthony Barreto Suarez | `5.429.679-2` |
| Patricia Anabel Demicce Carrera | `4.585.306-6` |
| Daniel Martín Olivera Casco | `4.846.236-1` |
| Michael Bellora Caneva | `5.382.147-9` |

### Resumen de los 20 documentos de preproducción con fuente complementaria

| Métrica | V15 |
|---|---:|
| Documentos analizados | 20 |
| `RESUELTO` | 18 |
| `RESUELTO_MULTIPLE` | 1 |
| `NO_RESUELTO` | 1 |
| Personas aceptadas en total | 25 |
| `SUFICIENTES` | 18 |
| `INSUFICIENTES` | 2 |

Las únicas diferencias frente a la consolidación base se registraron en los **documentos 2 y 5**.

## 8. Control de regresiones

La comparación se ejecutó directamente contra la consolidación histórica contenida en el archivo integrado, usando los mismos JSON de entrada.

| Conjunto | Documentos | Comparación V14 vs. V15 sin fuente internacional |
|---|---:|---|
| Oficios históricos, corrida `20261101-235003` | 80 | JSON por documento idéntico |
| Oficios históricos, corrida `20261030-175058` | 80 | JSON por documento idéntico |
| Preproducción, corrida `20261113-051954` | 20 | JSON por documento idéntico |

Al agregar las predicciones internacionales `20261117-043211` a los 20 documentos, **solo cambiaron los números de archivo 2 y 5**. Los restantes 18 —incluido el documento 16— conservaron resultados idénticos.

Esto valida la **ausencia de regresiones en los conjuntos ensayados**; no constituye garantía absoluta para cualquier documento futuro.

## 9. Uso desde Python

El archivo integrado expone una sola función pública para ambos casos:

```python
from consolidacion_oficios_v15_integrada import consolidar_documentos

# Comportamiento V14: entrada original únicamente.
resultado_original = consolidar_documentos(predicciones_originales)

# Comportamiento V15: entrada original + fuente internacional complementaria.
resultado_ampliado = consolidar_documentos(
    predicciones_originales,
    documentos_internacionales=predicciones_internacionales,
)
```

`predicciones_originales` y `predicciones_internacionales` representan listas de documentos ya cargadas desde sus archivos JSON. La función **no recibe rutas** ni ejecuta la extracción GLiNER.

**Pendiente de integración:** adaptar el comando/runner habitual del proyecto para que cargue la segunda fuente y la pase a `consolidar_documentos`. El ejecutor auxiliar previo importa el módulo internacional separado, por lo que **no debe considerarse automáticamente el ejecutor definitivo de este archivo único**.

## 10. Limitaciones y próximos pasos

1. **Cobertura restringida:** se probaron dos documentos extranjeros específicos. No se implementó un mecanismo general de clasificación de países; la detección actual utiliza marcas textuales del documento y palabras clave del fragmento.
2. **Solicitudes chilenas:** la comprobación del pedido a Mercado Pago es conservadora y depende de la estructura textual. Un OCR deteriorado o una redacción distinta pueden dejar una persona sin aceptar.
3. **Solicitudes uruguayas:** la recuperación depende de una lista explícita de personas y de identificadores ubicados cerca de sus nombres. Otros diseños de oficio requieren nuevas pruebas.
4. **Terceros:** existen reglas de descarte para peritos y ausencia de pedido pertinente; hace falta validar otros terceros y casos mixtos con más ejemplos.
5. **Alertas y suficiencia:** la revisión manual y la suficiencia son indicadores operativos, no una certificación de exactitud jurídica o identidad.
6. **Producción:** antes de integrar al flujo general, adaptar el runner, sumar pruebas automatizadas al repositorio y ampliar el banco de casos reales extranjeros.
7. **Integridad histórica:** conservar los 80 oficios de referencia y los 20 de preproducción como pruebas de regresión obligatorias para futuras versiones.

## 11. Conclusión

La V15 demuestra que es posible **recuperar las personas y los identificadores chilenos/uruguayos sin reentrenar GLiNER2, cambiar su esquema ni reescribir los métodos argentinos**. Se agregó una rama de recuperación activada mediante predicciones complementarias, con validación de identificadores, asociación local nombre–ID, contextualización del pedido y rechazo de terceros.

En esta evaluación se recuperaron **1 persona en Chile y 7 en Uruguay**, sin cambios en los resultados de los casos argentinos probados. La arquitectura conserva **una sola fuente de consolidación** y deja abierta la integración del segundo JSON en el runner general.
