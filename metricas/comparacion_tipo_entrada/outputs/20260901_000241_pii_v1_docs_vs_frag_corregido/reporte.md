# Comparación documentos completos vs fragmentos

## Configuración

* modelo: fastino/gliner2-privacy-filter-PII-multi
* schema: schema_v1_persona_simple
* threshold: 0.6
* cantidad de documentos: 80
* cantidad de fragmentos: 333

## Resumen principal

| metrica | documentos_completos | fragmentos |
| --- | --- | --- |
| Cobertura persona embargada | 96.25% | 95.00% |
| No detectados | 3.75% | 5.00% |
| Múltiples candidatos | 90.00% | 62.50% |
| Candidato único | 6.25% | 32.50% |
| Confidence media persona embargada | 0.8518651081370069 | 0.881834717957597 |
| Tiempo total segundos | None | None |

## Acuerdo entre modos

* Persona embargada: 47 de 74 (63.51%)

## Casos exclusivos

Ver `casos_solo_documento.csv` y `casos_solo_fragmentos.csv`.

## Ambigüedad

* Sin candidato en fragmentos: 4 (5.00%)
* Un candidato único en fragmentos: 26 (32.50%)
* Más de un candidato distinto en fragmentos: 50 (62.50%)

## Confidence

La confidence se reporta como señal del modelo, no como evidencia de exactitud.

## Rendimiento

* tiempo total documentos: None
* tiempo total fragmentos: None
* segundos por documento en documentos completos: None
* segundos por documento en fragmentos: None
* segundos por fragmento: None
* speedup fragmentos vs documentos: None

## Interpretación

Este experimento usa un schema simple que extrae únicamente `persona_embargada`. Por lo tanto, la comparación se centra en cobertura del rol, cantidad de candidatos, acuerdo entre modos, ambigüedad y confidence.

Estas métricas comparan el comportamiento de ambos modos de entrada. No representan accuracy real porque no se dispone aún de un gold manual.