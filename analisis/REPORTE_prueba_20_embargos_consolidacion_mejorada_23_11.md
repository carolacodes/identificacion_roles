# Mejoras de Consolidación de Embargos

## 1. Objetivo

La consolidación de embargos se encuentra en una etapa de preparación para producción.

La primera prueba sobre 20 documentos nuevos mostró resultados favorables, pero también permitió identificar algunos comportamientos que podían mejorarse para que la consolidación fuera más robusta frente a documentos desconocidos.

El objetivo de esta actualización no fue resolver exclusivamente los documentos observados, sino incorporar mecanismos generales que permitan:

- recuperar información evidente omitida parcialmente por GLiNER;
- reconocer una mayor variedad de contextos jurídicos de embargo;
- mejorar la calidad del nombre representativo elegido;
- conservar la trazabilidad entre lo extraído por GLiNER y lo recuperado por la consolidación;
- explicar claramente los casos que requieren revisión manual;
- mantener sin cambios los casos que ya funcionaban correctamente.

El principio utilizado fue:

> La consolidación puede completar información únicamente cuando existe evidencia literal, local e inequívoca dentro del mismo fragmento. No debe inventar una identidad nueva ni reemplazar a GLiNER como extractor.

---

# 2. Resultado general antes y después

| Métrica                       | Consolidación anterior | Consolidación actual | Cambio |
| ----------------------------- | ---------------------: | -------------------: | -----: |
| Documentos                    |                     20 |                   20 |      — |
| `RESUELTO`                    |                     14 |                   15 |     +1 |
| `RESUELTO_MULTIPLE`           |                      3 |                    3 |      = |
| `NO_RESUELTO`                 |                      3 |                    2 |     -1 |
| Personas embargadas devueltas |                     20 |                   21 |     +1 |
| Suficientes                   |                     15 |                   17 |     +2 |
| Insuficientes                 |                      5 |                    3 |     -2 |
| Requieren revisión            |                      1 |                    1 |      = |
| Conflictos de identificador   |                      4 |                    4 |      = |

La proporción de documentos suficientes pasó de:

```text
15 / 20 = 75 %
```

a:

```text
17 / 20 = 85 %
```

sin reducir los controles de conflictos ni convertir resultados dudosos en resultados suficientes.

---

# 3. Mejoras incorporadas

## 3.1 Recuperación de apellido en nombres parciales

GLiNER puede detectar correctamente una persona pero devolver solamente parte del nombre.

Ejemplo:

```text
Fragmento:
HERRERA, ALEJANDRO MATÍAS, DNI 32.377.252

GLiNER:
ALEJANDRO MATÍAS
```

La consolidación ahora puede ampliar el nombre cuando encuentra literalmente la estructura:

```text
APELLIDO, NOMBRE + identificador
```

Resultado:

```text
HERRERA, ALEJANDRO MATÍAS
```

Este mecanismo se utiliza solamente cuando la asociación es inequívoca.

---

## 3.2 Recuperación estricta de apellido sin coma

También se agregó soporte para formatos como:

```text
CUAL JORGE LUIS
DNI/CUIT 34.084.389
```

cuando GLiNER devuelve solamente:

```text
JORGE LUIS
```

La recuperación es más restrictiva que en el formato con coma.

El token anterior debe cumplir condiciones estructurales y no puede tratarse de palabras como:

```text
SR
SRA
DR
DRA
DEMANDADO
EMBARGADO
ACTOR
TITULAR
DE
DEL
```

Además debe existir un identificador asociado localmente al nombre.

---

# 4. Recuperación local de identificadores

Se incorporó una lógica inspirada en la consolidación de oficios.

Si GLiNER encuentra una persona pero omite su DNI/CUIT, la consolidación puede recuperar el identificador siempre que se encuentre explícitamente asociado al nombre dentro del mismo fragmento.

Ejemplo:

```text
GLiNER:
GABRIEL ARNALDO RAFAEL
sin DNI

Fragmento:
ÑANCÚ, GABRIEL ARNALDO RAFAEL,
DNI/CUIT 32148218
```

Resultado:

```text
ÑANCÚ, GABRIEL ARNALDO RAFAEL
DNI 32148218
```

La recuperación no crea personas desde cero.

Siempre debe existir primero una entidad detectada por GLiNER que funcione como ancla.

---

# 5. Validación del tipo de identificador

La consolidación ahora comprueba que la etiqueta textual y la estructura del identificador sean compatibles.

| Texto                    | Interpretación               |
| ------------------------ | ---------------------------- |
| `DNI 32148218`           | DNI                          |
| `CUIT 20-29304863-1`     | CUIT/CUIL                    |
| `DNI/CUIT 32148218`      | DNI                          |
| `DNI/CUIT 23-13340228-4` | CUIT/CUIL                    |
| `DNI 20-21927954-0`      | No recuperar automáticamente |

