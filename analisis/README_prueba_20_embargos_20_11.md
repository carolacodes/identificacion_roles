# Prueba de generalización — Extracción GLiNER + Consolidación de Embargos

## Objetivo

Esta prueba se realizó sobre **20 documentos de embargo nuevos**, distintos de los 80 documentos utilizados previamente para estudiar y ajustar la lógica de consolidación.

El objetivo principal es evaluar si el flujo actual puede funcionar como una **caja negra en producción**, es decir, recibir documentos con estructuras y redacciones desconocidas y resolver correctamente la identidad de las personas embargadas sin depender de reglas ajustadas exclusivamente a los casos previamente estudiados.

El flujo evaluado fue:

```text
Documentos
    ↓
Generación de fragmentos
    ↓
GLiNER2 Multi
    ↓
Candidatos extraídos
    ↓
Consolidación determinística
    ↓
RESUELTO / RESUELTO_MULTIPLE / NO_RESUELTO
    ↓
SUFICIENTE / INSUFICIENTE
```

---

# 1. Configuración utilizada

Se utilizó el experimento:

```yaml
multi_v7_fragmentos_thr50:
  model: gliner2_multi
  schema: schema_v7_persona_embargada_fragmentos

  input_mode: fragmentos
  text_column: fragmento

  threshold: 0.50

  filters:
    categoria:
      - Datos_Embargado
```

La ejecución procesó únicamente los fragmentos clasificados como `Datos_Embargado`.

La consolidación se ejecutó posteriormente sin modificar sus reglas, con el objetivo de comprobar cómo generalizaba sobre documentos nuevos.

---

# 2. Resultado general

| Resultado                              | Cantidad |
| -------------------------------------- | -------: |
| Documentos evaluados                   |       20 |
| `RESUELTO`                             |       14 |
| `RESUELTO_MULTIPLE`                    |        3 |
| `NO_RESUELTO`                          |        3 |
| Personas embargadas devueltas          |       20 |
| Documentos suficientes                 |       15 |
| Documentos insuficientes               |        5 |
| Documentos que requieren revisión      |        1 |
| Conflictos de identificador detectados |        4 |

La mayoría de los documentos fueron resueltos correctamente por el flujo actual.

Los casos problemáticos no corresponden todos a errores de consolidación. Se identificaron problemas provenientes de tres etapas diferentes:

```text
1. Fragmentación
2. Extracción de GLiNER
3. Consolidación
```

Por esta razón, no resulta conveniente modificar la consolidación automáticamente ante cada error observado.

---

# 3. Análisis de casos relevantes

