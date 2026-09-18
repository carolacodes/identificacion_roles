from src.consolidacion_embargado import (
    ESTADO_NO_RESUELTO,
    ESTADO_RESUELTO,
    ESTADO_RESUELTO_MULTIPLE,
    _nombres_equivalentes,
    consolidar_documento,
    evaluar_suficiencia,
    resumir_consolidacion,
)


def _candidate(
    nombre,
    dni="",
    cuit="",
    rol="embargado",
    confidence=0.95,
):
    return {
        "nombre_embargado": nombre,
        "nombre_embargado_confidence": confidence,
        "nombre_embargado_span_inicio": 50,
        "nombre_embargado_span_fin": 80,

        "dni_embargado": dni or None,
        "dni_embargado_confidence": (
            0.99 if dni else None
        ),

        "cuit_cuil_embargado": cuit or None,
        "cuit_cuil_embargado_confidence": (
            0.99 if cuit else None
        ),

        "rol_embargado": rol,
        "rol_embargado_confidence": 0.90,
    }


def _resultado(
    contador,
    fragmento,
    candidates,
):
    return {
        "contador_interno": str(contador),
        "palabra_clave": "dni",
        "categoria": "Datos_Embargado",
        "fragmento": fragmento,
        "candidates": candidates,
    }


def _documento(
    resultados,
    numero_archivo="1",
    document_id="doc-1",
):
    return {
        "id": document_id,
        "numero_archivo": numero_archivo,
        "nombre": "Embargo - usuario",
        "resultados": resultados,
    }


# ============================================================
# RAPIDFUZZ / NOMBRES
# ============================================================


def test_nombres_reordenados_son_equivalentes():
    assert _nombres_equivalentes(
        "HERRERA ANDREA JAQUELINA",
        "ANDREA JAQUELINA HERRERA",
    )


def test_nombre_parcial_de_dos_tokens_es_equivalente():
    assert _nombres_equivalentes(
        "ESTEFANIA MIHANOVICH",
        "NORMA ESTEFANIA MIHANOVICH",
    )


def test_un_solo_apellido_no_se_fusiona():
    assert not _nombres_equivalentes(
        "GONZALEZ",
        "SANTIAGO NICOLAS GONZALEZ",
    )


def test_nombres_totalmente_distintos_no_son_equivalentes():
    assert not _nombres_equivalentes(
        "HORACIO OSCAR NUÑEZ",
        "MIRTA EDITH BONACALZA",
    )


# ============================================================
# AGRUPACION CORRECTA
# ============================================================


