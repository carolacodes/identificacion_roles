# Consolidación V14 — 20 oficios y regresión contra 80 históricos

## Política de cambios

- **Sin modificar el modelo GLiNER2, su esquema ni el umbral de extracción.**
- Cambios puntuales en `consolidacion_oficios_v14_preproduccion.py`, generado a partir del archivo original `consolidacion_oficios_v13_codemandados.py`.
- Evidencias solo desde `fragmento`, no búsqueda de personas en `texto_completo` en la consolidación.
- El caso con DNI de nueve dígitos se conserva **provisionalmente** sin DNI validado, `suficiente=false`, `requiere_revision=true` y con identificador textual original en `identificador_pendiente_validacion`.
- Los oficios sin fragmentos mantienen `NO_RESUELTO` y se etiquetan para revisión manual; no se inventan candidatos.
- La revisión manual cuenta con `revision_manual_motivos` (código y descripción) y `revision_manual_descripcion`.

## Prueba de los 20 documentos

| Métrica | V13 | V14 |
|---|---:|---:|
| Suficientes | 13 | 16 |
| Insuficientes | 7 | 4 |
| Identidades aceptadas | 14 (incluye abogada) | 17 (incluye identidad provisional sin DNI) |
| Requieren revisión | 0 | 4 |

Cambios en decisión de identidad:

- Doc 4: LEANDRO ERAUSQUIN, DNI 34.753.007 recuperado localmente; nuevo reconocimiento del pedido sobre ciudadano.
- Doc 10: Tiago Alexander Méndez Mourelle, DNI 44.939.190; reconoce pedido con fórmula «a la mayor brevedad posible» y DNI.
- Doc 11: Pedro Pablo Sangoy, DNI textual `26.556.6320` (9 dígitos) **aceptado en estado provisional para revisión**, sin DNI numérico confirmado, **no suficiente**.
- Doc 16: Carlos José MENDOZA HERNÁNDEZ, DNI argentino 94.478.301 recuperado pese al calificativo «argentino» entre etiqueta y número.
- Doc 18: LOURDES SOSA MANTENBERG M.P 9730 (abogada de la audiencia) descartada; se acepta solo LAGOMARCINO ZORRILLA ALEJANDRO LIONEL.

Revisión obligatoria: docs 2, 5, 11, 12. El 2 contiene fragmentos irrelevantes para el pedido dirigido a Mercado Pago, y el 5 contiene siete personas uruguayas en texto completo pero recibió fragmento vacío; ambos requieren revisión/corrección de fragmentación o fallback explícito. El 12 requiere inspección porque el pedido busca autenticidad de comprobantes sin sujeto explícito. El 11 contiene DNI malformado.

## Regresión de 80 casos

Sobre `predicciones_por_documento(20261101-235003).json`, V13 vs V14:

- **0 cambios** en `(estado, suficiente, nombres/DNI/CUIT aceptados)` para los 80 documentos.
- **76/80** suficientes, **148 identidades aceptadas** en ambas versiones.
- Los registros de revisión pasan de 1 a 5 debido a anotaciones explicativas de documentos que ya eran insuficientes. **No cambia su clasificación ni las personas aceptadas.**

También se comprobó un segundo conjunto de 80 predicciones (`20261030-175058`) con **0 cambios en los mismos campos**: 75/80 suficientes y 147 identidades en ambas versiones.

## Advertencias

1. `suficiente` no equivale a exactitud validada por humanos.
2. La nueva aceptación provisional del caso 11 **no se debe enviar automáticamente al servicio de búsquedas por DNI**; el DNI es inválido y el resultado requiere revisión manual.
3. Los casos 2 y 5 no se pueden recuperar de forma segura con un consolidado que trabaja solo sobre fragmentos que no incluyen las entidades buscadas. Necesitan cambios en la generación de fragmentos o una segunda pasada supervisada sobre el texto completo.
4. La comparación de 80 casos es una **regresión de resultados** (estado, suficiencia, identidades), no prueba exhaustiva de que no haya variado ninguna descripción, score o detalle interno.
5. Antes de producción, integrar en una rama separada del repositorio y ejecutar su batería de tests y el flujo completo con los contratos de salida de los consumidores posteriores.

## Integración

Guardar el módulo V14 como `src/consolidacion_oficios.py` **solo en rama de prueba** si ese es el módulo que importa `src.run_consolidacion_oficios`, conservando previamente una copia de V13. Verificar los imports reales del ejecutor antes de sustituirlo.

Para los mismos 20 casos, ejecutar:

```powershell
python -m src.run_consolidacion_oficios --input "outputs/por_documento/20261113_021835_multi_v1_oficios_fragmentos_thr50_20_casos/predicciones_por_documento.json" --name consolidacion_preproduccion_20_casos_v14
```

Luego correr idéntica comparación sobre los 80 históricos.