Esto evita corregir silenciosamente documentos que contienen información contradictoria.

---

# 6. Asociación local del identificador

La búsqueda del DNI/CUIT no se realiza libremente sobre todo el fragmento.

Primero se localiza la posición del nombre y posteriormente se verifica que el identificador aparezca asociado localmente a esa persona.

Esto evita errores como:

```text
JUAN PEREZ DNI 30111222
MARIA LOPEZ DNI 33444555
```

y que accidentalmente se asocie:

```text
JUAN PEREZ
→ DNI 33444555
```

---

# 7. Mejora del nombre canónico

La consolidación ya agrupaba correctamente variantes como:

```text
ISA SEBASTIAN YAIR CUIT
Isa Sebastián Yair
```

pero anteriormente elegía:

```text
ISA SEBASTIAN YAIR CUIT
```

porque la selección del nombre canónico favorecía principalmente la variante con mayor cantidad de tokens.

Ahora se penalizan tokens administrativos que contaminan un span, por ejemplo:

```text
DNI
CUIT
CUIL
CBU
CVU
NRO
DOCUMENTO
```

La evidencia original no se modifica ni elimina.

Únicamente se elige una variante más limpia como nombre representativo.

Resultado:

```text
Isa Sebastián Yair
```

---

# 8. Ampliación del contexto jurídico

Se amplió la detección de contexto para contemplar distintas formas jurídicas de expresar una medida de embargo.

Se consideran relaciones entre conceptos como:

```text
fondos
sumas
cuentas
haberes
saldos
activos
depósitos
```

y expresiones como:

```text
tenga
posea
detente
perciba
pertenezca
de titularidad de
cuya titularidad
a nombre de
depositadas
a depositar en el futuro
```

Esto permite reconocer formulaciones como:

```text
sumas depositadas y/o a depositar en el futuro
que el Sr. Orlando Argentino Rossi
DNI 11.438.646,
tenga en vuestra entidad
```

sin necesitar una regla específica para ese documento.

---

# 9. Trazabilidad de las recuperaciones

La consolidación conserva ahora la diferencia entre:

```text
lo extraído originalmente por GLiNER
```

y:

```text
lo recuperado determinísticamente por consolidación
```

Entre los campos incorporados se encuentran:

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

Ejemplo real:

```json
{
  "nombre_detectado": "ÑANCÚ, GABRIEL ARNALDO RAFAEL",
  "nombre_original_gliner": "GABRIEL ARNALDO RAFAEL",

  "dni_detectado": "32148218",
  "dni_original_gliner": "",

  "nombre_recuperado": true,
  "dni_recuperado": true,

  "metodos_recuperacion": ["apellido_antes_nombre", "dni_local_adyacente"],

  "etiqueta_identificador_original": "DNI/CUIT"
}
```

Esta información permite auditar posteriormente qué información provino del modelo y cuál fue enriquecida por reglas determinísticas.

---

# 10. Notas de revisión manual

También se incorporó una explicación estructurada para los documentos que requieren revisión.

Además de:

```text
requiere_revision
```

ahora pueden aparecer:

```text
revision_manual_motivos
revision_manual_descripcion
```

Ejemplo:

```json
{
  "requiere_revision": true,

  "revision_manual_motivos": [
    {
      "codigo": "conflicto_identificador",
      "descripcion": "Se detectaron identidades incompatibles que comparten un DNI o CUIT/CUIL. Revisar las asociaciones antes de utilizar el resultado."
    }
  ]
}
```

Esto mejora la interpretabilidad del sistema sin modificar automáticamente un caso dudoso.

---

# 11. Comparación de los 20 documentos nuevos

