# RECON EXPRESS — productos de concreto, origen del slump y enlace de Maps

> Tercer recon, acotado. Complementa `RECON_BIOCRETO.md` y `RECON_COMPLEMENTO.md` **sin
> repetirlos**. Ejecutado el 2026-08-21 en **SOLO LECTURA**: ningún archivo del proyecto
> modificado, ningún `-u`/`-i`, todas las consultas fueron `SELECT`. Único archivo creado: este.

---

## 1. Resumen ejecutivo

1. **El slump NO vive en el producto.** El único campo técnico en `product.template` es `biocreto_fc_resistencia` (Integer, f'c). No hay slump, ni atributos, ni variantes.
2. **Solo hay DOS productos** en juego: `Concreto FC 210` (id 7, f'c=210) y `Servicio de Bombeo` (id 10). Un único producto de concreto para las 19 líneas.
3. **"5-6" y "7-8" NO existen en la base.** Barrido exhaustivo de **todas** las columnas de texto/jsonb de datos: 1 solo match, y es una fórmula contable ajena. El candidato más parecido es el catálogo **Huso TMN** (`3/4"` y `1/2"`) — dos entradas, con comillas de pulgada, justo al lado del slump en el formulario.
4. **Nada rellena el slump al elegir producto.** Cero `onchange`/`compute` sobre `product_id` que toquen slump.
5. **El RUC de la compañía NO se imprime en la cotización** (DESCONOCIDO #3 resuelto). El único `vat` del reporte es el **del cliente**. No hay riesgo de duplicado.
6. **La prueba del enlace de Maps queda pendiente**: `DESCONOCIDO — no se proporcionó un enlace real`. El script está listo para ejecutarse en cuanto lo facilites.

> ⚠️ **La base cambió durante el recon.** Se crearon las órdenes 30 y 31 hoy (18:18 y 18:34).
> Los conteos de `RECON_COMPLEMENTO.md` §3.4 **han quedado desactualizados**: ahora son
> **19 líneas con slump** (eran 16), **36 líneas totales** (eran 33) y **5 valores distintos**
> (apareció `4.00`). Los datos de este informe son los vigentes.

---

## 2. Productos y slump

### 2.1 Los productos de concreto

Solo existen **dos** productos en las categorías Concreto/Bombeo, y **uno solo** aparece en
líneas con slump:

```sql
SELECT pt.id, pt.name->>'en_US' AS nombre, pt.default_code, pc.complete_name AS categoria,
       pt.type, pt.uom_id, pt.biocreto_fc_resistencia AS fc, pt.active, pt.sale_ok
FROM product_template pt LEFT JOIN product_category pc ON pc.id = pt.categ_id
WHERE pc.name::text ILIKE '%concreto%' OR pc.name::text ILIKE '%bombeo%'
   OR pt.name::text ILIKE '%concreto%'
ORDER BY pc.complete_name, pt.id;
```
```
 id |       nombre       | default_code | categoria |  type   | uom_id | fc  | active | sale_ok
----+--------------------+--------------+-----------+---------+--------+-----+--------+---------
 10 | Servicio de Bombeo |              | Bombeo    | service |     30 |     | t      | t
  7 | Concreto FC 210    |              | Concreto  | consu   |     29 | 210 | t      | t
```

Y el que se usa en **todas** las líneas con slump es uno solo:

```sql
SELECT DISTINCT pt.id AS tmpl_id, pp.id AS prod_id, pt.name->>'en_US' AS nombre,
       pt.default_code, pt.categ_id, pc.complete_name AS categoria, pt.type,
       pt.uom_id, pt.biocreto_fc_resistencia AS fc
FROM sale_order_line l
JOIN product_product pp ON pp.id = l.product_id
JOIN product_template pt ON pt.id = pp.product_tmpl_id
LEFT JOIN product_category pc ON pc.id = pt.categ_id
WHERE l.biocreto_slump IS NOT NULL AND l.biocreto_slump <> 0;
```
```
 tmpl_id | prod_id |     nombre      | default_code | categ_id | categoria | type  | uom_id | fc
---------+---------+-----------------+--------------+----------+-----------+-------+--------+-----
       7 |       7 | Concreto FC 210 |              |        5 | Concreto  | consu |     29 | 210
```

> **Un solo producto de concreto, sin `default_code`, sin variantes** (`tmpl_id == prod_id == 7`).
> La diferenciación técnica (estructura, cemento, huso, slump) **no está en el producto**:
> vive en la línea de venta.

### 2.2 Campos personalizados en el producto — **NO hay slump**

Barrido completo de campos `biocreto_*` / `x_studio_*` / `x_*` en los dos modelos:

```sql
SELECT model, name, field_description->>'en_US' AS label, ttype, relation, state, store, required
FROM ir_model_fields
WHERE model IN ('product.template','product.product')
  AND (name LIKE 'biocreto_%' OR name LIKE 'x_studio_%' OR name LIKE 'x_%');
```
```
      model       |          name           |          label           |  ttype  | state | store | required
------------------+-------------------------+--------------------------+---------+-------+-------+----------
 product.product  | biocreto_fc_resistencia | Resistencia f'c (kg/cm²) | integer | base  |   f   |    f
 product.template | biocreto_fc_resistencia | Resistencia f'c (kg/cm²) | integer | base  |   t   |    f
```

**Un único campo**, definido en código (`state = 'base'`, no `manual` → **no es Studio**):

```python
# custom_addons/biocreto_base/models/product_template.py:1-11
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    biocreto_fc_resistencia = fields.Integer(
        string="Resistencia f'c (kg/cm²)",
        help="Resistencia característica del concreto. Dato maestro leído por "
             "Ventas, Laboratorio y Fabricación. Ej.: 210, 175.",
    )
```

| Pregunta | Respuesta |
|---|---|
| ¿Campo de **slump** en el producto? | **NO EXISTE** |
| ¿Campo de **resistencia f'c**? | **SÍ** — `biocreto_fc_resistencia`, Integer, código, valor cargado: `210` |
| ¿Otras características técnicas en el producto? | **NO** — ninguna más |
| ¿Studio? | **NO.** `state = 'base'` en ambos modelos |

*(La fila de `product.product` con `store = f` es el reflejo automático vía `_inherits`
del campo del template; no es un segundo campo.)*

### 2.3 Atributos de producto — **ninguno relacionado**

```sql
SELECT a.id, a.name->>'en_US' AS atributo, a.create_variant,
       (SELECT count(*) FROM product_attribute_value v WHERE v.attribute_id = a.id) AS valores
FROM product_attribute a ORDER BY a.id;
```
```
 id |   atributo   | create_variant | valores
----+--------------+----------------+---------
  1 | color        | always         |       0
  2 | gender       | always         |       0
  3 | material     | always         |       0
  4 | pattern      | always         |       0
  5 | manufacturer | always         |       0
  6 | brand        | always         |       0
  7 | size         | always         |       0
  8 | age group    | always         |       0
```

```sql
SELECT v.id, a.name->>'en_US' AS atributo, v.name->>'en_US' AS valor, v.sequence
FROM product_attribute_value v JOIN product_attribute a ON a.id = v.attribute_id;
-- (0 filas)
```

**Los 8 atributos son los de demo de Odoo, todos con CERO valores.** No hay ningún atributo
de slump, resistencia ni tipo de mezcla. **El sistema de variantes no se está usando.**

### 2.4 ★ Las entradas "5-6" y "7-8" — **NO EXISTEN EN LA BASE**

Hice un barrido **exhaustivo**, no una búsqueda por corazonada: generé dinámicamente un
`UNION ALL` sobre **todas** las columnas `character varying` / `text` / `jsonb` de **todas**
las tablas de datos del esquema `public` (excluyendo `ir_*`, `mail_*`, `bus_*`, `base_*`,
`website*` y tablas de relación), buscando el patrón `5-6` o `7-8` como número aislado:

```sql
-- generador (ejecutado, 407.835 caracteres de SQL resultante)
SELECT string_agg(format(
  'SELECT %L AS tabla, %L AS col, id::text AS id, %I::text AS val FROM %I
    WHERE %I::text ~ ''[^0-9](5 ?- ?6|7 ?- ?8)[^0-9]|^(5 ?- ?6|7 ?- ?8)$''',
  c.table_name, c.column_name, c.column_name, c.table_name, c.column_name), ' UNION ALL ')
FROM information_schema.columns c
JOIN information_schema.tables t ON t.table_name = c.table_name
     AND t.table_type = 'BASE TABLE' AND t.table_schema = 'public'
WHERE c.table_schema = 'public'
  AND c.data_type IN ('character varying','text','jsonb')
  AND c.table_name NOT LIKE 'ir\_%'   AND c.table_name NOT LIKE '%\_rel'
  AND c.table_name NOT LIKE 'mail\_%' AND c.table_name NOT LIKE 'bus\_%'
  AND c.table_name NOT LIKE 'website%' AND c.table_name NOT LIKE 'base\_%'
  AND EXISTS (SELECT 1 FROM information_schema.columns c2
              WHERE c2.table_name = c.table_name AND c2.column_name = 'id');
```

**Resultado completo de ejecutar ese SQL:**

```
           tabla           |   col   | id  |          val
---------------------------+---------+-----+------------------------
 account_report_expression | formula | 198 | -6 - 7 - 8\(882) - 999
(1 fila)
```

**Un solo match, y es una fórmula de un reporte contable nativo.** Nada que ver.

Verificaciones dirigidas adicionales, todas con **0 filas**:

```sql
SELECT 'product_template' t, id::text, name::text FROM product_template WHERE name::text ~ '5\s*-\s*6|7\s*-\s*8'
UNION ALL SELECT 'biocreto_huso_tmn', id::text, name::text FROM biocreto_huso_tmn WHERE ...
UNION ALL SELECT 'biocreto_estructura', ...
UNION ALL SELECT 'product_attribute_value', ...
UNION ALL SELECT 'mrp_bom(code)', ...;
-- (0 filas)
```

Y en las 8 tablas `biocreto_*` restantes con columna `name` (`biocreto_carga`,
`biocreto_documento_control`, `biocreto_medio_pago`, `biocreto_probeta`,
`biocreto_probeta_edad`, `biocreto_probeta_tamano`, `biocreto_requerimiento`,
`biocreto_requerimiento_categoria`): **0 coincidencias en todas**.

En **código**, el grep de `5-6`, `7-8`, `rango`, `catalogo`, `mix design`, `diseño de mezcla`
solo devuelve comentarios sobre el rango de **fechas de vaceo** y el rango de **coordenadas**.
Ninguna entrada de datos.

#### ¿Qué son entonces las "dos entradas" que recuerdas?

**El candidato más probable es el catálogo Huso TMN**, y encaja bastante:

```sql
SELECT id, name, sequence, active, company_id FROM biocreto_huso_tmn ORDER BY sequence, id;
```
```
 id | name | sequence | active | company_id
----+------+----------+--------+------------
  1 | 3/4" |       10 | t      |          1
  2 | 1/2" |       10 | t      |          1
```

Por qué encaja: son **exactamente dos entradas**, llevan **comillas de pulgada** (`"`), y
en el formulario aparecen **en el mismo `<group>`, justo encima del slump**
(`custom_addons/biocreto_sale_extension/views/sale_order_views.xml:221-225`):

```xml
                    <group>
                        <field name="biocreto_huso_tmn"
                               required="biocreto_product_categ == 'Concreto'"/>
                        <field name="biocreto_slump"
                               required="biocreto_product_categ == 'Concreto'"/>
                    </group>
```

Pero **no son rangos de slump**: el Huso TMN es el **tamaño máximo nominal del agregado**
(la piedra), no el asentamiento. Y sus valores son `3/4"` y `1/2"`, no `5-6` ni `7-8`.

Los otros dos catálogos, para descartarlos:

```
biocreto_estructura:            biocreto_tipo_cemento:
  1 | Zapatas                     1 | Premiun AI
  2 | Loza aligerada
  3 | Columnas
```

Y lo último que se creó en datos maestros (últimos 60 días) — ningún rango:

```
          t          | id |            nombre             |        create_date
---------------------+----+-------------------------------+----------------------------
 product_template    | 51 | Chaleco de seguridad          | 2026-08-19 22:14:59
 product_category    | 19 | Útiles de oficina             | 2026-08-16 01:38:13
 product_category    | 18 | Limpieza                      | 2026-08-16 01:37:09
 product_template    | 32 | Escoba 1.5m                   | 2026-08-16 01:17:12
 product_template    | 31 | Pizarra 1m                    | 2026-08-16 01:16:30
 product_template    | 16 | Botas de seguridad            | 2026-07-29 18:47:12
 product_category    | 7  | EPPS                          | 2026-07-29 18:47:07
 biocreto_huso_tmn   | 2  | 1/2"                          | 2026-07-24 14:26:43
 biocreto_estructura | 3  | Columnas                      | 2026-07-24 14:25:06
```

> **VEREDICTO:** `DESCONOCIDO — no pude localizar ninguna entrada "5-6" ni "7-8" porque no
> existe en la base de datos ni en el código.` Lo más parecido son las dos entradas del
> catálogo **Huso TMN** (`3/4"` y `1/2"`), que están pegadas al slump en el formulario pero
> **no son rangos de asentamiento**. Ver pregunta 1 del §6.

### 2.5 ¿Algo rellena el slump al elegir producto? — **NO**

Barrido de todos los `@api.onchange('product_id')` y `@api.depends('product_id')` del proyecto:

```
biocreto_requerimientos/models/biocreto_requerimiento_linea.py:119,129,137,148
biocreto_requerimientos/models/consolidado.py:534,539
biocreto_sale_extension/models/sale_order_line.py:151
```

Los seis de `biocreto_requerimientos` son de otro módulo (categoría, UdM y descripción del
requerimiento) y no tocan slump. El único de la línea de venta es:

```python
# custom_addons/biocreto_sale_extension/models/sale_order_line.py:151-156
    @api.depends('product_id', 'product_id.product_tmpl_id')
    def _compute_biocreto_bom_domain(self):
        for line in self:
            tmpl = line.product_id.product_tmpl_id
            line.biocreto_bom_domain = (
                ...
```

Calcula el **dominio de la lista de materiales**, no el slump.

Y los otros dos computes de la línea tampoco:

```python
# :85  @api.depends('price_unit', 'product_uom_qty', 'biocreto_volumen_operativo')
#      def _compute_biocreto_costo_compensado(self)
# :143 @api.depends('company_id', 'company_id.biocreto_bomba_categ_id')
#      def _compute_biocreto_vehiculo_domain(self)
```

> **VEREDICTO: el slump se teclea a mano, línea por línea.** No hay herencia desde el
> producto, ni valor por defecto, ni sugerencia. Nada.

### 2.6 Las 19 líneas con slump — tabla completa

```sql
SELECT l.id, l.order_id, so.name AS orden, so.state, pt.name->>'en_US' AS producto,
       l.biocreto_slump AS slump, l.biocreto_slump_bombeable AS bombeable,
       l.qty_invoiced, (l.qty_invoiced > 0) AS facturada
FROM sale_order_line l
JOIN sale_order so ON so.id = l.order_id
LEFT JOIN product_product pp ON pp.id = l.product_id
LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
WHERE (l.biocreto_slump IS NOT NULL AND l.biocreto_slump <> 0)
   OR (l.biocreto_slump_bombeable IS NOT NULL AND l.biocreto_slump_bombeable <> 0)
ORDER BY so.state, l.order_id, l.id;
```

| id | order | Orden | Estado | Producto | Slump | Bombeable | Fact. |
|---:|---:|---|---|---|---:|---:|:---:|
| 10 | 4 | 2026-ECO-TI-0004 | contract | Concreto FC 210 | **8.00** | 0.00 | |
| 13 | 8 | 2026-ECO-TI-0008 | contract | Concreto FC 210 | 6.00 | 0.00 | |
| 48 | 27 | 2026-ECO-PS-0027 | contract | Concreto FC 210 | 6.00 | 0.00 | |
| 49 | 27 | 2026-ECO-PS-0027 | contract | Servicio de Bombeo | 0.00 | 6.00 | |
| 52 | 29 | 2026-ECO-PS-0029 | contract | Concreto FC 210 | 6.00 | 0.00 | |
| 53 | 30 | 2026-ECO-PS-0030 | contract | Concreto FC 210 | 6.00 | 0.00 | |
| 54 | 31 | 2026-ECO-PS-0031 | contract | Concreto FC 210 | **4.00** | 0.00 | |
| 2 | 1 | 2026-ECO-TI-0001 | draft | Servicio de Bombeo | 0.00 | 6.00 | |
| 3 | 1 | 2026-ECO-TI-0001 | draft | Concreto FC 210 | 6.00 | 0.00 | |
| 50 | 28 | 2026-ECO-PS-0028 | programado | Concreto FC 210 | 6.00 | 0.00 | |
| 51 | 28 | 2026-ECO-PS-0028 | programado | Servicio de Bombeo | 0.00 | 6.00 | |
| 4 | 2 | 2026-ECO-TI-0002 | sale | Concreto FC 210 | **5.00** | 0.00 | |
| 5 | 3 | 2026-ECO-TI-0003 | sale | Concreto FC 210 | 6.00 | 0.00 | |
| 9 | 3 | 2026-ECO-TI-0003 | sale | Servicio de Bombeo | 0.00 | 6.00 | |
| **17** | 9 | 2026-ECO-TI-0009 | sale | Concreto FC 210 | 6.00 | 0.00 | **✔ 2.00** |
| **23** | 9 | 2026-ECO-TI-0009 | sale | Concreto FC 210 | 6.00 | 0.00 | **✔ 3.00** |
| **24** | 9 | 2026-ECO-TI-0009 | sale | Concreto FC 210 | **7.00** | 0.00 | **✔ 4.00** |
| 21 | 11 | 2026-ECO-TI-0011 | sale | Concreto FC 210 | 6.00 | 0.00 | |
| 22 | 11 | 2026-ECO-TI-0011 | sale | Servicio de Bombeo | 0.00 | 6.00 | |
| **29** | 12 | 2026-ECO-PS-0012 | sale | Concreto FC 210 | 6.00 | 0.00 | **✔ 20.00** |
| **30** | 12 | 2026-ECO-PS-0012 | sale | Servicio de Bombeo | 0.00 | 6.00 | **✔ 20.00** |
| 37 | 20 | 2026-ECO-PS-0020 | sale | Concreto FC 210 | 6.00 | 0.00 | |
| 38 | 20 | 2026-ECO-PS-0020 | sale | Servicio de Bombeo | 0.00 | 6.00 | |
| 41 | 21 | 2026-ECO-PS-0021 | sale | Concreto FC 210 | 6.00 | 0.00 | |
| 42 | 22 | 2026-ECO-PS-0022 | sale | Concreto FC 210 | 6.00 | 0.00 | |
| 43 | 22 | 2026-ECO-PS-0022 | sale | Servicio de Bombeo | 0.00 | 6.00 | |
| 47 | 26 | 2026-ECO-PS-0026 | sale | Concreto FC 210 | 6.00 | 0.00 | |

**27 filas en total: 19 con `biocreto_slump` y 8 con `biocreto_slump_bombeable`** (conjuntos
disjuntos — ninguna línea tiene los dos, porque una es Concreto y la otra Bombeo).

**5 líneas facturadas** (marcadas en negrita): ids **17, 23, 24, 29** con slump (4) y la
**30** con bombeable (1).

Distribución actualizada:

```sql
SELECT biocreto_slump, count(*) FROM sale_order_line
WHERE biocreto_slump IS NOT NULL AND biocreto_slump <> 0 GROUP BY 1 ORDER BY 1;
```
```
 biocreto_slump | count
----------------+-------
           4.00 |     1     <- NUEVO desde el informe anterior
           5.00 |     1
           6.00 |    15
           7.00 |     1
           8.00 |     1
```

`biocreto_slump_bombeable`: **8 líneas, todas con `6.00`**. Sin variación.

> **Tres observaciones para el diseño del rango:**
>
> 1. **Los valores reales van de 4 a 8 pulgadas**, todos enteros, y `6.00` concentra 15 de 19.
> 2. **`Servicio de Bombeo` nunca lleva `biocreto_slump`** (siempre 0.00) y **`Concreto FC 210` nunca lleva `biocreto_slump_bombeable`**. La separación por categoría funciona limpiamente en los datos.
> 3. **La orden 9 tiene TRES líneas del mismo producto con slumps distintos** (6, 6, 7), las tres facturadas. Es decir: **el slump varía por línea, no por pedido** — cualquier diseño que lo suba a la cabecera de la orden rompería este caso real.

---

## 3. Prueba del enlace de Google Maps

### 3.1 — 3.4 · `DESCONOCIDO`

`DESCONOCIDO — no pude ejecutar la prueba porque no se proporcionó un enlace real de
Google Maps.` El Paso 3.1 del encargo lo contempla explícitamente: *"Si aún no lo tiene a
mano, dejar este paso como DESCONOCIDO y pedirlo."*

Lo que **sí** está verificado (de `RECON_COMPLEMENTO.md` §4.5, revalidado hoy):

- `requests 2.31.0` / `urllib3 2.0.7` disponibles en `PruebasOdoo19` (Python 3.12.12).
- HTTPS saliente funciona: `nominatim` → 200, `maps.google.com` → 200, `google.com/generate_204` → 204.
- Con **códigos inventados**, `https://maps.app.goo.gl/abc123XYZ` devuelve **404 sin `Location`** — lo esperable para un código inexistente. Prueba conectividad, **no** el mecanismo de redirección.

### 3.5 · VEREDICTO: **PENDIENTE, no determinable sin el enlace**

No puedo pronunciarme sobre si la resolución es viable con una simple redirección HTTP o si
hace falta otro enfoque. **Sería inventar.** Los dos escenarios posibles y sus consecuencias:

| Escenario | Qué implica |
|---|---|
| **301/302 + cabecera `Location`** | Trivial: `requests.get(url, allow_redirects=False, timeout=8)` y leer la cabecera. Sin dependencias nuevas. |
| **200 con el destino resuelto por JavaScript** | Mucho más frágil: haría falta parsear HTML, o un navegador headless, o cambiar de enfoque (pedir al usuario que pegue el enlace largo en vez del corto). |

**Script listo para ejecutar en cuanto facilites el enlace** (cubre los pasos 3.2 a 3.4 de una vez):

```python
import re, requests

URL = "https://maps.app.goo.gl/XXXXXXXX"   # <-- pegar aqui el enlace real

# 3.2 - sin seguir redirecciones
r = requests.get(URL, allow_redirects=False, timeout=8)
print("3.2 status:", r.status_code)
print("3.2 Location:", r.headers.get("Location"))

# 3.3 - siguiendo redirecciones
r2 = requests.get(URL, allow_redirects=True, timeout=8)
print("3.3 saltos:", len(r2.history))
for i, h in enumerate(r2.history, 1):
    print("   salto %d: %s -> %s" % (i, h.status_code, h.headers.get("Location")))
print("3.3 URL final:", r2.url)

# 3.4 - los tres patrones de extraccion
final = r2.url
patrones = {
    "@lat,lng,zoom": r"@(-?\d+\.\d+),(-?\d+\.\d+)",
    "!3dlat!4dlng":  r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
    "?q=lat,lng":    r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)",
}
for nombre, patron in patrones.items():
    m = re.search(patron, final)
    print("3.4 %-15s -> %s" % (nombre, (m.group(1), m.group(2)) if m else "no coincide"))
```

---

## 4. RUC en la cotización — DESCONOCIDO #3 **resuelto**

**El RUC de la compañía NO se imprime en ningún punto de la cotización.**

Barrido de **todo** `report_cotizacion.xml` (981 líneas), no solo del `cot_layout`:

```
$ grep -n "vat\|RUC" custom_addons/biocreto_sale_report_cotizacion/report/report_cotizacion.xml
501:        <!--   RUC/DNI   = vat de la empresa (no del contacto)               -->
519:                    <span class="cliente-value"><t t-out="cp.vat or '—'"/></span>
```

**Dos ocurrencias: una es un comentario y la otra es el `vat` del CLIENTE.** El contexto
(`report_cotizacion.xml:504-520`) lo deja claro — `cp` se define como el partner comercial
del **cliente**, no de la compañía:

```xml
        <t t-set="cp" t-value="o.partner_id.commercial_partner_id"/>
        <div class="cliente-block">
            ...
            <div class="cliente-row">
                <div class="cliente-cell">
                    <span class="cliente-label"><t t-out="o.biocreto_cot_doc_tipo()"/></span>
                    <span class="cliente-value"><t t-out="cp.vat or '—'"/></span>
                </div>
```

Con la etiqueta resuelta dinámicamente según el tipo de documento del **cliente**:

```python
# custom_addons/biocreto_sale_report_cotizacion/models/sale_order.py:95-98
    def biocreto_cot_doc_tipo(self):
        self.ensure_one()
        cp = self.partner_id.commercial_partner_id
        return cp.l10n_latam_identification_type_id.name or 'RUC / DNI'
```

**Confirmación definitiva** — todo lo que el reporte lee de `company_id`, en las 981 líneas:

```
$ grep -n "company_id\|company\." custom_addons/biocreto_sale_report_cotizacion/report/report_cotizacion.xml
814:          - info-band Cuentas Bancarias (dinamica: company.bank_ids)     <- comentario
874:        <!-- Banda: Cuentas Bancarias (dinamica desde company.bank_ids) --> <- comentario
887:                    <t t-set="bancos" t-value="o.company_id.bank_ids"/>    <- ÚNICO uso real
```

> **El reporte de cotización toca `company_id` en UN SOLO SITIO: el bloque bancario.**
> El resto de la identidad de la empresa (nombre, logo, RUC) viaja en el **SVG estático del
> running header** (`report_cotizacion.xml:72-215`), que no contiene ningún `t-out` — es
> gráfico embebido, no datos.
>
> **Conclusión: NO hay riesgo de duplicar el RUC al añadirlo al bloque bancario.** Hoy no
> aparece en ninguna parte de la cotización.

---

## 5. DESCONOCIDOS que persisten

| # | Qué | Por qué | Qué haría falta |
|---|---|---|---|
| 1 | **Dónde están las entradas "5-6" y "7-8"** | `DESCONOCIDO — no existen en la base de datos ni en el código.` Barrido exhaustivo de todas las columnas de texto/jsonb: 1 match y es una fórmula contable ajena | Que confirmes en qué pantalla las viste, o si te refieres al catálogo Huso TMN |
| 2 | **Comportamiento real del enlace corto de Maps** | `DESCONOCIDO — no se proporcionó un enlace real.` Determina si la implementación es trivial o frágil | Un enlace `https://maps.app.goo.gl/...` real |
| 3 | Si el RUC aparece **gráficamente** en el SVG del header | El header es un SVG estático sin `t-out`; no lo rendericé a imagen para leer su contenido visual | Mirar un PDF de cotización ya generado |
| 4 | Por qué `Concreto FC 210` no tiene `default_code` | Verificado que está vacío, pero no sé si es deliberado | Decisión tuya; irrelevante para el slump |
| 5 | Si habrá más productos de concreto (f'c 175, 280...) | Hoy solo existe f'c 210. Condiciona si el rango debe ir en el producto o en la línea | Tu plan de catálogo (pregunta 3) |

> **Aviso sobre la volatilidad de los datos:** la base cambió **durante** este recon (órdenes
> 30 y 31 creadas a las 18:18 y 18:34 de hoy). Cualquier conteo de este informe es una foto
> del 2026-08-21 ~19:00. Los de `RECON_COMPLEMENTO.md` §3.4 ya están desactualizados.

---

## 6. DECISIONES PARA EL USUARIO

1. **★ Las "dos entradas 5-6 y 7-8": ¿dónde las viste?** No existen en la base. Las opciones que veo: (a) te refieres al catálogo **Huso TMN** (`3/4"` y `1/2"`), que está pegado al slump en el formulario pero es el tamaño del agregado; (b) las creaste en otra base de datos; (c) las tienes pensadas pero aún no creadas. La respuesta cambia por completo el prompt de implementación.

2. **★ ¿El rango de slump debe vivir en el PRODUCTO o en la LÍNEA?** Hoy vive en la línea y se teclea a mano. Dos caminos:
   - **En la línea** (donde está): mínimo cambio, y respeta el caso real de la orden 9, que tiene tres líneas del mismo producto con slumps 6, 6 y 7.
   - **En el producto**: implicaría crear productos tipo `Concreto FC 210 slump 5-6"` y `Concreto FC 210 slump 7-8"`. Encaja con lo de "dos entradas" — y explicaría por qué las recuerdas. Pero con un solo producto hoy y tres líneas de la misma orden con slumps distintos, **rompería un caso ya facturado**.

3. **Si el rango va al producto: ¿cuántos productos vas a tener?** Hoy hay **uno solo** (`Concreto FC 210`). Si multiplicas f'c × rango de slump, el catálogo crece rápido (3 resistencias × 3 rangos = 9 productos). ¿Prefieres eso, o productos por f'c con el rango en la línea?

4. **¿El slump debe autocompletarse al elegir el producto?** Hoy no lo hace nada. Si el rango pasa al producto, lo natural sería un `onchange` que lo copie a la línea — pero eso es una decisión de negocio (¿el vendedor puede sobrescribirlo?).

5. **La línea con slump `4.00`** (id 54, orden `2026-ECO-PS-0031`, creada hoy): está fuera del rango 5-8 del resto. ¿Es un valor válido o un error de captura? Importa porque define el mínimo del catálogo de rangos.

6. **El Huso TMN, ¿se queda como está?** Son dos entradas (`3/4"`, `1/2"`) y es obligatorio para Concreto. Si el slump pasa a rango, conviene decidir si ambos siguen siendo campos independientes o si van juntos en un "diseño de mezcla".

7. **★ El enlace de Maps.** Pégame uno real y en un minuto te digo si la resolución server-side es viable o hay que cambiar de enfoque. Es lo único que bloquea ese prompt.

---

## 7. Aceptación

```
$ git diff --name-only
(vacío)

$ git status --short
?? RECON_BIOCRETO.md
?? RECON_COMPLEMENTO.md
?? RECON_EXPRESS.md
?? custom_addons/LogoReq.svg
?? custom_addons/PruebaLaboratorio.svg
?? custom_addons/biocreto_fabricacion/
?? custom_addons/biocreto_laboratorio/
?? custom_addons/biocreto_requerimientos/
?? custom_addons/draw_planta.svg
?? custom_addons/icono_fabrica.svg
?? custom_addons/mixer_truck.svg
```

**Cero archivos modificados.** Ningún `-u` ni `-i`. Todas las consultas fueron `SELECT`.