|            Doc. | GLiNER extrajo                                                                                                                                                                          | Qué se esperaba de la consolidación                                                                                        | Qué hizo la consolidación                                                                                                                             | Mejora necesaria                                                                                                                                         |
| --------------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  **1 — 789511** | Extrajo `s6fRMNN0z` como nombre y rol `embargado`. El verdadero sujeto, `ROMERO FERNANDO SALUSTIANO`, no estaba disponible en los fragmentos útiles.                                    | Rechazar el código porque no corresponde a una persona y no inventar un embargado.                                         | ✅ Lo descartó como `nombre_no_valido` y dejó el documento `NO_RESUELTO`.                                                                             | **Ninguna en consolidación.** El problema está en la fragmentación/entrada de GLiNER.                                                                    |
|  **2 — 789784** | `WHITE SHIP S.R.L.`, CUIT `30-71606996-2`, rol `titular`.                                                                                                                               | Reconocer correctamente una persona jurídica como embargada.                                                               | ✅ `RESUELTO`, suficiente, una persona.                                                                                                               | Ninguna. Buen caso de generalización sobre personas jurídicas.                                                                                           |
|  **3 — 789892** | `BRAULIO MAXIMILIANO SOPLANES`, DNI `29.784.922`, y `JULIO ALBERTO SOPLANES`, DNI `13.080.347`.                                                                                         | Mantener a ambos como personas diferentes y no fusionarlos por compartir apellido.                                         | ✅ `RESUELTO_MULTIPLE`, 2 embargados reales, suficiente.                                                                                              | Ninguna. Confirma que la fusión transitiva no está fusionando personas diferentes.                                                                       |
|  **4 — 790065** | `JACINTA GIMENEZ` y `ISA SEBASTIAN YAIR`. Una variante fue extraída como `ISA SEBASTIAN YAIR CUIT`.                                                                                     | Consolidar las variantes de cada persona y devolver dos embargados.                                                        | ✅ Detectó 2 personas y fusionó correctamente las variantes. ⚠️ Eligió `ISA SEBASTIAN YAIR CUIT` como nombre representativo.                          | **Mejorar la selección del nombre canónico** penalizando tokens administrativos finales como `CUIT`, `CUIL` o `DNI`.                                     |
|  **5 — 790073** | `NIETO DE LA PUENTE ROXANA`, CUIT `27-29138049-8`, rol `demandado`. También apareció un código de validación como posible nombre.                                                       | Mantener al demandado y eliminar el código basura.                                                                         | ✅ Resolvió a Roxana y descartó `1mHrm5AP8` como `nombre_no_valido`.                                                                                  | Ninguna. La validación incorporada originalmente para casos como `dato` generalizó correctamente.                                                        |
|  **6 — 790090** | `Orlando Argentino ROSSI`, DNI `11.438.646`, rol `embargado`.                                                                                                                           | Aceptarlo como embargado: nombre válido + DNI + rol fuerte representan evidencia clara.                                    | ❌ Lo descartó por `senales_insuficientes`, `sin_contexto_juridico` y `sin_repeticion`.                                                               | **Sí requiere estudio.** Ampliar el contexto jurídico positivo para construcciones como `sumas depositadas y/o a depositar ... que el Sr./Sra. X tenga`. |
|  **7 — 790107** | Detectó correctamente a `NELSON DARÍO BRIZUELA`, pero también asoció erróneamente su DNI a `MARIA XIMENA RODRIGUEZ COSTANTINO` y `ROCIO BELEN TARRES`.                                  | Evitar considerar seguro el resultado ante identidades incompatibles compartiendo identificadores.                         | ✅ Detectó conflictos de identificador, dejó el resultado insuficiente y solicitó fallback/revisión.                                                  | No es prioritario modificar consolidación. GLiNER produjo asociaciones incorrectas, pero la consolidación **falló de forma segura**.                     |
| **11 — 790128** | Extrajo `ALEJANDRO MATÍAS` aunque el fragmento decía `HERRERA, ALEJANDRO MATÍAS`.                                                                                                       | Idealmente devolver el nombre completo.                                                                                    | ⚠️ Consolidó correctamente lo que recibió y lo consideró suficiente, pero no puede recuperar automáticamente `HERRERA` porque GLiNER omitió ese span. | Problema principalmente de **extracción GLiNER**, no de consolidación. Estudiar nombres `APELLIDO, NOMBRE`.                                              |
| **13 — 790131** | No produjo candidatos para la persona embargada. El documento completo contiene `ALBARIÑO, JIMENA CECILIA`, DNI `37796425`, pero esa información no llegó en los fragmentos procesados. | No inventar una identidad inexistente en las entradas recibidas.                                                           | ✅ `NO_RESUELTO`, sin candidatos.                                                                                                                     | **Ninguna en consolidación.** Revisar generación/selección de fragmentos.                                                                                |
| **14 — 790135** | Extrajo `GABRIEL ARNALDO RAFAEL`, perdiendo `ÑANCÚ`, y no obtuvo el identificador.                                                                                                      | Aceptar la evidencia jurídica pero evitar considerar completamente confiable una identidad incompleta con evidencia única. | ✅ `RESUELTO`, pero insuficiente por `evidencia_unica_debil`.                                                                                         | Principalmente problema de GLiNER. Estudiar extracción de nombres con formato `APELLIDO, NOMBRES`.                                                       |
| **17 — 790142** | Extrajo `ELIDA MAGDALENA` aunque el texto decía `ARANDA, ELIDA MAGDALENA`.                                                                                                              | Reconocer a la persona pero idealmente conservar el nombre completo.                                                       | ⚠️ `RESUELTO` y suficiente porque recibió rol fuerte, identificador y contexto válido.                                                                | Problema principalmente de **GLiNER**. Mismo patrón de apellido omitido.                                                                                 |
| **18 — 790329** | Extrajo `JORGE LUIS` cuando el documento contiene `CUAL JORGE LUIS`.                                                                                                                    | Idealmente devolver el nombre completo.                                                                                    | ⚠️ Consolidó el candidato recibido.                                                                                                                   | Problema principalmente de **GLiNER**. Investigar pérdida del primer token/apellido.                                                                     |
| **20 — 790338** | Extrajo correctamente `CARRIZO ANDREA LILIANA`, pero además detectó aproximadamente 10 personas de una lista de autorizados para diligenciar.                                           | Mantener solamente a Carrizo y descartar abogados/autorizados.                                                             | ✅ De 11 grupos candidatos aceptó solamente a Carrizo y descartó los otros 10.                                                                        | Resultado final correcto. Como mejora de robustez se puede agregar `facultado(s) para el diligenciamiento` a los patrones explícitos de terceros.        |

---

# 4. Casos donde la consolidación funcionó especialmente bien

## 4.1 Validación semántica/estructural del nombre