def test_misma_persona_por_nombre_reordenado():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Trábese embargo sobre los fondos de "
                    "HERRERA ANDREA JAQUELINA "
                    "DNI 23333216."
                ),
                [
                    _candidate(
                        "HERRERA ANDREA JAQUELINA",
                        dni="23333216",
                        rol="embargada",
                    )
                ],
            ),
            _resultado(
                2,
                (
                    "La demandada ANDREA JAQUELINA HERRERA "
                    "DNI 23.333.216 posee fondos."
                ),
                [
                    _candidate(
                        "ANDREA JAQUELINA HERRERA",
                        dni="23.333.216",
                        rol="demandada",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["estado"]
        == ESTADO_RESUELTO
    )

    assert (
        resultado["cantidad_embargados"]
        == 1
    )

    persona = (
        resultado[
            "personas_embargadas"
        ][0]
    )

    assert (
        len(
            persona[
                "variantes_nombre"
            ]
        )
        == 2
    )

    assert (
        persona[
            "dni_embargado"
        ]
        in {
            "23333216",
            "23.333.216",
        }
    )


def test_mismo_dni_y_nombre_compatible_fusiona():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Embargado: JUAN CARLOS PEREZ "
                    "DNI 30111222."
                ),
                [
                    _candidate(
                        "JUAN CARLOS PEREZ",
                        dni="30111222",
                    )
                ],
            ),
            _resultado(
                2,
                (
                    "El demandado JUAN CARLOS PEREZ "
                    "DNI 30.111.222."
                ),
                [
                    _candidate(
                        "JUAN CARLOS PEREZ",
                        dni="30.111.222",
                        rol="demandado",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["cantidad_embargados"]
        == 1
    )

    assert (
        resultado["estado"]
        == ESTADO_RESUELTO
    )

    assert (
        resultado[
            "cantidad_conflictos_identificador"
        ]
        == 0
    )


# ============================================================
# CONFLICTOS DE IDENTIFICADORES
# ============================================================


def test_mismo_dni_no_fusiona_nombres_incompatibles():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Embargado: HORACIO OSCAR NUÑEZ "
                    "DNI 26592524."
                ),
                [
                    _candidate(
                        "HORACIO OSCAR NUÑEZ",
                        dni="26592524",
                    )
                ],
            ),
            _resultado(
                2,
                (
                    "Embargada: MIRTA EDITH BONACALZA "
                    "DNI 26592524."
                ),
                [
                    _candidate(
                        "MIRTA EDITH BONACALZA",
                        dni="26592524",
                        rol="embargada",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado[
            "cantidad_grupos_candidatos"
        ]
        == 2
    )

    assert (
        resultado[
            "cantidad_conflictos_identificador"
        ]
        == 1
    )

    assert (
        resultado[
            "requiere_revision"
        ]
        is True
    )

    conflicto = (
        resultado[
            "conflictos_identificador"
        ][0]
    )

    assert (
        conflicto[
            "tipo_identificador"
        ]
        == "dni"
    )

    assert (
        conflicto[
            "valor_normalizado"
        ]
        == "26592524"
    )

    assert {
        conflicto["nombre_a"],
        conflicto["nombre_b"],
    } == {
        "HORACIO OSCAR NUÑEZ",
        "MIRTA EDITH BONACALZA",
    }


def test_mismo_cuit_no_fusiona_nombres_incompatibles():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Demandado HORACIO OSCAR NUÑEZ "
                    "CUIT 20-26592524-4."
                ),
                [
                    _candidate(
                        "HORACIO OSCAR NUÑEZ",
                        cuit="20-26592524-4",
                        rol="demandado",
                    )
                ],
            ),
            _resultado(
                2,
                (
                    "Demandada MIRTA EDITH BONACALZA "
                    "CUIT 20-26592524-4."
                ),
                [
                    _candidate(
                        "MIRTA EDITH BONACALZA",
                        cuit="20-26592524-4",
                        rol="demandada",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado[
            "cantidad_grupos_candidatos"
        ]
        == 2
    )

    assert (
        resultado[
            "cantidad_conflictos_identificador"
        ]
        == 1
    )

    conflicto = (
        resultado[
            "conflictos_identificador"
        ][0]
    )

    assert (
        conflicto[
            "tipo_identificador"
        ]
        == "cuit_cuil"
    )


# ============================================================
# MULTIPLES EMBARGADOS
# ============================================================


def test_dos_personas_distintas_se_conservan():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Embargado: JUAN PEREZ "
                    "DNI 30111222."
                ),
                [
                    _candidate(
                        "JUAN PEREZ",
                        dni="30111222",
                    )
                ],
            ),
            _resultado(
                2,
                (
                    "Embargada: MARIA GOMEZ "
                    "DNI 28999888."
                ),
                [
                    _candidate(
                        "MARIA GOMEZ",
                        dni="28999888",
                        rol="embargada",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["estado"]
        == ESTADO_RESUELTO_MULTIPLE
    )

    assert (
        resultado[
            "cantidad_embargados"
        ]
        == 2
    )

    nombres = {
        persona[
            "nombre_embargado"
        ]
        for persona
        in resultado[
            "personas_embargadas"
        ]
    }

    assert nombres == {
        "JUAN PEREZ",
        "MARIA GOMEZ",
    }


# ============================================================
# CONTEXTO NEGATIVO
# ============================================================


def test_contexto_de_deposito_penaliza_tercero():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Embargado: VINCI BRIAN EMMANUEL "
                    "DNI 34.436.998."
                ),
                [
                    _candidate(
                        "VINCI BRIAN EMMANUEL",
                        dni="34.436.998",
                    )
                ],
            ),

            _resultado(
                2,
                (
                    "La suma retenida deberá depositarse "
                    "en la cuenta abierta a nombre de la "
                    "Sra. Micaela Yanina Rodino "
                    "DNI 34.652.957."
                ),
                [
                    _candidate(
                        "Micaela Yanina Rodino",
                        dni="34.652.957",
                        rol="embargada",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    nombres = {
        persona[
            "nombre_embargado"
        ]
        for persona
        in resultado[
            "personas_embargadas"
        ]
    }

    assert (
        "VINCI BRIAN EMMANUEL"
        in nombres
    )

    assert (
        "Micaela Yanina Rodino"
        not in nombres
    )


# ============================================================
# TERCEROS FUERTES
# ============================================================


def test_abogado_autorizado_se_descarta():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Embargado: DANIEL CARLOS PEREZ "
                    "DNI 24391072."
                ),
                [
                    _candidate(
                        "DANIEL CARLOS PEREZ",
                        dni="24391072",
                        rol="embargado",
                    )
                ],
            ),

            _resultado(
                2,
                (
                    "Se encuentran autorizados para "
                    "diligenciar el presente los Dres. "
                    "MARCOS WEISFELD DNI 23.524.519."
                ),
                [
                    _candidate(
                        "MARCOS WEISFELD",
                        dni="23.524.519",
                        rol="embargado",
                    )
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    nombres = {
        persona[
            "nombre_embargado"
        ]
        for persona
        in resultado[
            "personas_embargadas"
        ]
    }

    assert (
        "DANIEL CARLOS PEREZ"
        in nombres
    )

    assert (
        "MARCOS WEISFELD"
        not in nombres
    )


# ============================================================
# BASURA / CANDIDATOS INVALIDOS
# ============================================================


def test_expresion_generica_no_se_considera_persona():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Se aplicó la medida sobre "
                    "un usuario incorrecto."
                ),
                [
                    _candidate(
                        "usuario incorrecto",
                        rol="embargado",
                    )
                ],
            )
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["estado"]
        == ESTADO_NO_RESUELTO
    )

    assert (
        resultado[
            "cantidad_embargados"
        ]
        == 0
    )


