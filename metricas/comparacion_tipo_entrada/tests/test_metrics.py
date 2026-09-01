import csv
import json
import tempfile
import unittest
from pathlib import Path

from metricas.comparacion_tipo_entrada.src.compare_by_document import compare_by_document
from metricas.comparacion_tipo_entrada.src.metrics import compute_global_metrics, timing_metrics
from metricas.comparacion_tipo_entrada.src.reports import create_output_dir, write_all_outputs


def metadata():
    return {
        "modelo": "fastino/gliner2-privacy-filter-PII-multi",
        "schema": "schema_v3_persona_structured",
        "threshold": "0.5",
        "ids_solo_documentos": [],
        "ids_solo_fragmentos": [],
        "ids_comunes": ["1", "2", "3"],
    }


def doc(doc_id, nombre=None, dni=None, cuil=None, conf=None):
    return {
        "id": doc_id,
        "modo_entrada": "documento_completo",
        "modelo": metadata()["modelo"],
        "schema": metadata()["schema"],
        "threshold": metadata()["threshold"],
        "nombre_detectado": nombre,
        "nombre_confidence": conf,
        "dni_detectado": dni,
        "dni_confidence": conf,
        "cuil_cuit_detectado": cuil,
        "cuil_cuit_confidence": conf,
    }


def frag(doc_id, nombre=None, dni=None, cuil=None, conf=None):
    return {
        "id": doc_id,
        "modo_entrada": "fragmento",
        "modelo": metadata()["modelo"],
        "schema": metadata()["schema"],
        "threshold": metadata()["threshold"],
        "nombre_detectado": nombre,
        "nombre_confidence": conf,
        "dni_detectado": dni,
        "dni_confidence": conf,
        "cuil_cuit_detectado": cuil,
        "cuil_cuit_confidence": conf,
    }


def build_metrics():
    docs = [
        doc("1", nombre="ANA TEST", dni="11.111.111", conf=0.8),
        doc("2", nombre="SOLO DOC", conf=None),
        doc("3"),
    ]
    frags = [
        frag("1", nombre="ANA TEST", dni="11111111", conf=0.9),
        frag("2"),
        frag("3", nombre="SOLO FRAG", conf=0.6),
    ]
    comparisons = compare_by_document(docs, frags, ["1", "2", "3"])
    return docs, frags, comparisons, compute_global_metrics(docs, frags, comparisons, metadata(), 30.0, 6.0)


class MetricsTests(unittest.TestCase):
    def test_denominators_for_agreement_are_both_detected(self):
        _, _, _, metrics = build_metrics()

        agreement = metrics["agreement_entre_modos"]
        self.assertEqual(agreement["acuerdo_nombre_denominador"], 1)
        self.assertEqual(agreement["acuerdo_nombre_count"], 1)
        self.assertEqual(agreement["acuerdo_dni_denominador"], 1)

    def test_confidence_with_null_values(self):
        _, _, _, metrics = build_metrics()

        self.assertEqual(metrics["confidence"]["documentos"]["nombre_confidence"]["media"], 0.8)

    def test_metrics_with_missing_fields(self):
        docs = [{"id": "1"}]
        frags = [{"id": "1"}]
        comparisons = compare_by_document(docs, frags, ["1"])

        metrics = compute_global_metrics(docs, frags, comparisons, {"ids_comunes": ["1"]})

        self.assertEqual(metrics["deteccion_exclusiva"]["nombre"]["ninguno"]["cantidad"], 1)

    def test_timing_per_document_per_fragment_and_speedup(self):
        metrics = timing_metrics(30.0, 6.0, total_docs=3, total_fragments=6)

        self.assertEqual(metrics["segundos_por_documento_documentos"], 10.0)
        self.assertEqual(metrics["segundos_por_fragmento"], 1.0)
        self.assertEqual(metrics["speedup_fragmentos_vs_documentos"], 5.0)

    def test_generation_of_outputs(self):
        _, _, comparisons, metrics = build_metrics()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = create_output_dir(Path(temp_dir), "fixture")

            write_all_outputs(output_dir, comparisons, metrics)

            expected = {
                "resumen_comparacion.csv",
                "comparacion_por_documento.csv",
                "comparacion_por_documento.json",
                "metricas_globales.json",
                "metricas_globales.csv",
                "casos_desacuerdo.csv",
                "casos_solo_documento.csv",
                "casos_solo_fragmentos.csv",
                "casos_ambiguos_fragmentos.csv",
                "reporte.md",
            }
            self.assertEqual(expected, {path.name for path in output_dir.iterdir()})
            with (output_dir / "metricas_globales.json").open(encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["configuracion"]["cantidad_documentos_comparados"], 3)
            with (output_dir / "resumen_comparacion.csv").open(encoding="utf-8-sig", newline="") as fh:
                self.assertEqual(
                    list(csv.DictReader(fh))[0]["metrica"],
                    "Cobertura persona embargada",
                )

if __name__ == "__main__":
    unittest.main()

