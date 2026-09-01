"""Normalizacion conservadora para comparar valores detectados."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def is_present(value: Any) -> bool:
    """Devuelve True si el valor representa una deteccion usable."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    return text != "" and text.lower() not in {"none", "null", "nan", "false"}


def normalize_name(value: Any, remove_accents: bool = True) -> str:
    """Normaliza nombres solo para comparacion, sin alterar el original."""
    if not is_present(value):
        return ""
    text = re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip().upper()
    if remove_accents:
        text = "".join(
            char
            for char in unicodedata.normalize("NFD", text)
            if unicodedata.category(char) != "Mn"
        )
    return text


def only_digits(value: Any) -> str:
    """Conserva solo digitos para comparar DNI, CUIL o CUIT."""
    if not is_present(value):
        return ""
    return re.sub(r"\D+", "", str(value))


def normalize_dni(value: Any) -> str:
    """Normaliza DNI para comparacion."""
    return only_digits(value)


def normalize_cuil_cuit(value: Any) -> str:
    """Normaliza CUIL/CUIT para comparacion."""
    return only_digits(value)


def to_float(value: Any) -> float | None:
    """Convierte un valor de confidence en float cuando es posible."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

