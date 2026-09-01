"""Lectura de CSVs de documentos completos y fragmentos."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, TextIO


DOCUMENT_MODE = "documentos_completos"
FRAGMENT_MODE = "fragmentos"

DOCUMENT_REQUIRED_COLUMNS = {
    "numero_archivo",
    "id",
    "nombre",
}

FRAGMENT_REQUIRED_COLUMNS = {
    "numero_archivo",
    "id",
    "nombre",
    "contador_interno",
    "palabra_clave",
    "posicion_inicio",
    "posicion_fin",
    "inicio_fragmento",
    "fin_fragmento",
}


class DataLoaderError(ValueError):
    """Error de lectura o validación de datos."""


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
            "posicion_inicio": self.posicion_inicio,
            "posicion_fin": self.posicion_fin,
            "inicio_fragmento": self.inicio_fragmento,
            "fin_fragmento": self.fin_fragmento,
        }

        base.update(self.metadata)
        return base


def _open_csv(path: Path) -> TextIO:
    """
    Abre CSV tolerando UTF-8 con o sin BOM.

    utf-8-sig también funciona correctamente con archivos UTF-8 normales,
    por lo que es suficiente como primera opción.
    """
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
    """
    Detecta automáticamente el delimitador del CSV.

    Soporta principalmente:
    - ;
    - ,
    - tabulación

    Si csv.Sniffer no puede determinarlo, usa ';' como fallback
    porque es el formato principal de los datasets del proyecto.
    """
    sample = fh.read(8192)
    fh.seek(0)

    if not sample:
        raise DataLoaderError("El archivo CSV está vacío.")

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=";,\t",
        )
        return dialect.delimiter

    except csv.Error:
        # Fallback manual para archivos con texto jurídico complejo.
        first_line = sample.splitlines()[0]

        semicolons = first_line.count(";")
        commas = first_line.count(",")
        tabs = first_line.count("\t")

        counts = {
            ";": semicolons,
            ",": commas,
            "\t": tabs,
        }

        delimiter = max(
            counts,
            key=lambda key: counts[key],
        )

        if counts[delimiter] == 0:
            # El proyecto trabaja principalmente con ';'.
            return ";"

        return delimiter


def _normalize_fieldnames(
    fieldnames: Iterable[str] | None,
) -> list[str]:
    """
    Limpia nombres de columnas.

    Evita problemas por:
    - espacios accidentales;
    - BOM residual;
    - headers vacíos.
    """
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
) -> None:
    """Valida que estén presentes todas las columnas obligatorias."""
    columns = set(
        _normalize_fieldnames(fieldnames)
    )

    expected = set(required)
    expected.add(text_column)

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
    row: dict[str | None, str | list[str] | None],
) -> dict[str, str]:
    """
    Normaliza claves y valores de una fila de DictReader.
    """
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


def load_records(
    input_file: str | Path,
    input_mode: str,
    text_column: str,
) -> list[InputRecord]:
    """
    Carga registros desde un CSV y los normaliza para inferencia.

    El delimitador se detecta automáticamente.
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

        # Normalizamos los nombres directamente en el reader.
        reader.fieldnames = _normalize_fieldnames(
            reader.fieldnames
        )

        _validate_columns(
            reader.fieldnames,
            required,
            text_column,
        )

        rows = [
            _clean_row(row)
            for row in reader
            if row
        ]

    records: list[InputRecord] = []

    for row in rows:
        texto = row.get(
            text_column,
            "",
        )

        metadata = {
            key: value
            for key, value in row.items()
            if key not in required
            and key != text_column
        }

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
                    row.get("contador_interno")
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                palabra_clave=(
                    row.get("palabra_clave")
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                posicion_inicio=(
                    row.get("posicion_inicio")
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                posicion_fin=(
                    row.get("posicion_fin")
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                inicio_fragmento=(
                    row.get("inicio_fragmento")
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                fin_fragmento=(
                    row.get("fin_fragmento")
                    if input_mode == FRAGMENT_MODE
                    else None
                ),

                metadata=metadata,
            )
        )

    return records