|   Doc. |       ID | Consolidación anterior                                                                                                       | Consolidación actual                                                                                                         | Resultado del cambio                                                                             |
| -----: | -------: | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
|  **1** | `789511` | `NO_RESUELTO`, insuficiente. `s6fRMNN0z` fue descartado como nombre inválido.                                                | `NO_RESUELTO`, insuficiente. El mismo código continúa descartado.                                                            | ✅ **Sin cambios.** La protección contra nombres basura sigue funcionando.                       |
|  **2** | `789784` | `WHITE SHIP S.R.L.`, CUIT `30-71606996-2`. `RESUELTO`, suficiente.                                                           | Mismo resultado.                                                                                                             | ✅ **Sin cambios.** Persona jurídica correctamente mantenida.                                    |
|  **3** | `789892` | BRAULIO MAXIMILIANO SOPLANES y JULIO ALBERTO SOPLANES. `RESUELTO_MULTIPLE`, suficiente.                                      | Mismos dos embargados.                                                                                                       | ✅ **Sin cambios.** La recuperación nueva no fusionó personas diferentes.                        |
|  **4** | `790065` | Dos personas. Para Isa elegía `ISA SEBASTIAN YAIR CUIT`.                                                                     | Dos personas. Ahora devuelve `Isa Sebastián Yair`.                                                                           | ✅ **Mejora.** Nombre canónico limpio; identidad y CUIT permanecen iguales.                      |
|  **5** | `790073` | `NIETO DE LA PUENTE ROXANA`, suficiente. El código `1mHrm5AP8` era descartado.                                               | Mismo resultado.                                                                                                             | ✅ **Sin cambios.** Sigue rechazando el código de validación.                                    |
|  **6** | `790090` | Orlando Argentino ROSSI era candidato correcto, pero terminaba `NO_RESUELTO` por `sin_contexto_juridico` y `sin_repeticion`. | `Orlando Argentino ROSSI`, DNI `11.438.646`, `RESUELTO`, suficiente.                                                         | ✅ **Resuelto.** El nuevo contexto jurídico reconoce la relación `sumas ... que X tenga`.        |
|  **7** | `790107` | `RESUELTO_MULTIPLE`, insuficiente por `conflicto_identificador`.                                                             | Mismo resultado e identidades. Ahora incorpora además una nota explícita de revisión manual.                                 | ✅ **Sin cambio en decisión; mejora de trazabilidad.** El caso sigue protegido.                  |
|  **8** | `790119` | `Mario Alberto GALLARDO`, DNI `26.996.352`, suficiente.                                                                      | Mismo resultado.                                                                                                             | ✅ **Sin cambios.**                                                                              |
|  **9** | `790120` | `Noelia Soledad CARDENAS`, DNI `36.307.261`, suficiente.                                                                     | Mismo resultado.                                                                                                             | ✅ **Sin cambios.**                                                                              |
| **10** | `790126` | `CARLOS GARDEL MORALES MARTÍNEZ`, DNI `92.726.724`, suficiente.                                                              | Mismo resultado.                                                                                                             | ✅ **Sin cambios.**                                                                              |
| **11** | `790128` | `ALEJANDRO MATÍAS`, DNI `32.377.252`.                                                                                        | `HERRERA, ALEJANDRO MATÍAS`, mismo DNI.                                                                                      | ✅ **Mejora.** Recuperación literal del apellido omitido por GLiNER.                             |
| **12** | `790130` | `JARA MIRIAM LILIANA ANTONIA`, DNI `16.284.693`, suficiente.                                                                 | Mismo resultado.                                                                                                             | ✅ **Sin cambios.**                                                                              |
| **13** | `790131` | `NO_RESUELTO`, sin candidatos de GLiNER.                                                                                     | `NO_RESUELTO`, sin candidatos.                                                                                               | ✅ **Sin cambios.** La consolidación no crea personas cuando no existe ancla de GLiNER.          |
| **14** | `790135` | `GABRIEL ARNALDO RAFAEL`, sin identificador. `RESUELTO` pero insuficiente por `evidencia_unica_debil`.                       | `ÑANCÚ, GABRIEL ARNALDO RAFAEL`, DNI `32148218`. `RESUELTO`, suficiente.                                                     | ✅ **Resuelto.** Recuperó apellido + DNI explícitos en el fragmento.                             |
| **15** | `790137` | `ROLDAN, GUSTAVO ALEJANDRO`, CUIT `20-18521291-3`, suficiente.                                                               | Mismo resultado.                                                                                                             | ✅ **Sin cambios.**                                                                              |
| **16** | `790140` | `FERNANDEZ AUGUSTO ELIO`, sin identificador, suficiente por contexto + rol.                                                  | Mismo resultado. La recuperación detecta `DNI. 20-21927954-0` pero la bloquea por incompatibilidad entre etiqueta y formato. | ✅ **Sin cambio y nueva protección.** No convierte silenciosamente un supuesto DNI en CUIT.      |
| **17** | `790142` | `ELIDA MAGDALENA`, CUIT/CUIL `23-13340228-4`.                                                                                | `ARANDA, ELIDA MAGDALENA`, mismo identificador.                                                                              | ✅ **Mejora.** Recuperación literal de apellido.                                                 |
| **18** | `790329` | `JORGE LUIS`, DNI `34.084.389`.                                                                                              | `CUAL JORGE LUIS`, mismo DNI.                                                                                                | ✅ **Mejora.** Recuperación estricta del token anterior sin coma.                                |
| **19** | `790334` | `ROFFE BARBARA`, DNI `24.089.292`, suficiente.                                                                               | Mismo resultado.                                                                                                             | ✅ **Sin cambios.**                                                                              |
| **20** | `790338` | `CARRIZO ANDREA LILIANA`, DNI `24.075.107`. Los autorizados eran descartados.                                                | Mismo embargado y mismos terceros descartados.                                                                               | ✅ **Sin cambios.** La nueva recuperación no fortaleció incorrectamente la lista de autorizados. |

