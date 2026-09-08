from pathlib import Path

import pytest

from src.data_loader import DataLoaderError, load_records


def test_load_document_records_preserves_text(tmp_path: Path):
    csv_path = tmp_path / "documentos.csv"

    csv_path.write_text(
        "numero_archivo,id,nombre,texto_limpio\n"
        '1,doc-1,oficio,"Embarguese a Juan Perez"\n',
        encoding="utf-8-sig",
    )

    records = load_records(
        csv_path,
        input_mode="documentos_completos",
        text_column="texto_limpio",
    )

    assert len(records) == 1
    assert records[0].texto == "Embarguese a Juan Perez"
    assert records[0].modo_entrada == "documentos_completos"
    assert records[0].contador_interno is None


def test_load_document_records_only_requires_id_and_text(tmp_path: Path):
    csv_path = tmp_path / "documentos_minimo.csv"

    csv_path.write_text(
        "id,texto_ocr_limpio_Q8\n"
        'doc-1,"Embarguese a Juan Perez"\n',
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="documentos_completos",
        text_column="texto_ocr_limpio_Q8",
    )

    assert len(records) == 1
    assert records[0].id == "doc-1"
    assert records[0].texto == "Embarguese a Juan Perez"

    # Estas columnas ahora son opcionales.
    assert records[0].numero_archivo == ""
    assert records[0].nombre == ""


def test_load_fragment_records_preserves_metadata(tmp_path: Path):
    csv_path = tmp_path / "fragmentos.csv"

    csv_path.write_text(
        "numero_archivo,id,nombre,contador_interno,palabra_clave,fragmento,"
        "posicion_inicio,posicion_fin,inicio_fragmento,fin_fragmento\n"
        '1,doc-1,oficio,7,embargo,"retener fondos de ACME SA",10,20,5,30\n',
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="fragmentos",
        text_column="fragmento",
    )

    assert records[0].texto == "retener fondos de ACME SA"
    assert records[0].contador_interno == "7"
    assert records[0].palabra_clave == "embargo"
    assert records[0].posicion_inicio == "10"


def test_missing_id_raises_clear_error(tmp_path: Path):
    csv_path = tmp_path / "bad.csv"

    csv_path.write_text(
        "texto_limpio\n"
        "texto\n",
        encoding="utf-8",
    )

    with pytest.raises(
        DataLoaderError,
        match="Faltan columnas obligatorias",
    ):
        load_records(
            csv_path,
            input_mode="documentos_completos",
            text_column="texto_limpio",
        )


def test_missing_text_column_raises_clear_error(tmp_path: Path):
    csv_path = tmp_path / "bad_text.csv"

    csv_path.write_text(
        "id,otra_columna\n"
        "doc-1,texto\n",
        encoding="utf-8",
    )

    with pytest.raises(
        DataLoaderError,
        match="Faltan columnas obligatorias",
    ):
        load_records(
            csv_path,
            input_mode="documentos_completos",
            text_column="texto_ocr_limpio_Q8",
        )