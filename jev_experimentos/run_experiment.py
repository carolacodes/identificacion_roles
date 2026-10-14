"""CLI JEV-V1. Por defecto exige autorización explícita para enviar datos."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.metadata
from pathlib import Path
import platform
from contextlib import contextmanager

from .config import Config, DEFAULT_BASELINE, DEFAULT_EXPERIMENT, PROJECT_ROOT, QUESTION_VERSION, predictions_path
from .src.comparison import write_comparison
from .src.decision_engine import interpret_responses, prepare_plan
from .src.jev_client import ClientError, JevClient, RequestLimitError
from .src.loader import load_predictions, select_documents
from .src.result_builder import build_result
from .src.storage import digest, read_json, write_json


def now():
    return datetime.now(timezone(timedelta(hours=-3))).isoformat()


def sdk_version():
    try:
        return importlib.metadata.version("typesafe-sdk")
    except importlib.metadata.PackageNotFoundError:
        return None


@contextmanager
def execution_lock(directory):
    """Un solo escritor por ejecución; el SO libera el bloqueo tras un cierre abrupto."""
    with (directory / ".run.lock").open("a+b") as handle:
        if platform.system() == "Windows":
            import msvcrt
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("Esta ejecución ya está abierta en otro proceso.") from None
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError("Esta ejecución ya está abierta en otro proceso.") from None
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def run_experiment(**kwargs):
    config = kwargs.get("config") or Config()
    kwargs["config"] = config
    if not kwargs.get("dry_run", False) and not kwargs.get("authorized", False):
        raise ClientError("Envío no autorizado. Use --dry-run o autorice explícitamente con --autorizar-envio-datos.")
    if kwargs.get("resume") and kwargs.get("output_dir"):
        raise ValueError("Use output_dir o resume, no ambos.")
    if kwargs.get("resume"):
        directory = Path(kwargs["resume"]).resolve()
        if not directory.is_dir():
            raise ValueError("No existe la ejecución a reanudar.")
    else:
        run_id = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y%m%d_%H%M%S_%f") + f"_{config.strategy}" + ("_dry_run" if kwargs.get("dry_run") else "_jev")
        directory = Path(kwargs.get("output_dir") or PROJECT_ROOT / "jev_experimentos/outputs" / run_id).resolve()
        directory.mkdir(parents=True, exist_ok=False)
        kwargs["output_dir"] = directory
    with execution_lock(directory):
        return _run_experiment(**kwargs)


def _run_experiment(*, experiment=DEFAULT_EXPERIMENT, config=None, dry_run=False,
                   numbers=None, limit=None, output_dir=None, resume=None,
                   authorized=False, retry_errors=False, client_factory=None,
                   input_path=None, baseline_path=None):
    config = config or Config()
    if not dry_run and not authorized:
        raise ClientError("Envío no autorizado. Use --dry-run o autorice explícitamente con --autorizar-envio-datos.")
    if output_dir and resume:
        raise ValueError("Use output_dir o resume, no ambos.")
    source = Path(input_path or predictions_path(experiment)).resolve()
    all_documents, source_hash = load_predictions(source)
    documents = select_documents(all_documents, numbers, limit)
    plans = {doc.key: prepare_plan(doc, config) for doc in documents}
    comparison_source = Path(baseline_path).resolve() if baseline_path else (
        DEFAULT_BASELINE if experiment == DEFAULT_EXPERIMENT and input_path is None else None)
    if comparison_source and not comparison_source.is_file():
        raise ValueError("No existe la consolidación de referencia indicada.")
    contract_config = config.as_dict()
    contract_config.pop("max_requests")  # Puede aumentarse para reanudar con un nuevo presupuesto.
    contract = {
        "estrategia": config.strategy,
        "input_sha256": source_hash, "documentos": [d.key for d in documents],
        "config": contract_config, "version_preguntas": QUESTION_VERSION,
        "hashes_planes": {key: p["hash_plan"] for key, p in plans.items()},
        "modo": "dry-run" if dry_run else "simulado" if client_factory else "real",
        "baseline_sha256": hashlib.sha256(comparison_source.read_bytes()).hexdigest() if comparison_source else None,
    }
    if resume:
        directory = Path(resume).resolve()
        metadata = read_json(directory / "metadata.json")
        # Las ejecuciones previas a esta opción corresponden a completa.
        previous_contract = metadata["contrato"]
        previous_contract["config"].setdefault("strategy", "completa")
        previous_contract.setdefault("estrategia", previous_contract["config"]["strategy"])
        if previous_contract["estrategia"] != config.strategy:
            raise ValueError("Reanudación incompatible: estrategia diferente.")
        if metadata["contrato"] != contract:
            raise ValueError("Reanudación incompatible: cambiaron entrada, documentos, preguntas, configuración o modo.")
        if any((directory / "documentos" / f"{doc.key}.json").exists() and
               any(b["estado"] == "EN_CURSO" for b in read_json(directory / "documentos" / f"{doc.key}.json")["lotes"])
               for doc in documents) and not retry_errors:
            raise ValueError("Hay llamadas EN_CURSO sin respuesta guardada. Revise antes de --reintentar-errores; podrían haber consumido API.")
    else:
        run_id = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y%m%d_%H%M%S_%f") + f"_{config.strategy}" + ("_dry_run" if dry_run else "_jev")
        directory = Path(output_dir or PROJECT_ROOT / "jev_experimentos/outputs" / run_id).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        metadata = {
            "id_ejecucion": directory.name, "experimento_origen": experiment,
            "input_path": str(source), "input_sha256": source_hash,
            "modelo_solicitado": config.model, "version_preguntas": QUESTION_VERSION,
            "umbral": config.threshold, "config": config.as_dict(), "fecha_inicio": now(),
            "sdk": {"nombre": "typesafe-sdk", "version_instalada": sdk_version()},
            "python": platform.python_version(), "solicitudes_realizadas": 0,
            "contrato": contract, "modo": contract["modo"],
            "baseline_path": str(comparison_source) if comparison_source else None,
            "interpretacion_comparacion": "Acuerdo/desacuerdo no demuestra corrección. Comparación literal sin normalizar.",
        }
    metadata["config"]["max_requests"] = config.max_requests
    metadata["config"]["strategy"] = config.strategy
    metadata["estrategia"] = config.strategy
    write_json(directory / "metadata.json", metadata)
    records = {}
    for document in documents:
        cache_path = directory / "documentos" / f"{document.key}.json"
        plan = plans[document.key]
        if cache_path.exists():
            record = read_json(cache_path)
            record["plan"].setdefault("estrategia", "completa")
            if record["plan"] != plan:
                raise ValueError("El checkpoint no corresponde al plan original.")
        else:
            record = {
                "id": document.original["id"], "numero_archivo": document.original["numero_archivo"],
                "plan": plan, "lotes": [{"indice": i, "estado": "PENDIENTE", "errores": [],
                                          "hash_solicitud": digest({"state": plan["state"], "questions": q, "model": config.model})}
                                         for i, q in enumerate(plan["lotes"])],
            }
        record["estrategia"] = config.strategy
        write_json(cache_path, record)
        records[document.key] = record

    def persist_outputs():
        results, errors, usage, models = [], [], [], set()
        for doc in documents:
            rec = records[doc.key]
            complete = not rec["plan"]["dimension"]["bloqueado_por_estimacion"] and all(b["estado"] == "RESPONDIDO" for b in rec["lotes"])
            if not dry_run and complete:
                interpreted = interpret_responses(rec["plan"], [b["respuesta_original"] for b in rec["lotes"]],
                                                  expected_batches=rec["plan"]["lotes"])
                result = build_result(doc, interpreted, config)
                results.append(result)
                if interpreted["errores"]:
                    errors.append({"id": doc.original["id"], "numero_archivo": doc.original["numero_archivo"], "errores": interpreted["errores"]})
            for batch in rec["lotes"]:
                if batch["estado"] in ("ERROR", "EN_CURSO"):
                    errors.append({"id": doc.original["id"], "numero_archivo": doc.original["numero_archivo"],
                                   "lote": batch["indice"], "estado": batch["estado"], "errores": batch["errores"]})
                if "respuesta_original" in batch:
                    raw = batch["respuesta_original"]
                    usage.append(raw.get("usage", {}))
                    if isinstance(raw.get("model"), str):
                        models.add(raw["model"])
        summary = {
            "estrategia": config.strategy,
            **({"deduplicacion": "NO_EVALUADA", "unidad_conteo": "candidatos_aceptados_sin_deduplicar"}
               if config.strategy == "simple" else {}),
            "total_documentos": len(documents), "documentos_en_fuente": len(all_documents),
            "documentos_procesados": len(results), "documentos_pendientes": len(documents) - len(results),
            **{state: sum(r["estado"] == state for r in results) for state in ("RESUELTO", "RESUELTO_MULTIPLE", "NO_RESUELTO")},
            "total_personas_embargadas": sum(r["cantidad_embargados"] for r in results),
            "documentos_con_incertidumbre": sum(r["incertidumbre"] for r in results),
            "documentos_con_conflictos": sum(bool(r["conflictos"]) for r in results),
            "documentos_con_conflictos_identificador": sum(bool(r["conflictos_identificador"]) for r in results),
            "documentos_requieren_revision": sum(r["requiere_revision"] for r in results),
            "errores_procesamiento": errors,
            "total_fragmentos": sum(len(d.original["resultados"]) for d in documents),
            "total_candidatos": sum(len(d.candidates) for d in documents),
            "total_preguntas": sum(len(p["preguntas"]) for p in plans.values()),
            "solicitudes_previstas_sin_reintentos": sum(len(p["lotes"]) for p in plans.values()),
            "solicitudes_realizadas": metadata["solicitudes_realizadas"], "modo": metadata["modo"],
            "documentos_bloqueados_por_estimacion": [d.original["numero_archivo"] for d in documents if plans[d.key]["dimension"]["bloqueado_por_estimacion"]],
            "documentos_exceden_estimacion": [d.original["numero_archivo"] for d in documents if plans[d.key]["dimension"]["excede_estimacion"]],
            "dimension_por_documento": [{"id": d.original["id"], "numero_archivo": d.original["numero_archivo"],
                                         "candidatos": len(d.candidates), "fragmentos": len(d.original["resultados"]),
                                         **plans[d.key]["dimension"]} for d in documents],
        }
        write_json(directory / "decisiones_jev.json", list(records.values()))
        write_json(directory / "consolidacion_jev.json", results)
        write_json(directory / "resumen_jev.json", summary)
        comparison_count = write_comparison(directory / "comparacion.csv", results, comparison_source)
        metadata.update({"fecha_actualizacion": now(), "errores": errors, "consumo_por_respuesta": usage,
                         "errores_api": [{"id": rec["id"], "numero_archivo": rec["numero_archivo"],
                                          "lote": batch["indice"], **error}
                                         for rec in records.values() for batch in rec["lotes"] for error in batch["errores"]],
                         "modelos_respondidos": sorted(models), "filas_comparacion": comparison_count,
                         "comparacion_estado": "PENDIENTE" if not results else "SIN_REFERENCIA" if not comparison_source else "GENERADA",
                         "input_no_modificado": hashlib.sha256(source.read_bytes()).hexdigest() == source_hash})
        write_json(directory / "metadata.json", metadata)
        return summary

    summary = persist_outputs()
    if dry_run:
        # Barrera antes de cualquier construcción/importación del cliente SDK.
        return directory, summary
    client = None
    stopped = False
    try:
        for doc in documents:
            rec, plan = records[doc.key], plans[doc.key]
            if plan["dimension"]["bloqueado_por_estimacion"]:
                continue
            cache_path = directory / "documentos" / f"{doc.key}.json"
            for batch in rec["lotes"]:
                if batch["estado"] == "RESPONDIDO" or (batch["estado"] == "ERROR" and not retry_errors):
                    continue
                if metadata["solicitudes_realizadas"] >= config.max_requests:
                    stopped = True
                    break
                if client is None:
                    client = client_factory(config) if client_factory else JevClient(config, authorized=authorized)

                def on_attempt():
                    if metadata["solicitudes_realizadas"] >= config.max_requests:
                        raise RequestLimitError("Se alcanzó el límite global, incluidos reintentos y reanudaciones.")
                    metadata["solicitudes_realizadas"] += 1
                    write_json(directory / "metadata.json", metadata)
                    batch["estado"] = "EN_CURSO"
                    write_json(cache_path, rec)

                def on_error(error):
                    batch["errores"].append(error)
                    write_json(cache_path, rec)

                try:
                    response = client.evaluate(plan["state"], plan["lotes"][batch["indice"]],
                                               on_attempt=on_attempt, on_error=on_error)
                    batch["respuesta_original"] = response
                    batch["estado"] = "RESPONDIDO"
                except RequestLimitError:
                    batch["estado"] = "PENDIENTE"
                    stopped = True
                except ClientError:
                    batch["estado"] = "ERROR"
                    if any(e.get("status_http") in (401, 403) for e in batch["errores"]):
                        stopped = True
                write_json(cache_path, rec)
                persist_outputs()
                if stopped or batch["estado"] == "ERROR":
                    break
            if stopped:
                break
    finally:
        if client:
            client.close()
        summary = persist_outputs()
    return directory, summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Consolidación experimental JEV-V1 sobre extracciones originales.")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--estrategia", choices=("simple", "completa"), default=Config.strategy)
    parser.add_argument("--solo-archivos", nargs="+")
    parser.add_argument("--limite-documentos", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--autorizar-envio-datos", action="store_true",
                        help="Autorización explícita para transmitir datos jurídicos al servicio oficial TypeSafe.")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--reintentar-errores", action="store_true",
                        help="Reintenta errores o llamadas sin respuesta guardada; puede repetir consumo.")
    parser.add_argument("--model", default=Config.model)
    parser.add_argument("--umbral", type=float, default=Config.threshold)
    parser.add_argument("--umbral-equivalencia", type=float, default=Config.equivalence_threshold)
    parser.add_argument("--max-solicitudes", type=int, default=Config.max_requests)
    parser.add_argument("--preguntas-por-solicitud", type=int, default=Config.questions_per_request)
    parser.add_argument("--timeout", type=float, default=Config.timeout)
    parser.add_argument("--reintentos", type=int, default=Config.retries)
    parser.add_argument("--permitir-contexto-estimado", action="store_true",
                        help="Permite enviar state que supera la estimación local por bytes; la API valida los límites reales por tokens. No trunca evidencia.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        directory, summary = run_experiment(
            experiment=args.experiment,
            config=Config(model=args.model, threshold=args.umbral, equivalence_threshold=args.umbral_equivalencia,
                          timeout=args.timeout, retries=args.reintentos, max_requests=args.max_solicitudes,
                          questions_per_request=args.preguntas_por_solicitud,
                          allow_estimated_oversize=args.permitir_contexto_estimado, strategy=args.estrategia),
            dry_run=args.dry_run, numbers=args.solo_archivos, limit=args.limite_documentos,
            output_dir=args.output_dir, resume=args.resume, authorized=args.autorizar_envio_datos,
            retry_errors=args.reintentar_errores, baseline_path=args.baseline,
        )
    except (ClientError, ValueError, OSError):
        # Solo excepciones propias contienen mensajes controlados; no filtrar SDK/secretos.
        import sys
        exc = sys.exception() if hasattr(sys, "exception") else sys.exc_info()[1]
        print(f"Error: {exc}")
        return 2
    print(f"Salida: {directory}\nEstrategia: {summary['estrategia']}; documentos: {summary['total_documentos']}; candidatos: {summary['total_candidatos']}; "
          f"preguntas: {summary['total_preguntas']}; solicitudes previstas: {summary['solicitudes_previstas_sin_reintentos']}; "
          f"solicitudes realizadas: {summary['solicitudes_realizadas']}")
    if summary["documentos_exceden_estimacion"]:
        print("Hay documentos que superan la estimación local de contexto (no es una medición del tokenizer de Jev). Consultar resumen_jev.json.")
    return 0 if args.dry_run or summary["documentos_pendientes"] == 0 and not summary["errores_procesamiento"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
