# Mejoras de la consolidación sobre la extracción de GLiNER2

## Objetivo

Este documento resume el valor agregado de la etapa de **consolidación determinística** aplicada después de la extracción de entidades con GLiNER2. La comparación busca mostrar que la salida del modelo NER no se utiliza de forma directa: la consolidación reconstruye información parcial, vincula identificadores con personas, interpreta el contexto local del requerimiento, deduplica evidencia y descarta terceros o candidatos ambiguos.

> **Principio de diseño:** la decisión automática se realiza sobre los **fragmentos de entrada y las predicciones de GLiNER2**. El `texto_completo` se conserva como metadata/revisión, pero no se utiliza para completar automáticamente una identidad ausente del fragmento.

## Resultado del lote evaluado

- **Documentos evaluados:** 37
- **Resueltos automáticamente:** 33/37 (**89%**)
- **No resueltos / revisión:** 4/37
- **Identidades estructuradas recuperadas explícitamente para revisión manual:** 1
- **Mejora respecto de la referencia anterior del mismo lote:** el documento `790138` pasa de no resuelto a resuelto gracias a que la nueva fragmentación entrega la identidad útil y la consolidación puede validarla.

## Qué agrega la consolidación

1. **Reconstrucción de nombres incompletos.** Puede recuperar apellidos u otras partes literales presentes en el mismo fragmento cuando GLiNER devuelve solo una porción del nombre.
2. **Recuperación local de identificadores.** Vincula DNI/CUIT/CUIL próximos al nombre cuando el modelo omite el campo o lo entrega de forma incompleta.
3. **Validación del objeto del oficio.** No alcanza con que una persona aparezca en el fragmento: se evalúa si está vinculada al requerimiento principal.
4. **Filtrado de terceros.** Firmantes, abogados, funcionarios, autorizados y otros intervinientes pueden ser detectados por GLiNER, pero la consolidación evita incorporarlos como sujetos del oficio cuando el contexto los identifica como terceros.
5. **Deduplicación de evidencia.** Varias predicciones originadas en el mismo fragmento no se contabilizan como múltiples evidencias independientes.
6. **Auditoría de roles.** Los roles predichos por GLiNER se contrastan con el texto del fragmento y se conserva información de contradicciones sin corregir silenciosamente la salida del modelo.
7. **Recuperación conservadora para revisión.** Una identidad puede recuperarse estructuralmente sin ser aceptada automáticamente si falta evidencia suficiente sobre su naturaleza o sobre el alcance del pedido.

## Comparación: extracción GLiNER2 vs. resultado de consolidación

**Leyenda:** `R/S` = resuelto y suficiente · `NR/I` = no resuelto / insuficiente · `RM` = requiere revisión manual.

