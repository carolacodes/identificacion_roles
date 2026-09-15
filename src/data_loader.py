"""Lectura de CSVs de documentos completos y fragmentos."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, TextIO


DOCUMENT_MODE = "documentos_completos"
FRAGMENT_MODE = "fragmentos"


DOCUMENT_REQUIRED_COLUMNS = {
    "id",
}


FRAGMENT_REQUIRED_COLUMNS = {
    "numero_archivo",
    "id",
    "nombre",
    "contador_interno",
    "palabra_clave",
    "categoria",
    "posicion_inicio",
    "posicion_fin",
    "inicio_fragmento",
    "fin_fragmento",
}


class DataLoaderError(ValueError):
    """Error de lectura o validacion de datos."""


@dataclass(slots=True)
class InputRecord:
    """Registro normalizado usado por el pipeline."""

    numero_archivo: str
    id: str
    nombre: str
    texto: str
    modo_entrada: str

    contador_interno: str | None = None
    palabra_clave: str | None = None
    categoria: str | None = None

    posicion_inicio: str | None = None
    posicion_fin: str | None = None
    inicio_fragmento: str | None = None
    fin_fragmento: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convierte el registro a dict conservando metadata adicional."""

        base = {
            "numero_archivo": self.numero_archivo,
            "id": self.id,
            "nombre": self.nombre,
            "texto": self.texto,
            "modo_entrada": self.modo_entrada,

            "contador_interno": self.contador_interno,
            "palabra_clave": self.palabra_clave,
            "categoria": self.categoria,

            "posicion_inicio": self.posicion_inicio,
            "posicion_fin": self.posicion_fin,
            "inicio_fragmento": self.inicio_fragmento,
            "fin_fragmento": self.fin_fragmento,
        }

        base.update(self.metadata)

        return base


def _open_csv(path: Path) -> TextIO:
    """Abre CSV tolerando UTF-8 con o sin BOM."""

    try:
        return path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        )

    except UnicodeError as exc:
        raise DataLoaderError(
            f"No se pudo leer el archivo como UTF-8: {path}"
        ) from exc


def _detect_delimiter(fh: TextIO) -> str:
    """Detecta delimitador ; , o tabulacion."""

    sample = fh.read(8192)
    fh.seek(0)

    if not sample:
        raise DataLoaderError(
            "El archivo CSV esta vacio."
        )

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=";,\t",
        )

        return dialect.delimiter

    except csv.Error:

        first_line = sample.splitlines()[0]

        counts = {
            ";": first_line.count(";"),
            ",": first_line.count(","),
            "\t": first_line.count("\t"),
        }

        delimiter = max(
            counts,
            key=lambda key: counts[key],
        )

        if counts[delimiter] == 0:
            return ";"

        return delimiter


def _normalize_fieldnames(
    fieldnames: Iterable[str] | None,
) -> list[str]:
    """Limpia los nombres de columnas."""

    if fieldnames is None:
        return []

    normalized: list[str] = []

    for fieldname in fieldnames:

        if fieldname is None:
            continue

        cleaned = (
            fieldname
            .replace("\ufeff", "")
            .strip()
        )

        if cleaned:
            normalized.append(cleaned)

    return normalized


def _validate_columns(
    fieldnames: Iterable[str] | None,
    required: set[str],
    text_column: str,
    filters: dict[str, Any] | None = None,
    metadata_columns: list[str] | None = None,
) -> None:
    """Valida columnas obligatorias y columnas usadas por config."""

    columns = set(
        _normalize_fieldnames(fieldnames)
    )

    expected = set(required)
    expected.add(text_column)

    if filters:
        expected.update(filters.keys())

    if metadata_columns:
        expected.update(metadata_columns)

    missing = sorted(
        expected - columns
    )

    if missing:

        present = (
            ", ".join(sorted(columns))
            if columns
            else "(ninguna)"
        )

        raise DataLoaderError(
            "Faltan columnas obligatorias en el CSV: "
            f"{', '.join(missing)}. "
            f"Columnas encontradas: {present}"
        )


def _clean_row(
    row: dict[
        str | None,
        str | list[str] | None,
    ],
) -> dict[str, str]:
    """Normaliza claves y valores de una fila."""

    cleaned: dict[str, str] = {}

    for key, value in row.items():

        if key is None:
            continue

        clean_key = (
            key
            .replace("\ufeff", "")
            .strip()
        )

        if isinstance(value, list):

            clean_value = " ".join(
                str(item)
                for item in value
            )

        elif value is None:

            clean_value = ""

        else:

            clean_value = str(value)

        cleaned[clean_key] = clean_value

    return cleaned