---

# 12. Documentos que cambiaron

De los 20 documentos:

```text
14 documentos
→ resultado final idéntico

6 documentos
→ presentaron mejoras esperadas
```

Los documentos modificados fueron:

| Doc. | Tipo de mejora                  |
| ---: | ------------------------------- |
|    4 | Selección del nombre canónico   |
|    6 | Ampliación de contexto jurídico |
|   11 | Recuperación de apellido        |
|   14 | Recuperación de apellido + DNI  |
|   17 | Recuperación de apellido        |
|   18 | Recuperación estricta sin coma  |

No apareció ningún cambio inesperado en los otros 14 documentos.

---

# 13. Casos que continúan insuficientes

La nueva consolidación deja únicamente tres documentos insuficientes.

|            Doc. | Motivo                                                           | Evaluación                                                                              |
| --------------: | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
|  **1 — 789511** | GLiNER solamente produjo un código de validación como candidato. | Correcto mantener `NO_RESUELTO`.                                                        |
|  **7 — 790107** | Varias identidades incompatibles comparten DNI/CUIT.             | Correcto mantener insuficiente y enviar a revisión.                                     |
| **13 — 790131** | No existen candidatos GLiNER en los fragmentos procesados.       | Correcto mantener `NO_RESUELTO`; la consolidación no debe crear identidades desde cero. |

Estos casos representan fallos seguros.

La consolidación prefiere no producir una respuesta confiable cuando la evidencia disponible es insuficiente o contradictoria.

---

# 14. Comportamientos que permanecieron protegidos

Las mejoras nuevas no alteraron los comportamientos anteriores considerados correctos:

| Comportamiento                                     | Estado                                              |
| -------------------------------------------------- | --------------------------------------------------- |
| Personas jurídicas                                 | ✅ Conservado                                       |
| Múltiples embargados reales                        | ✅ Conservado                                       |
| Personas diferentes con identificadores diferentes | ✅ Conservado                                       |
| Fusión de variantes de una misma identidad         | ✅ Conservado                                       |
| Rechazo de códigos como nombres                    | ✅ Conservado                                       |
| Rechazo de terceros/autorizados                    | ✅ Conservado                                       |
| Conflictos de identificadores                      | ✅ Conservado                                       |
| Casos sin candidatos                               | ✅ No se inventan personas                          |
| Identificadores contradictorios                    | ✅ No se corrigen automáticamente                   |
| Suficiencia                                        | ✅ Continúa funcionando como mecanismo de seguridad |

---

# 15. Arquitectura actual

La consolidación puede representarse actualmente como:

```text
GLiNER
   │
   ▼
Candidatos extraídos
   │
   ▼
RECUPERACIÓN LOCAL DETERMINÍSTICA
   │
   ├── completar apellido
   ├── completar nombre sin coma con restricciones
   ├── recuperar identificador local
   ├── validar DNI/CUIT
   └── registrar trazabilidad
   │
   ▼
Construcción de evidencias
   │
   ▼
Agrupación de candidatos
   │
   ▼
Fusión transitiva de variantes
   │
   ▼
Selección de nombre canónico
   │
   ▼
Evaluación de contexto jurídico
   │
   ▼
Reglas de aceptación
   │
   ▼
Evaluación de suficiencia
   │
   ├── suficiente
   │
   └── insuficiente / fallback
            │
            ▼
       Revisión manual
       con motivo explicable
```

La recuperación de información no reemplaza las reglas de aceptación.

Una persona que recupera un DNI continúa necesitando superar normalmente las reglas de:

```text
rol jurídico
contexto
repetición
tercero fuerte
conflictos
score
suficiencia
```

---

# 16. Conclusión

La actualización mejoró los resultados de la prueba sin volver más permisiva la consolidación de manera general.

El cambio principal fue pasar de:

```text
75 % de documentos suficientes
```

a:

```text
85 % de documentos suficientes
```

mientras permanecieron iguales:

```text
cantidad de documentos en revisión
cantidad de conflictos de identificadores
resultados correctos de los otros 14 documentos
```

Los cambios observados corresponden exactamente a los problemas que se pretendían resolver:

```text
nombre canónico contaminado
contexto jurídico no reconocido
nombres parciales
identificadores omitidos por GLiNER
```

La nueva consolidación conserva además trazabilidad suficiente para conocer qué información produjo originalmente GLiNER y qué información fue recuperada posteriormente mediante reglas determinísticas.

Los casos ambiguos continúan sin resolverse automáticamente y, cuando corresponde, incluyen una explicación de revisión manual.

Por lo tanto, esta versión representa una mejora de la información extraída y de la capacidad de generalización de la consolidación sin sacrificar las protecciones incorporadas previamente.
