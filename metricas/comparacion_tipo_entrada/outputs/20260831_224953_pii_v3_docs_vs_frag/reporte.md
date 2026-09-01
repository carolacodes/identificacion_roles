# Comparación documentos completos vs fragmentos

## Configuración

* modelo: fastino/gliner2-privacy-filter-PII-multi
* schema: schema_v3_persona_structured
* threshold: 0.65
* cantidad de documentos: 80
* cantidad de fragmentos: 235

## Resumen principal

| metrica | documentos_completos | fragmentos |
| --- | --- | --- |
| Cobertura nombre | 45.00% | 82.50% |
| Cobertura DNI | 87.50% | 65.00% |
| Cobertura CUIL/CUIT | 48.75% | 21.25% |
| No detectados | 5.00% | 15.00% |
| Confidence media nombre | 0.7773723420169618 | 0.8710463181890623 |
| Tiempo total segundos | 872.277 | 164.663 |

## Acuerdo entre modos

* Nombre: 17 de 30 (56.67%)
* DNI: 46 de 49 (93.88%)
* CUIL/CUIT: 11 de 13 (84.62%)

## Casos exclusivos

Ver `casos_solo_documento.csv` y `casos_solo_fragmentos.csv`.

## Ambigüedad en fragmentos

Ver `casos_ambiguos_fragmentos.csv` y la sección `ambiguedad_fragmentos` en `metricas_globales.json`.

## Confidence

La confidence se reporta como señal del modelo, no como evidencia de exactitud.

## Rendimiento

* tiempo total documentos: 872.277
* tiempo total fragmentos: 164.663
* segundos por documento en documentos completos: 10.9034625
* segundos por documento en fragmentos: 2.0582875
* segundos por fragmento: 0.7006936170212766
* speedup fragmentos vs documentos: 5.29734670205207

## Interpretación

Estas métricas permiten observar mayor o menor cobertura, cantidad de no detectados, acuerdo entre modos, ambigüedad, confidence media y tiempo de ejecución. No permiten afirmar que un modo sea más preciso porque no existe un gold manual.

Estas métricas comparan el comportamiento de ambos modos de entrada. No representan accuracy real porque no se dispone aún de un gold manual de roles.
