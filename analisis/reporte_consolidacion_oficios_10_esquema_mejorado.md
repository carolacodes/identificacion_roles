# Resultados de consolidación de oficios — 10 documentos (esquema mejorado)

**Fuente:** `consolidacion(20261023-180929).json` · **Tipo:** fragmentos `Datos_Embargado` · **Fecha:** 23/10/2026

## Resumen

- Documentos: **10**; suficientes: **7**; requieren fallback: **3**.
- Personas aceptadas: **21**; candidatos descartados: **3**.
- Estado RESUELTO no implica suficiencia ni cobertura completa.

## Resumen por documento

| Archivo | ID | PDF | Estado | Aceptados | Descartados | Suficiente | Fallback | Motivos insuficiencia |
|---:|---|---|---|---:|---:|---|---|---|
| 1 | 494149 | 494149_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |
| 2 | 494154 | 494154_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |
| 3 | 494158 | 494158_1.pdf | `NO_RESUELTO` | 0 | 1 | No | Sí | no_resuelto, sin_persona_objeto_oficio, solo_candidatos_descartados |
| 4 | 494454 | 494454_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |
| 5 | 494455 | 494455_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |
| 6 | 495016 | 495016_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |
| 7 | 495017 | 495017_1.pdf | `RESUELTO` | 1 | 2 | No | Sí | candidatos_con_identificador_descartados |
| 8 | 495018 | 495018_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |
| 9 | 495024 | 495024_1.pdf | `RESUELTO_MULTIPLE` | 13 | 0 | No | Sí | lista_personas_cobertura_incompleta, persona_4:evidencia_unica_debil, persona_5:evidencia_unica_debil, persona_6:evidencia_unica_debil, persona_7:evidencia_unica_debil, persona_8:evidencia_unica_debil, persona_9:evidencia_unica_debil, persona_10:evidencia_unica_debil, persona_11:evidencia_unica_debil, persona_12:evidencia_unica_debil, persona_13:evidencia_unica_debil |
| 10 | 496887 | 496887_1.pdf | `RESUELTO` | 1 | 0 | Sí | No | — |

## Personas aceptadas

| Archivo | N.º | Nombre | DNI | CUIT/CUIL | Roles | Fragmentos | Score |
|---:|---:|---|---|---|---|---:|---:|
| 1 | 1 | GONZÁLEZ REINALDO | 92.883.503 | — | titular | 1 | 12.653 |
| 2 | 1 | Arias Rodrigo Maximiliano | 34.085.295 | — | titular | 2 | 23.781 |
| 3 | — | *Sin personas aceptadas* | — | — | — | — | — |
| 4 | 1 | LEVY VERONICA LILIANA | — | 27-22403438-0 | actora | 1 | 11.82 |
| 5 | 1 | Daniel Hugo Sánchez | — | 20165581785 | causante | 2 | 26.698 |
| 6 | 1 | OSVALDO, PABLO DANIEL | — | 20319844504 | — | 1 | 10.445 |
| 7 | 1 | Micaela Esther | — | 27-43057221-6 | titular | 1 | 11.771 |
| 8 | 1 | Sr. FLORENTINO ROMAN FERNANDO | 37.367.958 | — | actor | 1 | 11.026 |
| 9 | 1 | TAUZY CARLOS IGNACIO | 29.240.482 | — | actor | 1 | 11.269 |
| 9 | 2 | GONZALEZ SANDRA NOEMI | 33.390.010 | — | — | 1 | 9.537 |
| 9 | 3 | VILLALBA VALERIA GISELE | 33.040.021 | — | — | 1 | 8.748 |
| 9 | 4 | MOLINA LUCAS ADRIAN | 41.208.023 | — | — | 1 | 7.929 |
| 9 | 5 | SOSA GISELA SOLANGE | 33.342.980 | — | — | 1 | 7.697 |
| 9 | 6 | PAJON KAREN AGUSTINA | 38.524.293 | — | — | 1 | 7.572 |
| 9 | 7 | AMARILLO DEBORA ELISABET | 35.425.357 | — | — | 1 | 7.549 |
| 9 | 8 | ROBLEDO FEDERICO ESTEBAN | 36.953.294 | — | — | 1 | 7.482 |
| 9 | 9 | LOPEZ MIRTA BETIANA | 38.081.993 | — | — | 1 | 7.361 |
| 9 | 10 | CASCO CARLOS ANTONIO | 32.642.146 | — | — | 1 | 7.33 |
| 9 | 11 | BOUCHARD GERARDO FEDERICO | 30.001.707 | — | — | 1 | 7.105 |
| 9 | 12 | VELAZQUEZ MICHAELA TALIA | 36.995.659 | — | — | 1 | 7.011 |
| 9 | 13 | GOMEZ ALBERTO NICOLAS | 32.342.118 | — | — | 1 | 6.91 |
| 10 | 1 | ANGELA DEL BUONO | 14124313 | — | titular | 1 | 9.974 |

## Candidatos descartados

| Archivo | Nombre | DNI | CUIT/CUIL | Rol | Motivos del descarte |
|---:|---|---|---|---|---|
| 3 | Martin Eduardo Hualde | — | — | — | senales_insuficientes, sin_rol_juridico_fuerte, sin_identificador, sin_repeticion |
| 7 | Anahí Luna Zebrún | 40.349.044 | — | actora | senales_insuficientes, sin_contexto_juridico, sin_repeticion |
| 7 | AniZebrun | — | 27-40349044-5 | titular | nombre_no_valido |

## Hallazgos a revisar

- **Documento 3:** Martin Eduardo Hualde fue descartado por falta de identificador, rol fuerte y repetición. El DNI `29.959.152` existe en el fragmento OCR, pero GLiNER2 no lo extrajo.
- **Documento 6:** mejora lograda: `OSVALDO, PABLO DANIEL`, CUIT `20319844504`, ahora aceptado y marcado suficiente.
- **Documento 7:** se aceptó `Micaela Esther` como nombre parcial, pero se descartó `Anahí Luna Zebrún` aunque el requerimiento incluye a ambas; el alias `AniZebrun` fue descartado por `nombre_no_valido`. El documento se marcó insuficiente.
- **Documento 9:** el oficio enumera 37 personas, pero se aceptaron 13; se marcó insuficiente por cobertura incompleta y evidencias únicas débiles. El DNI `36.995.659` asociado a `VELAZQUEZ MICHAELA TALIA` pertenece en el OCR a `CEBALLOS BRAIAN DAMIAN` (Velázquez tiene `39.741.501`).
- **Rol documento 9:** se asignó `actor` a TAUZY CARLOS IGNACIO, aunque el oficio es una verificación administrativa de personal policial; revisar ese rol.

## Notas de interpretación

- Esta tabla transcribe el resultado del consolidador, **no valida automáticamente la exactitud jurídica ni de identidad**.
- Una persona puede tener más de una evidencia fragmentaria sin equivaler a dos personas distintas.
- `—` significa valor vacío o no extraído; no se completaron valores faltantes.
