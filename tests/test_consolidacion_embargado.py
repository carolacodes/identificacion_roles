from src.consolidacion_embargado import (
    ESTADO_NO_RESUELTO,
    ESTADO_RESUELTO,
    ESTADO_RESUELTO_MULTIPLE,
    _nombres_equivalentes,
    consolidar_documento,
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