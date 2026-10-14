"""Proyección técnica de decisiones: todos los valores provienen de GLiNER2."""
from itertools import combinations

FIELDS = ("nombre_embargado", "dni_embargado", "cuit_cuil_embargado")
ALIASES = {"nombre_embargado": "nombre", "dni_embargado": "dni", "cuit_cuil_embargado": "cuil_cuit"}


def original_value(candidate, field):
    # La forma canónica del exportador tiene precedencia, incluso cuando es null.
    if field in candidate:
        return candidate[field]
    nested = candidate.get("fields")
    if isinstance(nested, dict) and isinstance(nested.get(field), dict):
        return nested[field].get("text")
    return candidate.get(ALIASES[field])


def unique_values(candidates, field):
    values = []
    for candidate in candidates:
        value = original_value(candidate, field)
        if value is not None and value != "" and value not in values:
            values.append(value)
    return values


def build_result(document, interpreted, config):
    if config.strategy == "simple":
        return build_simple_result(document, interpreted, config)
    answers = interpreted["answers"]
    issues, conflicts = list(interpreted["errores"]), []
    uncertain = bool(issues)
    accepted, decisions = [], []

    def noul(qid):
        return answers.get(qid, {}).get("noul")

    for cid in document.candidates:
        p = noul(f"acepta:{cid}")
        selected = p is not None and p >= config.threshold
        status = "ACEPTADO" if selected else "DESCARTADO" if p is not None and p <= 1 - config.threshold else "INCIERTO"
        if status == "INCIERTO":
            uncertain = True
            issues.append({"tipo": "aceptacion_incierta", "candidatos": [cid]})
        if selected:
            accepted.append(cid)
        role = answers.get(f"rol:{cid}", {})
        if role.get("choice") == "insuficiente" or role.get("confidence", 0) < config.threshold:
            uncertain = True
            issues.append({"tipo": "rol_incierto", "candidatos": [cid]})
        if role.get("confidence", 0) >= config.threshold and (
            (selected and role.get("choice") != "embargado") or
            (status == "DESCARTADO" and role.get("choice") == "embargado")
        ):
            conflicts.append({"tipo": "rol_aceptacion_contradictorios", "candidatos": [cid]})
        p_conflict = noul(f"conflicto:{cid}")
        if p_conflict is not None and p_conflict >= config.threshold:
            conflicts.append({"tipo": "identificador_segun_jev", "candidatos": [cid], "probabilidad_jev": p_conflict})
        elif p_conflict is None or p_conflict > 1 - config.threshold:
            uncertain = True
            issues.append({"tipo": "conflicto_incierto", "candidatos": [cid]})
        decisions.append({"candidato_id": cid, "decision": status, "probabilidad_jev": p, "rol_jev": role})

    adjacency = {cid: set() for cid in accepted}
    for left, right in combinations(document.candidates, 2):
        p = noul(f"equiv:{left}:{right}")
        pc = noul(f"conflicto_par:{left}:{right}")
        if pc is not None and pc >= config.threshold:
            conflicts.append({"tipo": "identificadores_par_segun_jev", "candidatos": [left, right], "probabilidad_jev": pc})
        elif pc is None or pc > 1 - config.threshold:
            uncertain = True
            issues.append({"tipo": "conflicto_par_incierto", "candidatos": [left, right]})
        if p is None or 1 - config.equivalence_threshold < p < config.equivalence_threshold:
            uncertain = True
            issues.append({"tipo": "equivalencia_incierta", "candidatos": [left, right]})
        if p is not None and p >= config.equivalence_threshold:
            if left in adjacency and right in adjacency:
                adjacency[left].add(right)
                adjacency[right].add(left)
            elif (left in adjacency) != (right in adjacency):
                conflicts.append({"tipo": "equivalencia_aceptacion_contradictorias", "candidatos": [left, right]})

    groups, visited = [], set()
    for cid in accepted:
        if cid in visited:
            continue
        component, pending = set(), [cid]
        while pending:
            node = pending.pop()
            if node not in component:
                component.add(node)
                pending.extend(adjacency[node] - component)
        visited |= component
        ordered = [node for node in accepted if node in component]
        # Evita inventar equivalencias transitivas que el modelo no confirmó.
        if any(right not in adjacency[left] for left, right in combinations(ordered, 2)):
            conflicts.append({"tipo": "equivalencia_no_transitiva", "candidatos": ordered})
            groups.extend([[node] for node in ordered])
        else:
            groups.append(ordered)

    people = []
    for group in groups:
        candidates = [document.candidates[cid] for cid in group]
        full_ids = [cid for cid in group if (noul(f"completo:{cid}") or 0) >= config.threshold
                    and original_value(document.candidates[cid], "nombre_embargado") not in (None, "")]
        representative = full_ids[0] if full_ids else group[0]
        limitations = [] if full_ids else ["nombre_completo_no_confirmado_por_jev"]
        if limitations:
            uncertain = True
        variants = {field: unique_values(candidates, field) for field in FIELDS}
        person = {"nombre_embargado": original_value(document.candidates[representative], "nombre_embargado")}
        for field in FIELDS[1:]:
            values = variants[field]
            person[field] = values[0] if len(values) == 1 else None
            if len(values) > 1:
                conflicts.append({"tipo": "valores_literales_divergentes", "campo": field,
                                  "candidatos": group, "valores_originales": values})
                limitations.append(f"{field}_sin_valor_unico")
        person.update({
            "candidato_representante": representative, "candidatos_ids": group,
            "valores_originales": variants, "limitaciones": limitations,
            "referencias_evidencia": [document.references[cid]["candidato"] for cid in group],
            "evidencias": [{"candidato_id": cid, "referencias": document.references[cid],
                            "extraccion_original": document.candidates[cid],
                            "resultado_original": document.state["documento"]["resultados"][int(cid[1:5]) - 1]}
                           for cid in group],
            # No combina probabilidades ni las presenta como confianza de la identidad.
            "probabilidad_jev": noul(f"acepta:{representative}"),
            "probabilidades_por_candidato": {cid: noul(f"acepta:{cid}") for cid in group},
        })
        people.append(person)
    if not document.candidates:
        uncertain = True
        issues.append({"tipo": "sin_candidatos_originales"})
    count = len(people)
    identifier_conflicts = [c for c in conflicts if c["tipo"] in {
        "identificador_segun_jev", "identificadores_par_segun_jev", "valores_literales_divergentes",
    }]
    return {
        "id": document.original["id"], "numero_archivo": document.original["numero_archivo"],
        "nombre_documento": document.original.get("nombre"), "metodo_consolidacion": "jev",
        "estado": "NO_RESUELTO" if count == 0 else "RESUELTO" if count == 1 else "RESUELTO_MULTIPLE",
        "cantidad_embargados": count, "personas_embargadas": people,
        "requiere_revision": uncertain or bool(conflicts), "incertidumbre": uncertain,
        "conflictos": conflicts,
        "conflictos_identificador": identifier_conflicts, "cantidad_conflictos_identificador": len(identifier_conflicts),
        "observaciones": issues, "decisiones_candidatos": decisions,
        "evaluacion_suficiencia": "NO_EVALUADA_EN_JEV_V1",
        "procesamiento": "RESPUESTA_INCOMPLETA" if interpreted["errores"] else "COMPLETO",
        "errores_respuesta": interpreted["errores"],
    }