def test_nombre_demasiado_corto_se_descarta():
    documento = _documento(
        [
            _resultado(
                1,
                "Embargo sobre A c.",
                [
                    _candidate(
                        "A c.",
                    )
                ],
            )
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado[
            "cantidad_embargados"
        ]
        == 0
    )


# ============================================================
# RESUMEN
# ============================================================


def test_resumen_consolidacion():
    resultados = [
        {
            "estado":
                ESTADO_RESUELTO,

            "cantidad_embargados":
                1,

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,
        },
        {
            "estado":
                ESTADO_RESUELTO_MULTIPLE,

            "cantidad_embargados":
                2,

            "requiere_revision":
                True,

            "cantidad_conflictos_identificador":
                1,
        },
        {
            "estado":
                ESTADO_NO_RESUELTO,

            "cantidad_embargados":
                0,

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,
        },
    ]

    resumen = resumir_consolidacion(
        resultados
    )

    assert (
        resumen[
            "total_documentos"
        ]
        == 3
    )

    assert (
        resumen[
            "RESUELTO"
        ]
        == 1
    )

    assert (
        resumen[
            "RESUELTO_MULTIPLE"
        ]
        == 1
    )

    assert (
        resumen[
            "NO_RESUELTO"
        ]
        == 1
    )

    assert (
        resumen[
            "total_personas_embargadas"
        ]
        == 3
    )

    assert (
        resumen[
            "documentos_requieren_revision"
        ]
        == 1
    )

    assert (
        resumen[
            "total_conflictos_identificador"
        ]
        == 1
    )


def test_administrado_por_no_convierte_al_demandado_en_tercero():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Fondo administrado por Mercado Pago Asset Management S.A., "
                    "el demandado en autos ROBERTO CARLOS LOBO, "
                    "con DNI 21773000."
                ),
                [
                    _candidate(
                        "ROBERTO CARLOS LOBO",
                        dni="21773000",
                        rol="demandado",
                    )
                ],
            )
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["estado"]
        == ESTADO_RESUELTO
    )

    assert (
        resultado["cantidad_embargados"]
        == 1
    )

    persona = (
        resultado[
            "personas_embargadas"
        ][0]
    )

    assert (
        persona["nombre_embargado"]
        == "ROBERTO CARLOS LOBO"
    )

    evidencia = (
        persona[
            "evidencias"
        ][0]
    )

    assert (
        evidencia[
            "tercero_fuerte"
        ]
        is False
    )

    assert (
        evidencia[
            "motivo_tercero"
        ]
        == ""
    )


