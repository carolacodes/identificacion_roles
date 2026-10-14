"""Comparación posterior descriptiva, sin inferir cuál método es correcto."""
import csv
import json
import os
import tempfile

from .storage import read_json

COLUMNS = ["numero_archivo", "id", "estado_actual", "estado_jev", "nombres_ambos",
           "nombres_solo_jev", "nombres_solo_actual", "identificadores_actual",
           "identificadores_jev", "diferencias_identificadores", "conflictos_actual",
           "conflictos_jev", "requiere_revision_actual", "requiere_revision_jev"]


def write_comparison(path, results, baseline_path=None):
    # Dry-run entrega solo el encabezado: no simula resultados de Jev.
    baseline = read_json(baseline_path) if results and baseline_path else []
    if not isinstance(baseline, list):
        raise ValueError("La consolidación de referencia debe ser una lista.")
    lookup = {(str(row["id"]), str(row["numero_archivo"])): row for row in baseline}
    rows = []
    def names(doc):
        values = set()
        for person in doc.get("personas_embargadas", []):
            originals = person.get("valores_originales", {}).get("nombre_embargado")
            values.update(originals or person.get("variantes_nombre") or [person.get("nombre_embargado")])
        return sorted(v for v in values if isinstance(v, str) and v)
    def identifiers(doc):
        return [{"nombre": p.get("nombre_embargado"), "dni": p.get("dni_embargado"),
                 "cuit_cuil": p.get("cuit_cuil_embargado"), "originales": p.get("valores_originales", {})}
                for p in doc.get("personas_embargadas", [])]
    def identifier_set(doc, name=None):
        values = set()
        for p in doc.get("personas_embargadas", []):
            if name is not None and name not in names({"personas_embargadas": [p]}):
                continue
            for field in ("dni_embargado", "cuit_cuil_embargado"):
                variants = p.get("valores_originales", {}).get(field, [p.get(field)])
                values.update((field, v) for v in variants if v not in (None, ""))
        return values
    for result in results:
        old = lookup.get((str(result["id"]), str(result["numero_archivo"])))
        if old is None:
            continue
        a, j = set(names(old)), set(names(result))
        association_differences = {}
        for name in sorted(a & j):
            old_ids, new_ids = identifier_set(old, name), identifier_set(result, name)
            if old_ids != new_ids:
                association_differences[name] = {"solo_actual": sorted(old_ids - new_ids),
                                                "solo_jev": sorted(new_ids - old_ids)}
        rows.append({
            "numero_archivo": result["numero_archivo"], "id": result["id"],
            "estado_actual": old["estado"], "estado_jev": result["estado"],
            "nombres_ambos": sorted(a & j), "nombres_solo_jev": sorted(j - a), "nombres_solo_actual": sorted(a - j),
            "identificadores_actual": identifiers(old), "identificadores_jev": identifiers(result),
            "diferencias_identificadores": {"solo_actual": sorted(identifier_set(old) - identifier_set(result)),
                                           "solo_jev": sorted(identifier_set(result) - identifier_set(old)),
                                           "por_nombre_compartido": association_differences},
            "conflictos_actual": old.get("conflictos_identificador", []),
            "conflictos_jev": result["conflictos"],
            "requiere_revision_actual": old.get("requiere_revision"), "requiere_revision_jev": result["requiere_revision"],
        })
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".jev-", suffix=".csv")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(rows)
