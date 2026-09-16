"""CLI independiente para consolidar predicciones por documento.

Este modulo NO ejecuta GLiNER.

Toma como entrada un archivo:

    predicciones_por_documento.json

generado previamente por el pipeline de extraccion y ejecuta:

    consolidar_documentos()
    resumir_consolidacion()
    export_consolidation()

La salida se guarda en:

    outputs/consolidacion/
"""

from __future__ import annotations

import argparse
import json
import logging

from pathlib import Path
from typing import Any

from .consolidacion_embargado import (
    consolidar_documentos,
    resumir_consolidacion,
)

from .exporter import export_consolidation


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

LOG_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "logs"
)


def parse_args() -> argparse.Namespace:
    """Lee argumentos de consola."""

    parser = argparse.ArgumentParser(
        description=(
            "Consolida personas embargadas a partir "
            "de predicciones_por_documento.json."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "Ruta al archivo "
            "predicciones_por_documento.json."
        ),
    )

    parser.add_argument(
        "--name",
        required=False,
        default=None,
        help=(
            "Nombre opcional para identificar "
            "la corrida de consolidacion."
        ),
    )

    return parser.parse_args()


def setup_logging() -> None:
    """Configura logging de consola y archivo."""

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logging.basicConfig(
        level=logging.INFO,

        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s - "
            "%(message)s"
        ),

        handlers=[
            logging.StreamHandler(),

            logging.FileHandler(
                LOG_DIR
                / "consolidacion.log",
                encoding="utf-8",
            ),
        ],
    )


def _resolve_input_path(
    input_value: str,
) -> Path:
    """Resuelve rutas relativas respecto de la raiz del proyecto."""

    path = Path(
        input_value
    )

    if not path.is_absolute():
        path = (
            PROJECT_ROOT
            / path
        )

    return path.resolve()


def load_predictions(
    input_path: str | Path,
) -> list[dict[str, Any]]:
    """Carga y valida predicciones_por_documento.json."""

    path = Path(
        input_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"No existe el archivo de entrada: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"La ruta de entrada no es un archivo: {path}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as fh:
            data = json.load(
                fh
            )

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"El archivo no contiene JSON valido: {path}"
        ) from exc

    if not isinstance(
        data,
        list,
    ):
        raise ValueError(
            "El JSON de entrada debe contener "
            "una lista de documentos."
        )

    for index, documento in enumerate(
        data
    ):
        if not isinstance(
            documento,
            dict,
        ):
            raise ValueError(
                "Cada elemento del JSON debe ser "
                f"un objeto. Error en indice {index}."
            )

        if "id" not in documento:
            raise ValueError(
                f"Documento en indice {index} "
                "no contiene campo 'id'."
            )

        if "resultados" not in documento:
            raise ValueError(
                f"Documento en indice {index} "
                "no contiene campo 'resultados'."
            )

        if not isinstance(
            documento["resultados"],
            list,
        ):
            raise ValueError(
                f"'resultados' debe ser una lista "
                f"en documento indice {index}."
            )

    return data


def _derive_run_name(
    input_path: Path,
    explicit_name: str | None,
) -> str:
    """Obtiene un nombre razonable para la corrida."""

    if explicit_name:
        return explicit_name.strip()

    parent_name = (
        input_path
        .parent
        .name
        .strip()
    )

    if parent_name:
        return parent_name

    return "consolidacion"


def run_consolidacion(
    input_file: str | Path,
    run_name: str | None = None,
) -> dict[str, Path]:
    """Ejecuta el pipeline completo de consolidacion."""

    logger = logging.getLogger(
        __name__
    )

    input_path = (
        _resolve_input_path(
            str(input_file)
        )
    )

    logger.info(
        "Inicio de consolidacion"
    )

    logger.info(
        "Archivo de entrada: %s",
        input_path,
    )

    documentos = load_predictions(
        input_path
    )

    logger.info(
        "Documentos cargados: %s",
        len(documentos),
    )

    resultados = (
        consolidar_documentos(
            documentos
        )
    )

    resumen = (
        resumir_consolidacion(
            resultados
        )
    )

    resolved_name = (
        _derive_run_name(
            input_path,
            run_name,
        )
    )

    used_config: dict[
        str,
        Any,
    ] = {
        "input_file":
            str(input_path),

        "run_name":
            resolved_name,

        "consolidacion": {
            "fuzzy_threshold_strict":
                90.0,

            "fuzzy_threshold_partial":
                85.0,

            "min_tokens_partial_match":
                2,

            "min_score_embargado":
                6.0,

            "score_evidencia_fuerte":
                10.0,
        },
    }

    paths = export_consolidation(
        resultados=resultados,

        resumen=resumen,

        experiment_name=resolved_name,

        used_config=used_config,
    )

    logger.info(
        (
            "Consolidacion finalizada: "
            "documentos=%s "
            "resueltos=%s "
            "multiples=%s "
            "no_resueltos=%s "
            "personas=%s"
        ),

        resumen.get(
            "total_documentos",
            0,
        ),

        resumen.get(
            "RESUELTO",
            0,
        ),

        resumen.get(
            "RESUELTO_MULTIPLE",
            0,
        ),

        resumen.get(
            "NO_RESUELTO",
            0,
        ),

        resumen.get(
            "total_personas_embargadas",
            0,
        ),
    )

    logger.info(
        "Salida: %s",
        paths.get(
            "consolidacion_dir"
        ),
    )

    return paths


def main() -> None:
    """Entry point."""

    args = parse_args()

    setup_logging()

    run_consolidacion(
        input_file=args.input,
        run_name=args.name,
    )


if __name__ == "__main__":
    main()