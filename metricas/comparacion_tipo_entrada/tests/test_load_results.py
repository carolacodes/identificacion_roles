import csv
import json
import tempfile
import unittest
from pathlib import Path

from metricas.comparacion_tipo_entrada.src.load_results import (
    load_results,
    validate_compatible_inputs,
)


def base_row(doc_id="1", modo="documento_completo"):
    return {
        "id": doc_id,
        "modo_entrada": modo,
        "modelo": "fastino/gliner2-privacy-filter-PII-multi",
        "schema": "schema_v3_persona_structured",
        "threshold": "0.5",
    }


class LoadResultsTests(unittest.TestCase):
    def test_load_json_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "predicciones.json"
            path.write_text(json.dumps([base_row()]), encoding="utf-8")
            rows = load_results(path)

        self.assertEqual(rows[0]["id"], "1")

    def test_load_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "predicciones.csv"
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(base_row().keys()))
                writer.writeheader()
                writer.writerow(base_row())
            rows = load_results(path)

        self.assertEqual(rows[0]["modelo"], "fastino/gliner2-privacy-filter-PII-multi")

    def test_validate_ids_not_matching_reports_sets(self):
        docs = [base_row("1"), base_row("2")]
        frags = [base_row("2", "fragmento"), base_row("3", "fragmento")]

        metadata = validate_compatible_inputs(docs, frags)

        self.assertEqual(metadata["ids_comunes"], ["2"])
        self.assertEqual(metadata["ids_solo_documentos"], ["1"])
        self.assertEqual(metadata["ids_solo_fragmentos"], ["3"])

    def test_validate_requires_id(self):
        docs = [base_row()]
        frags = [base_row("1", "fragmento")]
        docs[0].pop("id")

        with self.assertRaisesRegex(ValueError, "id"):
            validate_compatible_inputs(docs, frags)


if __name__ == "__main__":
    unittest.main()