La regla agregada previamente para impedir que términos genéricos como:

```text
dato
```

sean aceptados como personas también logró eliminar nuevos falsos positivos como:

```text
s6fRMNN0z
1mHrm5AP8
```

Esto indica que la regla no estaba sobreajustada exclusivamente al caso original.

La consolidación reconoció que esos valores no presentan una estructura válida de nombre y los descartó como:

```text
nombre_no_valido
```

---

## 4.2 Personas jurídicas

El caso:

```text
WHITE SHIP S.R.L.
CUIT 30-71606996-2
rol: titular
```

fue aceptado correctamente.

Esto confirma que la validación de estructura de nombres no está restringiendo el sistema únicamente a personas físicas.

---

## 4.3 Múltiples embargados reales

El documento de los hermanos Soplanes contenía:

```text
BRAULIO MAXIMILIANO SOPLANES
DNI 29.784.922
```

y:

```text
JULIO ALBERTO SOPLANES
DNI 13.080.347
```

La consolidación mantuvo correctamente dos grupos independientes:

```text
RESUELTO_MULTIPLE
cantidad_embargados = 2
suficiente = true
```

Este caso es especialmente importante después de incorporar la **fusión transitiva de variantes**, porque demuestra que la mejora no está provocando que personas distintas se fusionen simplemente por tener nombres parecidos.

---

## 4.4 Detección de inconsistencias provenientes de GLiNER

En el documento de Nelson Darío Brizuela, GLiNER generó asociaciones incorrectas:

```text
NELSON DARÍO BRIZUELA
DNI 34.063.787
```

pero también:

```text
MARIA XIMENA RODRIGUEZ COSTANTINO
DNI 34.063.787
```

y:

```text
ROCIO BELEN TARRES
DNI 34.063.787
```

La consolidación no pudo determinar automáticamente cuál asociación de GLiNER era correcta, pero sí detectó que existía una contradicción.

Por lo tanto produjo:

```text
suficiente = false
requiere_fallback_documento_completo = true
requiere_revision = true
motivo = conflicto_identificador
```

Este comportamiento es deseable para producción.

Cuando la evidencia es contradictoria, el sistema no debería forzar una respuesta aparentemente segura.

---

## 4.5 Lista de autorizados

El documento de `CARRIZO ANDREA LILIANA` fue uno de los mejores stress tests de la muestra.

GLiNER generó candidatos para:

```text
CARRIZO ANDREA LILIANA
Ignacio Martinez
Javier Martin Mauri
Rodrigo Antonio Gelvez
Leandro Julian De la Parra
Micaela Ailin Mengual
...
```

La consolidación generó 11 grupos candidatos, pero finalmente aceptó solamente:

```text
CARRIZO ANDREA LILIANA
DNI 24.075.107
```

y descartó los demás candidatos.

Esto demuestra que las señales combinadas de:

```text
rol jurídico
identificador
contexto
repetición
```

están evitando que una simple aparición de nombre + DNI implique automáticamente que la persona sea considerada embargada.

---

# 5. Casos donde el problema no debe corregirse desde consolidación

Es importante no modificar las reglas de consolidación para compensar errores producidos antes en el pipeline.

## Problemas de fragmentación

### Documento 1

El nombre real:

```text
ROMERO FERNANDO SALUSTIANO
```

está en el documento completo, pero no quedó correctamente disponible dentro de los fragmentos útiles procesados por GLiNER.

### Documento 13

El documento completo contiene:

```text
ALBARIÑO, JIMENA CECILIA
DNI 37796425
```

pero GLiNER no recibió un fragmento adecuado con esa información.

En ambos casos la consolidación actuó correctamente al devolver:

```text
NO_RESUELTO
```

en lugar de inventar una identidad.

---

# 6. Patrón detectado en GLiNER: pérdida del apellido

La nueva muestra permitió observar un patrón que conviene estudiar específicamente en GLiNER.

Ejemplos:

```text
HERRERA, ALEJANDRO MATÍAS
→ ALEJANDRO MATÍAS
```

```text
ÑANCÚ, GABRIEL ARNALDO RAFAEL
→ GABRIEL ARNALDO RAFAEL
```

```text
ARANDA, ELIDA MAGDALENA
→ ELIDA MAGDALENA
```

```text
CUAL JORGE LUIS
→ JORGE LUIS
```

La consolidación no debería reconstruir arbitrariamente estos apellidos.

El problema debería investigarse primero en:

```text
schema de GLiNER
descripción de nombre_embargado
tokenización
formato APELLIDO, NOMBRE
ventana del fragmento
```

antes de implementar heurísticas de recuperación en consolidación.

---

# 7. Mejoras candidatas de la consolidación

