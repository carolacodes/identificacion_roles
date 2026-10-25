# Resultados de extracción — GLiNER2 Multi (oficios, texto completo)

**Configuración:** esquema `schema_v1_persona_objeto_oficio_texto_ocr` · threshold `0.50` · sin consolidación.

**Alcance:** 10 documentos; 28 candidatos extraídos. La tabla reproduce exactamente los campos generados por GLiNER2. Un guion (—) significa que ese campo no fue extraído; no implica que no figure en el oficio.

## Tabla de extracciones

| Archivo | ID     | Documento      | Candidato | Nombre extraído               | DNI extraído | CUIT/CUIL extraído | Rol extraído | Revisión manual |
| ------: | ------ | -------------- | --------: | ----------------------------- | ------------ | ------------------ | ------------ | --------------- |
|       1 | 494149 | `494149_1.pdf` |         1 | —                             | —            | —                  | actora       | ☐               |
|       2 | 494154 | `494154_1.pdf` |         1 | BONVICINI Agustina Soledad    | —            | —                  | —            | ☐               |
|       3 | 494158 | `494158_1.pdf` |         1 | —                             | 30.004.000   | —                  | —            | ☐               |
|       4 | 494454 | `494454_1.pdf` |         1 | LEVY VERONICA LILIANA         | —            | 30-52915644-4      | actora       | ☐               |
|       4 | 494454 | `494454_1.pdf` |         2 | —                             | —            | —                  | demandada    | ☐               |
|       5 | 494455 | `494455_1.pdf` |         1 | Daniel Hugo Sánchez           | —            | 20165581785        | causante     | ☐               |
|       6 | 495016 | `495016_1.pdf` |         1 | OERTLINGER ANA ERIKA          | —            | 20319844504        | demandado    | ☐               |
|       7 | 495017 | `495017_1.pdf` |         1 | Anahí Luna Zebrún             | 40.349.044   | 27-43057221-6      | actora       | ☐               |
|       8 | 495018 | `495018_1.pdf` |         1 | FLORENTINO ROMAN FERNANDO     | 37.367.958   | —                  | actor        | ☐               |
|       9 | 495024 | `495024_1.pdf` |         1 | TAUZY CARLOS IGNACIO          | 29.240.482   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         2 | VILLALBA VALERIA GISELE       | 33.040.021   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         3 | GONZALEZ SANDRA NOEMI         | 33.390.010   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         4 | MOLINA LUCAS ADRIAN           | 41.208.023   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         5 | SOSA GISELA SOLANGE           | 33.342.980   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         6 | AMARILLO DEBORA ELISABET      | 35.425.357   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         7 | CASCO CARLOS ANTONIO          | 32.642.146   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         8 | LOPEZ MIRTA BETIANA           | 38.081.993   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |         9 | PAJON KAREN AGUSTINA          | 38.524.293   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        10 | VELAZQUEZ MICHAELA TALIA      | 39.741.501   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        11 | CEBALLOS BRAIAN DAMIAN        | 36.953.294   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        12 | ROBLEDO FEDERICO ESTEBAN      | 36.953.294   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        13 | BOUCHARD GERARDO FEDERICO     | 32.342.118   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        14 | GOMEZ ALBERTO NICOLAS         | 29.231.250   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        15 | MONTEROS GABRIELA ELIZABETH   | 38.629.313   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        16 | DELGADO DANIEL ANDRES         | 38.629.313   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        17 | SALINAS DAIANA SOLEDAD        | 31.095.210   | —                  | —            | ☐               |
|       9 | 495024 | `495024_1.pdf` |        18 | DOMINGUEZ ARIEL ROQUE JOAQUIN | 24.832.972   | —                  | —            | ☐               |
|      10 | 496887 | `496887_1.pdf` |         1 | Angela Del Buono              | 14124313     | —                  | —            | ☐               |

## Observaciones para la revisión (contrastadas con el texto OCR incluido en el JSON)

| Archivo | Observación                                                                                                                                                                                                              |
| ------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|       1 | Solo se extrajo el rol `actora`. El requerimiento menciona a **GONZÁLEZ REINALDO**, DNI **92.883.503**; no fue extraído.                                                                                                 |
|       2 | GLiNER2 seleccionó a **BONVICINI Agustina Soledad** (firmante/parte). El pedido consulta por **Arias Rodrigo Maximiliano**, DNI **34.085.295**.                                                                          |
|       3 | Solo extrajo DNI **30.004.000**, perteneciente a **Vanina Celeste Saavedra**, autorizada para diligenciar. El requerimiento pide datos de **Martin Eduardo Hualde**, DNI **29.959.152**.                                 |
|       4 | Asoció a **LEVY VERONICA LILIANA** el CUIT **30-52915644-4**, que en el oficio corresponde a **CLUB ATLETICO ATLANTA**. El CUIT de Levy es **27-22403438-0**. Además generó un candidato sin nombre con rol `demandada`. |
|       6 | Extrajo **OERTLINGER ANA ERIKA** junto con el CUIT **20319844504** y el rol `demandado`, pero el oficio solicita información sobre **OSVALDO, PABLO DANIEL**, titular de ese CUIT.                                       |
|       7 | Asoció **Anahí Luna Zebrún** al CUIL **27-43057221-6**, que aparece vinculado a **Micaela Esther Almada**. El oficio menciona para Anahí el CUIL **27-40349044-5**. El pedido involucra a ambas personas.                |
|       9 | El oficio enumera **37 efectivos policiales**, pero GLiNER2 devolvió **18 candidatos**. Varias asociaciones de DNI están desplazadas (p. ej. CEBALLOS, BOUCHARD, GOMEZ, MONTEROS, DELGADO, SALINAS y DOMINGUEZ).         |

