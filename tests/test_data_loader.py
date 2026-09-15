from pathlib import Path

import pytest

from src.data_loader import (
    DataLoaderError,
    load_records,
)


def test_load_document_records_preserves_text(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "documentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,texto_limpio\n"
            '1,doc-1,oficio,"Embarguese a Juan Perez"\n'
        ),
        encoding="utf-8-sig",
    )

    records = load_records(
        csv_path,
        input_mode="documentos_completos",
        text_column="texto_limpio",
    )

    assert len(records) == 1

    assert (
        records[0].texto
        == "Embarguese a Juan Perez"
    )

    assert (
        records[0].modo_entrada
        == "documentos_completos"
    )

    assert (
        records[0].contador_interno
        is None
    )

    assert (
        records[0].categoria
        is None
    )


def test_load_document_records_only_requires_id_and_text(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "documentos_minimo.csv"
    )

    csv_path.write_text(
        (
            "id,texto_ocr_limpio_Q8\n"
            'doc-1,"Embarguese a Juan Perez"\n'
        ),
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="documentos_completos",
        text_column="texto_ocr_limpio_Q8",
    )

    assert len(records) == 1

    assert (
        records[0].id
        == "doc-1"
    )

    assert (
        records[0].texto
        == "Embarguese a Juan Perez"
    )

    assert (
        records[0].numero_archivo
        == ""
    )

    assert (
        records[0].nombre
        == ""
    )


def test_load_fragment_records_preserves_metadata(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,categoria,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"
            '1,doc-1,oficio,7,embargo,Datos_Embargado,'
            '"retener fondos de ACME SA",10,20,5,30\n'
        ),
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="fragmentos",
        text_column="fragmento",
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.texto
        == "retener fondos de ACME SA"
    )

    assert (
        record.contador_interno
        == "7"
    )

    assert (
        record.palabra_clave
        == "embargo"
    )

    assert (
        record.categoria
        == "Datos_Embargado"
    )

    assert (
        record.posicion_inicio
        == "10"
    )


def test_filter_fragment_records_by_category(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,categoria,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"

            "1,doc-1,oficio,1,demandado,"
            "Datos_Embargado,"
            '"Juan Perez demandado",'
            "10,20,5,30\n"

            "1,doc-1,oficio,2,monto,"
            "Montos,"
            '"capital $ 100000",'
            "31,40,25,50\n"

            "1,doc-1,oficio,3,cbu,"
            "Cuenta_depositar,"
            '"CBU 123456789",'
            "41,50,35,60\n"
        ),
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="fragmentos",
        text_column="fragmento",
        filters={
            "categoria": [
                "Datos_Embargado"
            ]
        },
    )

    assert len(records) == 1

    assert (
        records[0].categoria
        == "Datos_Embargado"
    )

    assert (
        records[0].contador_interno
        == "1"
    )

    assert (
        records[0].texto
        == "Juan Perez demandado"
    )


def test_filter_accepts_multiple_values(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,categoria,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"

            "1,doc-1,oficio,1,demandado,"
            "Datos_Embargado,"
            '"Juan Perez",'
            "10,20,5,30\n"

            "1,doc-1,oficio,2,monto,"
            "Montos,"
            '"$ 100000",'
            "31,40,25,50\n"

            "1,doc-1,oficio,3,cbu,"
            "Cuenta_depositar,"
            '"CBU 123",'
            "41,50,35,60\n"
        ),
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="fragmentos",
        text_column="fragmento",
        filters={
            "categoria": [
                "Datos_Embargado",
                "Montos",
            ]
        },
    )

    assert len(records) == 2

    assert {
        record.categoria
        for record in records
    } == {
        "Datos_Embargado",
        "Montos",
    }


def test_metadata_columns_are_preserved(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,categoria,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"

            "1,doc-1,oficio,7,embargo,"
            "Datos_Embargado,"
            '"Juan Perez demandado",'
            "10,20,5,30\n"
        ),
        encoding="utf-8",
    )

    records = load_records(
        csv_path,
        input_mode="fragmentos",
        text_column="fragmento",
        metadata_columns=[
            "numero_archivo",
            "id",
            "contador_interno",
            "palabra_clave",
            "categoria",
        ],
    )

    assert len(records) == 1

    metadata = records[0].metadata

    assert (
        metadata["numero_archivo"]
        == "1"
    )

    assert (
        metadata["id"]
        == "doc-1"
    )

    assert (
        metadata["contador_interno"]
        == "7"
    )

    assert (
        metadata["palabra_clave"]
        == "embargo"
    )

    assert (
        metadata["categoria"]
        == "Datos_Embargado"
    )


def test_missing_fragment_category_raises_error(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos_sin_categoria.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"

            "1,doc-1,oficio,7,embargo,"
            '"Juan Perez",'
            "10,20,5,30\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DataLoaderError,
        match="Faltan columnas obligatorias",
    ):
        load_records(
            csv_path,
            input_mode="fragmentos",
            text_column="fragmento",
        )


def test_missing_filter_column_raises_error(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,categoria,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"

            "1,doc-1,oficio,7,embargo,"
            "Datos_Embargado,"
            '"Juan Perez",'
            "10,20,5,30\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DataLoaderError,
        match="Faltan columnas obligatorias",
    ):
        load_records(
            csv_path,
            input_mode="fragmentos",
            text_column="fragmento",
            filters={
                "columna_inexistente": [
                    "valor"
                ]
            },
        )


def test_missing_metadata_column_raises_error(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "fragmentos.csv"
    )

    csv_path.write_text(
        (
            "numero_archivo,id,nombre,contador_interno,"
            "palabra_clave,categoria,fragmento,"
            "posicion_inicio,posicion_fin,"
            "inicio_fragmento,fin_fragmento\n"

            "1,doc-1,oficio,7,embargo,"
            "Datos_Embargado,"
            '"Juan Perez",'
            "10,20,5,30\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DataLoaderError,
        match="Faltan columnas obligatorias",
    ):
        load_records(
            csv_path,
            input_mode="fragmentos",
            text_column="fragmento",
            metadata_columns=[
                "columna_inexistente"
            ],
        )


def test_missing_id_raises_clear_error(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "bad.csv"
    )

    csv_path.write_text(
        (
            "texto_limpio\n"
            "texto\n"
        ),
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


def test_missing_text_column_raises_clear_error(
    tmp_path: Path,
):
    csv_path = (
        tmp_path
        / "bad_text.csv"
    )

    csv_path.write_text(
        (
            "id,otra_columna\n"
            "doc-1,texto\n"
        ),
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