# Mejora de contexto jurídico — Consolidación de Embargos

## 1. Objetivo de esta versión

Esta actualización de la consolidación de embargos tiene como objetivo mejorar el reconocimiento de **contextos jurídicos positivos** cuando la persona embargada ya fue correctamente detectada por GLiNER, pero el fragmento utiliza una formulación jurídica distinta de las contempladas hasta el momento.

La mejora surge a partir del documento:

```text
790131 — ALBARIÑO, JIMENA CECILIA
```

En una ejecución anterior, el fragmentador no proporcionaba a GLiNER un fragmento útil con la persona embargada.

Luego de actualizar los fragmentos, GLiNER comenzó a extraer correctamente:

```text
Sr/Sra. ALBARIÑO, JIMENA CECILIA
DNI 37796425
rol = embargado
```

Sin embargo, la consolidación seguía descartando el candidato porque no reconocía la expresión:

```text
dar cumplimiento con el embargo ordenado
```

como contexto jurídico positivo.

Por este motivo se amplió `PATRONES_CONTEXTO_POSITIVO` con una nueva familia general de expresiones.

---

# 2. Problema detectado

El fragmento del documento 13 contiene:

```text
de dar cumplimiento con el embargo ordenado,
Sr/Sra. ALBARIÑO, JIMENA CECILIA –
DNI N° 37796425
```

GLiNER produjo correctamente:

```text
nombre = Sr/Sra. ALBARIÑO, JIMENA CECILIA
dni = 37796425
rol = embargado
```

Pero la consolidación anterior evaluaba:

```text
rol_juridico_fuerte = true
tiene_identificador = true
contexto_juridico_positivo = false
repeticion = false
```

Por lo tanto el candidato era descartado con:

```text
senales_insuficientes
sin_contexto_juridico
sin_repeticion
```

El problema no estaba en GLiNER ni en el identificador.

El problema estaba exclusivamente en la detección de contexto jurídico.

---

# 3. Mejora implementada

Se agregó una nueva familia dentro de:

```python
PATRONES_CONTEXTO_POSITIVO
```

para reconocer expresiones del tipo:

```text
dar cumplimiento con el embargo ordenado
cumplimiento del embargo ordenado
cumplimiento al embargo ordenado

dar cumplimiento con el embargo dispuesto
cumplimiento del embargo dispuesto

dar cumplimiento con el embargo decretado
cumplimiento al embargo decretado
```

La expresión incorporada es:

```python
r"\b(?:dar\s+)?cumplimiento\s+"
r"(?:con\s+el|del|al)\s+embargo\s+"
r"(?:ordenad[oa]|dispuest[oa]|decretad[oa])\b"
```

Esta regla no depende del nombre de la persona ni del documento analizado.

Por lo tanto, puede utilizarse sobre futuros documentos que empleen la misma familia de redacción jurídica.

---

# 4. Restricción de seguridad

No se agregó una regla genérica como:

```text
dar cumplimiento con lo ordenado
```

porque esa expresión puede aparecer en distintos tipos de requerimientos judiciales y no necesariamente implica un embargo.

La nueva regla exige simultáneamente:

```text
cumplimiento
+
embargo
+
ordenado / dispuesto / decretado
```

Por ejemplo:

```text
dar cumplimiento con lo ordenado
```

no se considera contexto positivo.

Mientras que:

```text
dar cumplimiento con el embargo ordenado
```

sí se considera contexto jurídico positivo.

Esto reduce el riesgo de aumentar falsos positivos.

---

# 5. Reglas de aceptación que no fueron modificadas

Esta actualización **no cambia**:

- thresholds;
- scores mínimos;
- fusión de personas;
- recuperación de nombres;
- recuperación de identificadores;
- reglas de terceros;
- validación de nombres;
- conflictos de identificadores;
- suficiencia;
- revisión manual.

Solo se amplió el conjunto de fórmulas jurídicas reconocidas.

Por lo tanto, el candidato sigue necesitando cumplir las reglas normales de consolidación.

En el caso de Jimena Albariño:

```text
rol fuerte ✅
DNI ✅
contexto jurídico ✅
tercero fuerte ❌
conflictos ❌
```

es suficiente para resolver correctamente la identidad aunque exista una sola evidencia.

---

# 6. Comparación de los 20 documentos nuevos

La última ejecución previa ya había mejorado los documentos 4, 6, 11, 14, 17 y 18.

En esta nueva versión solamente se espera un cambio adicional:

```text
Documento 13 — 790131
```

Los otros 19 documentos deben conservar el comportamiento de la versión anterior.

