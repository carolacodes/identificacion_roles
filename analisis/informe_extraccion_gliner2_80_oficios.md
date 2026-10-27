# Informe preliminar de extracción GLiNER2 — 80 oficios

**Corrida:** `predicciones_por_documento(20261027-165828).json`  
**Etapa:** extracción de GLiNER2, antes de consolidación.

## Resumen cuantitativo

- Documentos: **80**; fragmentos procesados: **121**.
- Fragmentos con candidato(s): **106**; sin candidatos: **15**.
- Candidatos brutos: **167**; con nombre: **152**; con nombre e identificador: **148**.
- Candidatos con DNI: **129**; con CUIT/CUIL: **48**; con rol: **80**.
- Documentos con al menos un nombre: **72**; sin nombres: **8**.
- Documentos con al menos un candidato nombre + identificador: **69**.

> Importante: estas cantidades corresponden a predicciones, no a personas únicas validadas ni a precisión/recall. Un mismo individuo puede aparecer varias veces o con variantes.

## Tabla de resultados por documento

| N.º | ID | Fragmentos | Candidatos | Nombres distintos (literales) | Candidatos nombre + ID | ID sin nombre | Nombres extraídos (muestra) | Alertas |
|---:|---|---:|---:|---:|---:|---:|---|---|
| 1 | `494149` | 1 | 1 | 1 | 1 | 0 | GONZÁLEZ REINALDO | — |
| 2 | `494154` | 2 | 2 | 1 | 2 | 0 | Arias Rodrigo Maximiliano | — |
| 3 | `494158` | 1 | 1 | 1 | 1 | 0 | Martin Eduardo Hualde | — |
| 4 | `494454` | 1 | 1 | 1 | 1 | 0 | LEVY VERONICA LILIANA | — |
| 5 | `494455` | 3 | 2 | 1 | 2 | 0 | Daniel Hugo Sánchez | — |
| 6 | `495016` | 2 | 1 | 1 | 1 | 0 | OSVALDO, PABLO DANIEL | — |
| 7 | `495017` | 3 | 3 | 3 | 3 | 0 | Anahí Luna Zebrún; Micaela Esther Almada; Luna Zebrún | Revisión manual |
| 8 | `495018` | 1 | 1 | 1 | 1 | 0 | FLORENTINO ROMAN FERNANDO | — |
| 9 | `495024` | 1 | 19 | 13 | 14 | 5 | TAUZY CARLOS IGNACIO; GONZALEZ SANDRA NOEMI; MOLINA LUCAS ADRIAN; … (+10) | ID sin nombre, Fragmento largo, Revisar duplicados/asociaciones |
| 10 | `496887` | 1 | 1 | 1 | 1 | 0 | ANGELA DEL BUONO | — |
| 11 | `497722` | 2 | 1 | 1 | 1 | 0 | ROLON SOFIA LUDMILA | — |
| 12 | `497723` | 1 | 1 | 1 | 1 | 0 | GALEANO MARCELO DANIEL ISAAC | — |
| 13 | `497724` | 1 | 1 | 1 | 1 | 0 | Leandro Javier VILAS | — |
| 14 | `497726` | 1 | 1 | 1 | 1 | 0 | Leandro Javier VILAS | — |
| 15 | `498367` | 1 | 1 | 1 | 1 | 0 | Alejandra Amalia Elizabeth Ortiz | — |
| 16 | `498368` | 2 | 2 | 2 | 1 | 0 | IBARRA CHRISTIAN ADRIAN; Christian Adrian IBARRA | Nombre sin ID |
| 17 | `498371` | 1 | 1 | 1 | 1 | 0 | Abad Braian José | — |
| 18 | `498372` | 1 | 1 | 1 | 1 | 0 | Diego Alejandro EFFENBERGER | — |
| 19 | `498373` | 1 | 1 | 1 | 1 | 0 | VERONICA EUGENIA PUGA | — |
| 20 | `498374` | 1 | 1 | 1 | 1 | 0 | VERONICA EUGENIA PUGA | — |
| 21 | `499475` | 3 | 2 | 2 | 2 | 0 | Carla Noelia Manzur; celemontiel888 | Revisión manual |
| 22 | `501701` | 1 | 1 | 1 | 0 | 0 | ROBERTO ADRIAN CAPRIA | Nombre sin ID |
| 23 | `501702` | 1 | 1 | 1 | 1 | 0 | Zulma Haydee STOESSEL | — |
| 24 | `502122` | 2 | 1 | 1 | 1 | 0 | DAVID MAXIMILIANO SANCHEZ | — |
| 25 | `502665` | 1 | 1 | 1 | 1 | 0 | Víctor Fabián González | — |
| 26 | `503247` | 2 | 2 | 2 | 2 | 0 | EZEQUIEL MATÍAS KLANG; Sr. EZEQUIEL MATÍAS KLANG | — |
| 27 | `503249` | 2 | 1 | 1 | 0 | 0 | García Minzoni | Nombre sin ID, Revisión manual |
| 28 | `503809` | 1 | 1 | 1 | 1 | 0 | SANCHEZ JUAN PABLO | — |
| 29 | `503811` | 1 | 1 | 1 | 1 | 0 | MAGRINI GUSTAVO SILVIO | — |
| 30 | `503812` | 1 | 1 | 1 | 1 | 0 | BERTOLINI OLGA BEATRIZ | — |
| 31 | `503813` | 1 | 1 | 1 | 1 | 0 | SANCHEZ FERNANDEZ MARCELA VERONICA | — |
| 32 | `503814` | 1 | 1 | 1 | 1 | 0 | VELAZQUEZ CESAR ARTURO | — |
| 33 | `503815` | 1 | 1 | 1 | 1 | 0 | TAMBUSSI PATRICIA MONICA | — |
| 34 | `503816` | 2 | 2 | 2 | 2 | 0 | VILLARREAL ROSANA GABRIELA; ROSANA GABRIELA VILLARREAL | — |
| 35 | `503817` | 1 | 1 | 1 | 1 | 0 | BOHACZENKO MATIAS ARIEL | — |
| 36 | `503818` | 1 | 1 | 1 | 1 | 0 | ROMANO GISELA ANDREA SOLEDAD | — |
| 37 | `503821` | 1 | 1 | 0 | 0 | 1 | — | Sin nombre, ID sin nombre |
| 38 | `504419` | 1 | 1 | 1 | 1 | 0 | Jorge Ivan Diaz | — |
| 39 | `504962` | 3 | 3 | 1 | 2 | 1 | ASTRID MARIA SALINAS ZORZOLI | ID sin nombre |
| 40 | `504978` | 1 | 1 | 1 | 1 | 0 | GABRIEL GUSTAVO PINTO | — |
| 41 | `504980` | 1 | 1 | 1 | 1 | 0 | Riccombeni Melisa | — |
| 42 | `504981` | 4 | 4 | 3 | 4 | 0 | Leandro Anibal Jesús Rubin; Leandro Anibal Jesus Rubin; Micaela Ailen RUBIN BAROSI | Revisar duplicados/asociaciones |
| 43 | `504983` | 1 | 1 | 1 | 1 | 0 | ACUÑA ALAN CRISTIAN FERNANDO | — |
| 44 | `505531` | 1 | 1 | 1 | 1 | 0 | Maria Paula Marconi | — |
| 45 | `507161` | 1 | 0 | 0 | 0 | 0 | — | Sin candidatos |
| 46 | `507163` | 2 | 1 | 0 | 0 | 0 | — | Sin nombre |
| 47 | `507208` | 1 | 2 | 2 | 2 | 0 | Bruno Hernán BARTEL; Maira Ailen FLORES | — |
| 48 | `507219` | 2 | 1 | 1 | 1 | 0 | Tatiana Gulián | — |
| 49 | `507226` | 1 | 1 | 1 | 0 | 0 | Maximiliano Arnaldo GOMEZ | Nombre sin ID |
| 50 | `507911` | 2 | 2 | 1 | 2 | 0 | GASTON ENRIQUE LOPEZ | — |
| 51 | `507929` | 12 | 13 | 4 | 13 | 0 | Rosa Itati Quintana; Viviana Lorena Paluj; Itati Quintana; … (+1) | Revisar duplicados/asociaciones, Revisión manual |
| 52 | `507939` | 1 | 0 | 0 | 0 | 0 | — | Sin candidatos |
| 53 | `508926` | 1 | 1 | 1 | 1 | 0 | Mariana Milano | — |
| 54 | `508929` | 1 | 1 | 1 | 1 | 0 | JULIETA ANALIA NOVAIS | — |
| 55 | `510026` | 1 | 1 | 1 | 1 | 0 | MATIAS GONZALO VAZQUEZ | — |
| 56 | `510055` | 2 | 4 | 2 | 4 | 0 | LUIS ALFREDO LICERA SANCHEZ; CAROLINA LARA BECERRA | Revisar duplicados/asociaciones |
| 57 | `510065` | 1 | 1 | 1 | 1 | 0 | DIEGO RAUL CATALANO | — |
| 58 | `510067` | 1 | 3 | 2 | 3 | 0 | Miguel Ángel MILLETARI; Viviana Delia HERNÁNDEZ DE MILLETARI | Revisar duplicados/asociaciones |
| 59 | `510941` | 2 | 2 | 1 | 2 | 0 | BILAŃSKI MIGUEL | — |
| 60 | `510976` | 1 | 1 | 1 | 1 | 0 | Cristina Antunes Borges Da Cunha | — |
| 61 | `510977` | 1 | 1 | 1 | 1 | 0 | WILFRIDO GAMARRA GONZALEZ | — |
| 62 | `510992` | 1 | 1 | 1 | 1 | 0 | Diego Gabriel Contreras | — |
| 63 | `510996` | 1 | 0 | 0 | 0 | 0 | — | Sin candidatos |
| 64 | `511032` | 1 | 1 | 1 | 1 | 0 | Sr Alvarez Jason Matias | Revisión manual |
| 65 | `512276` | 1 | 1 | 1 | 1 | 0 | ORLANDO NORMA BEATRIZ | — |
| 66 | `512278` | 1 | 1 | 1 | 1 | 0 | SIMON ADRIAN FERNANDO | — |
| 67 | `512280` | 1 | 1 | 1 | 1 | 0 | GONZALEZ RAUL ALBERTO | — |
| 68 | `512287` | 2 | 2 | 1 | 1 | 1 | OLIVERA, CARINA ALEJANDRA | ID sin nombre |
| 69 | `512288` | 1 | 1 | 1 | 1 | 0 | PISTILLO ARIEL JOSE | — |
| 70 | `512289` | 1 | 1 | 1 | 1 | 0 | RAMIREZ ROMINA ELISABET | — |
| 71 | `512297` | 1 | 1 | 1 | 1 | 0 | Polola Daiana Sol | — |
| 72 | `513001` | 1 | 16 | 14 | 15 | 1 | BARRIOS NESTOR HORACIO; CORVALAN SILVINA BEATRIZ; ESPINOLA RAMON ALBERTO; … (+11) | ID sin nombre, Fragmento largo, Revisar duplicados/asociaciones |
| 73 | `513002` | 1 | 17 | 14 | 14 | 3 | HUGO ORLANDO; GISELA PAOLA; CASTRO, MARIANO FEDERICO; … (+11) | ID sin nombre, Fragmento largo, Revisar duplicados/asociaciones, Revisión manual |
| 74 | `513003` | 2 | 2 | 1 | 1 | 1 | SERGIO ARIEL | ID sin nombre, Revisión manual |
| 75 | `513004` | 2 | 3 | 2 | 3 | 0 | FACUNDO HERNAN; PERALTA, MARCOS GABRIEL | Revisar duplicados/asociaciones, Revisión manual |
| 76 | `513005` | 1 | 1 | 0 | 0 | 1 | — | Sin nombre, ID sin nombre |
| 77 | `513006` | 3 | 3 | 3 | 3 | 0 | ELECTRO HOGAR S.R.L.; RICARDO ESTEBAN VÁZQUEZ; MARCELO DANIEL VÁZQUEZ | — |
| 78 | `513007` | 1 | 0 | 0 | 0 | 0 | — | Sin candidatos |
| 79 | `513008` | 1 | 0 | 0 | 0 | 0 | — | Sin candidatos |
| 80 | `513009` | 2 | 5 | 2 | 5 | 0 | Roberto Carlos ÁLVAREZ; Marta Susana TISSERA DE ÁLVAREZ | Revisar duplicados/asociaciones |

