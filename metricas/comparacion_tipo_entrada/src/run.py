"""CLI para generar metricas de comparacion por tipo de entrada."""

from __future__ import annotations

import argparse
from pathlib import Path

from .compare_by_document import compare_by_document
from .load_results import load_results, validate_compatible_inputs
from .metrics import compute_global_metrics
from .reports import create_output_dir, write_all_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compara documentos completos contra fragmentos sin gold manual.")
    parser.add_argument("--documentos", required=True, help="Archivo JSON o CSV de predicciones sobre documentos completos.")
    parser.add_argument("--fragmentos", required=True, help="Archivo JSON o CSV de predicciones sobre fragmentos.")
    parser.add_argument("--run-name", required=True, help="Nombre descriptivo de la corrida de metricas.")
    parser.add_argument("--docs-seconds", type=float, default=None, help="Tiempo total de documentos completos en segundos.")
    parser.add_argument("--fragments-seconds", type=float, default=None, help="Tiempo total de fragmentos en segundos.")
    return parser.parse_args()


def run(
    documentos: str | Path,
    fragmentos: str | Path,
    run_name: str,
    docs_seconds: float | None = None,
    fragments_seconds: float | None = None,
) -> Path:
    document_rows = load_results(documentos)
    fragment_rows = load_results(fragmentos)
    metadata = validate_compatible_inputs(document_rows, fragment_rows)
    comparisons = compare_by_document(document_rows, fragment_rows, metadata["ids_comunes"])
    metrics = compute_global_metrics(document_rows, fragment_rows, comparisons, metadata, docs_seconds, fragments_seconds)
    base_output_dir = Path(__file__).resolve().parents[1] / "outputs"
    output_dir = create_output_dir(base_output_dir, run_name)
    write_all_outputs(output_dir, comparisons, metrics)
    return output_dir


def main() -> None:
    args = parse_args()
    output_dir = run(
        documentos=args.documentos,
        fragmentos=args.fragmentos,
        run_name=args.run_name,
        docs_seconds=args.docs_seconds,
        fragments_seconds=args.fragments_seconds,
    )
    print(f"Outputs generados en: {output_dir}")


if __name__ == "__main__":
    main()

