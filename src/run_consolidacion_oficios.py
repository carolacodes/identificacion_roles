"""CLI independiente para consolidar predicciones de fragmentos de OFICIOS.

Ejecutar desde la raiz del repositorio:
    python -m src.run_consolidacion_oficios --input RUTA/predicciones_por_documento.json --name prueba10

No importa consolidacion_embargado ni exporter.py y no escribe en outputs/consolidacion/.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .consolidacion_oficios import consolidar_documentos, resumir_consolidacion

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / 'outputs' / 'consolidacion_oficios'
LOG_DIR = PROJECT_ROOT / 'outputs' / 'logs'
LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Consolida personas objeto de oficios a partir de predicciones por documento.')
    parser.add_argument('--input', required=True, help='Ruta a predicciones_por_documento.json')
    parser.add_argument('--name', default=None, help='Etiqueta opcional para la corrida')
    return parser.parse_args()


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s - %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / 'consolidacion_oficios.log', encoding='utf-8')])


def _resolve_input_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def load_predictions(input_path: str | Path) -> list[dict[str, Any]]:
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f'No existe el archivo de entrada: {path}')
    try:
        with path.open(encoding='utf-8') as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f'JSON invalido: {path}') from exc
    if not isinstance(data, list):
        raise ValueError('El JSON debe contener una lista de documentos')
    for index, item in enumerate(data):
        if not isinstance(item, dict) or 'id' not in item or not isinstance(item.get('resultados'), list):
            raise ValueError(f'Documento en posicion {index}: requiere id y resultados (lista)')
    return data


def _run_label(input_path: Path, name: str | None) -> str:
    label = (name or input_path.parent.name or 'oficios').strip()
    label = re.sub(r'[^a-zA-Z0-9_-]+', '_', label).strip('_')
    return label[:80] or 'oficios'


def _write_json(path: Path, data: Any) -> None:
    with path.open('w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter=',', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def _csv_rows(resultados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for doc in resultados:
        personas = doc.get('personas_objeto_oficio') or []
        base = {
            'numero_archivo': doc.get('numero_archivo', ''),
            'id': doc.get('id', ''),
            'nombre_documento': doc.get('nombre_documento', ''),
            'estado': doc.get('estado', ''),
            'suficiente': doc.get('suficiente', False),
            'requiere_fallback_documento_completo': doc.get('requiere_fallback_documento_completo', False),
            'motivos_insuficiencia': ' | '.join(doc.get('motivos_insuficiencia') or []),
            'cantidad_personas_objeto_oficio': len(personas),
            'requiere_revision': doc.get('requiere_revision', False),
            'cantidad_conflictos_identificador': doc.get('cantidad_conflictos_identificador', 0),
        }
        if not personas:
            rows.append({**base, 'indice_persona': '', 'nombre_persona': '', 'dni_persona': '', 'cuit_cuil_persona': '', 'roles_detectados': '', 'variantes_nombre': '', 'cantidad_fragmentos_soporte': 0, 'cantidad_evidencias': 0, 'score_total': '', 'identidad_inconsistente': ''})
            continue
        for idx, person in enumerate(personas, start=1):
            rows.append({**base,
                'indice_persona': idx,
                'nombre_persona': person.get('nombre_persona', ''),
                'dni_persona': person.get('dni_persona', ''),
                'cuit_cuil_persona': person.get('cuit_cuil_persona', ''),
                'roles_detectados': ' | '.join(person.get('roles_detectados') or []),
                'variantes_nombre': ' | '.join(person.get('variantes_nombre') or []),
                'cantidad_fragmentos_soporte': person.get('cantidad_fragmentos_soporte', 0),
                'cantidad_evidencias': person.get('cantidad_evidencias', 0),
                'score_total': person.get('score_total', ''),
                'identidad_inconsistente': person.get('identidad_inconsistente', False),
            })
    return rows


CSV_FIELDS = ['numero_archivo', 'id', 'nombre_documento', 'estado', 'suficiente',
              'requiere_fallback_documento_completo', 'motivos_insuficiencia',
              'cantidad_personas_objeto_oficio', 'indice_persona', 'nombre_persona',
              'dni_persona', 'cuit_cuil_persona', 'roles_detectados', 'variantes_nombre',
              'cantidad_fragmentos_soporte', 'cantidad_evidencias', 'score_total',
              'identidad_inconsistente', 'requiere_revision', 'cantidad_conflictos_identificador']


def export_oficios(resultados: list[dict[str, Any]], resumen: dict[str, int],
                   input_path: Path, run_name: str) -> dict[str, Path]:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out_dir = OUTPUT_ROOT / f'{timestamp}_{run_name}'
    out_dir.mkdir(parents=True, exist_ok=False)
    consol = out_dir / 'consolidacion.json'
    summary = out_dir / 'resumen.json'
    metadata = out_dir / 'metadata.json'
    csv_path = out_dir / 'consolidacion.csv'
    insuff = out_dir / 'insuficientes.json'
    suff = out_dir / 'suficientes.json'
    insuff_csv = out_dir / 'insuficientes.csv'
    suff_csv = out_dir / 'suficientes.csv'

    # Un mismo criterio para JSON y CSV: evita discrepancias entre formatos.
    suficientes = [r for r in resultados if r.get('suficiente') is True]
    insuficientes = [r for r in resultados if r.get('suficiente') is not True]

    _write_json(consol, resultados)
    _write_json(summary, resumen)
    _write_json(metadata, {'tipo': 'oficios', 'input_file': str(input_path), 'run_name': run_name,
                          'total_documentos': len(resultados), 'modulo': 'src.consolidacion_oficios',
                          'exportador': 'src.run_consolidacion_oficios'})
    _write_json(insuff, insuficientes)
    _write_json(suff, suficientes)
    _write_csv(csv_path, _csv_rows(resultados), CSV_FIELDS)
    _write_csv(insuff_csv, _csv_rows(insuficientes), CSV_FIELDS)
    _write_csv(suff_csv, _csv_rows(suficientes), CSV_FIELDS)

    return {
        'consolidacion_dir': out_dir,
        'consolidacion_json': consol,
        'consolidacion_csv': csv_path,
        'resumen_json': summary,
        'metadata_json': metadata,
        'insuficientes_json': insuff,
        'insuficientes_csv': insuff_csv,
        'suficientes_json': suff,
        'suficientes_csv': suff_csv,
    }



def run_consolidacion(input_file: str | Path, run_name: str | None = None) -> dict[str, Path]:
    path = _resolve_input_path(input_file)
    LOGGER.info('Inicio consolidacion oficios. Archivo: %s', path)
    documentos = load_predictions(path)
    resultados = consolidar_documentos(documentos)
    resumen = resumir_consolidacion(resultados)
    paths = export_oficios(resultados, resumen, path, _run_label(path, run_name))
    LOGGER.info('Finalizado: documentos=%s resueltos=%s multiples=%s no_resueltos=%s personas=%s suficientes=%s insuficientes=%s',
                resumen.get('total_documentos', 0), resumen.get('RESUELTO', 0),
                resumen.get('RESUELTO_MULTIPLE', 0), resumen.get('NO_RESUELTO', 0),
                resumen.get('total_personas_objeto_oficio', 0), resumen.get('SUFICIENTES', 0),
                resumen.get('INSUFICIENTES', 0))
    LOGGER.info('Salida: %s', paths['consolidacion_dir'])
    return paths


def main() -> None:
    args = parse_args()
    setup_logging()
    run_consolidacion(args.input, args.name)


if __name__ == '__main__':
    main()