def test_retencion_directa_del_reconoce_embargado():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Procédase a la retención directa del 20 % "
                    "de los haberes mensuales que perciba el Sr. "
                    "BRAVO LUIS ALBERTO, DNI 40770662."
                ),
                [
                    _candidate(
                        "BRAVO LUIS ALBERTO",
                        dni="40770662",
                        rol="embargado",
                    )
                ],
            )
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["estado"]
        == ESTADO_RESUELTO
    )

    assert (
        resultado[
            "cantidad_embargados"
        ]
        == 1
    )

    persona = (
        resultado[
            "personas_embargadas"
        ][0]
    )

    assert (
        persona[
            "nombre_embargado"
        ]
        == "BRAVO LUIS ALBERTO"
    )

    evidencia = (
        persona[
            "evidencias"
        ][0]
    )

    assert (
        evidencia[
            "score_contextual"
        ]
        > 0
    )

    assert (
        evidencia[
            "tercero_fuerte"
        ]
        is False
    )


def test_lista_de_autorizados_descarta_profesionales():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Embargado: DANIEL CARLOS PEREZ, "
                    "DNI 24391072."
                ),
                [
                    _candidate(
                        "DANIEL CARLOS PEREZ",
                        dni="24391072",
                        rol="embargado",
                    )
                ],
            ),

            _resultado(
                2,
                (
                    "Se encuentran autorizados para diligenciar "
                    "el presente los Dres. "
                    "MARCOS WEISFELD, DNI 23524519, "
                    "CECILIA LORENA SATCHIAN, DNI 28444555."
                ),
                [
                    _candidate(
                        "MARCOS WEISFELD",
                        dni="23524519",
                        rol="embargado",
                    ),
                    _candidate(
                        "CECILIA LORENA SATCHIAN",
                        dni="28444555",
                        rol="embargado",
                    ),
                ],
            ),
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    nombres_validos = {
        persona[
            "nombre_embargado"
        ]
        for persona
        in resultado[
            "personas_embargadas"
        ]
    }

    assert (
        "DANIEL CARLOS PEREZ"
        in nombres_validos
    )

    assert (
        "MARCOS WEISFELD"
        not in nombres_validos
    )

    assert (
        "CECILIA LORENA SATCHIAN"
        not in nombres_validos
    )

    descartados = {
        grupo[
            "nombre_embargado"
        ]:
        grupo
        for grupo
        in resultado[
            "grupos_descartados"
        ]
    }

    assert (
        descartados[
            "MARCOS WEISFELD"
        ][
            "evidencias"
        ][0][
            "tercero_fuerte"
        ]
        is True
    )

    assert (
        descartados[
            "MARCOS WEISFELD"
        ][
            "evidencias"
        ][0][
            "motivo_tercero"
        ]
        == "lista_autorizados_profesionales"
    )