| Doc. (ID) | Extracción de GLiNER2 | Resultado de la consolidación | Estado | Mejora / control aportado por la consolidación |
| :-- | :-- | :-- | :--: | :-- |
| **1 (`788347`)** | Caledonia Argentina Compañía de Seguros SA; CUIT/CUIL 3050003967-8 / CUIT/CUIL 3050003967-8 [incompleto] | ACEPTA: Caledonia Argentina Compañía de Seguros SA; CUIT/CUIL 3050003967-8 | **R/S** | GLiNER deja información incompleta; la consolidación recupera y vincula la razón social/identificador desde el fragmento y evita asociar identificadores aislados. |
| **2 (`789454`)** | UNGAR, NORBERTO HORACIO; CUIT/CUIL 20-10041809-7 / MARIA VIRGINIA RAFFO | ACEPTA: UNGAR, NORBERTO HORACIO; CUIT/CUIL 20-10041809-7 / DESCARTA: MARIA VIRGINIA RAFFO (tercero_fuerte) | **R/S** | Reconstruye el apellido omitido por GLiNER y separa al sujeto del oficio de la firmante/profesional. |
| **3 (`790063`)** | Marta Elisa PUGLIESE; DNI 4756818; CUIT/CUIL 27-04756818-3; rol causante | ACEPTA: Marta Elisa PUGLIESE; DNI 4756818; CUIT/CUIL 27-04756818-3; rol causante | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **4 (`790072`)** | GONZALEZ DAVID AVELINO; DNI 33903621; rol titular / GONZALEZ DAVID AVELINO; DNI 33903621 / Alejandro Luis Alberto Siliano; DNI 26874119; rol actor / Sra. RODRIGUEZ MAIRA ALEJANDRA; DNI 39550318 / CUIT/CUIL 30-50098787-8 [incompleto] | ACEPTA: GONZALEZ DAVID AVELINO; DNI 33903621; rol titular / DESCARTA: Alejandro Luis Alberto Siliano; DNI 26874119; rol actor (senales_insuficientes, sin_contexto_juridico, sin_repeticion) / DESCARTA: Sra. RODRIGUEZ MAIRA ALEJANDRA; DNI 39550318 (senales_insuficientes, sin_rol_juridico_fuerte, sin_contexto_juridico, sin_repeticion) | **R/S** | Deduplica predicciones repetidas del mismo fragmento y descarta personas autorizadas; no aumenta artificialmente la evidencia. |
| **5 (`790081`)** | PIZZERIA | DESCARTA: PIZZERIA (nombre_no_valido) / RECUPERA PARA REVISIÓN: PIZZERIA NAPOLES; CUIT/CUIL 20288024554 | **NR/I** + RM | GLiNER detecta solo «PIZZERIA». La consolidación reconstruye «PIZZERIA NAPOLES» + CUIT 20288024554, pero lo conserva para revisión manual por ambigüedad. |
| **6 (`790085`)** | SORIA, MARÍA FERNANDA; CUIT/CUIL 27-34953534-9 | ACEPTA: SORIA, MARÍA FERNANDA; CUIT/CUIL 27-34953534-9 | **R/S** | Reconstruye el apellido faltante y usa contexto positivo del pedido para reforzar la identidad correcta. |
| **7 (`790089`)** | Martin Ignacio Galvan; DNI 39054617 | ACEPTA: Martin Ignacio Galvan; DNI 39054617 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **8 (`790091`)** | Horacio Guillermo PÉREZ; DNI 22.513.908; rol demandado | ACEPTA: Horacio Guillermo PÉREZ; DNI 22.513.908; rol demandado | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **9 (`790092`)** | Franco Eduardo Cárdenas; DNI 32.851.047; CUIT/CUIL 20-32851047-3 | ACEPTA: Franco Eduardo Cárdenas; DNI 32.851.047; CUIT/CUIL 20-32851047-3 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **10 (`790094`)** | Arcadio Samuel Hamil García; DNI 37433769 | ACEPTA: Arcadio Samuel Hamil García; DNI 37433769 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **11 (`790097`)** | Sr. Romero Hector; DNI 34.472.193; rol actor | ACEPTA: Sr. Romero Hector; DNI 34.472.193; rol actor | **R/S** | Audita el rol predicho por GLiNER frente al contexto jurídico sin sobrescribir silenciosamente la predicción. |
| **12 (`790102`)** | ENDARA MARIANO ADRIÁN; DNI 38.804.970; CUIT/CUIL 20-38804970-8 | ACEPTA: ENDARA MARIANO ADRIÁN; DNI 38.804.970; CUIT/CUIL 20-38804970-8 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **13 (`790106`)** | NANCY SILVANA GRACIANO; DNI 27017871; CUIT/CUIL 27-27017871-0 / nombrada | ACEPTA: NANCY SILVANA GRACIANO; DNI 27017871; CUIT/CUIL 27-27017871-0 / DESCARTA: nombrada (nombre_no_valido) | **R/S** | Selecciona el sujeto correcto y filtra candidatos/terceros que no son objeto del oficio. |
| **14 (`790111`)** | Susana Esther Gigerey; DNI 44.379.117 | ACEPTA: Susana Esther Gigerey; DNI 44.379.117 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **15 (`790114`)** | ARIAS MARIA BELEN; DNI 37.128.726; rol demandada | ACEPTA: ARIAS MARIA BELEN; DNI 37.128.726; rol demandada | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **16 (`790115`)** | Sin candidato utilizable | Sin persona consolidada | **NR/I** | No fuerza una persona cuando la entrada fragmentada no aporta un candidato utilizable; deriva a revisión. |
| **17 (`790122`)** | Mariano Fabián Ferro; rol titular | DESCARTA: Mariano Fabián Ferro; rol titular (sin_identificador_verificable) | **NR/I** | GLiNER detecta Mariano Fabián Ferro y rol titular, pero al no existir DNI/CUIT/CUIL verificable la consolidación lo descarta conservadoramente. Queda como mejora futura incorporar CVU/alias con vínculo local. |
| **18 (`790129`)** | LOPEZ, JOSE LEONARDO; DNI 30500719 | ACEPTA: LOPEZ, JOSE LEONARDO; DNI 30500719 | **R/S** | Reconstruye literalmente el apellido omitido por GLiNER y conserva el DNI asociado. |
| **19 (`790136`)** | ANDRADE NORA; DNI 18223729 | ACEPTA: ANDRADE NORA; DNI 18223729 | **R/S** | Acepta a ANDRADE NORA y evita incorporar automáticamente personas vinculadas a cuentas de destino sin confirmar que sean objeto del pedido. |
| **20 (`790138`)** | JUAN JOSE CESARIO; DNI 33.660.482 | ACEPTA: JUAN JOSE CESARIO; DNI 33.660.482 | **R/S** | La nueva fragmentación ya aporta JUAN JOSE CESARIO + DNI 33.660.482; la consolidación valida el vínculo con el requerimiento y ahora resuelve correctamente el caso. |
| **21 (`780381`)** | Gabriela Karina Ledesma; CUIT/CUIL 27417562260 | ACEPTA: Gabriela Karina Ledesma; CUIT/CUIL 27417562260 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **22 (`780618`)** | Muñoz Marcos Damián; DNI 32.981.114; rol demandado / Tandil; rol actora | ACEPTA: Muñoz Marcos Damián; DNI 32.981.114; rol demandado / DESCARTA: Tandil; rol actora (nombre_no_valido) | **R/S** | Selecciona el sujeto correcto y filtra candidatos/terceros que no son objeto del oficio. |
| **23 (`780740`)** | LEANDRO ERAUSQUIN; DNI 34.753.007; rol actor | ACEPTA: LEANDRO ERAUSQUIN; DNI 34.753.007; rol actor | **R/S** | Completa información omitida o parcial de GLiNER mediante recuperación local segura: dni_local_adyacente. |
| **24 (`784519`)** | JUAN BELMAR SERRI; DNI 33.507.686 | ACEPTA: JUAN BELMAR SERRI; DNI 33.507.686 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **25 (`784524`)** | Adrian Delgado; DNI 43.922.338; rol titular | ACEPTA: Adrian Delgado; DNI 43.922.338; rol titular | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **26 (`784528`)** | MUÑOZ JOAQUIN DANIEL; DNI 40.948.975; CUIT/CUIL 20-40948975-4; rol titular | ACEPTA: MUÑOZ JOAQUIN DANIEL; DNI 40.948.975; CUIT/CUIL 20-40948975-4; rol titular | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **27 (`784530`)** | Rodrigo Exequiel Diaz; DNI 34.087.361; CUIT/CUIL 20-34087361-1 | ACEPTA: Rodrigo Exequiel Diaz; DNI 34.087.361; CUIT/CUIL 20-34087361-1 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **28 (`784536`)** | Tiago Alexander Méndez Mourelle; DNI 44.939.190 | ACEPTA: Tiago Alexander Méndez Mourelle; DNI 44.939.190 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **29 (`784537`)** | Pedro Pablo Sangoy / victima | ACEPTA: Pedro Pablo Sangoy / DESCARTA: victima (nombre_no_valido) | **R/S** | Selecciona el sujeto correcto y filtra candidatos/terceros que no son objeto del oficio. |
| **30 (`784558`)** | SANDRA DEL CARMEN CORDOBA; DNI 18.593.084 | ACEPTA: SANDRA DEL CARMEN CORDOBA; DNI 18.593.084 | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **31 (`784560`)** | Nancy Edith Difabio; DNI 18.516.749; rol titular | ACEPTA: Nancy Edith Difabio; DNI 18.516.749; rol titular | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **32 (`784570`)** | FEDERICO MARTIN DURBAS; DNI 31.637.995; rol demandada / Federico Martin Durbas; DNI 31.637.995; rol demandada | ACEPTA: Federico Martin Durbas; DNI 31.637.995; rol demandada | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **33 (`784585`)** | Carlos José MENDOZA HERNÁNDEZ; DNI 94.478.301 | ACEPTA: Carlos José MENDOZA HERNÁNDEZ; DNI 94.478.301 | **R/S** | Completa información omitida o parcial de GLiNER mediante recuperación local segura: dni_local_adyacente. |
| **34 (`784598`)** | Alejandro Bruno PINTO APARICIO; DNI 16.759.558; CUIT/CUIL 20-16759558-9; rol actor | ACEPTA: Alejandro Bruno PINTO APARICIO; DNI 16.759.558; CUIT/CUIL 20-16759558-9; rol actor | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **35 (`784617`)** | LAGOMARCINO ZORRILLA ALEJANDRO LIONEL; DNI 40736446 / LOURDES SOSA MANTENBERG M.P 9730; CUIT/CUIL 27-33481177-3 | ACEPTA: LAGOMARCINO ZORRILLA ALEJANDRO LIONEL; DNI 40736446 / DESCARTA: LOURDES SOSA MANTENBERG M.P 9730; CUIT/CUIL 27-33481177-3 (tercero_fuerte) | **R/S** | Selecciona el sujeto correcto y filtra candidatos/terceros que no son objeto del oficio. |
| **36 (`784627`)** | AGUSTIN FERREYRA; DNI 39261503; rol causante | ACEPTA: AGUSTIN FERREYRA; DNI 39261503; rol causante | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |
| **37 (`784633`)** | SILVINA SOLEDAD CARITA; DNI 27.694.948; rol actora / Silvina Soledad Carita; DNI 27.694.948 | ACEPTA: Silvina Soledad Carita; DNI 27.694.948; rol actora | **R/S** | Valida la extracción de GLiNER con contexto, asociación local de identificadores y evidencia del requerimiento. |

