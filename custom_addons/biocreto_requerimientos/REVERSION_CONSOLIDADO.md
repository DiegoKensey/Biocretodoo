# Reversión del consolidado (BIOCRETO CONSOLIDADO v1)

Instrucción única para descartar por completo la funcionalidad de consolidado
mensual de `biocreto_requerimientos`. Si alguien dice *"borra el consolidado"*,
basta con seguir este archivo.

Introducido en la versión **19.0.1.1.0** del módulo.
Rehecho en la **19.0.1.3.0**: el periodo pasó a ser un filtro de la vista, el
diálogo «Configurar» desapareció y la generación de la compra se convirtió en
una acción de lote sobre las filas marcadas. Ver la sección 7.

---

## 1. Archivos a eliminar completos

```
custom_addons/biocreto_requerimientos/models/consolidado.py
custom_addons/biocreto_requerimientos/views/consolidado_views.xml
custom_addons/biocreto_requerimientos/security/consolidado/    (carpeta entera)
custom_addons/biocreto_requerimientos/REVERSION_CONSOLIDADO.md (este archivo)
```

No contienen nada más que consolidado. Los dos primeros llevan los marcadores
`=== BIOCRETO CONSOLIDADO v1 — INICIO/FIN ===` en la primera y última línea.

**Por qué el ACL vive en una carpeta propia y no al final del
`ir.model.access.csv` existente:** el cargador de Odoo no admite filas de
comentario en un CSV — una fila que empiece por `#` revienta con `IndexError`
(`odoo/tools/convert.py:750` → `odoo/orm/models.py:1178`), así que no hay forma
de poner una fila de marca. Y el nombre del archivo tampoco es libre:
`convert_csv_import` deduce el modelo del *basename*, de modo que tiene que
llamarse `ir.model.access.csv`. La solución es un archivo con ese nombre en su
propia subcarpeta — que además aísla mejor que mezclarlo.

## 2. Bloques marcados a quitar de archivos preexistentes

Buscar en el módulo y borrar cada bloque delimitado por

```
=== BIOCRETO CONSOLIDADO v1 — INICIO (bloque reversible) ===
...
=== BIOCRETO CONSOLIDADO v1 — FIN ===
```

Comando de localización:

```bash
grep -rn "BIOCRETO CONSOLIDADO v1" custom_addons/biocreto_requerimientos/
```

| Archivo | Bloques | Qué contiene |
|---|---|---|
| `__manifest__.py` | 2 | `'purchase'` y `'stock'` en `depends`; el ACL y la vista del consolidado en `data` |
| `models/__init__.py` | 1 | `from . import consolidado` |
| `views/menus.xml` | 1 | `menuitem` **Consolidado** bajo Logística |

Bajar además la versión del manifest de `19.0.1.1.0` a `19.0.1.0.0` si se
quiere dejar el módulo exactamente como estaba.

## 3. Bloques PERMANENTES — **NO borrar**

Estos llevan el marcador `(bloque PERMANENTE, no borrar en la reversión)`.
Son trazabilidad requerimiento → compra y sobreviven aunque el consolidado se
descarte: si mañana la orden de compra se genera por otra vía, estos son los
campos que se rellenan.

| Archivo | Qué contiene |
|---|---|
| `models/biocreto_requerimiento_linea.py` | `purchase_line_id`, `purchase_order_id` |
| `models/biocreto_requerimiento.py` | `purchase_order_ids`, `purchase_order_count`, `action_ver_compras` |
| `views/biocreto_requerimiento_views.xml` | Stat button **Compras** |
| `views/biocreto_requerimiento_linea_views.xml` | Columna `purchase_order_id` (lista y modal) |

**Consecuencia:** `purchase` sigue siendo una dependencia real del módulo por
culpa de estos campos. Al quitar `'purchase'` del `depends` en el paso 2 hay
que **volver a añadirlo**, o mover los campos permanentes a un módulo puente.
`'stock'` sí se puede quitar: solo lo usaba el consolidado.

## 4. Aplicar la reversión

```bash
"C:/Users/Diego/anaconda3/envs/PruebasOdoo19/python.exe" odoo-bin \
    -c odoo19.conf -d Prueba -u biocreto_requerimientos --stop-after-init
```

Odoo elimina solo las vistas, menús y ACL que ya no estén en los datos
(`ir.model.data` huérfanos). Los **modelos transitorios** desaparecidos dejan
sus tablas en la base; borrarlas es opcional y seguro porque son transitorias:

```sql
DROP TABLE IF EXISTS biocreto_requerimiento_consolidado_linea_biocreto_requerimiento_linea_rel;
DROP TABLE IF EXISTS biocreto_requerimiento_consolidado_linea;
DROP TABLE IF EXISTS biocreto_requerimiento_consolidado;
```

Verificar después:

```sql
SELECT state, latest_version FROM ir_module_module
 WHERE name = 'biocreto_requerimientos';
```

## 5. Plan B ya decidido (qué lo reemplaza)

Si esta versión se descarta, lo que ocupa su lugar es una **vista lista
agrupada de solo lectura** sobre `biocreto.requerimiento.linea`:

- Sin asistente ni modelo transitorio.
- Sin edición de "A comprar".
- Sin generación de compra desde ahí.
- Agrupación por `categoria_producto_id` mediante un filtro del `<search>`.

**No improvisar otra cosa.**

## 6. Contexto técnico que motivó esta arquitectura

Para que quien revierta no repita la investigación:

- `purchase.order.partner_id` es `required=True`
  (`odoo/addons/purchase/models/purchase_order.py:91-94`) y `NOT NULL` en la
  tabla. No se puede crear una OC "sin proveedor". Desde la 19.0.1.3.0 el
  proveedor se pide en un diálogo propio al generar la cotización
  (`BiocretoRequerimientoCotizacionWizard`), con `partner_id` **required en el
  modelo del diálogo**: así el cliente no deja pulsar «Generar» sin él.
- Una lista **embebida** en un x2many **no se puede agrupar**: usa
  `StaticList` (`web/static/src/model/relational_model/static_list.js:78`),
  que no implementa `isGrouped` ni `groupBy`, y `x2many_field.js` nunca lee
  `defaultGroupBy`. El atributo `default_group_by` se ignora en silencio.
  Por eso la pantalla principal es una vista lista **suelta** (decisión B2),
  igual que `l10n_in/views/account_invoice_views.xml:107`.
- `display="always"` en un botón del `<header>` lo pinta en la barra de control
  sin necesidad de marcar filas; el valor por defecto de `processButton` es
  `"selection"` (`web/static/src/views/utils.js:236`), que lo pinta como botón
  **directo** en la barra de selección (`list_controller.xml:63-79`) en cuanto
  hay filas marcadas. Desde la 19.0.1.3.0 se usa el segundo, que es lo que
  corresponde a una acción de lote. Con `"always"`, `MultiRecordViewButton`
  llama al método con el recordset **vacío** si no hay selección
  (`getResIds(true)` devuelve `this.selection`, `dynamic_list.js:115-129`); por
  eso `_biocreto_get_consolidado()` conserva el respaldo por contexto.
- La lectura de stock va con `sudo()`: `qty_available` se calcula sobre
  `stock.quant`/`stock.move`, cuyas ACL exigen *Inventario/Usuario*. Un
  Encargado de requerimientos no lo tiene por defecto y, sin `sudo()`, el
  consolidado ni siquiera abre (`AccessError` en `_compute_quantities`).
- El `Many2many` a las líneas de origen declara `relation=` explícito: el
  nombre derivado por convención tendría 71 caracteres y `check_pg_name`
  (`odoo/orm/utils.py:102`) aborta el arranque por encima de 63.

---

## 7. Cambios de la 19.0.1.3.0 (contexto para quien revierta)

El archivo `consolidado.py` sigue siendo el único a borrar, y `consolidado_views.xml`
también. Lo que cambió por dentro:

| Antes (1.1.0) | Ahora (1.3.0) | Por qué |
|---|---|---|
| `fecha_desde` / `fecha_hasta` en la cabecera, aplicadas en el dominio del cálculo | Sin fechas. El cálculo trae todo y el recorte lo hace el filtro `mes_actual` de la vista de búsqueda | El usuario puede quitar el filtro y ver meses anteriores sin recalcular. Los subtotales y el total al pie pasan a reflejar lo filtrado, porque el cliente los agrega sobre las filas visibles |
| El dominio descartaba `purchase_line_id != False` | No lo descarta | Las filas ya cotizadas siguen visibles con su distintivo. Al recibirse la compra, sube el stock y `cantidad_comprar` cae sola |
| El dominio pedía `estado in ('pendiente','atendido')` | `estado != 'cancelado'` | Entró el estado `parcial` con el flujo de entregas |
| Botón «Configurar» + `consolidado_view_form` | Eliminados | El único parámetro que quedaba era el proveedor, y ahora se pide al generar |
| `partner_id` en la cabecera | En `biocreto.requerimiento.cotizacion.wizard`, `required=True` | Un solo sitio donde se elige, y el cliente ya no deja generar sin él |
| `purchase_id` (Many2one) | `purchase_ids` (Many2many) | Un mismo consolidado puede generar varias cotizaciones, a proveedores distintos o en tandas |
| Botón «Generar compra» con `display="always"` | Botón «Generar cotización» sin `display` | Sin el atributo, el valor por defecto es `"selection"` (`web/static/src/views/utils.js:236`) y el cliente lo pinta como botón **directo** en la barra de selección (`list_controller.xml:63-79`), no dentro del engranaje |

**Campos que quedaron sin pantalla** al eliminarse el diálogo de configuración:
`aviso_tecnico`, `total_solicitado`, `total_a_comprar`, `sin_producto_count` y
`sin_producto_texto`. Se siguen calculando y escribiendo, pero ya no se pintan
en ningún sitio. El único con contenido que se pierde de vista es
`aviso_tecnico`: recoge las conversiones de UdM y el aviso de planta sin
almacén. Si hacen falta, hay que darles un hueco nuevo.