|   Doc. |       ID | Consolidación antes de las mejoras                                | Consolidación previa a esta versión                                                                                                         | Consolidación nueva                                                                               | Resultado                                                         |
| -----: | -------: | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
|  **1** | `789511` | `NO_RESUELTO`. Código `s6fRMNN0z` descartado.                     | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios. Continúa rechazando nombres inválidos.            |
|  **2** | `789784` | `WHITE SHIP S.R.L.`, CUIT `30-71606996-2`, suficiente.            | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
|  **3** | `789892` | BRAULIO MAXIMILIANO SOPLANES + JULIO ALBERTO SOPLANES.            | Mismos dos embargados.                                                                                                                      | Mismos dos embargados.                                                                            | ✅ Sin cambios. Continúa conservando múltiples personas reales.   |
|  **4** | `790065` | Elegía `ISA SEBASTIAN YAIR CUIT` como nombre canónico.            | `Isa Sebastián Yair`.                                                                                                                       | `Isa Sebastián Yair`.                                                                             | ✅ Mejora anterior conservada.                                    |
|  **5** | `790073` | `NIETO DE LA PUENTE ROXANA`; código `1mHrm5AP8` descartado.       | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
|  **6** | `790090` | Orlando Rossi quedaba `NO_RESUELTO` por falta de contexto.        | `Orlando Argentino ROSSI`, DNI `11.438.646`, `RESUELTO`, suficiente.                                                                        | Mismo resultado.                                                                                  | ✅ Mejora anterior conservada.                                    |
|  **7** | `790107` | `RESUELTO_MULTIPLE`, insuficiente por conflicto de identificador. | Mismo resultado + nota de revisión manual.                                                                                                  | Mismo resultado.                                                                                  | ✅ Sin cambios en decisión. Protección conservada.                |
|  **8** | `790119` | `Mario Alberto GALLARDO`, DNI `26.996.352`.                       | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
|  **9** | `790120` | `Noelia Soledad CARDENAS`, DNI `36.307.261`.                      | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
| **10** | `790126` | `CARLOS GARDEL MORALES MARTÍNEZ`, DNI `92.726.724`.               | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
| **11** | `790128` | `ALEJANDRO MATÍAS`.                                               | `HERRERA, ALEJANDRO MATÍAS`.                                                                                                                | Mismo resultado.                                                                                  | ✅ Recuperación de apellido conservada.                           |
| **12** | `790130` | `JARA MIRIAM LILIANA ANTONIA`, DNI `16.284.693`.                  | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
| **13** | `790131` | Inicialmente no existían candidatos útiles de GLiNER.             | GLiNER ya detecta `Sr/Sra. ALBARIÑO, JIMENA CECILIA`, DNI `37796425`, pero consolidación lo deja `NO_RESUELTO` por `sin_contexto_juridico`. | **Debe pasar a `RESUELTO`, suficiente**, al reconocer `dar cumplimiento con el embargo ordenado`. | ✅ **Nueva mejora de esta versión.**                              |
| **14** | `790135` | `GABRIEL ARNALDO RAFAEL`, sin identificador; insuficiente.        | `ÑANCÚ, GABRIEL ARNALDO RAFAEL`, DNI `32148218`, suficiente.                                                                                | Mismo resultado.                                                                                  | ✅ Recuperación de apellido + DNI conservada.                     |
| **15** | `790137` | `ROLDAN, GUSTAVO ALEJANDRO`, CUIT `20-18521291-3`.                | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
| **16** | `790140` | `FERNANDEZ AUGUSTO ELIO`, sin identificador.                      | Mismo resultado; recuperación bloqueada por `DNI` con estructura de CUIT.                                                                   | Mismo resultado.                                                                                  | ✅ Protección conservada.                                         |
| **17** | `790142` | `ELIDA MAGDALENA`.                                                | `ARANDA, ELIDA MAGDALENA`.                                                                                                                  | Mismo resultado.                                                                                  | ✅ Recuperación de apellido conservada.                           |
| **18** | `790329` | `JORGE LUIS`.                                                     | `CUAL JORGE LUIS`.                                                                                                                          | Mismo resultado.                                                                                  | ✅ Recuperación sin coma conservada.                              |
| **19** | `790334` | `ROFFE BARBARA`, DNI `24.089.292`.                                | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios.                                                   |
| **20** | `790338` | `CARRIZO ANDREA LILIANA`; autorizados descartados.                | Mismo resultado.                                                                                                                            | Mismo resultado.                                                                                  | ✅ Sin cambios. Los terceros continúan correctamente descartados. |

---

# 7. Evolución específica del documento 13

## Primera ejecución

Los fragmentos originales no contenían correctamente la información de la persona embargada.

Resultado:

```text
GLiNER
→ sin candidato útil

Consolidación
→ NO_RESUELTO
```

En este punto la consolidación actuaba correctamente porque no debía inventar una persona.

---

## Segunda ejecución después de mejorar los fragmentos

El nuevo fragmento contiene:

```text
de dar cumplimiento con el embargo ordenado,
Sr/Sra. ALBARIÑO, JIMENA CECILIA –
DNI N° 37796425
```

GLiNER devuelve:

```text
nombre:
Sr/Sra. ALBARIÑO, JIMENA CECILIA

DNI:
37796425

rol:
embargado
```

Pero la consolidación anterior evaluaba:

