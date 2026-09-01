"""Carga centralizada de modelos GLiNER2 y GLiNER clásico."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ModelLoaderError(ValueError):
    """Error al cargar o configurar un modelo."""


@dataclass(slots=True)
class LoadedModel:
    """
    Wrapper común para modelos de distintas arquitecturas.
    """

    model: Any
    architecture: str
    model_id: str
    display_name: str


def load_model(model_config: dict[str, Any]) -> LoadedModel:
    """
    Carga un modelo según la arquitectura declarada en modelos.yaml.

    Soporta:
    - gliner2
    - gliner
    """
    if not model_config.get("enabled", False):
        raise ModelLoaderError(
            f"El modelo '{model_config.get('display_name')}' no está habilitado."
        )

    model_id = model_config.get("model_id")
    if not model_id:
        raise ModelLoaderError(
            "El modelo no tiene model_id configurado."
        )

    architecture = str(
        model_config.get("architecture", "")
    ).strip().lower()

    display_name = str(
        model_config.get("display_name", model_id)
    )

    device = str(
        model_config.get("device", "cpu")
    )

    if architecture == "gliner2":
        model = _load_gliner2(
            model_id=model_id,
            device=device,
        )

    elif architecture == "gliner":
        model = _load_gliner(
            model_id=model_id,
            device=device,
        )

    else:
        raise ModelLoaderError(
            f"Arquitectura no soportada: '{architecture}'. "
            "Valores permitidos: gliner2, gliner."
        )

    return LoadedModel(
        model=model,
        architecture=architecture,
        model_id=model_id,
        display_name=display_name,
    )


def _load_gliner2(
    model_id: str,
    device: str,
) -> Any:
    """
    Carga modelos GLiNER2 actuales.

    Se usa AutoExtractor cuando es posible.
    """
    try:
        from gliner2 import AutoExtractor
    except ImportError as exc:
        raise ModelLoaderError(
            "No se pudo importar gliner2. "
            "Instalá las dependencias con: pip install -r requirements.txt"
        ) from exc

    try:
        return AutoExtractor.from_pretrained(
            model_id,
            map_location=device,
        )

    except Exception as auto_error:
        # Fallback útil para checkpoints span/legacy.
        try:
            from gliner2 import GLiNER2

            return GLiNER2.from_pretrained(
                model_id,
                map_location=device,
            )

        except Exception as fallback_error:
            raise ModelLoaderError(
                f"No se pudo cargar el modelo GLiNER2 '{model_id}'. "
                f"AutoExtractor: {auto_error}. "
                f"GLiNER2 fallback: {fallback_error}"
            ) from fallback_error


def _load_gliner(
    model_id: str,
    device: str,
) -> Any:
    """
    Carga modelos GLiNER clásicos, como ContractNER.
    """
    try:
        from gliner import GLiNER
    except ImportError as exc:
        raise ModelLoaderError(
            "No se pudo importar gliner. "
            "Instalá las dependencias con: pip install -r requirements.txt"
        ) from exc

    try:
        return GLiNER.from_pretrained(
            model_id,
            device=device,
        )

    except TypeError:
        # Compatibilidad con versiones que no aceptan device en from_pretrained.
        model = GLiNER.from_pretrained(model_id)

        if hasattr(model, "to"):
            model = model.to(device)

        return model

    except Exception as exc:
        raise ModelLoaderError(
            f"No se pudo cargar el modelo GLiNER '{model_id}': {exc}"
        ) from exc