def test_rol_demandado_cercano_tiene_prioridad_sobre_referencia_a_abogado():
    documento = _documento(
        [
            _resultado(
                1,
                (
                    "Interviene el abogado de la actora. "
                    "Respecto de la medida solicitada, "
                    "el demandado JUAN PEREZ, DNI 30111222, "
                    "posee fondos en la cuenta informada."
                ),
                [
                    _candidate(
                        "JUAN PEREZ",
                        dni="30111222",
                        rol="demandado",
                    )
                ],
            )
        ]
    )

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado[
            "estado"
        ]
        == ESTADO_RESUELTO
    )

    persona = (
        resultado[
            "personas_embargadas"
        ][0]
    )

    assert (
        persona[
            "nombre_embargado"
        ]
        == "JUAN PEREZ"
    )

    evidencia = (
        persona[
            "evidencias"
        ][0]
    )

    assert (
        evidencia[
            "tercero_fuerte"
        ]
        is False
    )


def test_suficiencia_resultado_fuerte():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO,
        personas_embargadas=[
            {
                "nombre_embargado": "JUAN CARLOS PEREZ",
                "dni_embargado": "30111222",
                "cuit_cuil_embargado": "",
                "roles_detectados": [
                    "demandado"
                ],
                "cantidad_evidencias": 2,
                "score_total": 15.0,
                "identidad_inconsistente": False,
                "evidencias": [
                    {
                        "score_contextual": 1.5,
                    },
                    {
                        "score_contextual": 1.5,
                    },
                ],
            }
        ],
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is True
    assert motivos == []


def test_suficiencia_no_resuelto_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_NO_RESUELTO,
        personas_embargadas=[],
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "no_resuelto"
        in motivos
    )

    assert (
        "sin_persona_embargada"
        in motivos
    )


def test_suficiencia_solo_descartados_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_NO_RESUELTO,
        personas_embargadas=[],
        grupos_descartados=[
            {
                "nombre_embargado":
                    "JUAN PEREZ"
            }
        ],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "solo_candidatos_descartados"
        in motivos
    )


def test_suficiencia_nombre_incompleto_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO,
        personas_embargadas=[
            {
                "nombre_embargado": "GONZALEZ",
                "roles_detectados": [
                    "demandado"
                ],
                "cantidad_evidencias": 2,
                "score_total": 14.0,
                "identidad_inconsistente": False,
                "evidencias": [
                    {
                        "score_contextual": 1.5,
                    },
                    {
                        "score_contextual": 1.5,
                    },
                ],
            }
        ],
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "persona_1:nombre_incompleto"
        in motivos
    )


def test_suficiencia_conflicto_identificador_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO_MULTIPLE,
        personas_embargadas=[
            {
                "nombre_embargado":
                    "HORACIO OSCAR NUÑEZ",

                "roles_detectados": [
                    "demandado"
                ],

                "cantidad_evidencias":
                    2,

                "score_total":
                    15.0,

                "identidad_inconsistente":
                    False,

                "evidencias": [
                    {
                        "score_contextual":
                            1.5
                    }
                ],
            },
            {
                "nombre_embargado":
                    "MIRTA EDITH BONACALZA",

                "roles_detectados": [
                    "demandada"
                ],

                "cantidad_evidencias":
                    2,

                "score_total":
                    15.0,

                "identidad_inconsistente":
                    False,

                "evidencias": [
                    {
                        "score_contextual":
                            1.5
                    }
                ],
            },
        ],
        grupos_descartados=[],
        conflictos_identificador=[
            {
                "tipo_identificador":
                    "cuit_cuil",

                "valor_normalizado":
                    "20265925244",

                "nombre_a":
                    "HORACIO OSCAR NUÑEZ",

                "nombre_b":
                    "MIRTA EDITH BONACALZA",
            }
        ],
    )

    assert suficiente is False

    assert (
        "conflicto_identificador"
        in motivos
    )


