from src.data_loader import InputRecord
from src.inference import PredictionResult
from src.postprocess import postprocess_prediction


def _prediction(
    raw_response,
    normalized_items,
    schema_type="entities",
):
    return PredictionResult(
        record=InputRecord(
            numero_archivo="1",
            id="doc-1",
            nombre="oficio",
            texto="texto",
            modo_entrada="fragmentos",
            categoria="Datos_Embargado",
        ),
        model_id="gliner2_multi",
        schema_id="schema_v1",
        threshold=0.65,
        schema_type=schema_type,
        architecture="gliner2",
        raw_response=raw_response,
        normalized_items=normalized_items,
    )


def test_postprocess_without_candidates():
    result = postprocess_prediction(
        _prediction(
            {},
            [],
        )
    )

    assert (
        result.status
        == "no_detectado"
    )

    assert (
        result.candidates
        == []
    )


def test_postprocess_with_multiple_candidates():
    result = postprocess_prediction(
        _prediction(
            {
                "entities": {
                    "persona_embargada": [
                        "Juan Perez",
                        "ACME SA",
                    ]
                }
            },
            [
                {
                    "entity_type":
                        "persona_embargada",

                    "value":
                        "Juan Perez",

                    "score":
                        0.72,
                },
                {
                    "entity_type":
                        "persona_embargada",

                    "value":
                        "ACME SA",

                    "score":
                        0.68,
                },
            ],
        )
    )

    assert (
        result.status
        == "multiples_candidatos"
    )

    assert [
        candidate["valor"]
        for candidate
        in result.candidates
    ] == [
        "Juan Perez",
        "ACME SA",
    ]


def test_postprocess_structured_v3_v6_compatibility():
    """Los schemas anteriores deben seguir funcionando."""

    result = postprocess_prediction(
        _prediction(
            {
                "persona_embargada": {
                    "nombre":
                        "ACME SA",

                    "dni":
                        "33.470.065",

                    "cuil_cuit":
                        "30-12345678-9",

                    "rol_mencionado":
                        "demandado",
                }
            },
            [],
            schema_type="structured",
        )
    )

    assert (
        result.status
        == "candidato_unico"
    )

    candidate = (
        result.candidates[0]
    )

    # Campos historicos.
    assert (
        candidate["nombre"]
        == "ACME SA"
    )

    assert (
        candidate["dni"]
        == "33.470.065"
    )

    assert (
        candidate["cuil_cuit"]
        == "30-12345678-9"
    )

    # Canonicos nuevos.
    assert (
        candidate[
            "nombre_embargado"
        ]
        == "ACME SA"
    )

    assert (
        candidate[
            "dni_embargado"
        ]
        == "33.470.065"
    )

    assert (
        candidate[
            "cuit_cuil_embargado"
        ]
        == "30-12345678-9"
    )

    assert (
        candidate[
            "rol_embargado"
        ]
        == "demandado"
    )


def test_postprocess_structured_v7():
    result = postprocess_prediction(
        _prediction(
            {
                "persona_embargada": {
                    "nombre_embargado": {
                        "text":
                            "NAHUEL OSCAR MARQUEZ",

                        "confidence":
                            0.93,

                        "start":
                            25,

                        "end":
                            45,
                    },

                    "dni_embargado": {
                        "text":
                            "33.470.065",

                        "confidence":
                            0.97,

                        "start":
                            50,

                        "end":
                            60,
                    },

                    "cuit_cuil_embargado": {
                        "text":
                            "20-33470065-8",

                        "confidence":
                            0.95,

                        "start":
                            65,

                        "end":
                            78,
                    },

                    "rol_embargado": {
                        "text":
                            "demandado",

                        "confidence":
                            0.89,

                        "start":
                            10,

                        "end":
                            19,
                    },
                }
            },
            [],
            schema_type="structured",
        )
    )

    assert (
        result.status
        == "candidato_unico"
    )

    assert (
        len(result.candidates)
        == 1
    )

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate[
            "nombre_embargado"
        ]
        == "NAHUEL OSCAR MARQUEZ"
    )

    assert (
        candidate[
            "dni_embargado"
        ]
        == "33.470.065"
    )

    assert (
        candidate[
            "cuit_cuil_embargado"
        ]
        == "20-33470065-8"
    )

    assert (
        candidate[
            "rol_embargado"
        ]
        == "demandado"
    )

    assert (
        candidate[
            "nombre_embargado_confidence"
        ]
        == 0.93
    )

    assert (
        candidate[
            "nombre_embargado_span_inicio"
        ]
        == 25
    )

    assert (
        candidate[
            "nombre_embargado_span_fin"
        ]
        == 45
    )


def test_postprocess_v7_keeps_compatibility_aliases():
    result = postprocess_prediction(
        _prediction(
            {
                "persona_embargada": {
                    "nombre_embargado":
                        "Juan Perez",

                    "dni_embargado":
                        "30.000.000",

                    "cuit_cuil_embargado":
                        "20-30000000-1",
                }
            },
            [],
            schema_type="structured",
        )
    )

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate["nombre"]
        == "Juan Perez"
    )

    assert (
        candidate["dni"]
        == "30.000.000"
    )

    assert (
        candidate["cuil_cuit"]
        == "20-30000000-1"
    )


def test_postprocess_v7_without_name_but_with_dni():
    """Un fragmento puede no contener nombre y aun asi aportar evidencia."""

    result = postprocess_prediction(
        _prediction(
            {
                "persona_embargada": {
                    "nombre_embargado":
                        None,

                    "dni_embargado": {
                        "text":
                            "33.470.065",

                        "confidence":
                            0.91,
                    },

                    "cuit_cuil_embargado":
                        None,

                    "rol_embargado":
                        "demandado",
                }
            },
            [],
            schema_type="structured",
        )
    )

    assert (
        result.status
        == "candidato_unico"
    )

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate[
            "nombre_embargado"
        ]
        is None
    )

    assert (
        candidate[
            "dni_embargado"
        ]
        == "33.470.065"
    )

    assert (
        candidate[
            "rol_embargado"
        ]
        == "demandado"
    )