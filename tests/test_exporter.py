import csv
import json

from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from src.exporter import _to_dict
from src.exporter import (
    _build_consolidation_csv_rows,
    build_document_rows,
    export_consolidation,
)

def test_build_consolidation_csv_single_person():
    resultados = [
        {
            "numero_archivo": "1",
            "id": "doc-1",
            "nombre_documento": "Embargo",
            "estado": "RESUELTO",
            "cantidad_embargados": 1,

            "personas_embargadas": [
                {
                    "nombre_embargado":
                        "JUAN PEREZ",

                    "dni_embargado":
                        "30111222",

                    "cuit_cuil_embargado":
                        "20-30111222-3",

                    "roles_detectados": [
                        "demandado",
                        "embargado",
                    ],

                    "variantes_nombre": [
                        "JUAN PEREZ",
                        "PEREZ JUAN",
                    ],

                    "cantidad_fragmentos_soporte":
                        3,

                    "cantidad_evidencias":
                        4,

                    "score_total":
                        18.5,
                }
            ],
        }
    ]

    rows = (
        _build_consolidation_csv_rows(
            resultados
        )
    )

    assert len(rows) == 1

    row = rows[0]

    assert (
        row["nombre_embargado"]
        == "JUAN PEREZ"
    )

    assert (
        row["indice_embargado"]
        == 1
    )

    assert (
        row["roles_detectados"]
        == "demandado | embargado"
    )


def test_build_consolidation_csv_multiple_people():
    resultados = [
        {
            "numero_archivo": "1",
            "id": "doc-1",
            "nombre_documento": "Embargo",
            "estado": "RESUELTO_MULTIPLE",
            "cantidad_embargados": 2,

            "personas_embargadas": [
                {
                    "nombre_embargado":
                        "JUAN PEREZ",

                    "dni_embargado":
                        "11111111",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados": [
                        "demandado"
                    ],

                    "variantes_nombre": [
                        "JUAN PEREZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        2,

                    "cantidad_evidencias":
                        2,

                    "score_total":
                        10,
                },

                {
                    "nombre_embargado":
                        "MARIA GOMEZ",

                    "dni_embargado":
                        "22222222",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados": [
                        "demandada"
                    ],

                    "variantes_nombre": [
                        "MARIA GOMEZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        2,

                    "cantidad_evidencias":
                        2,

                    "score_total":
                        9,
                },
            ],
        }
    ]

    rows = (
        _build_consolidation_csv_rows(
            resultados
        )
    )

    assert (
        len(rows)
        == 2
    )

    assert (
        rows[0]["indice_embargado"]
        == 1
    )

    assert (
        rows[1]["indice_embargado"]
        == 2
    )


