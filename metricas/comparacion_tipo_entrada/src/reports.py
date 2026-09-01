"""Generacion de archivos de salida para la comparacion."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_COLUMNS = [
    "id",
    "numero_archivo",
    "nombre_documento",
    "docs_detecto_algo",
    "docs_detecto_nombre",
    "docs_nombre",
    "docs_nombre_normalizado",
    "docs_nombre_confidence",
    "docs_detecto_dni",
    "docs_dni",
    "docs_dni_normalizado",
    "docs_dni_confidence",
    "docs_detecto_cuil_cuit",
    "docs_cuil_cuit",
    "docs_cuil_cuit_normalizado",
    "docs_cuil_cuit_confidence",
    "docs_estado_postprocess",
    "frag_cantidad_fragmentos",
    "frag_fragmentos_con_candidato",
    "frag_detecto_algo",
    "frag_detecto_nombre",
    "frag_nombres_unicos",
    "frag_nombres_normalizados",
    "frag_detecto_dni",
    "frag_dni_unicos",
    "frag_dni_normalizados",
    "frag_detecto_cuil_cuit",
    "frag_cuil_cuit_unicos",
    "frag_cuil_cuit_normalizados",
    "frag_nombre_confidence_max",
    "frag_nombre_confidence_media",
    "frag_dni_confidence_max",
    "frag_dni_confidence_media",
    "frag_cuil_cuit_confidence_max",
    "frag_cuil_cuit_confidence_media",
    "acuerdo_nombre",
    "acuerdo_dni",
    "acuerdo_cuil_cuit",
    "ambos_detectan_nombre",
    "solo_documento_detecta_nombre",
    "solo_fragmentos_detectan_nombre",
    "ninguno_detecta_nombre",
    "ambos_detectan_dni",
    "solo_documento_detecta_dni",
    "solo_fragmentos_detectan_dni",
    "ninguno_detecta_dni",
    "ambos_detectan_cuil_cuit",
    "solo_documento_detecta_cuil_cuit",
    "solo_fragmentos_detectan_cuil_cuit",
    "ninguno_detecta_cuil_cuit",
]


def create_output_dir(base_dir: str | Path, run_name: str | None) -> Path:
    safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in (run_name or "comparacion"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(base_dir) / f"{timestamp}_{safe_name}"
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def serialize_cell(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_cell(row.get(key)) for key in fieldnames})


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def flatten_metrics(metrics: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in metrics.items():
        metric_name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(flatten_metrics(value, metric_name))
        else:
            rows.append({"metrica": metric_name, "valor": serialize_cell(value)})
    return rows


def format_pct(metric: dict[str, Any]) -> str:
    return f"{metric.get('porcentaje', 0):.2f}%"


def build_summary_rows(
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Construye el resumen principal adaptado al tipo de schema."""

    config = metrics.get(
        "configuracion",
        {},
    )

    simple_schema = bool(
        config.get(
            "schema_simple",
            False,
        )
    )

    docs = metrics[
        "cobertura_documentos_completos"
    ]

    frags = metrics[
        "cobertura_fragmentos_por_documento"
    ]

    confidence = metrics[
        "confidence"
    ]

    timing = metrics[
        "rendimiento"
    ]

    def format_pct(
        value: dict[str, Any] | None,
    ) -> str:
        if not value:
            return "-"

        porcentaje = value.get(
            "porcentaje"
        )

        if porcentaje is None:
            return "-"

        return f"{porcentaje:.2f}%"

    rows: list[
        dict[str, Any]
    ] = [
        {
            "metrica":
                "Cobertura persona embargada",

            "documentos_completos":
                format_pct(
                    docs.get(
                        "documentos_con_nombre"
                    )
                ),

            "fragmentos":
                format_pct(
                    frags.get(
                        "documentos_con_nombre"
                    )
                ),
        },
        {
            "metrica":
                "No detectados",

            "documentos_completos":
                format_pct(
                    docs.get(
                        "documentos_no_detectados"
                    )
                ),

            "fragmentos":
                format_pct(
                    frags.get(
                        "documentos_sin_deteccion_en_ningun_fragmento"
                    )
                ),
        },
        {
            "metrica":
                "Múltiples candidatos",

            "documentos_completos":
                format_pct(
                    docs.get(
                        "documentos_multiples_candidatos"
                    )
                ),

            "fragmentos":
                format_pct(
                    frags.get(
                        "documentos_con_multiples_nombres_distintos"
                    )
                ),
        },
        {
            "metrica":
                "Candidato único",

            "documentos_completos":
                format_pct(
                    docs.get(
                        "documentos_candidato_unico"
                    )
                ),

            "fragmentos":
                format_pct(
                    frags.get(
                        "documentos_con_un_nombre_unico"
                    )
                ),
        },
    ]

    if not simple_schema:

        rows.extend(
            [
                {
                    "metrica":
                        "Cobertura DNI",

                    "documentos_completos":
                        format_pct(
                            docs.get(
                                "documentos_con_dni"
                            )
                        ),

                    "fragmentos":
                        format_pct(
                            frags.get(
                                "documentos_con_dni"
                            )
                        ),
                },
                {
                    "metrica":
                        "Cobertura CUIL/CUIT",

                    "documentos_completos":
                        format_pct(
                            docs.get(
                                "documentos_con_cuil_cuit"
                            )
                        ),

                    "fragmentos":
                        format_pct(
                            frags.get(
                                "documentos_con_cuil_cuit"
                            )
                        ),
                },
            ]
        )

    docs_confidence = (
        confidence
        .get(
            "documentos",
            {}
        )
        .get(
            "nombre_confidence",
            {}
        )
        .get(
            "media"
        )
    )

    fragments_confidence = (
        confidence
        .get(
            "fragmentos",
            {}
        )
        .get(
            "nombre_confidence_max_por_documento",
            {}
        )
        .get(
            "media"
        )
    )

    rows.append(
        {
            "metrica":
                "Confidence media persona embargada",

            "documentos_completos":
                docs_confidence,

            "fragmentos":
                fragments_confidence,
        }
    )

    rows.append(
        {
            "metrica":
                "Tiempo total segundos",

            "documentos_completos":
                timing.get(
                    "tiempo_total_documentos"
                ),

            "fragmentos":
                timing.get(
                    "tiempo_total_fragmentos"
                ),
        }
    )

    return rows