def _matches_filters(
    row: dict[str, str],
    filters: dict[str, Any] | None,
) -> bool:
    """Indica si una fila cumple todos los filtros configurados.

    Ejemplo:

        filters:
          categoria:
            - Datos_Embargado

    equivale a:

        row["categoria"] in {"Datos_Embargado"}
    """

    if not filters:
        return True

    for column, allowed_values in filters.items():

        if isinstance(
            allowed_values,
            (list, tuple, set),
        ):
            accepted = {
                str(value)
                for value in allowed_values
            }

        else:
            accepted = {
                str(allowed_values)
            }

        row_value = str(
            row.get(column, "")
        )

        if row_value not in accepted:
            return False

    return True


def _build_metadata(
    row: dict[str, str],
    required: set[str],
    text_column: str,
    metadata_columns: list[str] | None,
) -> dict[str, Any]:
    """Construye metadata adicional del registro.

    Si metadata_columns fue configurado, conserva explicitamente
    esas columnas.

    Si no fue configurado, mantiene el comportamiento historico:
    conserva todas las columnas adicionales.
    """

    if metadata_columns is not None:

        return {
            column: row.get(column, "")
            for column in metadata_columns
        }

    return {
        key: value
        for key, value in row.items()
        if key not in required
        and key != text_column
    }


def load_records(
    input_file: str | Path,
    input_mode: str,
    text_column: str,
    filters: dict[str, Any] | None = None,
    metadata_columns: list[str] | None = None,
) -> list[InputRecord]:
    """Carga registros desde CSV y los normaliza para inferencia.

    Para documentos completos:
    - id es obligatorio;
    - text_column es obligatorio.

    Para fragmentos:
    - conserva numero_archivo;
    - contador_interno;
    - palabra_clave;
    - categoria;
    - posiciones del fragmento.

    Tambien permite aplicar filtros declarados en experimentos.yaml.
    """

    path = Path(input_file)

    if not path.exists():
        raise DataLoaderError(
            f"No existe el archivo de entrada: {path}"
        )

    if input_mode == DOCUMENT_MODE:

        required = DOCUMENT_REQUIRED_COLUMNS

    elif input_mode == FRAGMENT_MODE:

        required = FRAGMENT_REQUIRED_COLUMNS

    else:

        raise DataLoaderError(
            f"Modo de entrada no soportado: {input_mode}"
        )

    with _open_csv(path) as fh:

        delimiter = _detect_delimiter(fh)

        reader = csv.DictReader(
            fh,
            delimiter=delimiter,
        )

        if reader.fieldnames is None:
            raise DataLoaderError(
                f"El CSV no contiene cabecera: {path}"
            )

        reader.fieldnames = _normalize_fieldnames(
            reader.fieldnames
        )

        _validate_columns(
            fieldnames=reader.fieldnames,
            required=required,
            text_column=text_column,
            filters=filters,
            metadata_columns=metadata_columns,
        )

        rows: list[dict[str, str]] = []

        for row in reader:

            if not row:
                continue

            cleaned_row = _clean_row(row)

            if not _matches_filters(
                cleaned_row,
                filters,
            ):
                continue

            rows.append(cleaned_row)

    records: list[InputRecord] = []

    for row in rows:

        texto = row.get(
            text_column,
            "",
        )

        metadata = _build_metadata(
            row=row,
            required=required,
            text_column=text_column,
            metadata_columns=metadata_columns,
        )

        records.append(
            InputRecord(
                numero_archivo=row.get(
                    "numero_archivo",
                    "",
                ),

                id=row.get(
                    "id",
                    "",
                ),

                nombre=row.get(
                    "nombre",
                    "",
                ),

                texto=texto,

                modo_entrada=input_mode,

                contador_interno=(
                    row.get(
                        "contador_interno"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                palabra_clave=(
                    row.get(
                        "palabra_clave"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                categoria=(
                    row.get(
                        "categoria"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                posicion_inicio=(
                    row.get(
                        "posicion_inicio"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                posicion_fin=(
                    row.get(
                        "posicion_fin"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                inicio_fragmento=(
                    row.get(
                        "inicio_fragmento"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                fin_fragmento=(
                    row.get(
                        "fin_fragmento"
                    )
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                metadata=metadata,
            )
        )

    return records