def test_suficiencia_identidad_inconsistente_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO,
        personas_embargadas=[
            {
                "nombre_embargado":
                    "JUAN CARLOS PEREZ",

                "roles_detectados": [
                    "demandado"
                ],

                "cantidad_evidencias":
                    3,

                "score_total":
                    20.0,

                "identidad_inconsistente":
                    True,

                "evidencias": [
                    {
                        "score_contextual":
                            1.5
                    }
                ],
            }
        ],
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "persona_1:identidad_inconsistente"
        in motivos
    )


def test_suficiencia_evidencia_unica_debil_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO,
        personas_embargadas=[
            {
                "nombre_embargado":
                    "JUAN CARLOS PEREZ",

                "roles_detectados": [
                    "demandado"
                ],

                "cantidad_evidencias":
                    1,

                "score_total":
                    7.5,

                "identidad_inconsistente":
                    False,

                "evidencias": [
                    {
                        "score_contextual":
                            1.5
                    }
                ],
            }
        ],
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "persona_1:evidencia_unica_debil"
        in motivos
    )


def test_suficiencia_sin_rol_ni_contexto_es_insuficiente():
    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO,
        personas_embargadas=[
            {
                "nombre_embargado":
                    "JUAN CARLOS PEREZ",

                "roles_detectados":
                    [],

                "cantidad_evidencias":
                    2,

                "score_total":
                    12.0,

                "identidad_inconsistente":
                    False,

                "evidencias": [
                    {
                        "score_contextual":
                            0.0
                    },
                    {
                        "score_contextual":
                            0.0
                    },
                ],
            }
        ],
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "persona_1:sin_senal_juridica"
        in motivos
    )


def test_suficiencia_muchos_embargados_es_insuficiente():
    personas = []

    for index in range(
        6
    ):
        personas.append(
            {
                "nombre_embargado":
                    f"PERSONA NUMERO {index}",

                "roles_detectados": [
                    "demandado"
                ],

                "cantidad_evidencias":
                    2,

                "score_total":
                    15.0,

                "identidad_inconsistente":
                    False,

                "evidencias": [
                    {
                        "score_contextual":
                            1.5
                    }
                ],
            }
        )

    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO_MULTIPLE,
        personas_embargadas=personas,
        grupos_descartados=[],
        conflictos_identificador=[],
    )

    assert suficiente is False

    assert (
        "cantidad_embargados_anormal"
        in motivos
    )


def test_consolidacion_conserva_texto_completo():
    texto_completo = (
        "Este es el texto completo del oficio. "
        "Se decreta embargo contra JUAN CARLOS PEREZ."
    )

    documento = {
        "id": "doc-100",
        "numero_archivo": "100",
        "nombre": "Embargo - usuario",
        "texto_completo": texto_completo,

        "resultados": [
            _resultado(
                1,
                (
                    "Embargado: JUAN CARLOS PEREZ "
                    "DNI 30111222."
                ),
                [
                    _candidate(
                        "JUAN CARLOS PEREZ",
                        dni="30111222",
                        rol="embargado",
                    )
                ],
            )
        ],
    }

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["texto_completo"]
        == texto_completo
    )

    assert (
        resultado["tipo_consolidacion"]
        == "fragmentos"
    )


def test_evidencia_indica_tipo_entrada_fragmento():
    documento = {
        "id": "doc-101",
        "numero_archivo": "101",
        "nombre": "Embargo - usuario",
        "texto_completo": "Texto completo.",

        "resultados": [
            _resultado(
                1,
                (
                    "Embargado: JUAN CARLOS PEREZ "
                    "DNI 30111222."
                ),
                [
                    _candidate(
                        "JUAN CARLOS PEREZ",
                        dni="30111222",
                        rol="embargado",
                    )
                ],
            )
        ],
    }

    resultado = consolidar_documento(
        documento
    )

    evidencia = (
        resultado[
            "personas_embargadas"
        ][0][
            "evidencias"
        ][0]
    )

    assert (
        evidencia[
            "tipo_entrada"
        ]
        == "fragmento"
    )


