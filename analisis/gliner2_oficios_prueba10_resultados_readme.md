# Resultados de extracción — GLiNER2 Multi (oficios, texto completo)

**Configuración:** esquema `schema_v1_persona_objeto_oficio_texto_ocr` · threshold `0.50` · sin consolidación.

**Alcance:** 10 documentos; 28 candidatos extraídos. La tabla reproduce exactamente los campos generados por GLiNER2. Un guion (—) significa que ese campo no fue extraído; no implica que no figure en el oficio.

## Tabla de extracciones

| Archivo | ID | Documento | Candidato | Nombre extraído | DNI extraído | CUIT/CUIL extraído | Rol extraído | Revisión manual |
|---:|---|---|---:|---|---|---|---|---|
| 1 | 494149 | `494149_1.pdf` | 1 | — | — | — | actora | ☐ |
| 2 | 494154 | `494154_1.pdf` | 1 | BONVICINI Agustina Soledad | — | — | — | ☐ |
| 3 | 494158 | `494158_1.pdf` | 1 | — | 30.004.000 | — | — | ☐ |
| 4 | 494454 | `494454_1.pdf` | 1 | LEVY VERONICA LILIANA | — | 30-52915644-4 | actora | ☐ |
| 4 | 494454 | `494454_1.pdf` | 2 | — | — | — | demandada | ☐ |
| 5 | 494455 | `494455_1.pdf` | 1 | Daniel Hugo Sánchez | — | 20165581785 | causante | ☐ |
| 6 | 495016 | `495016_1.pdf` | 1 | OERTLINGER ANA ERIKA | — | 20319844504 | demandado | ☐ |
| 7 | 495017 | `495017_1.pdf` | 1 | Anahí Luna Zebrún | 40.349.044 | 27-43057221-6 | actora | ☐ |
| 8 | 495018 | `495018_1.pdf` | 1 | FLORENTINO ROMAN FERNANDO | 37.367.958 | — | actor | ☐ |
| 9 | 495024 | `495024_1.pdf` | 1 | TAUZY CARLOS IGNACIO | 29.240.482 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 2 | VILLALBA VALERIA GISELE | 33.040.021 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 3 | GONZALEZ SANDRA NOEMI | 33.390.010 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 4 | MOLINA LUCAS ADRIAN | 41.208.023 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 5 | SOSA GISELA SOLANGE | 33.342.980 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 6 | AMARILLO DEBORA ELISABET | 35.425.357 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 7 | CASCO CARLOS ANTONIO | 32.642.146 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 8 | LOPEZ MIRTA BETIANA | 38.081.993 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 9 | PAJON KAREN AGUSTINA | 38.524.293 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 10 | VELAZQUEZ MICHAELA TALIA | 39.741.501 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 11 | CEBALLOS BRAIAN DAMIAN | 36.953.294 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 12 | ROBLEDO FEDERICO ESTEBAN | 36.953.294 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 13 | BOUCHARD GERARDO FEDERICO | 32.342.118 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 14 | GOMEZ ALBERTO NICOLAS | 29.231.250 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 15 | MONTEROS GABRIELA ELIZABETH | 38.629.313 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 16 | DELGADO DANIEL ANDRES | 38.629.313 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 17 | SALINAS DAIANA SOLEDAD | 31.095.210 | — | — | ☐ |
| 9 | 495024 | `495024_1.pdf` | 18 | DOMINGUEZ ARIEL ROQUE JOAQUIN | 24.832.972 | — | — | ☐ |
| 10 | 496887 | `496887_1.pdf` | 1 | Angela Del Buono | 14124313 | — | — | ☐ |

## Observaciones para la revisión (contrastadas con el texto OCR incluido en el JSON)

| Archivo | Observación |
|---:|---|
| 1 | Solo se extrajo el rol `actora`. El requerimiento menciona a **GONZÁLEZ REINALDO**, DNI **92.883.503**; no fue extraído. |
| 2 | GLiNER2 seleccionó a **BONVICINI Agustina Soledad** (firmante/parte). El pedido consulta por **Arias Rodrigo Maximiliano**, DNI **34.085.295**. |
| 3 | Solo extrajo DNI **30.004.000**, perteneciente a **Vanina Celeste Saavedra**, autorizada para diligenciar. El requerimiento pide datos de **Martin Eduardo Hualde**, DNI **29.959.152**. |
| 4 | Asoció a **LEVY VERONICA LILIANA** el CUIT **30-52915644-4**, que en el oficio corresponde a **CLUB ATLETICO ATLANTA**. El CUIT de Levy es **27-22403438-0**. Además generó un candidato sin nombre con rol `demandada`. |
| 6 | Extrajo **OERTLINGER ANA ERIKA** junto con el CUIT **20319844504** y el rol `demandado`, pero el oficio solicita información sobre **OSVALDO, PABLO DANIEL**, titular de ese CUIT. |
| 7 | Asoció **Anahí Luna Zebrún** al CUIL **27-43057221-6**, que aparece vinculado a **Micaela Esther Almada**. El oficio menciona para Anahí el CUIL **27-40349044-5**. El pedido involucra a ambas personas. |
| 9 | El oficio enumera **37 efectivos policiales**, pero GLiNER2 devolvió **18 candidatos**. Varias asociaciones de DNI están desplazadas (p. ej. CEBALLOS, BOUCHARD, GOMEZ, MONTEROS, DELGADO, SALINAS y DOMINGUEZ). |

**Nota:** las observaciones son una comparación manual preliminar con el OCR, no una evaluación automática de precisión. Los valores de la tabla principal no fueron corregidos, normalizados ni consolidados.