## Casos que muestran mejor el valor agregado

### 1. Reconstrucción de identidad

En varios documentos GLiNER2 identifica correctamente una parte de la entidad, pero no devuelve todos los componentes necesarios. La consolidación utiliza únicamente la evidencia local del fragmento para reconstruir la identidad sin inventar información. Ejemplos representativos son `789454` (reconstrucción de **UNGAR, NORBERTO HORACIO**), `790085` (**SORIA, MARÍA FERNANDA**) y `790129` (**LOPEZ, JOSE LEONARDO**).

### 2. Filtrado de terceros

La extracción NER puede detectar correctamente nombres e identificadores de personas que aparecen en el documento pero que **no son el objeto del oficio**. La consolidación incorpora reglas contextuales para separar al sujeto requerido de firmantes, profesionales, autorizados y otros intervinientes. Esto evita que una detección técnicamente correcta de GLiNER se transforme en una respuesta jurídica incorrecta.

### 3. Deduplicación

En `790072`, varias predicciones provenientes del mismo fragmento no se consideran evidencias independientes. La consolidación conserva la información, pero evita aumentar artificialmente la confianza por repeticiones del modelo.

### 4. Recuperación sin sobreaceptación

En `790081`, GLiNER2 detecta solamente **PIZZERIA**. El fragmento estructurado permite recuperar **PIZZERIA NAPOLES** y el CUIT `20288024554`. Sin embargo, la consolidación no convierte esa recuperación en una aceptación automática: la almacena en `identidades_recuperadas_revision_manual` porque la naturaleza y el alcance de la identidad requieren validación. Esto permite aumentar cobertura sin sacrificar precisión.

