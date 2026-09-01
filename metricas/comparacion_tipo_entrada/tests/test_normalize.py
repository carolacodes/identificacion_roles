import unittest

from metricas.comparacion_tipo_entrada.src.normalize import (
    normalize_cuil_cuit,
    normalize_dni,
    normalize_name,
)


class NormalizeTests(unittest.TestCase):
    def test_normalize_name_spaces_newlines_and_accents(self):
        self.assertEqual(
            normalize_name(" Áurelio Rodolfo\nMelgarejo "),
            "AURELIO RODOLFO MELGAREJO",
        )

    def test_normalize_dni_keeps_only_digits(self):
        self.assertEqual(normalize_dni("33.470.065"), "33470065")
        self.assertEqual(normalize_dni("33 470 065"), "33470065")

    def test_normalize_cuil_cuit_keeps_only_digits(self):
        self.assertEqual(normalize_cuil_cuit("20-34436998-5"), "20344369985")
        self.assertEqual(normalize_cuil_cuit("20344369985"), "20344369985")


if __name__ == "__main__":
    unittest.main()