def disagreement_rows(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs = [
        ("nombre", "docs_nombre", "frag_nombres_unicos", "docs_nombre_confidence", "frag_nombre_confidence_media"),
        ("dni", "docs_dni", "frag_dni_unicos", "docs_dni_confidence", "frag_dni_confidence_media"),
        ("cuil_cuit", "docs_cuil_cuit", "frag_cuil_cuit_unicos", "docs_cuil_cuit_confidence", "frag_cuil_cuit_confidence_media"),
    ]
    for row in comparisons:
        for field, doc_value, frag_values, doc_conf, frag_conf in specs:
            if row[f"ambos_detectan_{field}"] and not row[f"acuerdo_{field}"]:
                rows.append({
                    "id": row["id"],
                    "numero_archivo": row["numero_archivo"],
                    "campo_desacuerdo": field,
                    "valor_documento": row[doc_value],
                    "valores_fragmentos": row[frag_values],
                    "confidence_documento": row[doc_conf],
                    "confidences_fragmentos": row[frag_conf],
                })
    return rows


def exclusive_rows(comparisons: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in comparisons:
        for field in ("nombre", "dni", "cuil_cuit"):
            key = f"solo_{side}_detecta_{field}" if side == "documento" else f"solo_{side}_detectan_{field}"
            if row[key]:
                rows.append({"id": row["id"], "numero_archivo": row["numero_archivo"], "campo": field, **row})
    return rows


def ambiguous_rows(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in comparisons:
        ambiguous_fields = [
            field
            for field, key in (
                ("nombre", "frag_nombres_normalizados"),
                ("dni", "frag_dni_normalizados"),
                ("cuil_cuit", "frag_cuil_cuit_normalizados"),
            )
            if len(row[key]) > 1
        ]
        if ambiguous_fields:
            rows.append({"campos_ambiguos": ambiguous_fields, **row})
    return rows


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(col, "")) for col in columns) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def build_report(
    metrics: dict[str, Any],
    summary_rows: list[dict[str, Any]],
) -> str:
    """Genera reporte Markdown adaptado al tipo de schema."""

    config = metrics.get(
        "configuracion",
        {},
    )

    simple_schema = bool(
        config.get(
            "schema_simple",
            False,
        )
    )

    agreement = metrics.get(
        "agreement_entre_modos",
        {},
    )

    ambiguity = metrics.get(
        "ambiguedad_fragmentos",
        {},
    )

    confidence = metrics.get(
        "confidence",
        {},
    )

    timing = metrics.get(
        "rendimiento",
        {},
    )

    lines: list[str] = []

    lines.append(
        "# Comparación documentos completos vs fragmentos"
    )

    lines.append("")
    lines.append("## Configuración")
    lines.append("")

    lines.append(
        f"* modelo: {config.get('modelo')}"
    )

    lines.append(
        f"* schema: {config.get('schema')}"
    )

    lines.append(
        f"* threshold: {config.get('threshold')}"
    )

    lines.append(
        "* cantidad de documentos: "
        f"{config.get('cantidad_documentos_comparados')}"
    )

    lines.append(
        "* cantidad de fragmentos: "
        f"{config.get('cantidad_fragmentos')}"
    )

    lines.append("")
    lines.append("## Resumen principal")
    lines.append("")

    lines.append(
        "| metrica | documentos_completos | fragmentos |"
    )

    lines.append(
        "| --- | --- | --- |"
    )

    for row in summary_rows:
        lines.append(
            "| "
            f"{row.get('metrica')} | "
            f"{row.get('documentos_completos')} | "
            f"{row.get('fragmentos')} |"
        )

    lines.append("")
    lines.append("## Acuerdo entre modos")
    lines.append("")

    nombre_count = agreement.get(
        "acuerdo_nombre_count",
        0,
    )

    nombre_den = agreement.get(
        "acuerdo_nombre_denominador",
        0,
    )

    nombre_pct = agreement.get(
        "acuerdo_nombre_pct",
        0.0,
    )

    lines.append(
        "* Persona embargada: "
        f"{nombre_count} de {nombre_den} "
        f"({nombre_pct:.2f}%)"
    )

    if not simple_schema:

        dni_count = agreement.get(
            "acuerdo_dni_count",
            0,
        )

        dni_den = agreement.get(
            "acuerdo_dni_denominador",
            0,
        )

        dni_pct = agreement.get(
            "acuerdo_dni_pct",
            0.0,
        )

        lines.append(
            "* DNI: "
            f"{dni_count} de {dni_den} "
            f"({dni_pct:.2f}%)"
        )

        cuil_count = agreement.get(
            "acuerdo_cuil_cuit_count",
            0,
        )

        cuil_den = agreement.get(
            "acuerdo_cuil_cuit_denominador",
            0,
        )

        cuil_pct = agreement.get(
            "acuerdo_cuil_cuit_pct",
            0.0,
        )

        lines.append(
            "* CUIL/CUIT: "
            f"{cuil_count} de {cuil_den} "
            f"({cuil_pct:.2f}%)"
        )

    lines.append("")
    lines.append("## Casos exclusivos")
    lines.append("")

    lines.append(
        "Ver `casos_solo_documento.csv` y "
        "`casos_solo_fragmentos.csv`."
    )

    lines.append("")
    lines.append("## Ambigüedad")
    lines.append("")

    if simple_schema:

        nombre_ambiguity = ambiguity.get(
            "nombre",
            {},
        )

        cero = nombre_ambiguity.get(
            "0_unicos",
            {},
        )

        uno = nombre_ambiguity.get(
            "1_unico",
            {},
        )

        multiples = nombre_ambiguity.get(
            "mas_de_1_unico",
            {},
        )

        lines.append(
            "* Sin candidato en fragmentos: "
            f"{cero.get('cantidad', 0)} "
            f"({cero.get('porcentaje', 0.0):.2f}%)"
        )

        lines.append(
            "* Un candidato único en fragmentos: "
            f"{uno.get('cantidad', 0)} "
            f"({uno.get('porcentaje', 0.0):.2f}%)"
        )

        lines.append(
            "* Más de un candidato distinto en fragmentos: "
            f"{multiples.get('cantidad', 0)} "
            f"({multiples.get('porcentaje', 0.0):.2f}%)"
        )

    else:

        lines.append(
            "Ver `casos_ambiguos_fragmentos.csv` y la sección "
            "`ambiguedad_fragmentos` en `metricas_globales.json`."
        )

    lines.append("")
    lines.append("## Confidence")
    lines.append("")

    lines.append(
        "La confidence se reporta como señal del modelo, "
        "no como evidencia de exactitud."
    )

    lines.append("")
    lines.append("## Rendimiento")
    lines.append("")

    lines.append(
        "* tiempo total documentos: "
        f"{timing.get('tiempo_total_documentos')}"
    )

    lines.append(
        "* tiempo total fragmentos: "
        f"{timing.get('tiempo_total_fragmentos')}"
    )

    lines.append(
        "* segundos por documento en documentos completos: "
        f"{timing.get('segundos_por_documento_documentos')}"
    )

    lines.append(
        "* segundos por documento en fragmentos: "
        f"{timing.get('segundos_por_documento_fragmentos')}"
    )

    lines.append(
        "* segundos por fragmento: "
        f"{timing.get('segundos_por_fragmento')}"
    )

    lines.append(
        "* speedup fragmentos vs documentos: "
        f"{timing.get('speedup_fragmentos_vs_documentos')}"
    )

    lines.append("")
    lines.append("## Interpretación")
    lines.append("")

    if simple_schema:

        lines.append(
            "Este experimento usa un schema simple que extrae únicamente "
            "`persona_embargada`. Por lo tanto, la comparación se centra en "
            "cobertura del rol, cantidad de candidatos, acuerdo entre modos, "
            "ambigüedad y confidence."
        )

    else:

        lines.append(
            "Estas métricas permiten observar cobertura de nombre, DNI y "
            "CUIL/CUIT, acuerdo entre modos, ambigüedad, confidence y tiempo "
            "de ejecución."
        )

    lines.append("")

    lines.append(
        "Estas métricas comparan el comportamiento de ambos modos de entrada. "
        "No representan accuracy real porque no se dispone aún de un gold manual."
    )

    return "\n".join(
        lines
    )


def write_all_outputs(output_dir: Path, comparisons: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    summary_rows = build_summary_rows(metrics)
    write_csv(output_dir / "resumen_comparacion.csv", summary_rows, ["metrica", "documentos_completos", "fragmentos"])
    write_csv(output_dir / "comparacion_por_documento.csv", comparisons, BASE_COLUMNS)
    write_json(output_dir / "comparacion_por_documento.json", comparisons)
    write_json(output_dir / "metricas_globales.json", metrics)
    write_csv(output_dir / "metricas_globales.csv", flatten_metrics(metrics), ["metrica", "valor"])
    write_csv(
        output_dir / "casos_desacuerdo.csv",
        disagreement_rows(comparisons),
        ["id", "numero_archivo", "campo_desacuerdo", "valor_documento", "valores_fragmentos", "confidence_documento", "confidences_fragmentos"],
    )
    write_csv(output_dir / "casos_solo_documento.csv", exclusive_rows(comparisons, "documento"), ["id", "numero_archivo", "campo", *BASE_COLUMNS])
    write_csv(output_dir / "casos_solo_fragmentos.csv", exclusive_rows(comparisons, "fragmentos"), ["id", "numero_archivo", "campo", *BASE_COLUMNS])
    write_csv(output_dir / "casos_ambiguos_fragmentos.csv", ambiguous_rows(comparisons), ["campos_ambiguos", *BASE_COLUMNS])
    (output_dir / "reporte.md").write_text(build_report(metrics, summary_rows), encoding="utf-8")
