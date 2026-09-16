import csv
import json

from datetime import datetime
from pathlib import Path

from src.exporter import (
    _build_consolidation_csv_rows,
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