```text
rol_juridico_fuerte = true
tiene_identificador = true
contexto_juridico_positivo = false
repeticion = false
```

Resultado:

```text
NO_RESUELTO
```

---

## Nueva consolidación

Con la nueva familia de contexto:

```text
dar cumplimiento con el embargo ordenado
```

pasa a ser reconocida como una fórmula jurídica válida.

Las señales esperadas quedan:

```text
rol_juridico_fuerte = true
tiene_identificador = true
contexto_juridico_positivo = true
repeticion = false
```

Y la regla general existente:

```text
contexto jurídico + rol jurídico fuerte
```

permite aceptar el candidato.

Resultado esperado:

```text
estado:
RESUELTO

suficiente:
true

nombre:
Sr/Sra. ALBARIÑO, JIMENA CECILIA

DNI:
37796425

motivos:
- contexto_juridico
- rol_juridico_fuerte
- identificador
```

---

# 8. Evolución global de la prueba

## Primera consolidación de los 20 documentos

```text
RESUELTO: 14
RESUELTO_MULTIPLE: 3
NO_RESUELTO: 3

SUFICIENTES: 15
INSUFICIENTES: 5
```

## Después de las mejoras de recuperación y contexto

```text
RESUELTO: 15
RESUELTO_MULTIPLE: 3
NO_RESUELTO: 2

SUFICIENTES: 17
INSUFICIENTES: 3
```

## Resultado esperado con esta nueva mejora

Si el documento 13 se comporta como se espera:

```text
RESUELTO: 16
RESUELTO_MULTIPLE: 3
NO_RESUELTO: 1

SUFICIENTES: 18
INSUFICIENTES: 2
```

Esto equivaldría a:

```text
18 / 20 = 90 % de documentos suficientes
```

sin modificar thresholds ni relajar las reglas generales de aceptación.

---

# 9. Casos que deberían continuar insuficientes

Después de esta mejora deberían permanecer únicamente dos casos problemáticos.

## Documento 1 — `789511`

GLiNER devuelve:

```text
s6fRMNN0z
```

que corresponde a un código de verificación.

La consolidación correctamente lo descarta como:

```text
nombre_no_valido
```

Por lo tanto debe permanecer:

```text
NO_RESUELTO
```

---

## Documento 7 — `790107`

GLiNER produce asociaciones incompatibles entre:

```text
NELSON DARÍO BRIZUELA
MARIA XIMENA RODRIGUEZ COSTANTINO
ROCIO BELEN TARRES
```

compartiendo identificadores.

La consolidación detecta:

```text
conflicto_identificador
```

y mantiene:

```text
suficiente = false
requiere_revision = true
```

Este comportamiento debe conservarse porque representa una falla segura.

---

# 10. Trazabilidad y revisión manual

Esta versión continúa conservando todas las mejoras anteriores de trazabilidad.

Entre ellas:

```text
nombre_original_gliner
dni_original_gliner
cuit_cuil_original_gliner

nombre_recuperado
dni_recuperado
cuit_cuil_recuperado

metodos_recuperacion
etiqueta_identificador_original
recuperacion_bloqueada_motivo
```

También continúa incorporando:

```text
requiere_revision
revision_manual_motivos
revision_manual_descripcion
```

para los casos que no pueden utilizarse automáticamente.

La nueva mejora del documento 13 no modifica ninguna de estas estructuras.

---

# 11. Principio mantenido

La consolidación continúa funcionando bajo el mismo criterio:

```text
GLiNER
   ↓
candidatos
   ↓
recuperación local determinística
   ↓
agrupación y fusión
   ↓
contexto jurídico
   ↓
reglas de aceptación
   ↓
suficiencia
   ↓
revisión manual cuando corresponde
```

La nueva expresión de contexto únicamente mejora la etapa:

```text
contexto jurídico
```

No agrega candidatos nuevos ni modifica identidades.

---

# 12. Conclusión

La nueva versión incorpora una mejora pequeña pero generalizable en la detección de contexto jurídico.

El caso que motivó el cambio utiliza:

```text
dar cumplimiento con el embargo ordenado
```

pero la implementación permite reconocer también distintas variantes de:

```text
cumplimiento del embargo ordenado
cumplimiento al embargo ordenado
cumplimiento del embargo dispuesto
cumplimiento con el embargo decretado
```

La modificación:

- no cambia thresholds;
- no modifica reglas de aceptación;
- no crea personas;
- no altera agrupaciones;
- no modifica conflictos;
- no afecta recuperaciones anteriores;
- no convierte expresiones genéricas de cumplimiento en contexto de embargo.

Por lo tanto, se mantiene el objetivo de que la consolidación funcione como una **caja negra determinística capaz de adaptarse a distintas redacciones jurídicas**, en lugar de resolver únicamente documentos previamente conocidos.

El único cambio esperado en la prueba actual de 20 documentos es el documento `790131`, que debería pasar de `NO_RESUELTO` a `RESUELTO` suficiente debido al reconocimiento de una fórmula jurídica que anteriormente no estaba contemplada.