**Nota:** las observaciones son una comparación manual preliminar con el OCR, no una evaluación automática de precisión. Los valores de la tabla principal no fueron corregidos, normalizados ni consolidados.

NOMBRE PERSONA ANTERIOR:

            Nombre completo de la persona fisica o razon social de la entidad
            sobre la que el oficio solicita informacion o alguna actuacion
            concreta. Extraer el nombre que figure expresamente en el fragmento,
            vinculado al pedido principal (por ejemplo, "informe si X posee
            cuenta", "movimientos de X", "fondos a nombre de X" o una lista
            de personas a verificar).

            El fragmento puede contener una parte del requerimiento judicial,
            una transcripcion del auto que ordena la medida o una enumeracion
            de personas sobre las cuales se solicita informacion.
            Identificar exclusivamente los nombres que puedan vincularse
            con el objeto del requerimiento a partir de la evidencia
            presente en el fragmento.

            Cuando el fragmento mencione varias personas sobre las cuales
            se solicita informacion o alguna actuacion, extraer cada nombre
            como una persona independiente, si el mecanismo de extraccion
            admite multiples registros.

            No confundir con nombres presentes solo en la caratula, firmas,
            datos de notificacion, representacion procesal o transcripciones
            ajenas al requerimiento. No asumir que una persona es objeto
            del oficio solamente porque aparezca mencionada en el fragmento.

            No completar nombres parciales, corregir errores de OCR ni
            modificar su grafia. Conservar el nombre exactamente como aparece
            en el fragmento.

            Si el fragmento no contiene el nombre de la persona consultada
            o no existe evidencia suficiente para vincularlo con el
            requerimiento, no extraer el campo. No inferir nombres a partir
            de otros datos o personas mencionadas.

=======================================================================================
description: >
Nombre completo de la persona fisica o razon social de la entidad
sobre la que el oficio solicita informacion o alguna actuacion
concreta. Extraer el nombre que figure expresamente en el fragmento,
vinculado al pedido principal (por ejemplo, "informe si X posee
cuenta", "movimientos de X", "fondos a nombre de X" o una lista
de personas a verificar).

          Para personas fisicas, extraer exclusivamente nombres completos
          que contengan al menos un nombre de pila y un apellido identificables.
          El nombre puede aparecer en orden nombre-apellido o apellido-nombre,
          y sus componentes pueden estar separados por espacios, comas
          u otros signos de puntuacion.

          No extraer solamente el primer nombre, un apellido aislado,
          iniciales, apodos, diminutivos o fragmentos incompletos
          del nombre de una persona.

          IMPORTANTE: cuando el nombre aparezca dividido por una coma,
          como "OSVALDO, PABLO DANIEL", considerar todos sus componentes
          como parte del mismo nombre, siempre que correspondan a una
          unica persona. No detener la extraccion en la coma ni devolver
          solamente "OSVALDO" si el fragmento contiene el nombre completo.

          No asumir que dos palabras constituyen necesariamente un
          nombre completo. Verificar, cuando el contexto lo permita,
          que correspondan a un nombre de pila y un apellido,
          y no solamente a dos nombres de pila o a una expresion parcial.

          Para personas juridicas, permitir razones sociales identificables,
          incluso cuando incluyan denominaciones comerciales y formas
          societarias como S.R.L., S.A., S.A.S. u otras equivalentes.
          Por ejemplo, "OSCAR S.R.L." debe considerarse una razon social
          valida aunque no siga la estructura de nombre y apellido.

          No exigir que una persona juridica tenga nombre y apellido.
          Sin embargo, no extraer como persona juridica palabras genericas,
          siglas societarias aisladas o nombres de organismos y empresas
          mencionados unicamente como destinatarios del oficio.

          No confundir nombres completos con alias de cuentas bancarias,
          billeteras virtuales, CVU, CBU, nombres de usuario,
          identificadores digitales, correos electronicos o apodos.
          Por ejemplo, "alias: AniZebrun" no debe extraerse como
          nombre_persona, aunque aparezca asociado a un CUIL
          o a una cuenta de Mercado Pago.

          El fragmento puede contener una parte del requerimiento judicial,
          una transcripcion del auto que ordena la medida o una enumeracion
          de personas sobre las cuales se solicita informacion.
          Identificar exclusivamente los nombres que puedan vincularse
          con el objeto del requerimiento a partir de la evidencia
          presente en el fragmento.

          Cuando el fragmento mencione varias personas sobre las cuales
          se solicita informacion o alguna actuacion, extraer cada nombre
          como una persona independiente, si el mecanismo de extraccion
          admite multiples registros.

          No confundir con nombres presentes solo en la caratula, firmas,
          datos de notificacion, representacion procesal o transcripciones
          ajenas al requerimiento. No asumir que una persona es objeto
          del oficio solamente porque aparezca mencionada en el fragmento.

          No completar nombres parciales, corregir errores de OCR ni
          modificar su grafia. Conservar el nombre exactamente como
          aparece en el fragmento, incluyendo comas y separadores
          que formen parte de su escritura original.

          Si el fragmento contiene solamente un nombre parcial,
          un alias o una identificacion insuficiente de la persona,
          no extraer el campo. No inferir componentes faltantes
          a partir de otras personas o datos mencionados.