Después de esta prueba, las mejoras concretas que vale la pena estudiar son pocas y localizadas.

## Mejora 1 — Contexto jurídico: `sumas ... que X tenga`

### Caso detectado

```text
sumas depositadas y/o a depositar en el futuro
que el Sr. Orlando Argentino ROSSI
DNI 11.438.646,
tenga en vuestra entidad
```

GLiNER produjo:

```text
nombre válido
+ DNI
+ rol embargado
```

pero la consolidación no encontró `contexto_juridico_positivo`.

### Propuesta

Ampliar `PATRONES_CONTEXTO_POSITIVO` para contemplar formulaciones generales similares a:

```text
sumas/fondos depositados o a depositar
que [persona] tenga/posea
```

Esta modificación debería hacerse con test unitario antes de incorporarla.

---

## Mejora 2 — Selección del nombre canónico

### Caso detectado

Las variantes fueron:

```text
ISA SEBASTIAN YAIR CUIT
Isa Sebastián Yair
```

La consolidación fusionó correctamente ambas, pero seleccionó:

```text
ISA SEBASTIAN YAIR CUIT
```

como nombre representativo.

### Propuesta

Al seleccionar la mejor variante de nombre, penalizar tokens administrativos al inicio o final:

```text
DNI
CUIT
CUIL
CBU
CVU
NRO
```

El objetivo no es eliminar la evidencia, sino elegir como nombre canónico:

```text
Isa Sebastián Yair
```

conservando igualmente la otra variante dentro de `variantes_nombre`.

---

## Mejora 3 — Autorizados para diligenciar

### Caso detectado

Aparecieron expresiones como:

```text
se encuentran facultados para el diligenciamiento
```

La consolidación descartó correctamente a los autorizados utilizando las demás señales, pero no siempre los clasificó directamente como:

```text
tercero_fuerte = true
```

### Propuesta

Agregar patrones negativos como:

```text
facultado para diligenciar
facultados para diligenciar
facultado para el diligenciamiento
facultados para el diligenciamiento
se encuentran facultados
```

Esta mejora sería principalmente defensiva.

El resultado actual ya es correcto.

---

# 8. Prioridad de las mejoras

| Prioridad | Mejora                                                 | Motivo                                                                                      |
| --------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| 🔴 Alta   | Contexto `sumas/fondos que X tenga`                    | Actualmente produjo un falso `NO_RESUELTO` de una persona correctamente extraída por GLiNER |
| 🟡 Media  | Selección del nombre canónico                          | No modifica la identidad, pero puede devolver nombres contaminados con tokens como `CUIT`   |
| 🟢 Baja   | `facultados para diligenciamiento` como tercero fuerte | El caso actual ya fue resuelto correctamente; aumentaría robustez futura                    |

---

# 9. Qué no modificar

A partir de esta prueba **no se recomienda**:

```text
bajar thresholds generales
aceptar automáticamente por DNI
aceptar automáticamente por rol
usar el texto completo para corregir nombres de manera heurística
fusionar candidatos únicamente por identificador
relajar la validación de nombres
```

Estas modificaciones podrían mejorar casos puntuales pero aumentar falsos positivos en producción.

La estrategia debería continuar siendo:

```text
caso nuevo
    ↓
identificar etapa que falló
    ↓
crear test que represente el comportamiento esperado
    ↓
hacer modificación mínima
    ↓
ejecutar suite completa
    ↓
volver a ejecutar muestra
```

---

# 10. Conclusión

La prueba sobre 20 documentos nuevos muestra que la consolidación actual **generaliza razonablemente bien fuera del conjunto original de 80 documentos**.

Especialmente se comprobó que puede:

- manejar personas físicas;
- manejar personas jurídicas;
- conservar múltiples embargados reales;
- fusionar variantes de una misma persona;
- rechazar códigos y valores que no son nombres;
- descartar grandes listas de personas incidentales;
- detectar conflictos de identificadores;
- marcar casos dudosos como insuficientes;
- solicitar fallback cuando la evidencia disponible no permite una resolución segura.

Los errores observados no corresponden todos a la consolidación.

La principal mejora claramente atribuible a ella es ampliar de manera controlada el **contexto jurídico positivo** para expresiones como:

```text
sumas depositadas y/o a depositar
que el Sr./Sra. [persona] tenga
```

Las demás situaciones principales detectadas —especialmente apellidos omitidos y sujetos ausentes de los fragmentos— deben investigarse en GLiNER y en la generación de fragmentos antes de agregar nuevas reglas determinísticas.

Por lo tanto, la recomendación es **mantener la consolidación estable y realizar mejoras pequeñas, justificadas por casos reproducibles y acompañadas por tests unitarios**, evitando adaptar el sistema caso por caso.