### 5. Mejora de fragmentación reflejada en el resultado final

El documento `790138` es una mejora concreta del nuevo lote. En la referencia anterior no había un fragmento útil para identificar al sujeto. En la corrida actual, GLiNER2 recibe/detecta **JUAN JOSE CESARIO** con DNI `33.660.482`, y la consolidación valida que la identidad está directamente vinculada al pedido de información. El documento pasa correctamente a **RESUELTO / suficiente**.

## Casos pendientes

- **`790115`**: el pedido está centrado en una cuenta identificada mediante `ID SELLER`, apodo y nombre de seller, no mediante una identidad personal tradicional con DNI/CUIT/CUIL. Se mantiene en revisión para no forzar una persona.
- **`790122`**: GLiNER2 detecta **Mariano Fabián Ferro** y el rol `titular`, y el fragmento contiene CVU/alias, pero la consolidación actual no trata esos identificadores financieros como sustitutos seguros de DNI/CUIT/CUIL. Es el principal candidato para una mejora futura mediante una regla de **identificador financiero local verificado**.
- **`790081`**: la identidad estructurada se recupera correctamente, pero se mantiene deliberadamente en revisión por ambigüedad.

## Conclusión

La consolidación no reemplaza a GLiNER2: **transforma una extracción probabilística de entidades en una salida más segura y utilizable para el dominio jurídico**. El principal beneficio no es únicamente recuperar más nombres, sino determinar cuáles de las entidades detectadas corresponden realmente al objeto del oficio, completar información cuando existe evidencia local suficiente y rechazar o derivar a revisión los casos ambiguos.

En este lote, el flujo alcanza **33/37 documentos resueltos automáticamente (89%)**, manteniendo un comportamiento conservador en los 4 casos restantes.