def test_consolidacion_marca_fallback_si_es_insuficiente():
    documento = {
        "id": "doc-102",
        "numero_archivo": "102",
        "nombre": "Embargo - usuario",
        "texto_completo":
            "Documento completo disponible.",

        "resultados":
            [],
    }

    resultado = consolidar_documento(
        documento
    )

    assert (
        resultado["suficiente"]
        is False
    )

    assert (
        resultado[
            "requiere_fallback_documento_completo"
        ]
        is True
    )

    assert (
        "no_resuelto"
        in resultado[
            "motivos_insuficiencia"
        ]
    )


def test_resumen_incluye_suficientes_e_insuficientes():
    resultados = [
        {
            "estado":
                ESTADO_RESUELTO,

            "cantidad_embargados":
                1,

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,

            "suficiente":
                True,
        },
        {
            "estado":
                ESTADO_NO_RESUELTO,

            "cantidad_embargados":
                0,

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,

            "suficiente":
                False,
        },
    ]

    resumen = resumir_consolidacion(
        resultados
    )

    assert (
        resumen["SUFICIENTES"]
        == 1
    )

    assert (
        resumen["INSUFICIENTES"]
        == 1
    )


def test_conflicto_solo_entre_descartados_no_vuelve_insuficiente():
    personas_embargadas = [
        {
            "nombre_embargado": "DANIEL CARLOS PEREZ",
            "roles_detectados": [
                "demandado"
            ],
            "cantidad_evidencias": 2,
            "score_total": 15.0,
            "identidad_inconsistente": False,
            "evidencias": [
                {
                    "score_contextual": 1.5,
                },
                {
                    "score_contextual": 1.5,
                },
            ],
        }
    ]

    grupos_descartados = [
        {
            "nombre_embargado": "MARCOS WEISFELD",
        },
        {
            "nombre_embargado": "CECILIA LORENA SATCHIAN",
        },
    ]

    conflictos = [
        {
            "tipo_identificador": "dni",
            "valor_normalizado": "23524519",
            "nombre_a": "MARCOS WEISFELD",
            "nombre_b": "CECILIA LORENA SATCHIAN",
        }
    ]

    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO,
        personas_embargadas=personas_embargadas,
        grupos_descartados=grupos_descartados,
        conflictos_identificador=conflictos,
    )

    assert suficiente is True

    assert (
        "conflicto_identificador"
        not in motivos
    )


def test_conflicto_que_afecta_aceptado_vuelve_insuficiente():
    personas_embargadas = [
        {
            "nombre_embargado": "HORACIO OSCAR NUÑEZ",
            "roles_detectados": [
                "demandado"
            ],
            "cantidad_evidencias": 3,
            "score_total": 20.0,
            "identidad_inconsistente": False,
            "evidencias": [
                {
                    "score_contextual": 1.5,
                },
                {
                    "score_contextual": 1.5,
                },
                {
                    "score_contextual": 1.5,
                },
            ],
        },
        {
            "nombre_embargado": "MIRTA EDITH BONACALZA",
            "roles_detectados": [
                "demandada"
            ],
            "cantidad_evidencias": 3,
            "score_total": 18.0,
            "identidad_inconsistente": False,
            "evidencias": [
                {
                    "score_contextual": 1.5,
                },
                {
                    "score_contextual": 1.5,
                },
                {
                    "score_contextual": 1.5,
                },
            ],
        },
    ]

    conflictos = [
        {
            "tipo_identificador": "cuit_cuil",
            "valor_normalizado": "20265925244",
            "nombre_a": "HORACIO OSCAR NUÑEZ",
            "nombre_b": "MIRTA EDITH BONACALZA",
        }
    ]

    suficiente, motivos = evaluar_suficiencia(
        estado=ESTADO_RESUELTO_MULTIPLE,
        personas_embargadas=personas_embargadas,
        grupos_descartados=[],
        conflictos_identificador=conflictos,
    )

    assert suficiente is False

    assert (
        "conflicto_identificador"
        in motivos
    )