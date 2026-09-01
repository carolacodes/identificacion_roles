from src.data_loader import InputRecord
from src.inference import PredictionResult
from src.postprocess import postprocess_prediction


def _prediction(raw_response, normalized_items, schema_type="entities"):
    return PredictionResult(
        record=InputRecord(
            numero_archivo="1",
            id="doc-1",
            nombre="oficio",
            texto="texto",
            modo_entrada="fragmentos",
        ),
        model_id="gliner2_multi",
        schema_id="schema_v1",
        threshold=0.65,
        schema_type=schema_type,
        raw_response=raw_response,
        normalized_items=normalized_items,
    )


def test_postprocess_without_candidates():
    result = postprocess_prediction(_prediction({}, []))

    assert result.status == "no_detectado"
    assert result.candidates == []


def test_postprocess_with_multiple_candidates():
    result = postprocess_prediction(
        _prediction(
            {"entities": {"persona_embargada": ["Juan Perez", "ACME SA"]}},
            [
                {"entity_type": "persona_embargada", "value": "Juan Perez", "score": 0.72},
                {"entity_type": "persona_embargada", "value": "ACME SA", "score": 0.68},
            ],
        )
    )

    assert result.status == "multiples_candidatos"
    assert [candidate["valor"] for candidate in result.candidates] == ["Juan Perez", "ACME SA"]


def test_postprocess_structured_candidate():
    result = postprocess_prediction(
        _prediction(
            {"persona_embargada": {"nombre": "ACME SA", "cuil_cuit": "30-12345678-9"}},
            [],
            schema_type="structured",
        )
    )

    assert result.status == "candidato_unico"
    assert result.candidates[0]["nombre"] == "ACME SA"
    assert result.candidates[0]["cuil_cuit"] == "30-12345678-9"