def test_build_consolidation_csv_no_resuelto():
    resultados = [
        {
            "numero_archivo": "1",
            "id": "doc-1",
            "nombre_documento": "Embargo",
            "estado": "NO_RESUELTO",
            "cantidad_embargados": 0,
            "personas_embargadas": [],
        }
    ]

    rows = (
        _build_consolidation_csv_rows(
            resultados
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["estado"]
        == "NO_RESUELTO"
    )

    assert (
        rows[0]["nombre_embargado"]
        == ""
    )


def test_export_consolidation_creates_files(
    tmp_path: Path,
):
    resultados = [
        {
            "numero_archivo": "1",
            "id": "doc-1",
            "nombre_documento": "Embargo",
            "estado": "RESUELTO",
            "cantidad_embargados": 1,

            "personas_embargadas": [
                {
                    "nombre_embargado":
                        "JUAN PEREZ",

                    "dni_embargado":
                        "30111222",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados": [
                        "demandado"
                    ],

                    "variantes_nombre": [
                        "JUAN PEREZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        1,

                    "cantidad_evidencias":
                        1,

                    "score_total":
                        9.5,
                }
            ],
        }
    ]

    resumen = {
        "total_documentos": 1,
        "RESUELTO": 1,
        "RESUELTO_MULTIPLE": 0,
        "NO_RESUELTO": 0,
        "total_personas_embargadas": 1,
    }

    paths = export_consolidation(
        resultados=resultados,
        resumen=resumen,
        experiment_name="test_multi",
        used_config={
            "test":
                True
        },
        outputs_dir=tmp_path,
        now=datetime(
            2026,
            9,
            15,
            12,
            0,
            0,
        ),
    )

    output_dir = (
        paths["consolidacion_dir"]
    )

    assert output_dir.exists()

    assert (
        paths[
            "consolidacion_json"
        ].exists()
    )

    assert (
        paths[
            "consolidacion_csv"
        ].exists()
    )

    assert (
        paths[
            "resumen_json"
        ].exists()
    )

    assert (
        output_dir
        / "config_usada.yaml"
    ).exists()


def test_exported_json_contains_people(
    tmp_path: Path,
):
    resultados = [
        {
            "numero_archivo": "1",
            "id": "doc-1",
            "nombre_documento": "Embargo",
            "estado": "RESUELTO",
            "cantidad_embargados": 1,

            "personas_embargadas": [
                {
                    "nombre_embargado":
                        "JUAN PEREZ",

                    "dni_embargado":
                        "30111222",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados":
                        [],

                    "variantes_nombre": [
                        "JUAN PEREZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        1,

                    "cantidad_evidencias":
                        1,

                    "score_total":
                        8,
                }
            ],
        }
    ]

    paths = export_consolidation(
        resultados=resultados,
        resumen={},
        experiment_name="test",
        used_config={},
        outputs_dir=tmp_path,
        now=datetime(
            2026,
            9,
            15,
            12,
            0,
            0,
        ),
    )

    with paths[
        "consolidacion_json"
    ].open(
        "r",
        encoding="utf-8",
    ) as fh:

        data = json.load(
            fh
        )

    assert (
        data[0][
            "personas_embargadas"
        ][0][
            "nombre_embargado"
        ]
        == "JUAN PEREZ"
    )


def test_exported_csv_contains_multiple_rows(
    tmp_path: Path,
):
    resultados = [
        {
            "numero_archivo": "1",
            "id": "doc-1",
            "nombre_documento": "Embargo",
            "estado": "RESUELTO_MULTIPLE",
            "cantidad_embargados": 2,

            "personas_embargadas": [
                {
                    "nombre_embargado":
                        "JUAN PEREZ",

                    "dni_embargado":
                        "11111111",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados":
                        [],

                    "variantes_nombre": [
                        "JUAN PEREZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        1,

                    "cantidad_evidencias":
                        1,

                    "score_total":
                        8,
                },
                {
                    "nombre_embargado":
                        "MARIA GOMEZ",

                    "dni_embargado":
                        "22222222",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados":
                        [],

                    "variantes_nombre": [
                        "MARIA GOMEZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        1,

                    "cantidad_evidencias":
                        1,

                    "score_total":
                        8,
                },
            ],
        }
    ]

    paths = export_consolidation(
        resultados=resultados,
        resumen={},
        experiment_name="test",
        used_config={},
        outputs_dir=tmp_path,
        now=datetime(
            2026,
            9,
            15,
            12,
            0,
            0,
        ),
    )

    with paths[
        "consolidacion_csv"
    ].open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as fh:

        rows = list(
            csv.DictReader(
                fh
            )
        )

    assert len(rows) == 2

    assert {
        row["nombre_embargado"]
        for row in rows
    } == {
        "JUAN PEREZ",
        "MARIA GOMEZ",
    }

def test_build_document_rows_conserva_texto_completo():
    texto_completo = (
        "OFICIO COMPLETO. "
        "Se decreta embargo sobre JUAN PEREZ."
    )

    rows = [
        {
            "id": "538118",

            "metadata": {
                "numero_archivo":
                    "1",

                "id":
                    "538118",

                "nombre":
                    "Embargo - usuario",

                "contador_interno":
                    "1",

                "palabra_clave":
                    "dni",

                "categoria":
                    "Datos_Embargado",

                "fragmento":
                    "Embargado JUAN PEREZ",

                "texto_completo":
                    texto_completo,
            },

            "candidates":
                [],
        }
    ]

    documentos = build_document_rows(
        rows
    )

    assert (
        len(documentos)
        == 1
    )

    assert (
        documentos[0][
            "texto_completo"
        ]
        == texto_completo
    )


def test_build_document_rows_recupera_texto_completo_de_otra_fila():
    texto_completo = (
        "Texto completo del documento."
    )

    rows = [
        {
            "id": "doc-1",

            "metadata": {
                "numero_archivo":
                    "1",

                "id":
                    "doc-1",

                "fragmento":
                    "Primer fragmento",
            },

            "candidates":
                [],
        },

        {
            "id": "doc-1",

            "metadata": {
                "numero_archivo":
                    "1",

                "id":
                    "doc-1",

                "fragmento":
                    "Segundo fragmento",

                "texto_completo":
                    texto_completo,
            },

            "candidates":
                [],
        },
    ]

    documentos = build_document_rows(
        rows
    )

    assert (
        len(documentos)
        == 1
    )

    assert (
        documentos[0][
            "texto_completo"
        ]
        == texto_completo
    )

    assert (
        len(
            documentos[0][
                "resultados"
            ]
        )
        == 2
    )


def test_export_consolidation_separa_suficientes_e_insuficientes(
    tmp_path: Path,
):
    resultados = [
        {
            "id":
                "doc-suficiente",

            "numero_archivo":
                "1",

            "nombre_documento":
                "Embargo - usuario",

            "texto_completo":
                "Texto completo 1",

            "estado":
                "RESUELTO",

            "suficiente":
                True,

            "requiere_fallback_documento_completo":
                False,

            "motivos_insuficiencia":
                [],

            "cantidad_embargados":
                1,

            "personas_embargadas": [
                {
                    "nombre_embargado":
                        "JUAN CARLOS PEREZ",

                    "dni_embargado":
                        "30111222",

                    "cuit_cuil_embargado":
                        "",

                    "roles_detectados": [
                        "demandado"
                    ],

                    "variantes_nombre": [
                        "JUAN CARLOS PEREZ"
                    ],

                    "cantidad_fragmentos_soporte":
                        2,

                    "cantidad_evidencias":
                        2,

                    "score_total":
                        15.0,

                    "identidad_inconsistente":
                        False,

                    "evidencias":
                        [],
                }
            ],

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,

            "conflictos_identificador":
                [],

            "grupos_descartados":
                [],
        },

        {
            "id":
                "doc-insuficiente",

            "numero_archivo":
                "2",

            "nombre_documento":
                "Embargo - usuario",

            "texto_completo":
                "Texto completo para fallback",

            "estado":
                "NO_RESUELTO",

            "suficiente":
                False,

            "requiere_fallback_documento_completo":
                True,

            "motivos_insuficiencia": [
                "no_resuelto",
                "sin_persona_embargada",
            ],

            "cantidad_embargados":
                0,

            "personas_embargadas":
                [],

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,

            "conflictos_identificador":
                [],

            "grupos_descartados":
                [],
        },
    ]

    resumen = {
        "total_documentos":
            2,

        "RESUELTO":
            1,

        "RESUELTO_MULTIPLE":
            0,

        "NO_RESUELTO":
            1,

        "total_personas_embargadas":
            1,

        "documentos_requieren_revision":
            0,

        "total_conflictos_identificador":
            0,

        "SUFICIENTES":
            1,

        "INSUFICIENTES":
            1,
    }

    paths = export_consolidation(
        resultados=resultados,
        resumen=resumen,
        experiment_name="test_suficiencia",
        used_config={},
        outputs_dir=tmp_path,
        now=datetime(
            2026,
            9,
            17,
            12,
            0,
            0,
        ),
    )

    assert (
        paths[
            "suficientes_json"
        ].exists()
    )

    assert (
        paths[
            "insuficientes_json"
        ].exists()
    )

    assert (
        paths[
            "suficientes_csv"
        ].exists()
    )

    assert (
        paths[
            "insuficientes_csv"
        ].exists()
    )

    with paths[
        "suficientes_json"
    ].open(
        "r",
        encoding="utf-8",
    ) as fh:

        suficientes = json.load(
            fh
        )

    with paths[
        "insuficientes_json"
    ].open(
        "r",
        encoding="utf-8",
    ) as fh:

        insuficientes = json.load(
            fh
        )

    assert (
        len(suficientes)
        == 1
    )

    assert (
        suficientes[0][
            "id"
        ]
        == "doc-suficiente"
    )

    assert (
        len(insuficientes)
        == 1
    )

    assert (
        insuficientes[0][
            "id"
        ]
        == "doc-insuficiente"
    )


def test_insuficientes_json_conserva_texto_completo(
    tmp_path: Path,
):
    texto_completo = (
        "DOCUMENTO COMPLETO PARA "
        "EJECUTAR EL FALLBACK."
    )

    resultados = [
        {
            "id":
                "doc-1",

            "numero_archivo":
                "1",

            "nombre_documento":
                "Embargo - usuario",

            "texto_completo":
                texto_completo,

            "estado":
                "NO_RESUELTO",

            "suficiente":
                False,

            "requiere_fallback_documento_completo":
                True,

            "motivos_insuficiencia": [
                "no_resuelto"
            ],

            "cantidad_embargados":
                0,

            "personas_embargadas":
                [],

            "grupos_descartados":
                [],

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,

            "conflictos_identificador":
                [],
        }
    ]

    paths = export_consolidation(
        resultados=resultados,
        resumen={
            "total_documentos":
                1,

            "RESUELTO":
                0,

            "RESUELTO_MULTIPLE":
                0,

            "NO_RESUELTO":
                1,

            "total_personas_embargadas":
                0,

            "documentos_requieren_revision":
                0,

            "total_conflictos_identificador":
                0,

            "SUFICIENTES":
                0,

            "INSUFICIENTES":
                1,
        },
        experiment_name="fallback_test",
        used_config={},
        outputs_dir=tmp_path,
        now=datetime(
            2026,
            9,
            17,
            12,
            0,
            0,
        ),
    )

    with paths[
        "insuficientes_json"
    ].open(
        "r",
        encoding="utf-8",
    ) as fh:

        data = json.load(
            fh
        )

    assert (
        data[0][
            "texto_completo"
        ]
        == texto_completo
    )

    assert (
        data[0][
            "requiere_fallback_documento_completo"
        ]
        is True
    )


def test_csv_consolidacion_incluye_campos_suficiencia():
    resultados = [
        {
            "numero_archivo":
                "1",

            "id":
                "doc-1",

            "nombre_documento":
                "Embargo",

            "estado":
                "NO_RESUELTO",

            "suficiente":
                False,

            "requiere_fallback_documento_completo":
                True,

            "motivos_insuficiencia": [
                "no_resuelto",
                "sin_persona_embargada",
            ],

            "cantidad_embargados":
                0,

            "personas_embargadas":
                [],

            "requiere_revision":
                False,

            "cantidad_conflictos_identificador":
                0,
        }
    ]

    rows = (
        _build_consolidation_csv_rows(
            resultados
        )
    )

    assert len(
        rows
    ) == 1

    row = rows[
        0
    ]

    assert (
        row["suficiente"]
        is False
    )

    assert (
        row[
            "requiere_fallback_documento_completo"
        ]
        is True
    )

    assert (
        row[
            "motivos_insuficiencia"
        ]
        == (
            "no_resuelto | "
            "sin_persona_embargada"
        )
    )


def test_to_dict_soporta_dataclass():
    @dataclass(slots=True)
    class ResultadoPrueba:
        id: str
        nombre: str

    resultado = ResultadoPrueba(
        id="123",
        nombre="Prueba",
    )

    convertido = _to_dict(
        resultado
    )

    assert convertido == {
        "id": "123",
        "nombre": "Prueba",
    }

def test_build_document_rows_postprocessed_real_structure():
    rows = [
        {
            "prediction": {
                "record": {
                    "numero_archivo": "1",
                    "id": "538118",
                    "nombre": "Embargo - usuario",
                    "texto": (
                        "decretado el EMBARGO sobre "
                        "los fondos del demandado"
                    ),
                    "modo_entrada": "fragmentos",
                    "contador_interno": "1",
                    "palabra_clave": "dni",
                    "posicion_inicio": "1787",
                    "posicion_fin": "1790",
                    "inicio_fragmento": "1687",
                    "fin_fragmento": "1810",
                    "metadata": {
                        "categoria":
                            "Datos_Embargado",

                        "texto_completo":
                            "TEXTO COMPLETO DEL DOCUMENTO",
                    },
                },
                "model_id": "gliner2_multi",
                "schema_id":
                    "schema_v7_persona_embargada_fragmentos",
                "threshold": 0.5,
                "schema_type": "structured",
                "architecture": "gliner2",
                "raw_response": {},
                "normalized_items": [],
            },
            "status": "candidato_unico",
            "candidates": [
                {
                    "nombre_embargado":
                        "NAHUEL OSCAR MARQUEZ",

                    "dni_embargado":
                        "33.470.065",
                }
            ],
        }
    ]

    documentos = build_document_rows(
        rows
    )

    assert len(
        documentos
    ) == 1

    documento = documentos[
        0
    ]

    assert (
        documento["id"]
        == "538118"
    )

    assert (
        documento["numero_archivo"]
        == "1"
    )

    assert (
        documento["texto_completo"]
        == "TEXTO COMPLETO DEL DOCUMENTO"
    )

    assert (
        documento[
            "resultados"
        ][0][
            "contador_interno"
        ]
        == "1"
    )

    assert (
        documento[
            "resultados"
        ][0][
            "palabra_clave"
        ]
        == "dni"
    )

    assert (
        documento[
            "resultados"
        ][0][
            "categoria"
        ]
        == "Datos_Embargado"
    )

    assert (
        documento[
            "resultados"
        ][0][
            "fragmento"
        ]
        == (
            "decretado el EMBARGO sobre "
            "los fondos del demandado"
        )
    )

    assert (
        documento[
            "resultados"
        ][0][
            "candidates"
        ][0][
            "nombre_embargado"
        ]
        == "NAHUEL OSCAR MARQUEZ"
    )

def test_build_document_rows_no_mezcla_documentos():
    rows = [
        {
            "prediction": {
                "record": {
                    "numero_archivo": "1",
                    "id": "doc-1",
                    "nombre": "Embargo 1",
                    "texto": "Fragmento 1",
                    "modo_entrada": "fragmentos",
                    "contador_interno": "1",
                    "palabra_clave": "dni",
                    "metadata": {},
                }
            },
            "status": "candidato_unico",
            "candidates": [],
        },
        {
            "prediction": {
                "record": {
                    "numero_archivo": "2",
                    "id": "doc-2",
                    "nombre": "Embargo 2",
                    "texto": "Fragmento 2",
                    "modo_entrada": "fragmentos",
                    "contador_interno": "1",
                    "palabra_clave": "dni",
                    "metadata": {},
                }
            },
            "status": "candidato_unico",
            "candidates": [],
        },
    ]

    documentos = build_document_rows(
        rows
    )

    assert len(
        documentos
    ) == 2

    ids = {
        documento["id"]
        for documento
        in documentos
    }

    assert ids == {
        "doc-1",
        "doc-2",
    }