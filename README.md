# Identificacion de roles embargados

Proyecto experimental en Python para identificar, con maxima precision posible, la persona fisica o juridica sobre la cual recae una medida judicial de embargo, retencion o ejecucion en documentos judiciales argentinos.

El proyecto esta preparado para usar GLiNER2 localmente. Por privacidad, no agrega servicios cloud ni envia documentos legales a APIs externas.

## Estado actual

Este repositorio solo prepara estructura, configuracion, loaders, schemas, pipeline, exportacion, tests y documentacion. Todavia no implementa una decision final hibrida, metricas contra gold manual ni regex juridica para determinar demandado definitivo.

## Estructura

```text
identificacion_roles/
├── config/
│   ├── modelos.yaml
│   ├── schemas.yaml
│   └── experimentos.yaml
├── data/
│   ├── input_documentos/
│   └── input_fragmentos/
├── outputs/
│   ├── raw/
│   ├── por_documento/
│   └── logs/
├── src/
│   ├── __init__.py
│   ├── config_loader.py
│   ├── data_loader.py
│   ├── model_loader.py
│   ├── schema_builder.py
│   ├── inference.py
│   ├── postprocess.py
│   ├── exporter.py
│   └── run_experiment.py
├── tests/
├── requirements.txt
└── .gitignore
```

## Instalacion futura

Cuando se apruebe ejecutar el proyecto:

```bash
pip install -r requirements.txt
```

`requirements.txt` usa `gliner2[local]` porque la documentacion oficial de GLiNER2 indica ese extra para inferencia local con PyTorch y Transformers. Se usan `PyYAML` para configuracion y `pytest` para tests. No se agrega `pandas` para mantener dependencias minimas; la lectura CSV usa la biblioteca estandar de Python.

## Modelos

Los modelos se declaran en `config/modelos.yaml`. Cada entrada permite configurar:

- `model_id`
- `display_name`
- `architecture`
- `enabled`
- `device`
- `default_threshold`

Modelos iniciales:

- `gliner2_multi`: `fastino/gliner2-multi-v1`, habilitado.
- `contractner_multi`: deshabilitado y con `model_id: null` hasta conocer el repository ID exacto. No se inventa namespace de Hugging Face.

Para agregar otro modelo, crear una nueva clave en `models` y referenciarla desde un experimento.

## Schemas

Los schemas viven en `config/schemas.yaml` y se transforman en `src/schema_builder.py`.

- `schema_v1`: entidad unica `persona_embargada`.
- `schema_v2`: entidades separadas `demandado`, `embargado`, `ejecutado`, `deudor`.
- `schema_v3`: structured extraction `persona_embargada` con campos `nombre`, `dni`, `cuil_cuit`.

Para agregar otro schema, declarar una nueva entrada YAML de tipo `entities` o `structured`.

## Modos de entrada

`documentos_completos`: CSV con una fila por documento. La columna de texto es configurable.

`fragmentos`: CSV generado por un proyecto externo independiente. Este proyecto solo consume ese output y conserva `contador_interno`, `palabra_clave` y posiciones originales por fragmento.

## Experimentos

`config/experimentos.yaml` declara combinaciones de modelo, schema, modo de entrada, archivo, columna de texto, threshold y nombre de corrida.

Comando futuro:

```bash
python -m src.run_experiment --experiment gliner2_v1_fragmentos
```

No ejecutar hasta revisar configuracion, datos y API efectiva del modelo.

## Outputs

Cada corrida crea carpetas con fecha:

```text
outputs/raw/YYYYMMDD_nombre_corrida/
├── predicciones.csv
├── predicciones.json
└── config_usada.yaml

outputs/por_documento/YYYYMMDD_nombre_corrida/
├── predicciones_por_documento.csv
├── predicciones_por_documento.json
└── config_usada.yaml
```

El output raw conserva texto usado, metadata de fragmento, modelo, schema, threshold, candidatos, confidence, spans cuando existan y respuesta cruda serializada como JSON.

La salida por documento agrupa predicciones por `id` sin elegir todavia un demandado definitivo. Si un documento tiene diez fragmentos, los diez resultados se conservan.

## API GLiNER2 a verificar antes de ejecutar

La documentacion oficial recomienda `AutoExtractor.from_pretrained(...)` para cargar checkpoints actuales. El proyecto lo centraliza en `src/model_loader.py`.

Antes de correr inferencia real conviene verificar, con el entorno instalado, el metodo exacto disponible para structured extraction del checkpoint elegido. El codigo intenta `extract_structured(...)` y luego `extract(...)` para ese modo, pero esa parte debe confirmarse con la version instalada.

