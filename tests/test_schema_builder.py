from src.schema_builder import build_schema


def test_build_entity_schema():
    schema = build_schema(
        "schema_test",
        {
            "type": "entities",
            "entities": {
                "persona_embargada": {
                    "description": "Persona afectada por embargo",
                    "threshold": 0.7,
                }
            },
        },
    )

    assert schema.schema_type == "entities"
    assert schema.gliner_schema == ["persona_embargada"]
    assert schema.descriptions["persona_embargada"] == "Persona afectada por embargo"
    assert schema.thresholds["persona_embargada"] == 0.7


def test_build_structured_schema():
    schema = build_schema(
        "schema_struct",
        {
            "type": "structured",
            "name": "persona_embargada",
            "fields": {
                "nombre": {"description": "Nombre", "required": True},
                "dni": {"description": "DNI", "required": False},
            },
        },
    )

    assert schema.schema_type == "structured"
    assert schema.gliner_schema["name"] == "persona_embargada"
    assert schema.gliner_schema["fields"]["nombre"]["required"] is True
    assert schema.gliner_schema["fields"]["dni"]["required"] is False
