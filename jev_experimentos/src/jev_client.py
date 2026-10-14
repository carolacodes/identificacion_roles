"""Cliente oficial con reintentos visibles y sin credenciales en outputs."""
import importlib.metadata
import logging
import os
import time

from ..config import SDK_VERSION


class ClientError(RuntimeError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


class RequestLimitError(ClientError):
    pass


def redact(value):
    """Redacta cualquier eco de la clave; jamás serializa objetos de solicitud HTTP."""
    secret = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, dict):
        return {redact(k): redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def serialize_response(response):
    if hasattr(response, "model_dump"):
        response = response.model_dump(mode="json")
    if not isinstance(response, dict):
        raise ClientError("El SDK no devolvió una respuesta serializable.")
    return redact(response)


class JevClient:
    def __init__(self, config, *, authorized=False, sdk_client=None, sleep=time.sleep):
        if not authorized:
            raise ClientError("Envío no autorizado: se requiere --autorizar-envio-datos.")
        self.config, self.sleep = config, sleep
        self.attempts = 0
        if sdk_client is None:
            key = os.environ.get("TYPESAFE_API_KEY", "").strip()
            if not key:
                raise ClientError("Falta TYPESAFE_API_KEY en el entorno.")
            try:
                if importlib.metadata.version("typesafe-sdk") != SDK_VERSION:
                    raise ClientError(f"Se requiere typesafe-sdk=={SDK_VERSION} para esta integración.")
                from typesafe_sdk import RetryPolicy, TypeSafeClient
                # Fija el servicio oficial y desactiva reintentos ocultos del SDK.
                logging.getLogger("typesafe_sdk").disabled = True
                self.sdk = TypeSafeClient(
                    api_key=key, model=config.model, timeout=config.timeout,
                    retry=RetryPolicy(max_retries=0), base_url="https://api.typesafe.ai",
                )
            except ClientError:
                raise
            except Exception:
                raise ClientError("No se pudo inicializar el SDK oficial; revise instalación y clave.") from None
        else:
            self.sdk = sdk_client

    def evaluate(self, state, questions, *, on_attempt=None, on_error=None):
        errors = []
        for retry_index in range(self.config.retries + 1):
            if self.attempts >= self.config.max_requests:
                raise RequestLimitError("Se alcanzó max_requests.", errors)
            if on_attempt:
                on_attempt()  # Persistir el costo potencial ANTES de la llamada.
            self.attempts += 1
            try:
                response = self.sdk.system_one(
                    state=state, questions=questions, model=self.config.model,
                    timeout=self.config.timeout,
                )
                return serialize_response(response)
            except Exception as exc:
                # Nunca str(exc), headers ni request: podrían incluir credenciales.
                status = getattr(exc, "status", None)
                transient = isinstance(exc, (TimeoutError, ConnectionError)) or status in {
                    429, 500, 502, 503, 504, 529,
                }
                error = {"tipo": type(exc).__name__, "status_http": status,
                         "reintento": retry_index, "transitorio": transient}
                # Una respuesta inválida del SDK conserva el cuerpo original redactado.
                if status == 200 and isinstance(getattr(exc, "body", None), (dict, list, str)):
                    error["respuesta_original_invalida"] = redact(exc.body)
                errors.append(error)
                if on_error:
                    on_error(error)
                if not transient or retry_index >= self.config.retries:
                    raise ClientError("La solicitud Jev falló; consulte los errores estructurados.", errors) from None
                delay = min(30.0, self.config.backoff * (2 ** retry_index))
                retry_ms = getattr(exc, "retry_after_ms", None)
                if isinstance(retry_ms, (int, float)):
                    if retry_ms > 30000:
                        raise ClientError("Retry-After excede la espera máxima de 30 segundos.", errors) from None
                    delay = max(delay, max(0, retry_ms / 1000))
                self.sleep(delay)
        raise AssertionError("Unreachable")

    def close(self):
        self.sdk.close()