## Casos que requieren revisión prioritaria

| Documento | Observación |
|---|---|
| 9 · 495024 | Lista de 37 personas en un fragmento de 1491 caracteres. Salen 13 nombres distintos, 19 candidatos, identificadores sueltos y una asociación errónea de DNI para GONZALEZ SANDRA NOEMI. |
| 72 · 513001 | Lista extensa: 14 nombres distintos, 16 candidatos; el DNI 28.654.123 se vincula como alternativa a MAMANI GASTON ARIEL, aunque en el texto corresponde a otra persona. |
| 73 · 513002 | Fragmento de 817 caracteres, 14 nombres literales y tres DNI sin nombre. BENÍTEZ y otros nombres salen parcialmente. |
| 51 · 507929 | 12 fragmentos con transferencias repetidas; 13 candidatos brutos y variantes de Rosa Itati Quintana. También aparece una persona autorizada para diligenciar, que puede no ser objeto de consulta. |
| 7 · 495017 | Mejora: ahora Micaela Esther Almada sale completa. Pero se genera Luna Zebrún como nombre parcial asociado al CUIL; revisar rol y objeto de oficio. |
| 21 · 499475 | Se extrajo `celemontiel888` (alias) como nombre; falso positivo probable. |
| 27 · 503249 | `García Minzoni` parece surgir del contexto de un funcionario/dirección, sin identificador; revisar si realmente es objeto del oficio. |
| 46 · 507163 | Candidato con rol `demandada` pero sin nombre ni identificador. |
| 37 · 503821 y 76 · 513005 | Identificadores CUIT sin nombre; podrían corresponder a sociedades expresamente mencionadas, revisar el objetivo antes de considerarlos errores. |
| 74 · 513003 y 75 · 513004 | Nombres personales parciales (`SERGIO ARIEL`, `FACUNDO HERNAN`) y CUIT vinculados a distintos sujetos: revisar asociaciones. |
| 45, 52, 63, 78, 79 | Son los cinco documentos cuya única fila tiene categoría vacía, fragmento vacío y `no_detectado`. Quitar el filtro los incluyó, pero **no aportó texto útil para extraer**. |

## Interpretación y siguiente etapa

No llamar a este resumen tasa de acierto: se requiere una referencia de personas esperadas por oficio y revisión de asociaciones nombre–DNI/CUIT. La consolidación debe analizar conflictos de identificación, duplicados y roles, pero no puede recuperar información ausente si no se prevé un mecanismo de reprocesamiento o fallback.

Conviene ejecutar el consolidador sin cambiar reglas y luego cruzar resultados por `id` y por candidato para contabilizar: aceptados, descartados, correctamente vinculados, falsos positivos y documentos insuficientes.