Referencias:

- [GLiNER2 GitHub](https://github.com/fastino-ai/GLiNER2)
- [fastino/gliner2-multi-v1](https://huggingface.co/fastino/gliner2-multi-v1)

====================================================================================
schema_v1_persona_simple

Objetivo: encontrar solo el nombre de la persona afectada por la medida.

persona_embargada

Descripción sugerida:

Persona física o jurídica sobre la cual recae directamente la medida de embargo, retención o ejecución. Puede aparecer como demandado, demandada, embargado, embargada, ejecutado, ejecutada o deudor. No incluir jueces, abogados, funcionarios, firmantes, personas autorizadas, actores, acreedores ni destinatarios del oficio.

Sirve para: baseline simple.

schema_v2_roles

Objetivo: ver con qué rol jurídico aparece la persona.

demandado
embargado
ejecutado
deudor

Cada uno con su descripción específica.

Ejemplo:

demandado
→ Persona contra la cual se dirige la demanda.

embargado
→ Persona cuyos fondos, cuentas o bienes son objeto del embargo.

ejecutado
→ Persona contra la cual se lleva adelante la ejecución.

deudor
→ Persona obligada al pago de la deuda reclamada.

Sirve para: estudiar lenguaje jurídico y comparar qué label funciona mejor.

No lo usaría como salida final principal.

schema_v3_persona_structured

Este sería mi favorito para roles.

persona_embargada
├── nombre
├── dni
└── cuil_cuit
nombre

Nombre completo de la persona física o razón social de la persona jurídica sobre la cual recae directamente la medida.

dni

DNI correspondiente exclusivamente a la persona afectada por la medida.

Opcional.

cuil_cuit

CUIL o CUIT correspondiente exclusivamente a la persona afectada por la medida.

Opcional.

Acá luego conviene agregar validadores regex para DNI/CUIL/CUIT.

schema_v4_datos_embargo

Este sería para el dinero que realmente corresponde a la medida.

datos_embargo
├── monto_capital
├── monto_costas
├── monto_total
└── moneda
monto_capital

Importe principal reclamado o sobre el cual se decreta el embargo.

monto_costas

Importe adicional previsto para intereses, costos o costas.

monto_total

Importe total a embargar cuando el documento lo expresa explícitamente como una suma total.

Importante: no debería sumar automáticamente capital + costas. Solo extraerlo si aparece expresado.

moneda

Moneda correspondiente a los montos extraídos, por ejemplo ARS.

Esto permitiría diferenciar cosas como:

$108.332,50 → capital
$81.249 → intereses/costas

en vez de devolver todos los montos juntos.

schema_v5_cuenta_deposito

Este sería exclusivamente para dónde deben depositarse los fondos embargados.

cuenta_deposito
├── cbu
├── cvu
├── alias
├── numero_cuenta
├── banco
└── titular
cbu

CBU de la cuenta judicial o cuenta indicada para depositar las sumas retenidas.

cvu

CVU indicado para el depósito de las sumas retenidas.

alias

Alias de la cuenta de depósito.

numero_cuenta

Número de cuenta judicial o bancaria asociado al depósito.

banco

Banco donde se encuentra la cuenta indicada para depositar los fondos.

titular

Titular de la cuenta de depósito, si está explícitamente indicado.

Acá la descripción debería recalcar algo muy importante:

No extraer cuentas del demandado ni cuentas sobre las cuales recae el embargo; solamente la cuenta de destino donde deben depositarse los fondos retenidos.

Esto evitaría una confusión bastante peligrosa.

Más adelante: schema_v6_embargo_completo

Solo después de probar los anteriores.

Podría tener:

embargo
├── persona_embargada
│ ├── nombre
│ ├── dni
│ └── cuil_cuit
│
├── datos_embargo
│ ├── monto_capital
│ ├── monto_costas
│ ├── monto_total
│ └── moneda
│
└── cuenta_deposito
├── cbu
├── cvu
├── alias
├── numero_cuenta
├── banco
└── titular

Pero no empezaría por este.

Primero quiero saber si GLiNER2 funciona bien con:

persona
montos
cuenta

por separado.

Cómo quedarían nuestros experimentos

Por ejemplo:

GLiNER2 + schema_v3 + fragmentos
GLiNER2 + schema_v3 + documento completo

GLiNER2 + schema_v4 + fragmentos
GLiNER2 + schema_v5 + fragmentos

Y después cambiamos modelo manteniendo exactamente los mismos schemas.

Eso nos va a permitir responder algo mucho más útil que “qué modelo es mejor”:

qué modelo + schema + tipo de entrada funciona mejor para cada dato.
