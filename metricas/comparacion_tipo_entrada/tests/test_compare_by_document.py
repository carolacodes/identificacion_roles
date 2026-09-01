import unittest

from metricas.comparacion_tipo_entrada.src.compare_by_document import (
    aggregate_fragments_by_document,
    compare_by_document,
)


def doc_row(doc_id="1", nombre="AURELIO RODOLFO MELGAREJO", dni="33.470.065", cuil=None):
    return {
        "id": doc_id,
        "numero_archivo": "001",
        "nombre": "archivo.pdf",
        "nombre_detectado": nombre,
        "nombre_confidence": 0.8,
        "dni_detectado": dni,
        "dni_confidence": 0.7,
        "cuil_cuit_detectado": cuil,
        "cuil_cuit_confidence": None,
        "estado_postprocess": "ok",
    }


def frag_row(doc_id="1", nombre="AURELIO RODOLFO\nMELGAREJO", dni="33470065", cuil=None, conf=0.9):
    return {
        "id": doc_id,
        "numero_archivo": "001",
        "nombre": "archivo.pdf",
        "nombre_detectado": nombre,
        "nombre_confidence": conf,
        "dni_detectado": dni,
        "dni_confidence": conf,
        "cuil_cuit_detectado": cuil,
        "cuil_cuit_confidence": conf if cuil else None,
    }


class CompareByDocumentTests(unittest.TestCase):
    def test_aggregate_fragments_by_document_keeps_unique_values_and_confidence(self):
        rows = [
            frag_row(nombre="AURELIO RODOLFO\nMELGAREJO", conf=0.9),
            frag_row(nombre="Aurelio Rodolfo Melgarejo", conf=0.7),
            frag_row(nombre="OTRO NOMBRE", dni="11.111.111", conf=0.5),
        ]

        aggregated = aggregate_fragments_by_document(rows)["1"]

        self.assertEqual(aggregated["cantidad_fragmentos"], 3)
        self.assertEqual(aggregated["fragmentos_con_candidato"], 3)
        self.assertEqual(aggregated["cantidad_nombres_distintos"], 2)
        self.assertEqual(aggregated["cantidad_dni_distintos"], 2)
        self.assertEqual(aggregated["nombre_confidence_max"], 0.9)

    def test_agreement_name_and_dni(self):
        rows = compare_by_document([doc_row()], [frag_row()])

        self.assertIs(rows[0]["acuerdo_nombre"], True)
        self.assertIs(rows[0]["acuerdo_dni"], True)

    def test_only_fragments_detects_field(self):
        rows = compare_by_document([doc_row(nombre=None, dni=None)], [frag_row()])

        self.assertIs(rows[0]["solo_fragmentos_detectan_nombre"], True)
        self.assertIs(rows[0]["solo_fragmentos_detectan_dni"], True)

    def test_only_document_detects_field(self):
        rows = compare_by_document([doc_row()], [frag_row(nombre=None, dni=None)])

        self.assertIs(rows[0]["solo_documento_detecta_nombre"], True)
        self.assertIs(rows[0]["solo_documento_detecta_dni"], True)

    def test_both_without_detection_is_not_positive_agreement(self):
        rows = compare_by_document([doc_row(nombre=None, dni=None)], [frag_row(nombre=None, dni=None)])

        self.assertIs(rows[0]["ninguno_detecta_nombre"], True)
        self.assertIs(rows[0]["acuerdo_nombre"], False)

    def test_multiple_names_in_fragments_are_preserved(self):
        rows = compare_by_document([doc_row()], [frag_row(nombre="UNO"), frag_row(nombre="DOS")])

        self.assertEqual(len(rows[0]["frag_nombres_normalizados"]), 2)


if __name__ == "__main__":
    unittest.main()

