from dataclasses import asdict, dataclass
from pathlib import Path
import math

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = "20261009_160006_multi_v7_fragmentos_thr50"
DEFAULT_BASELINE = PROJECT_ROOT / "outputs/consolidacion/20261009_160505_consolidacion_multi_v7_fragmentos_thr50_20261009_160006/consolidacion.json"
QUESTION_VERSION = "JEV-V1"
SDK_VERSION = "0.7.4"


@dataclass(frozen=True)
class Config:
    model: str = "jev-1.13.0"
    threshold: float = 0.8
    equivalence_threshold: float = 0.9
    timeout: float = 30.0
    retries: int = 2
    max_requests: int = 300
    questions_per_request: int = 64  # Límite técnico propio, no del proveedor.
    backoff: float = 0.5
    state_question_tokens: int = 32000
    request_tokens: int = 64000
    overhead_reserve: int = 2048
    allow_estimated_oversize: bool = False
    strategy: str = "completa"

    def __post_init__(self):
        if self.strategy not in ("simple", "completa"):
            raise ValueError("La estrategia debe ser simple o completa.")
        if not self.model.startswith("jev-"):
            raise ValueError("El modelo debe ser Jev oficial (jev-*).")
        for value in (self.threshold, self.equivalence_threshold):
            if not math.isfinite(value) or not 0.5 < value <= 1:
                raise ValueError("Los umbrales deben estar en (0.5, 1].")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("Timeout debe ser positivo y finito.")
        if not math.isfinite(self.backoff) or not 0 <= self.backoff <= 30:
            raise ValueError("Backoff debe estar entre 0 y 30 segundos.")
        if self.retries < 0 or self.max_requests < 0 or self.questions_per_request <= 0:
            raise ValueError("Límites de solicitudes/reintentos inválidos.")
        if not 0 < self.overhead_reserve < self.state_question_tokens <= 32000:
            raise ValueError("Presupuesto de contexto inválido.")
        if not self.state_question_tokens <= self.request_tokens <= 64000:
            raise ValueError("Presupuesto de solicitud inválido.")

    def as_dict(self):
        return asdict(self)


def predictions_path(experiment: str) -> Path:
    if not experiment or Path(experiment).name != experiment or experiment in (".", ".."):
        raise ValueError("Experimento debe ser un nombre de carpeta.")
    return PROJECT_ROOT / "outputs/por_documento" / experiment / "predicciones_por_documento.json"
