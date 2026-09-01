# Comparación por tipo de entrada

Este módulo compara el comportamiento del mismo modelo cuando procesa documentos completos y cuando procesa fragmentos. La pregunta que ayuda a responder es si GLiNER2 se comporta de manera más estable sobre documentos completos o sobre fragmentos.

Este módulo no compara modelos.

Inferencia y métricas son proyectos separados.

Este módulo no modifica ni ejecuta GLiNER2.

## Qué mide

El módulo mide cobertura, detección, acuerdo, desacuerdo, confidence, estabilidad, ambigüedad y eficiencia. Consume archivos `predicciones.json` o `predicciones.csv` ya generados por corridas existentes.

## Qué no mide

No existe todavía un gold manual de roles para los documentos. Por eso este módulo no calcula accuracy, precision, recall, F1 ni tasa de acierto real. Tampoco clasifica detecciones como correctas o incorrectas.

## Estructura

```text
metricas/comparacion_tipo_entrada/
├── input/
│   ├── documentos/
│   └── fragmentos/
├── src/
├── outputs/
├── tests/
├── README.md
└── requirements.txt
```

## Inputs

Se esperan dos archivos JSON o CSV:

* uno con predicciones de documentos completos
* uno con predicciones de fragmentos

Los campos principales son `id`, `modelo`, `schema`, `threshold`, `modo_entrada`, `nombre_detectado`, `dni_detectado`, `cuil_cuit_detectado` y sus campos de confidence. En fragmentos puede haber múltiples filas para el mismo `id`.

## Comparación por ID

La unidad principal es `id`. Los fragmentos se agregan primero por documento y recién después se comparan contra el resultado del documento completo. Si los conjuntos de IDs no son idénticos, el módulo reporta IDs exclusivos de cada lado y calcula métricas comparativas solo sobre IDs comunes.

## Normalización

La normalización se usa únicamente para comparar:

* nombres: trim, mayúsculas, espacios repetidos a uno, saltos de línea a espacios y remoción conservadora de tildes
* DNI: solo dígitos
* CUIL/CUIT: solo dígitos

Los valores originales exportados se conservan en las salidas.

## Agregación de fragmentos

Para cada `id`, la agregación conserva todos los valores únicos detectados y calcula cantidad de fragmentos, fragmentos con candidato, cantidades de valores distintos y estadísticas de confidence máxima y media por campo. No selecciona un demandado definitivo ni asume que el mayor confidence sea el valor más adecuado.

## Métricas

Las métricas globales incluyen:

* cobertura por tipo de entrada
* agreement entre modos, con denominador igual a documentos donde ambos modos detectan el campo
* detección exclusiva por campo
* ambigüedad de fragmentos
* estadísticas de confidence
* rendimiento opcional si se informan tiempos

## Outputs

Cada corrida crea una carpeta nueva en `outputs/<timestamp_nombre>/` con:

* `resumen_comparacion.csv`
* `comparacion_por_documento.csv`
* `comparacion_por_documento.json`
* `metricas_globales.json`
* `metricas_globales.csv`
* `casos_desacuerdo.csv`
* `casos_solo_documento.csv`
* `casos_solo_fragmentos.csv`
* `casos_ambiguos_fragmentos.csv`
* `reporte.md`

## Comando

```powershell
python -m metricas.comparacion_tipo_entrada.src.run `
  --documentos metricas\comparacion_tipo_entrada\input\documentos\predicciones.json `
  --fragmentos metricas\comparacion_tipo_entrada\input\fragmentos\predicciones.json `
  --run-name pii_v3_docs_vs_frag `
  --docs-seconds 872.277 `
  --fragments-seconds 164.663
```

Los argumentos de tiempo son opcionales. Si se informan, el módulo calcula tiempo total, segundos por documento, segundos por fragmento y speedup de fragmentos frente a documentos completos.

## Interpretación correcta

El reporte permite hablar de mayor cobertura, menor cantidad de no detectados, mayor acuerdo, menor ambigüedad, mayor confidence media o menor tiempo de ejecución.

Estas métricas comparan el comportamiento de ambos modos de entrada. No representan accuracy real porque no se dispone aún de un gold manual de roles.

