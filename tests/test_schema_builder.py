from src.model_loader import LoadedModel
from src.schema_builder import build_schema


class FakeStructure:
    """Simula un structure nativo de GLiNER2."""

    def __init__(
        self,
        name: str,
    ):
        self.name = name

        self.fields: dict[
            str,
            dict,
        ] = {}

    def field(
        self,
        field_name: str,
        **kwargs,
    ):
        self.fields[
            field_name
        ] = kwargs

        return self


class FakeSchemaBuilder:
    """Simula model.create_schema()."""

    def __init__(self):
        self.entity_definitions: dict[
            str,
            str,
        ] = {}

    def entities(
        self,
        definitions: dict[
            str,
            str,
        ],
    ):
        self.entity_definitions = (
            definitions
        )

        return {
            "type":
                "entities",

            "definitions":
                definitions,
        }

    def structure(
        self,
        name: str,
    ) -> FakeStructure:

        return FakeStructure(
            name
        )


class FakeGLiNER2Model:
    """Modelo minimo necesario para schema_builder."""

    def create_schema(self):
        return FakeSchemaBuilder()


def _loaded_gliner2_model() -> LoadedModel:

    return LoadedModel(
        model=FakeGLiNER2Model(),
        architecture="gliner2",
        model_id="fake/gliner2",
        display_name="Fake GLiNER2",
    )


def test_build_entity_schema():
    loaded_model = (
        _loaded_gliner2_model()
    )

    schema = build_schema(
        "schema_test",
        {
            "type":
                "entities",

            "entities": {
                "persona_embargada": {
                    "description": (
                        "Persona afectada por embargo"
                    ),
                    "threshold":
                        0.7,
                }
            },
        },
        loaded_model,
    )

    assert (
        schema.schema_id
        == "schema_test"
    )

    assert (
        schema.schema_type
        == "entities"
    )

    assert (
        schema.architecture
        == "gliner2"
    )

    assert (
        schema.descriptions[
            "persona_embargada"
        ]
        == "Persona afectada por embargo"
    )

    assert (
        schema.thresholds[
            "persona_embargada"
        ]
        == 0.7
    )

    assert (
        schema.gliner_schema[
            "type"
        ]
        == "entities"
    )


def test_build_structured_schema():
    loaded_model = (
        _loaded_gliner2_model()
    )

    schema = build_schema(
        "schema_struct",
        {
            "type":
                "structured",

            "name":
                "persona_embargada",

            "fields": {
                "nombre": {
                    "dtype":
                        "str",

                    "description":
                        "Nombre",

                    "required":
                        True,
                },

                "dni": {
                    "dtype":
                        "str",

                    "description":
                        "DNI",

                    "required":
                        False,
                },
            },
        },
        loaded_model,
    )

    assert (
        schema.schema_id
        == "schema_struct"
    )

    assert (
        schema.schema_type
        == "structured"
    )

    assert (
        schema.architecture
        == "gliner2"
    )

    assert (
        schema.gliner_schema.name
        == "persona_embargada"
    )

    assert (
        schema.gliner_schema.fields[
            "nombre"
        ][
            "dtype"
        ]
        == "str"
    )

    assert (
        schema.gliner_schema.fields[
            "nombre"
        ][
            "description"
        ]
        == "Nombre"
    )

    assert (
        schema.gliner_schema.fields[
            "dni"
        ][
            "dtype"
        ]
        == "str"
    )

    assert (
        schema.descriptions[
            "nombre"
        ]
        == "Nombre"
    )

    assert (
        schema.descriptions[
            "dni"
        ]
        == "DNI"
    )


def test_build_v7_structured_schema():
    loaded_model = (
        _loaded_gliner2_model()
    )

    schema = build_schema(
        "schema_v7_test",
        {
            "type":
                "structured",

            "name":
                "persona_embargada",

            "fields": {
                "nombre_embargado": {
                    "dtype":
                        "str",

                    "description":
                        "Nombre del embargado",

                    "threshold":
                        0.60,
                },

                "dni_embargado": {
                    "dtype":
                        "str",

                    "description":
                        "DNI del embargado",

                    "threshold":
                        0.50,
                },

                "cuit_cuil_embargado": {
                    "dtype":
                        "str",

                    "description":
                        "CUIT o CUIL",

                    "threshold":
                        0.50,
                },

                "rol_embargado": {
                    "dtype":
                        "str",

                    "description":
                        "Rol juridico",

                    "threshold":
                        0.50,

                    "choices": [
                        "demandado",
                        "embargado",
                        "ejecutado",
                        "otro",
                    ],
                },
            },
        },
        loaded_model,
    )

    assert (
        schema.gliner_schema.name
        == "persona_embargada"
    )

    fields = (
        schema.gliner_schema.fields
    )

    assert (
        fields[
            "nombre_embargado"
        ][
            "threshold"
        ]
        == 0.60
    )

    assert (
        fields[
            "dni_embargado"
        ][
            "threshold"
        ]
        == 0.50
    )

    assert (
        fields[
            "cuit_cuil_embargado"
        ][
            "threshold"
        ]
        == 0.50
    )

    assert (
        fields[
            "rol_embargado"
        ][
            "choices"
        ]
        == [
            "demandado",
            "embargado",
            "ejecutado",
            "otro",
        ]
    )

    assert (
        schema.thresholds[
            "nombre_embargado"
        ]
        == 0.60
    )