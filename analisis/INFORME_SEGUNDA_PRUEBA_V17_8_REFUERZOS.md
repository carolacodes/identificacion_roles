# Segunda prueba V17.8: refuerzo contextual seguro

Fecha: 23/11/2026. Base: `consolidacion_oficios_v17_7.py`.

## Objetivo y criterio

Ampliar las formas lingüísticas de requerimiento, objeto e identidad usando **exclusivamente fragmentos** de GLiNER2. Permitir `+1.5` adicional aunque ya haya contexto positivo, **solo cuando sea una relación verificable nueva**. No duplicar la señal V17.7 de la misma relación y no promover terceros por menciones genéricas. La versión anterior queda sin cambios.

## Resultados sobre los 120 casos solicitados

| Conjunto | Documentos | Suficientes V17.7 | Suficientes V17.8 | Cambios aceptación/descartes/suficiencia | Cambios diagnósticos de puntuación |
|---|---:|---:|---:|---:|---:|
| Históricos 01/11 | 80 | 76 | 76 | 0 | 1 |
| Internacionales | 20 | 1 | 1 | 0 | 0 |
| Nuevos | 20 | 16 | 16 | 0 | 0 |
| **Total** | **120** | **93** | **93** | **0** | **1** |

La mejora diagnóstica real fue el documento `496887`, `ANGELA DEL BUONO` (DNI `14124313`): `score_total` pasó de **9.977** a **11.477**, por vínculo literal de la cuenta a nombre de la persona. No se incorporó ningún sujeto nuevo.

En el ensayo sin desduplicación aparecían otros dos aumentos (`497726`, `790085`), pero **duplicaban relaciones ya reconocidas por V17.7**. Se evitó sumar esos puntos dos veces. Por tanto, **3 puntuaciones distintas en el ensayo bruto, 1 refuerzo independiente en la integración conservadora**.

### Corridas adicionales

- 80 históricos 30/10: 75 suficientes antes y después; una diferencia exclusivamente de puntuación en `496887`.
- 20 anteriores: 16 suficientes antes y después; cero diferencias.
- Total auditado: **220 ejecuciones por documento** (incluyen dos corridas de 80 históricos y dos grupos de 20 anteriores; no son 220 documentos únicos).

### Seguridad y límites

- **7/7 pruebas sintéticas dirigidas**: domicilio y contratos positivos; firmante repetido, autorizado, DNI de otra persona, falta de identificador y falta de solicitud rechazados.
- Mutar `texto_completo` de los 20 nuevos no modifica ningún campo de decisión: se conserva solo como metadato.
- Identidades aceptadas, descartadas, motivos de decisión, suficiencia, revisión manual, conflictos y asociación DNI/CUIT **sin cambios** en las corridas.
- `score_total` y `decision_consolidacion.detalle.score_total` reflejan la diferencia diagnóstica permitida; no se esperan salidas idénticas *byte a byte*.
- **Sin nuevos documentos resueltos**: la mejora es una evidencia contextual identificada, no una mejora demostrada de cobertura.

## Implementación

Archivo de versión: `consolidacion_oficios_v17_8_refuerzos.py`. Contiene las familias `_V17_8_FAMILIAS`, la función `_v17_8_relacion_refuerzo` y una incorporación acotada en `_score_contexto`. Conserva V17.7 y evita contabilizar dos veces la señal V17.7.

Prueba reproducible: `python verificar_v17_8_refuerzos_120.py`.

**Conclusión:** prueba de compatibilidad aprobada sobre los 120 solicitados y 100 ejecuciones complementarias. Integración recomendada solo como **refuerzo contextual aditivo acotado**, no como ampliación de criterios de aceptación sin más validación.
