# Resultados GLiNER2 Multi — Oficios (esquema de nombres mejorado)

**Fuente:** `predicciones_por_documento(20261023-180423).json`  
**Configuración:** fragmentos `Datos_Embargado`, threshold 0.50, sin consolidación.  
**Documentos:** 10 · **Fragmentos:** 14 · **Candidatos:** 30

> Se muestran las predicciones originales del modelo. Un guion (—) significa que GLiNER2 no extrajo ese campo. La repetición de candidatos entre fragmentos se conserva.

## Resumen por oficio

| Archivo | ID | PDF | Fragmentos | Candidatos |
|---:|---|---|---:|---:|
| 1 | 494149 | 494149_1.pdf | 1 | 1 |
| 2 | 494154 | 494154_1.pdf | 2 | 2 |
| 3 | 494158 | 494158_1.pdf | 1 | 1 |
| 4 | 494454 | 494454_1.pdf | 1 | 1 |
| 5 | 494455 | 494455_1.pdf | 2 | 2 |
| 6 | 495016 | 495016_1.pdf | 1 | 1 |
| 7 | 495017 | 495017_1.pdf | 3 | 3 |
| 8 | 495018 | 495018_1.pdf | 1 | 1 |
| 9 | 495024 | 495024_1.pdf | 1 | 17 |
| 10 | 496887 | 496887_1.pdf | 1 | 1 |

## Resultados completos

| Archivo | Fragmento | Candidato | Nombre extraído | DNI | CUIT/CUIL | Rol | Revisión manual |
|---:|---:|---:|---|---|---|---|---|
| 1 | 1 | 1 | GONZÁLEZ REINALDO | 92.883.503 | — | titular | ☐ |
| 2 | 1 | 1 | Arias Rodrigo Maximiliano | 34.085.295 | — | titular | ☐ |
| 2 | 2 | 1 | Arias Rodrigo Maximiliano | 34.085.295 | — | titular | ☐ |
| 3 | 1 | 1 | Martin Eduardo Hualde | — | — | — | ☐ |
| 4 | 1 | 1 | LEVY VERONICA LILIANA | — | 27-22403438-0 | actora | ☐ |
| 5 | 1 | 1 | Daniel Hugo Sánchez | — | 20165581785 | causante | ☐ |
| 5 | 2 | 1 | Daniel Hugo Sánchez | — | 20165581785 | causante | ☐ |
| 6 | 1 | 1 | OSVALDO, PABLO DANIEL | — | 20319844504 | — | ☐ |
| 7 | 1 | 1 | Anahí Luna Zebrún | 40.349.044 | — | actora | ☐ |
| 7 | 2 | 1 | Micaela Esther | — | 27-43057221-6 | titular | ☐ |
| 7 | 3 | 1 | AniZebrun | — | 27-40349044-5 | titular | ☐ |
| 8 | 1 | 1 | Sr. FLORENTINO ROMAN FERNANDO | 37.367.958 | — | actor | ☐ |
| 9 | 1 | 1 | TAUZY CARLOS IGNACIO | 29.240.482 | — | actor | ☐ |
| 9 | 1 | 2 | VILLALBA VALERIA GISELE | 33.040.021 | — | — | ☐ |
| 9 | 1 | 3 | GONZALEZ SANDRA NOEMI | 33.390.010 | — | — | ☐ |
| 9 | 1 | 4 | MOLINA LUCAS ADRIAN | 41.208.023 | — | — | ☐ |
| 9 | 1 | 5 | SOSA GISELA SOLANGE | 33.342.980 | — | — | ☐ |
| 9 | 1 | 6 | AMARILLO DEBORA ELISABET | 35.425.357 | — | — | ☐ |
| 9 | 1 | 7 | CASCO CARLOS ANTONIO | 32.642.146 | — | — | ☐ |
| 9 | 1 | 8 | LOPEZ MIRTA BETIANA | 38.081.993 | — | — | ☐ |
| 9 | 1 | 9 | PAJON KAREN AGUSTINA | 38.524.293 | — | — | ☐ |
| 9 | 1 | 10 | — | 39.741.501 | — | — | ☐ |
| 9 | 1 | 11 | VELAZQUEZ MICHAELA TALIA | 36.995.659 | — | — | ☐ |
| 9 | 1 | 12 | ROBLEDO FEDERICO ESTEBAN | 36.953.294 | — | — | ☐ |
| 9 | 1 | 13 | BOUCHARD GERARDO FEDERICO | 30.001.707 | — | — | ☐ |
| 9 | 1 | 14 | GOMEZ ALBERTO NICOLAS | 32.342.118 | — | — | ☐ |
| 9 | 1 | 15 | — | 38.629.313 | — | — | ☐ |
| 9 | 1 | 16 | — | 31.095.210 | — | — | ☐ |
| 9 | 1 | 17 | — | 31.095.210 | — | — | ☐ |
| 10 | 1 | 1 | ANGELA DEL BUONO | 14124313 | — | titular | ☐ |

## Observaciones de revisión (interpretación, no predicciones)

- **Archivo 3:** se extrajo el nombre Martin Eduardo Hualde, pero no su DNI `29.959.152`, aunque aparece en el fragmento.
- **Archivo 6:** mejora: ahora se extrajo `OSVALDO, PABLO DANIEL` completo con CUIT `20319844504`; antes se extraía `OSVALDO` solo.
- **Archivo 7:** se sigue extrayendo `AniZebrun` como `nombre_persona` pese a ser un alias. `Micaela Esther` sigue incompleto porque el fragmento corta antes de `Almada`.
- **Archivo 8:** se incluyó `Sr.` en el span del nombre.
- **Archivo 9:** hay 17 candidatos de una lista OCR de 37 personas; 4 candidatos carecen de nombre y el DNI `31.095.210` aparece dos veces. El DNI `36.995.659` se asoció a `VELAZQUEZ MICHAELA TALIA`, pero en el OCR corresponde a `CEBALLOS BRAIAN DAMIAN`. `39.741.501` corresponde a Velazquez y figura separado. Se requiere revisión de omisiones y asociaciones.

## Comparación puntual con la corrida previa

| Documento | Antes de ajustar descripción | Ahora |
|---|---|---|
| 6 | `OSVALDO` | `OSVALDO, PABLO DANIEL` (mejoró) |
| 7, alias | `AniZebrun` | `AniZebrun` (persiste) |
| 7, Micaela | `Micaela Esther` | `Micaela Esther` (persiste truncamiento) |
| 3, DNI | `29.959.152` | Sin DNI (regresión) |
| 9, candidatos | 18 | 17 (ambas corridas requieren evaluación de cobertura) |

**Nota:** estas observaciones no son una métrica automática de precisión; representan puntos de control a verificar manualmente.