def build_simple_result(document, interpreted, config):
    """Una salida por extracción aceptada; no evalúa ni presupone equivalencias."""
    unevaluated = ["deduplicacion", "rol", "nombre_completo", "conflictos_identificador"]
    issues = list(interpreted["errores"])
    uncertain = bool(issues)
    people, decisions = [], []
    for cid, candidate in document.candidates.items():
        p = interpreted["answers"].get(f"acepta:{cid}", {}).get("noul")
        selected = p is not None and p >= config.threshold
        status = "ACEPTADO" if selected else "DESCARTADO" if p is not None and p <= 1 - config.threshold else "INCIERTO"
        decisions.append({"candidato_id": cid, "decision": status, "probabilidad_jev": p})
        if status == "INCIERTO":
            uncertain = True
            issues.append({"tipo": "aceptacion_incierta", "candidatos": [cid]})
        if selected:
            people.append({
                **{field: original_value(candidate, field) for field in FIELDS},
                "candidato_representante": cid, "candidatos_ids": [cid],
                "valores_originales": {field: unique_values([candidate], field) for field in FIELDS},
                "limitaciones": ["deduplicacion_no_evaluada", "nombre_completo_no_evaluado",
                                 "conflictos_identificador_no_evaluados"],
                "referencias_evidencia": [document.references[cid]["candidato"]],
                "evidencias": [{"candidato_id": cid, "referencias": document.references[cid],
                                "extraccion_original": candidate,
                                "resultado_original": document.state["documento"]["resultados"][int(cid[1:5]) - 1]}],
                "probabilidad_jev": p, "probabilidades_por_candidato": {cid: p},
            })
    if not document.candidates:
        uncertain = True
        issues.append({"tipo": "sin_candidatos_originales"})
    issues.append({"tipo": "evaluaciones_no_realizadas", "evaluaciones": unevaluated})
    count = len(people)
    return {
        "id": document.original["id"], "numero_archivo": document.original["numero_archivo"],
        "nombre_documento": document.original.get("nombre"), "metodo_consolidacion": "jev",
        "estrategia": "simple", "deduplicacion": "NO_EVALUADA",
        "evaluaciones_no_realizadas": unevaluated, "unidad_conteo": "candidatos_aceptados_sin_deduplicar",
        "estado": "NO_RESUELTO" if count == 0 else "RESUELTO" if count == 1 else "RESUELTO_MULTIPLE",
        "cantidad_embargados": count, "personas_embargadas": people,
        # La probabilidad se registra aparte de las evaluaciones omitidas.
        "requiere_revision": True, "incertidumbre": uncertain,
        "conflictos": [], "conflictos_identificador": [], "cantidad_conflictos_identificador": 0,
        "observaciones": issues, "decisiones_candidatos": decisions,
        "evaluacion_suficiencia": "NO_EVALUADA_EN_JEV_V1",
        "procesamiento": "RESPUESTA_INCOMPLETA" if interpreted["errores"] else "COMPLETO",
        "errores_respuesta": interpreted["errores"],
    }
