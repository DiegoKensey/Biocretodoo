# RECON COMPLEMENTARIO — cotización (bancos + RUC), slump y ubicación

> Complemento de `RECON_BIOCRETO.md`. **No repite** lo ya documentado allí: cubre solo los
> huecos que quedaron abiertos. Ejecutado el 2026-08-21 en **SOLO LECTURA**: ningún archivo
> del proyecto modificado, ningún `-u`/`-i`, todas las consultas a BD fueron `SELECT` sobre
> `Prueba` vía `psql`, y su salida está pegada literal. Único archivo creado: este.

---

## 1. Resumen ejecutivo

1. **El bloque bancario NO se imprime en todas las cotizaciones.** Vive dentro de `cot_body_mayor`, así que solo sale cuando `biocreto_tipo_proyecto == 'mayor'`. Las cotizaciones "menor envergadura" **no muestran cuentas**.
2. **"SOLES" está triplemente hardcodeado**: en el título de la banda, en cada `<td>` de moneda, y en el texto de Términos y Condiciones. **Nunca** se lee `bank.currency_id` — aunque las 4 cuentas sí tienen `currency_id = PEN` cargado.
3. **"CONCRETOS ECOLOGICOS" no existe en ninguna parte** — ni en código, ni en BD, ni en los mockups HTML. La compañía se llama **`Biocreto`**, y el bloque bancario **no imprime hoy ningún nombre de titular**. Ese literal habrá que introducirlo, no corregirlo.
4. **El RUC está limpio: `20605252401`**, 11 dígitos, sin prefijo `PE`, en `res_partner.vat` del partner de la compañía, con `l10n_latam_identification_type_id = 4` (RUC, `l10n_pe_vat_code = 6`). **No hay ningún método que lo formatee para impresión** y **el RUC no aparece hoy en el bloque bancario**.
5. **Slump — DESCONOCIDO #13 resuelto:** son **2 vistas distintas** (`ir.ui.view` 4032 sobre `sale.order` y 4033 sobre `sale.order.line`), cada una con un `biocreto_slump` y un `biocreto_slump_bombeable`. Y hay un hallazgo que corrige al recon anterior: el campo **sí es obligatorio condicionalmente** en ambas vistas (`required="biocreto_product_categ == 'Concreto'"`).
6. **Slump — impacto real de la migración:** 19 líneas con valor repartidas en 5 estados, y **4 de ellas ya facturadas** (`qty_invoiced > 0`). No es un campo virgen.
7. **La estructura administrativa peruana SÍ existe y está completa**: 25 departamentos, 196 provincias (`res.city`) y **1874 distritos** (`l10n_pe.res.city.district`), ya cableados en `sale.order` como `biocreto_state_id` / `biocreto_city_id` / `biocreto_district_id` con cascada de dominios y onchange. **No hay que construir nada.**
8. **La resolución de enlaces cortos es viable**: `requests 2.31.0` disponible, HTTPS saliente OK. Pero **no existe en el proyecto ni una sola llamada HTTP saliente** — no hay patrón previo de timeouts/errores/logging que copiar.

---

## 2. Módulo `biocreto_sale_report_cotizacion`

### 2.1 Anatomía

| Archivo | Tipo | Líneas | Qué define |
|---|---|---|---|
| `__manifest__.py` | Manifest | 28 | Depends, data, assets |
| `__init__.py` | Python | 1 | `from . import models` |
| `models/__init__.py` | Python | 2 | Importa los dos modelos |
| `models/ir_actions_report.py` | Python | 28 | Suscripción a PlutoPrint por `report_name` |
| `models/sale_order.py` | Python | 168 | Helpers de render: subtotales por sección, QR, contacto-persona, fechas Lima, vigencia |
| `report/paperformat.xml` | Data | 39 | Paperformat (no asignado a ninguna acción — el `@page` del CSS manda) |
| `report/report_cotizacion.xml` | QWeb | **981** | Todos los templates + la herencia del document nativo |
| `static/src/scss/report_cotizacion.scss` | SCSS | **797** | Estilos, incluida `table.cuentas-table` |

**`__manifest__.py` completo** (`custom_addons/biocreto_sale_report_cotizacion/__manifest__.py`):

```python
{
    'name': 'BIOCRETO - Reporte Cotizacion FR-09/FR-10',
    'version': '19.0.2.0.13',
    'category': 'Sales/Reports',
    'summary': 'Reporte QWeb de cotizacion BC-GC-FR-09/FR-10 con render PlutoPrint (running header/footer) suscrito a biocreto_pdf_engine; sobrescribe sale.report_saleorder_document via Opcion A para cubrir Imprimir/Correo/Portal.',
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'sale_stock',
        'biocreto_sale_extension',
        'biocreto_sig',
        'biocreto_base',
        'biocreto_pdf_engine',
    ],
    'data': [
        'report/paperformat.xml',
        'report/report_cotizacion.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'biocreto_sale_report_cotizacion/static/src/scss/report_cotizacion.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

> **Nota:** el SCSS va al bundle **`web.report_assets_common`**, que es el que
> `biocreto_pdf_engine._biocreto_inline_assets` inlinea antes de pasar el HTML a PlutoPrint.

### 2.2 El reporte

**No tiene acción propia.** El módulo **sobrescribe el template nativo** de la cotización,
así que la acción que se dispara es la de Odoo:

| Punto | Valor |
|---|---|
| `ir.actions.report` | **id 1176**, xmlid `sale.action_report_saleorder` — **nativa, no del módulo** |
| `report_name` | `sale.report_saleorder` |
| `report_type` | `qweb-pdf` |
| `attachment` | **NULL** |
| `attachment_use` | **NULL** → **no hay caché de PDF** |
| `paperformat_id` | **NULL** (el `report/paperformat.xml` define uno pero no se asigna) |
| `print_report_name` | `(object.state in ('draft','sent','contract','programado') and 'Cotización - %s' % (object.name)) or 'Orden - %s' % (object.name)` |

**¿Hereda o es propio?** — **Híbrido, y esto es clave para tocarlo.** El módulo hereda
`sale.report_saleorder_document` y **reemplaza todo su árbol**, sustituyendo la llamada a
`web.external_layout` por su propio diseño a sangre
(`report/report_cotizacion.xml:951-979`):

```xml
    <template id="report_cotizacion_document"
              inherit_id="sale.report_saleorder_document">
        <xpath expr="//t[@t-call='web.external_layout']" position="replace">
            <t t-set="o" t-value="doc"/>
            <t t-call="biocreto_sale_report_cotizacion.cot_layout">
                <t t-if="o.biocreto_tipo_proyecto == 'mayor'">
                    <t t-call="biocreto_sale_report_cotizacion.cot_body_mayor"/>
                </t>
                <t t-else="">
                    <t t-call="biocreto_sale_report_cotizacion.cot_body_menor"/>
                </t>
            </t>
        </xpath>
    </template>
```

El propio archivo documenta por qué el xpath es específico y no `expr="."`
(`:953-966`): en Odoo 19, `expr="."` con `position="replace"` sobre la raíz de un template
heredado **no reemplaza nada** y deja la plantilla nativa intacta.

**Árbol de templates** (`report_cotizacion.xml`):

```
report_cotizacion_document  (:951)   inherit_id = sale.report_saleorder_document
  └─ cot_layout             (:79)
       ├─ cot_body_mayor    (:817)   <- si biocreto_tipo_proyecto == 'mayor'
       │    ├─ cot_body_common   (:461)
       │    ├─ cot_firmas_block  (:707)
       │    ├─ info-grid 2x2      (:845-872)
       │    ├─ ★ CUENTAS BANCARIAS (:874-903)
       │    └─ Capacidad Operativa (:905-...)
       └─ cot_body_menor    (:780)   <- resto
            ├─ cot_body_common  (:781)
            └─ cot_firmas_block (:791)
```

> ### ★ Hallazgo que condiciona toda la implementación
>
> **El bloque de cuentas bancarias está DENTRO de `cot_body_mayor`.** `cot_body_menor`
> (`:780-816`) llama únicamente a `cot_body_common` y `cot_firmas_block`: **no incluye ni
> las cuentas ni la banda de capacidad operativa.**
>
> Es decir: **una cotización de "menor envergadura" NO imprime hoy ninguna cuenta bancaria.**
> Coincide con los mockups originales: `cotizacion_biocreto_mayor.html` tiene el bloque
> (línea 1268), y `cotizacion_biocreto_menor.html` tiene **cero** ocurrencias de
> "Cuentas Bancarias" (verificado con `grep -c`).
>
> **Antes de implementar hay que decidir si el bloque debe aparecer también en la menor**
> (pregunta 3 del §6).

**¿Vistas de Studio que lo pisen?** — **NO.** Los únicos herederos de
`sale.report_saleorder_document` (view id 1439) son:

```
  id  |                             k                              |             module              | priority | active
------+------------------------------------------------------------+---------------------------------+----------+--------
 1569 | sale_stock.report_saleorder_document_inherit_sale_stock    | sale_stock                      |       16 | f
 4090 | biocreto_sale_report_cotizacion.report_cotizacion_document | biocreto_sale_report_cotizacion |       16 | t
```

El de `sale_stock` está **desactivado** (`active = f`) — lo desactiva el propio módulo en
`report_cotizacion.xml:29`. Ningún registro de `studio_customization` hereda estos
templates ni los de la cotización (consulta ejecutada sobre `cot_body_mayor` y
`cot_body_common`: 0 filas).

### 2.3 ★ Bloque de cuentas bancarias

#### Fragmento completo — `report/report_cotizacion.xml:874-903`

```xml
        <!-- Banda: Cuentas Bancarias (dinamica desde company.bank_ids) -->
        <div class="info-band">
            <h3 class="info-band-title">Cuentas Bancarias · Soles</h3>
            <table class="cuentas-table">
                <thead>
                    <tr>
                        <th>Banco</th>
                        <th>Moneda</th>
                        <th>Cta. Corriente</th>
                        <th>CCI</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-set="bancos" t-value="o.company_id.bank_ids"/>
                    <t t-if="bancos">
                        <t t-foreach="bancos" t-as="bank">
                            <tr>
                                <td><span t-out="bank.bank_id.name or bank.bank_name or ''"/></td>
                                <td>Soles</td>
                                <td><span t-out="bank.acc_number or ''"/></td>
                                <td><span t-out="bank.biocreto_cci or ''"/></td>
                            </tr>
                        </t>
                    </t>
                    <t t-else="">
                        <tr><td colspan="4" class="empty-msg">Sin cuentas bancarias registradas.</td></tr>
                    </t>
                </tbody>
            </table>
        </div>
```

#### De dónde sale cada dato HOY

| Columna | Origen exacto | Tipo |
|---|---|---|
| Qué cuentas se listan | `o.company_id.bank_ids` → **todas** las `res.partner.bank` del partner de la compañía | Dinámico |
| **Banco** | `bank.bank_id.name` (modelo `res.bank`), con fallback a `bank.bank_name` | Dinámico |
| **Moneda** | El literal `Soles` escrito en el `<td>` | **HARDCODEADO** |
| **Cta. Corriente** | `bank.acc_number` | Dinámico |
| **CCI** | `bank.biocreto_cci` — campo propio (`biocreto_base/models/res_partner_bank.py:7-10`) | Dinámico |
| Título de la banda | `Cuentas Bancarias · Soles` | **HARDCODEADO** |
| Fallback sin cuentas | `Sin cuentas bancarias registradas.` con `colspan="4"` | Estático |

#### La palabra "SOLES": **literal hardcodeado, en TRES sitios**

**No** se usa `bank.currency_id.name` en ningún punto. Las tres apariciones:

| Archivo:línea | Texto |
|---|---|
| `report_cotizacion.xml:876` | `<h3 class="info-band-title">Cuentas Bancarias · Soles</h3>` |
| `report_cotizacion.xml:892` | `<td>Soles</td>` — **dentro del `t-foreach`**, se repite por cada cuenta |
| `report_cotizacion.xml:845` | `<li>Moneda y pago: Soles (S/) — 50% anticipo y saldo contra entrega</li>` (Términos y Condiciones, otro bloque) |

> Las 4 cuentas de la base **sí tienen** `currency_id = 156 (PEN)` cargado, así que pasar a
> `bank.currency_id.name` es viable sin tocar datos. Ver pregunta 5 del §6.

#### El nombre "CONCRETOS ECOLOGICOS": **NO EXISTE**

Búsqueda exhaustiva, resultado literal:

```
$ grep -rni "CONCRETOS\|ECOLOGICOS\|ECOLÓGICOS" custom_addons/ --include=*.xml --include=*.py --include=*.js --include=*.html
custom_addons/biocreto_laboratorio/models/probeta.py:151:  concretos = line.order_id.order_line.filtered(   <- variable Python, no relacionado
custom_addons/biocreto_laboratorio/models/probeta.py:154:  for idx, l in enumerate(concretos, start=1):    <- idem
custom_addons/contrato_biocreto.html:1865:  CONCRETOS F'C PERÚ S.A.C.<br>                       <- mockup, y dice "F'C PERÚ", no "ECOLOGICOS"
```

```sql
SELECT id, name, complete_name FROM res_partner
WHERE name ILIKE '%concreto%' OR name ILIKE '%ecolog%';
```
```
 id | name | complete_name
----+------+---------------
(0 filas)
```

**Conclusión sin rodeos:**

- La compañía se llama **`Biocreto`** (`res_company.id = 1`, partner 1).
- **El bloque bancario NO imprime hoy NINGÚN nombre de titular.** No hay `bank.partner_id.name`, ni `o.company_id.name`, ni `bank.acc_holder_name` en el fragmento. Solo Banco / Moneda / Cuenta / CCI.
- El campo `acc_holder_name` **sí existe y está poblado** con `Biocreto` en las 3 cuentas propias (§2.5) — pero **no se usa en el reporte**.
- `DESCONOCIDO — no pude verificar de dónde sale "CONCRETOS ECOLOGICOS" porque el literal no aparece en el código, ni en la base de datos, ni en los mockups HTML.` Probablemente es la **razón social real** que hay que **añadir**, no un dato existente que haya que corregir. Ver pregunta 1 del §6.

#### Separador visual y estructura HTML

**El separador del título es `·` (U+00B7, MIDDLE DOT)**, escrito literal en el XML entre
"Cuentas Bancarias" y "Soles" (`:876`). Es el mismo separador que usa el consolidado de
requerimientos y el resto de reportes BIOCRETO.

**Estructura para insertar dos datos más sin romper el layout:**

```
div.info-band                       <- caja gris, borde izq. azul 3px
 ├─ h3.info-band-title              <- "Cuentas Bancarias · Soles"
 └─ table.cuentas-table             <- width:100%, border-collapse:collapse, 8.5pt
      ├─ thead > tr > th × 4        <- fondo #58595b, texto blanco, CENTRADO, 8pt, UPPERCASE
      └─ tbody > tr > td × 4        <- borde #d4d4d4, fondo blanco, CENTRADO
           └─ td:first-child        <- IZQUIERDA, font-weight 600, color #58595b
```

SCSS relevante (`static/src/scss/report_cotizacion.scss:687-743`):

```scss
.biocreto-cot .info-band {
    margin: 0 0 8pt 0;
    border: 1px solid #d4d4d4;
    border-left: 3px solid #1ea8e0;
    background: #fafafa;
    padding: 9pt 12pt;
}
.biocreto-cot .info-band-title {
    margin: 0 0 6pt 0;
    font-size: 9pt;  font-weight: bold;  color: #58595b;
    text-transform: uppercase;  letter-spacing: 0.5px;
    padding-bottom: 4pt;  border-bottom: 1px solid #d4d4d4;
}
.biocreto-cot table.cuentas-table {
    width: 100%;  border-collapse: collapse;  font-size: 8.5pt;  margin-top: 2pt;

    thead th {
        background: #58595b;  color: #ffffff;  padding: 4pt 6pt;
        font-weight: bold;  text-align: center;  font-size: 8pt;
        letter-spacing: 0.3px;  font-family: inherit;  text-transform: uppercase;
        border-bottom: 3px solid #1ea8e0;
    }
    tbody td {
        border: 1px solid #d4d4d4;  padding: 4pt 6pt;  font-family: inherit;
        text-align: center;  background: #ffffff;  vertical-align: middle;
    }
    tbody td:first-child {
        text-align: left;  font-weight: 600;  color: #58595b;
    }
    tbody td.empty-msg {
        text-align: center;  color: #999;  font-style: italic;  padding: 10pt;
    }
}
```

> **Tres cosas que hay que respetar al añadir columnas:**
>
> 1. **El `colspan="4"` de la fila vacía** (`:899`) hay que actualizarlo al nuevo número de columnas, o el mensaje "Sin cuentas bancarias registradas" quedará desalineado.
> 2. **Las anchuras son automáticas** (`width: 100%` sin `<colgroup>` ni `width` por celda). Añadir columnas comprime el resto proporcionalmente. Con 6 columnas a 8.5pt en A4 el CCI (24 caracteres con espacios) es el candidato a partirse.
> 3. **`break-inside: avoid` en `.pagina-2`.** El propio autor avisa en `report_cotizacion.xml:822-826`: *"Si con muchas cuentas bancarias el bloque deja de caber en una A4, hay que relajar `break-inside: avoid`. Por ahora confiamos en que cabe (max 4 cuentas)."* Hoy hay **3** cuentas imprimiéndose. Añadir columnas no aumenta filas, pero sí altura si algún valor hace *wrap*.

#### ¿Está duplicado en el contrato?

**Sí, pero NO son idénticos carácter por carácter.** El otro está en
`biocreto_sale_reports_contrato/report/report_contrato.xml:681-710`, dentro de la cláusula 4.4.

| Aspecto | Cotización `:874-903` | Contrato `:681-710` |
|---|---|---|
| Contenedor | `<div class="info-band">` | `<li>` + `<span class="text">` dentro de un `<ol>` |
| Título | `<h3 class="info-band-title">Cuentas Bancarias · Soles</h3>` | Frase corrida: *"Los pagos pueden realizarse directamente en nuestras cuentas corrientes siguientes:"* |
| Clase de la tabla | `cuentas-table` | `cuentas-table` (misma) |
| `<thead>` | Banco / Moneda / Cta. Corriente / CCI | **Idéntico** |
| `<tbody>` | `t-set bancos` + `t-foreach` + `t-else` | **Idéntico carácter por carácter** |
| Indentación | Base 8 espacios | Base 28 espacios |

> **El `<tbody>` sí es idéntico; el envoltorio no.** Un cambio de columnas hay que aplicarlo
> en **los dos** archivos. Ver pregunta 4 del §6 sobre factorizarlo.

### 2.4 ★ RUC de la empresa

#### Localización peruana instalada

```sql
SELECT name, state, latest_version FROM ir_module_module
WHERE name LIKE 'l10n_%' AND state='installed' ORDER BY name;
```
```
            name             |   state   | latest_version
-----------------------------+-----------+----------------
 l10n_latam_base             | installed | 19.0.1.0
 l10n_latam_invoice_document | installed | 19.0.1.0
 l10n_pe                     | installed | 19.0.3.1
 l10n_pe_edi                 | installed | 19.0.0.1
 l10n_pe_reports             | installed | 19.0.1.0
```

**5 módulos de localización instalados**, incluida la facturación electrónica (`l10n_pe_edi`).

#### Campo exacto donde vive el RUC

**`res_partner.vat`**, en el partner asociado a la compañía. **No hay campo propio de RUC.**
El *tipo* de documento va aparte, en `res_partner.l10n_latam_identification_type_id`.

#### Dump — `res.company` y su `res.partner` (es el mismo registro id 1)

```sql
SELECT c.id AS company_id, p.id AS partner_id, p.name, p.vat, length(p.vat) AS len_vat,
       p.l10n_latam_identification_type_id AS tipo_id, t.name AS tipo_nombre, t.l10n_pe_vat_code,
       p.country_id, co.code AS pais, c.currency_id, cur.name AS moneda, c.plant_code
FROM res_company c
JOIN res_partner p ON p.id = c.partner_id
LEFT JOIN l10n_latam_identification_type t ON t.id = p.l10n_latam_identification_type_id
LEFT JOIN res_country co ON co.id = p.country_id
LEFT JOIN res_currency cur ON cur.id = c.currency_id;
```
```
 company_id | partner_id |   name   |     vat     | len_vat | tipo_id |           tipo_nombre            | l10n_pe_vat_code | country_id | pais | currency_id | moneda | plant_code
------------+------------+----------+-------------+---------+---------+----------------------------------+------------------+------------+------+-------------+--------+------------
          1 |          1 | Biocreto | 20605252401 |      11 |       4 | {"en_US": "RUC", "es_PE": "RUC"} |                6 |        173 | PE   |         156 | PEN    | ECO
```

> **Una sola compañía.** `res.company.partner_id = 1` y `res.partner.id = 1` son el mismo
> registro, así que `o.company_id.vat` y `o.company_id.partner_id.vat` devuelven lo mismo.

#### ¿El valor tiene prefijo?

**NO. Es el RUC limpio de 11 dígitos:**

```
vat = 20605252401      (len_vat = 11)
```

Sin `PE`, sin guiones, sin espacios. El tipo de documento se identifica por el
`l10n_latam_identification_type_id = 4` → **RUC**, con `l10n_pe_vat_code = 6` (el código
SUNAT del RUC). **Se puede imprimir tal cual, sin limpieza previa.**

#### ¿Existe algún formateador de RUC?

**NO.** Búsqueda en todos los módulos `biocreto_*`:

```
$ grep -rn "\bvat\b\|\bruc\b\|RUC" custom_addons/ --include=*.py --include=*.xml
```

Los únicos resultados relevantes:

| Archivo:línea | Qué hace |
|---|---|
| `biocreto_base/models/res_partner.py:10` | *"Autoseleccionar DNI o RUC según `is_company` cuando el país es Perú"* — **selecciona el tipo**, no formatea el número |
| `biocreto_base/__manifest__.py:6` | Documenta *"validacion de longitud DNI(8)/RUC(11)"* |
| `biocreto_compras_reporte/models/purchase_order.py:125` | Comentario: *"nombre / RUC / direccion DE LA EMPRESA"* |

**No hay ningún método `biocreto_*_ruc()`, ni campo computado de RUC formateado, ni
helper de impresión.** Si se quiere imprimir como `RUC 20605252401` o `20605252401`, el
literal va en el QWeb.

#### ¿Dónde se imprime el RUC HOY?

`DESCONOCIDO parcialmente — no pude verificar el render de la cabecera porque el layout
`cot_layout` (`:79-460`) es extenso y no lo recorrí entero en este recon.` Lo que **sí**
está verificado:

- **El bloque bancario NO imprime el RUC.** Las 4 columnas son Banco / Moneda / Cuenta / CCI (§2.3).
- El reporte de compras sí lo maneja (`biocreto_compras_reporte/models/purchase_order.py:125`), pero es otro módulo.

Consulta lista para confirmar dónde aparece, si hace falta:

```sql
SELECT id, key FROM ir_ui_view
WHERE key LIKE 'biocreto_sale_report_cotizacion%'
  AND (arch_db::text LIKE '%vat%' OR arch_db::text LIKE '%RUC%');
```

### 2.5 Cuentas cargadas

```sql
SELECT b.id, b.acc_number, b.acc_holder_name, b.biocreto_cci, b.bank_id, rb.name AS banco,
       b.partner_id, p.name AS titular, b.currency_id, c.name AS moneda,
       b.company_id, b.sequence, b.active
FROM res_partner_bank b
LEFT JOIN res_bank rb ON rb.id = b.bank_id
LEFT JOIN res_partner p ON p.id = b.partner_id
LEFT JOIN res_currency c ON c.id = b.currency_id
ORDER BY b.sequence, b.id;
```
```
 id |     acc_number      | acc_holder_name |       biocreto_cci       | bank_id |             banco              | partner_id | titular  | currency_id | moneda | company_id | sequence | active
----+---------------------+-----------------+--------------------------+---------+--------------------------------+------------+----------+-------------+--------+------------+----------+--------
  1 | 355 5028342 0 90    | Biocreto        | 002 355 005028342090  64 |      20 | Banco de Crédito del  Perú BCP |          1 | Biocreto |         156 | PEN    |     (NULL) |       10 | t
  2 | 0011 02370100045620 | Biocreto        | 011 237 00010004562050   |      21 | Banco Continental  BBVA        |          1 | Biocreto |         156 | PEN    |     (NULL) |       10 | t
  3 | 0004455922          | Biocreto        | 009 423 000004455922 57  |      22 | Scotiabank  Perú               |          1 | Biocreto |         156 | PEN    |     (NULL) |       10 | t
  4 | 194-1234567-0-00    | UNACEM          | 002-194-001234567000-95  |      20 | Banco de Crédito del  Perú BCP |         18 | UNACEM   |         156 | PEN    |     (NULL) |       10 | t
```

**Cuántas se imprimen y en qué orden:**

- **Se imprimen 3** — las de `partner_id = 1` (Biocreto). La 4ª es de UNACEM (proveedor, partner 18) y **no** entra: el `t-foreach` recorre `o.company_id.bank_ids`, que filtra por el partner de la compañía.
- **El orden es indefinido en la práctica.** `sequence = 10` en las cuatro, empatadas. El `_order` de `res.partner.bank` es `sequence, id`, así que el desempate lo da el `id`: **BCP (1) → BBVA (2) → Scotiabank (3)**. Coincide con el mockup, pero **por coincidencia, no por configuración**: basta editar y volver a crear una cuenta para que cambie el orden. Si el orden importa, hay que poner `sequence` distintos.

**Datos a tener presentes:**

- **`acc_holder_name` está poblado** con `Biocreto` en las tres propias — es el candidato natural si se quiere imprimir el titular por cuenta, en vez de un literal.
- **`company_id` es NULL en las cuatro** — cuentas no asignadas a compañía. Con una sola compañía da igual, pero rompería en multiempresa.
- **Los nombres de banco traen dobles espacios**: `Banco de Crédito del␣␣Perú BCP`, `Banco Continental␣␣BBVA`, `Scotiabank␣␣Perú`. Se imprimen tal cual, con el doble espacio visible en el PDF. **Es un defecto de datos, no de código** — se corrige editando `res.bank`.
- **`currency_id = PEN` en las cuatro** → cambiar el literal "Soles" por `bank.currency_id.name` es viable sin tocar datos (imprimiría `PEN`, no `Soles`; ver pregunta 5).

---

## 3. Slump: huecos resueltos

### 3.1 DESCONOCIDO #13 — resuelto: son **2 vistas distintas**

```sql
SELECT v.id, d.module||'.'||d.name AS xmlid, v.model, v.type, v.inherit_id, v.priority, v.mode, v.active
FROM ir_ui_view v LEFT JOIN ir_model_data d ON d.res_id=v.id AND d.model='ir.ui.view'
WHERE v.id IN (4032,4033,4045,4046,4178);
```
```
  id  |                                     xmlid                                      |      model      | type | inherit_id | priority |   mode    | active
------+--------------------------------------------------------------------------------+-----------------+------+------------+----------+-----------+--------
 4032 | biocreto_sale_extension.view_order_form_biocreto                               | sale.order      | form |       1469 |       16 | extension | t
 4033 | biocreto_sale_extension.sale_order_line_view_form_biocreto                     | sale.order.line | form |     (NULL) |       99 | primary   | t
 4045 | biocreto_sale_contract_state.view_order_form_biocreto_contract                 | sale.order      | form |       1469 |       16 | extension | t
 4046 | studio_customization.odoo_studio_sale_ord_64de15cb-faad-4dc4-acf4-df0cac9dd835 | sale.order      | form |       1469 |      160 | extension | t
 4178 | biocreto_laboratorio.view_order_form_biocreto_lab_buttons                      | sale.order      | form |       1469 |       16 | extension | t
```

**Veredicto: 2 vistas, cada una con UNA aparición de cada campo. Ninguna duplicación real.**

| Vista | id | Modelo | inherit_id | priority | mode | Líneas del `.xml` | Slump |
|---|---|---|---|---|---|---|---|
| `view_order_form_biocreto` | **4032** | `sale.order` | 1469 (`sale.view_order_form`) | 16 | extension | 12-302 | `:223` y `:251` |
| `sale_order_line_view_form_biocreto` | **4033** | `sale.order.line` | **ninguno** | **99** | **primary** | 303-389 | `:355` y `:378` |

**Vista 4032** — pestaña "Información de Suministro" del formulario de la orden, editor
embebido de la línea (`custom_addons/biocreto_sale_extension/views/sale_order_views.xml:221-225`):

```xml
                    <group>
                        <field name="biocreto_huso_tmn"
                               required="biocreto_product_categ == 'Concreto'"/>
                        <field name="biocreto_slump"
                               required="biocreto_product_categ == 'Concreto'"/>
                    </group>
```

y (`:246-252`):

```xml
                <group string="Especificaciones técnicas — Bombeo"
                       name="biocreto_bombeo_group"
                       invisible="biocreto_product_categ != 'Bombeo'">
                    <group>
                        <field name="biocreto_vehiculo_id"
                               domain="biocreto_vehiculo_domain"/>
                        <field name="biocreto_tuberia_adicional"/>
                        <field name="biocreto_slump_bombeable"/>
                    </group>
```

**Vista 4033** — formulario **suelto** (`primary`, sin `inherit_id`, `priority=99`) que
Odoo usa como **modal/popup** al abrir una línea (`:352-357`):

```xml
                    <group>
                        <field name="biocreto_huso_tmn"
                               required="biocreto_product_categ == 'Concreto'"/>
                        <field name="biocreto_slump"
                               required="biocreto_product_categ == 'Concreto'"/>
                    </group>
```

y (`:373-379`), idéntico salvo el `name` del grupo (`biocreto_bombeo_group_form` en vez de
`biocreto_bombeo_group`).

> **Consecuencia práctica:** al migrar a rango hay que tocar **los dos bloques, en los dos
> archivos-vista**, y con **nombres de grupo distintos** (`_group` vs `_group_form`) para
> que los xpath no se confundan. Son 4 puntos de edición, no 2.

### 3.2 Los campos Float — corrección al recon anterior

#### `sale.order.line.biocreto_slump`

```python
# custom_addons/biocreto_sale_extension/models/sale_order_line.py:41-44
    biocreto_slump = fields.Float(
        string="Slump (pulg.)",
        digits=(5, 2),
    )
```

| Atributo | Valor |
|---|---|
| Modelo | `sale.order.line` |
| Tipo ORM | `float`, `digits=(5, 2)` |
| `string` | `"Slump (pulg.)"` |
| `help` | **ninguno** |
| `required` en el **modelo** | **NO** — `ir_model_fields.required = f` |
| `required` en la **vista** | **SÍ, condicional** — `required="biocreto_product_categ == 'Concreto'"` en **ambas** vistas (4032 `:224`, 4033 `:356`) |
| `default` | **ninguno** |
| Studio o código | **Código** |

> **Esto corrige el recon anterior**, que dijo *"required: No"*. Es cierto a nivel de modelo,
> pero **a nivel de vista el campo es obligatorio siempre que la categoría sea Concreto**.
> Al migrar a rango hay que decidir a cuál de los dos campos nuevos se traslada ese
> `required` condicional (pregunta 8 del §6).

#### `sale.order.line.biocreto_slump_bombeable`

```python
# custom_addons/biocreto_sale_extension/models/sale_order_line.py:58-61
    biocreto_slump_bombeable = fields.Float(
        string="Slump bombeable (pulg.)",
        digits=(5, 2),
    )
```

Mismos atributos, **pero SIN `required`** ni en modelo ni en vista. Vive en el grupo de
BOMBEO, oculto salvo `biocreto_product_categ == 'Bombeo'`.

#### ¿Hay `@api.constrains`?

**NO.** No existe ningún `@api.constrains` sobre slump en todo el proyecto. La única
validación es **al confirmar**, en un helper llamado explícitamente:

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:362-366 (fragmento)
                    if not line.biocreto_slump:
                        faltantes.append("Slump")
```

Dentro de `_biocreto_validate_before_confirm`, cuyo comentario de diseño
(`sale_order.py:322-330`) explica por qué **no** es un `constrains`:

```
    # No usa @api.constrains a propósito: causaría un bucle al impedir
    # guardar la cotización en borrador para abrir el popup de la línea.
```

> **Ojo con el test `if not line.biocreto_slump`:** en Python, `0.0` es falsy. Un slump de
> cero se trata como "no informado". Al pasar a rango, si el mínimo pudiera ser 0, este
> test cambia de significado.

### 3.3 El modelo de ensayo `biocreto.slump`

Definición completa — `custom_addons/biocreto_laboratorio/models/slump.py:1-44`:

```python
from odoo import _, api, fields, models


class BiocretoSlump(models.Model):
    _name = 'biocreto.slump'
    _description = 'Ensayo de slump (BIOCRETO)'
    _order = 'fecha desc, id desc'

    name = fields.Char(readonly=True, copy=False, index=True)
    sale_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string="Línea de venta",
        required=True,
        ondelete='cascade',
        index=True,
    )
    sale_id = fields.Many2one(
        related='sale_line_id.order_id', store=True, string="Orden", index=True,
    )
    partner_id = fields.Many2one(
        related='sale_id.partner_id', store=True, string="Cliente",
    )
    mixer_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Mixer",
        help="Mixer manualmente asociado al ensayo. Fabricacion lo automatizara mas adelante.",
    )
    tipo = fields.Selection([
        ('planta', 'Planta'),
        ('obra', 'Obra'),
    ], required=True, default='planta', string="Tipo")
    valor = fields.Float(string="Slump (pulg.)", digits=(5, 2))
    fecha = fields.Datetime(default=fields.Datetime.now, string="Fecha")
    observaciones = fields.Text()
    company_id = fields.Many2one(
        related='sale_id.company_id', store=True, string="Compañía",
    )
```

Más el naming automático (`slump.py:53-91`), con patrón
`L{pos}-{correlativo}-{fc}-M{n}-SLP0{1|2}`, donde `SLP01 = planta` y `SLP02 = obra`.

**¿Valor MEDIDO o PEDIDO?** — **MEDIDO.** Evidencia:

1. El `_description` es literalmente *"Ensayo de slump"* (`:6`).
2. El campo `tipo` distingue **dónde se tomó la medida**: `planta` u `obra` (`:33-36`).
3. Tiene `mixer_id` (`fleet.vehicle`) — se mide **por mixer**, no por pedido (`:28-32`).
4. Tiene `fecha` con `default=now` y `observaciones` — bitácora de laboratorio (`:38-39`).
5. Vive en `biocreto_laboratorio`, cuyo manifest declara *"ensayos de slump por mixer"* (`__manifest__.py:6`).

**¿Relación con `sale.order.line`?** — **SÍ, Many2one directo:**

```python
    sale_line_id = fields.Many2one('sale.order.line', string="Línea de venta",
        required=True, ondelete='cascade', index=True)
```

**No hay One2many inverso** en `sale.order.line`. Del lado de la orden solo existe un
contador computado por `search_count` (`biocreto_laboratorio/models/sale_order.py:26-28`).

> **Lectura para el diseño del rango:** son dos cosas distintas y no deben confundirse.
> `sale.order.line.biocreto_slump` = **lo que el cliente PIDE** (candidato natural a rango
> "6–8 pulgadas"). `biocreto.slump.valor` = **lo que el laboratorio MIDE** (un ensayo
> concreto da un número, no un rango). Lo natural sería que el rango viva solo en la línea
> de venta y que el ensayo siga siendo un valor único que se **compara** contra ese rango.
> Ver pregunta 7 del §6.

### 3.4 Verificación de impacto

**Conteo global** (ya establecido en el recon anterior, revalidado):

| Campo | Con valor | Total líneas | Valores distintos |
|---|---|---|---|
| `sale_order_line.biocreto_slump` | **16** | 33 | 4 → `5.00` ×1, `6.00` ×13, `7.00` ×1, `8.00` ×1 |
| `sale_order_line.biocreto_slump_bombeable` | **8** | 33 | 1 → `6.00` ×8 |
| `biocreto_slump.valor` (ensayos) | **0** | **0** | — (tabla vacía) |

**Distribución por estado de la orden — dato nuevo:**

```sql
SELECT so.state,
       count(*) FILTER (WHERE l.biocreto_slump IS NOT NULL AND l.biocreto_slump<>0) AS con_slump,
       count(*) FILTER (WHERE l.biocreto_slump_bombeable IS NOT NULL AND l.biocreto_slump_bombeable<>0) AS con_bombeable,
       count(*) AS lineas
FROM sale_order_line l JOIN sale_order so ON so.id = l.order_id
GROUP BY so.state ORDER BY so.state;
```
```
   state    | con_slump | con_bombeable | lineas
------------+-----------+---------------+--------
 contract   |         6 |             1 |     13
 draft      |         1 |             1 |      3
 programado |         1 |             1 |      2
 sale       |        11 |             5 |     17
 sent       |         0 |             0 |      1
```

**Líneas ya facturadas:**

```sql
SELECT count(*) FILTER (WHERE l.qty_invoiced > 0) AS lineas_facturadas_con_slump
FROM sale_order_line l WHERE l.biocreto_slump IS NOT NULL AND l.biocreto_slump <> 0;
```
```
 lineas_facturadas_con_slump
-----------------------------
                           4
```

> **Lo que esto significa para la migración, sin adornos:**
>
> - **19 líneas con valor** (16 slump + 8 bombeable, con solape), repartidas en **5 estados**.
> - **4 líneas ya facturadas.** Un contrato firmado y una factura emitida dicen `Slump 6"`.
>   Si el reporte pasa a imprimir `6" – 8"`, **un documento reimpreso dejará de coincidir con
>   el que se firmó**. La migración `min = max = valor` mantiene la equivalencia numérica,
>   pero el **formato impreso** cambia igualmente si no se contempla el caso `min == max`.
> - **6 líneas en órdenes en estado `contract`** — contratos vivos, sin facturar todavía.
> - La tabla de ensayos está **vacía**: ahí no hay nada que migrar.

---

## 4. Ubicación: huecos resueltos

### 4.1 Campos actuales de latitud/longitud

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:62-72
    biocreto_latitud = fields.Float(
        string="Latitud",
        digits=(10, 7),
        help="Latitud de la obra en grados decimales. Ej.: -12.0653000",
    )
    biocreto_longitud = fields.Float(
        string="Longitud",
        digits=(10, 7),
        help="Longitud de la obra en grados decimales. Ej.: -75.2049000",
    )
```

Confirmado contra el ORM:

```
   model    |       name        |    label     | ttype | required | store
------------+-------------------+--------------+-------+----------+-------
 sale.order | biocreto_latitud  | Latitud      | float | f        | t
 sale.order | biocreto_longitud | Longitud     | float | f        | t
```

| Atributo | Valor |
|---|---|
| Modelo | `sale.order` |
| Tipo | `Float`, `digits=(10, 7)` → 7 decimales ≈ **1 cm** |
| `required` | **No** |
| `default` | **ninguno** |
| Studio o código | **Código** |
| Columna en BD | `numeric` |

#### DÓNDE insertar el campo nuevo

**Bloque exacto**, `custom_addons/biocreto_sale_extension/views/sale_order_views.xml:20-73`.
El punto de inserción natural para un campo "pegar enlace de Maps" está marcado con `<<<`:

```xml
            <xpath expr="//page[@name='order_lines']" position="after">
                <page name="biocreto_supply_info"
                      string="Información de Suministro">
                    <group string="DATOS DE OBRA" name="biocreto_obra_group">
                        <group>
                            <label for="biocreto_street" string="Dirección"/>
                            <div class="o_address_format">
                                <field name="biocreto_street"
                                       placeholder="Calle / Av. / Jr. y número..."
                                       class="o_address_street"/>
                                <field name="biocreto_district_id"
                                       placeholder="Distrito"
                                       class="o_address_city"
                                       options="{'no_open': True, 'no_create': True}"/>
                                <field name="biocreto_city_id"
                                       placeholder="Provincia"
                                       class="o_address_city"
                                       options="{'no_open': True, 'no_create': True}"/>
                                <field name="biocreto_state_id"
                                       placeholder="Departamento"
                                       class="o_address_state"
                                       options="{'no_open': True, 'no_create': True}"/>
                            </div>
                            <label for="biocreto_latitud" string="Geolocalización (obra)"/>
                            <div>
                                <span>Lat:&#160;</span>
                                <field name="biocreto_latitud" nolabel="1" class="oe_inline"/>
                                <br/>
                                <span>Long:&#160;</span>
                                <field name="biocreto_longitud" nolabel="1" class="oe_inline"/>
                                <br/>
                                <field name="biocreto_latitud"
                                       widget="biocreto_geo_field"
                                       options="{'lng_field': 'biocreto_longitud'}"
                                       nolabel="1"
                                       class="oe_inline"/>
                            </div>
                            <!-- <<< AQUI iria el campo nuevo de enlace -->
                            <field name="biocreto_tipo_proyecto"/>
                        </group>
                        <group/>
                    </group>
```

> **Trampa ya documentada, revalidada:** `biocreto_latitud` aparece **DOS veces** en el mismo
> `<div>` (input normal + botón). Un xpath simple sobre `//field[@name='biocreto_latitud']`
> **falla por ambigüedad**. `biocreto_sale_contract_state/views/sale_order_views.xml:147-153`
> ya lo resuelve discriminando por widget:
> `//field[@name='biocreto_latitud'][not(@widget)]` y `[@widget='biocreto_geo_field']`.

**Cascada de dominios y limpieza** — ya implementada
(`biocreto_sale_extension/models/sale_order.py:14-32` y `:236-248`):

```python
    biocreto_state_id = fields.Many2one('res.country.state', string="Departamento",
        domain="[('country_id.code', '=', 'PE')]")
    biocreto_city_id = fields.Many2one('res.city', string="Provincia",
        domain="[('state_id', '=', biocreto_state_id)]")
    biocreto_district_id = fields.Many2one('l10n_pe.res.city.district', string="Distrito",
        domain="[('city_id', '=', biocreto_city_id)]")
    ...
    @api.onchange('biocreto_state_id')
    def _onchange_biocreto_state_id(self):
        if self.biocreto_city_id and self.biocreto_city_id.state_id != self.biocreto_state_id:
            self.biocreto_city_id = False
            self.biocreto_district_id = False

    @api.onchange('biocreto_city_id')
    def _onchange_biocreto_city_id(self):
        if self.biocreto_district_id and self.biocreto_district_id.city_id != self.biocreto_city_id:
            self.biocreto_district_id = False
```

Y la concatenación que consume el reporte y el mapa
(`sale_order.py:208-233`), con el orden **"calle - distrito, provincia, depto"**:

```python
    @api.depends('biocreto_street', 'biocreto_district_id',
                 'biocreto_city_id', 'biocreto_state_id')
    def _compute_biocreto_direccion_completa(self):
        for order in self:
            partes_zona = []
            if order.biocreto_district_id:
                partes_zona.append(order.biocreto_district_id.name)
            if order.biocreto_city_id:
                partes_zona.append(order.biocreto_city_id.name)
            if order.biocreto_state_id:
                partes_zona.append(order.biocreto_state_id.name)
            zona = ", ".join(partes_zona)
            calle = order.biocreto_street or ""
            if calle and zona:
                order.biocreto_direccion_completa = "%s - %s" % (calle, zona)
            else:
                order.biocreto_direccion_completa = calle or zona or False
```

> **Punto de integración clave:** si un enlace de Maps rellena `biocreto_street` /
> distrito / provincia / departamento, `biocreto_direccion_completa` **se recalcula solo**
> por el `@api.depends`, y con ella la `biocreto_gmaps_url`. No hay que tocar nada más.

### 4.2 El botón "jalar mi ubicación"

Código completo ya pegado en `RECON_BIOCRETO.md` §E2 — **no lo repito**. Resumen operativo:

| Punto | Valor |
|---|---|
| Archivos | `biocreto_sale_extension/static/src/components/geo_button/geo_button.js` (102 líneas) y `.xml` (20) |
| Registro | `registry.category("fields").add("biocreto_geo_field", ...)` (`geo_button.js:102`) |
| Escribe en | `this.props.name` (la latitud a la que se ancla) y `options.lng_field` (por defecto `"biocreto_longitud"`), en una sola llamada `this.props.record.update({...})` (`geo_button.js:67-71`) |
| **Qué valida** | 3 cosas: (1) que exista `navigator.geolocation`, si no → notificación `warning` y aborta (`:46-52`); (2) `isNaN(lat) \|\| isNaN(lng)`; (3) `Math.abs(lat) > 90 \|\| Math.abs(lng) > 180` → notificación `danger` *"Coordenadas fuera de rango. No se guardaron."* y **aborta sin escribir** (`:57-66`) |
| Precisión | `toFixed(7)` — trunca a 7 decimales antes de escribir (`:55-56`) |
| Opciones GPS | `{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }` (`:79`) |
| Controller | **NINGUNO.** Todo cliente; persiste con el `write` normal del formulario |
| Error del GPS | Callback de fallo → notificación `warning` *"No se pudo obtener la ubicación. Ingrese las coordenadas manualmente."* (`:73-78`) |

> **No valida `(0,0)`.** Ese caso lo filtra después el compute de la URL
> (`sale_order.py:157-158`), que trata el Golfo de Guinea como ausencia.

### 4.3 ★ Departamento / provincia / distrito — **VEREDICTO: SÍ EXISTE Y ESTÁ COMPLETA**

#### ¿Existen campos HOY?

**SÍ, en los dos modelos.** Confirmado contra `ir_model_fields`:

```
    model    |         name         |       label       |  ttype   |         relation          | required | store
-------------+----------------------+-------------------+----------+---------------------------+----------+-------
 res.partner | city_id              | City ID           | many2one | res.city                  | f        | t
 res.partner | l10n_pe_district     | District          | many2one | l10n_pe.res.city.district | f        | t
 res.partner | state_id             | State             | many2one | res.country.state         | f        | t
 sale.order  | biocreto_city_id     | Provincia         | many2one | res.city                  | f        | t
 sale.order  | biocreto_district_id | Distrito          | many2one | l10n_pe.res.city.district | f        | t
 sale.order  | biocreto_state_id    | Departamento      | many2one | res.country.state         | f        | t
 sale.order  | biocreto_street      | Calle / Dirección | char     |                           | f        | t
```

**Todos son Many2one, ninguno es Char.** Y `res.partner` ya trae `l10n_pe_district` de la
localización — o sea, **`sale.order` replica en `biocreto_*` la misma estructura que
`res.partner` tiene de fábrica**, apuntando a los mismos modelos.

#### ¿Existen los modelos de la localización?

```sql
SELECT model, name FROM ir_model
WHERE model ILIKE '%city%' OR model ILIKE '%district%' OR model ILIKE '%distrito%' OR model ILIKE '%state%';
```

Filtrando el ruido (`account.bank.statement`, `fleet.vehicle.state`, capacidades):

```
 l10n_pe.res.city.district | {"en_US": "District", "es_PE": "Distrito"}
 res.city                  | {"en_US": "City",     "es_PE": "Ciudad"}
 res.country.state         | {"en_US": "Country state", "es_PE": "Estado"}
```

#### ¿Tienen datos cargados?

```sql
SELECT 'res_city' t, count(*) FROM res_city
UNION ALL SELECT 'l10n_pe_res_city_district', count(*) FROM l10n_pe_res_city_district
UNION ALL SELECT 'res_country_state (PE)', count(*) FROM res_country_state s
   JOIN res_country c ON c.id=s.country_id WHERE c.code='PE'
UNION ALL SELECT 'res_city (PE)', count(*) FROM res_city ci
   JOIN res_country c ON c.id=ci.country_id WHERE c.code='PE';
```
```
             t             | count
---------------------------+-------
 res_city                  |   196
 l10n_pe_res_city_district |  1874
 res_country_state (PE)    |    25
 res_city (PE)             |   196
```

**196 provincias y 1874 distritos.** Y las 196 `res.city` de la base son **todas** peruanas
(196 = 196), así que no hay contaminación de otros países.

#### Los 25 departamentos

```
  id  | code |     name
------+------+---------------
 1121 | 01   | Amazonas          1134 | 14 | Lambayeque
 1122 | 02   | Áncash            1135 | 15 | Lima
 1123 | 03   | Apurímac          1136 | 16 | Loreto
 1124 | 04   | Arequipa          1137 | 17 | Madre de Dios
 1125 | 05   | Ayacucho          1138 | 18 | Moquegua
 1126 | 06   | Cajamarca         1139 | 19 | Pasco
 1127 | 07   | Callao            1140 | 20 | Piura
 1128 | 08   | Cusco             1141 | 21 | Puno
 1129 | 09   | Huancavelica      1142 | 22 | San Martín
 1130 | 10   | Huánuco           1143 | 23 | Tacna
 1131 | 11   | Ica               1144 | 24 | Tumbes
 1132 | 12   | Junin             1145 | 25 | Ucayali
 1133 | 13   | La Libertad
```

**Los 25 completos**, con código INEI de 2 dígitos. *(Nota de datos: "Junin" y "Ancash"
están sin tilde en `name`; "Áncash", "Apurímac", "San Martín" sí la llevan. Inconsistencia
de la localización, no del proyecto — relevante si se hace matching por texto contra lo que
devuelva Google.)*

#### Estructura de las tablas

```
res_city:                          l10n_pe_res_city_district:
  id, name (jsonb), country_id,      id, name (jsonb), city_id,
  state_id, zipcode, l10n_pe_code    code
```

> **Dos detalles importantes para el matching:**
> 1. **`name` es `jsonb`** (campo traducible) en las dos tablas — hay que buscar por
>    `name->>'es_PE'` o `name->>'en_US'`, no por `name` a secas.
> 2. **Hay códigos INEI:** `res_city.l10n_pe_code` y `l10n_pe_res_city_district.code`.
>    Más fiables que el nombre para cualquier cruce.

Muestra de la jerarquía (Junín, la zona de la planta ECO):

```
 id  |  provincia   | distritos
-----+--------------+-----------
 104 | Huancayo     |        28
 105 | Concepción   |        15
 106 | Chanchamayo  |         6
 107 | Jauja        |        34
 108 | Junin        |         4
 109 | Satipo       |         9
 110 | Tarma        |         9
 111 | Yauli        |        10
 112 | Chupaca      |         9
```

#### Uso real hoy

```sql
SELECT count(*) total, count(biocreto_state_id) con_depto, count(biocreto_city_id) con_prov,
       count(biocreto_district_id) con_dist,
       count(*) FILTER (WHERE biocreto_street IS NULL OR biocreto_street='') AS street_vacio,
       count(*) FILTER (WHERE biocreto_latitud IS NOT NULL AND biocreto_latitud<>0) AS con_lat
FROM sale_order;
```
```
 total | con_depto | con_prov | con_dist | street_vacio | con_lat
-------+-----------+----------+----------+--------------+---------
    25 |        16 |       16 |       16 |            7 |       4
```

> **16 de 25 órdenes tienen los tres niveles completos** — se llenan juntos, gracias a la
> cascada. Pero **solo 4 tienen coordenadas**: el botón GPS se usa poco. Es exactamente el
> hueco que un "pegar enlace de Maps" vendría a cubrir.

> ### VEREDICTO
>
> **La estructura administrativa peruana existe, está completa y ya está cableada.**
> 25 departamentos → 196 provincias → 1874 distritos, con dominios en cascada, onchange de
> limpieza y concatenación automática a `biocreto_direccion_completa`.
>
> **No hay que crear modelos, ni cargar datos, ni construir jerarquía.** Lo único que
> faltaría para "pegar un enlace y que se rellene solo" es el **matching** entre lo que
> devuelva el servicio de mapas y estos registros — con la salvedad de las tildes
> inconsistentes y de que `name` es `jsonb`.

### 4.4 `biocreto_street` — confirmación del `required` de Studio

**CONFIRMADO.** El campo **no** es obligatorio en el modelo:

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:33-36
    biocreto_street = fields.Char(
        string="Calle / Dirección",
        help="Calle, avenida, jirón y número de la obra.",
    )
```

```
   model    |      name       |       label       | ttype | required | store
------------+-----------------+-------------------+-------+----------+-------
 sale.order | biocreto_street | Calle / Dirección | char  |    f     |   t
```

**`required = f` en el ORM.** La obligatoriedad la impone **Studio, solo en la vista**.
Arch completo del registro (`ir_ui_view` **4046**, xmlid
`studio_customization.odoo_studio_sale_ord_64de15cb-faad-4dc4-acf4-df0cac9dd835`,
`inherit_id = 1469`, **`priority = 160`**, `mode = extension`, `active = t`):

```xml
<data>
  <xpath expr="/form//field[@name='biocreto_street']" position="attributes">
    <attribute name="required">True</attribute>
  </xpath>
  <xpath expr="/form//field[@name='biocreto_fecha_vaceo_inicio']" position="attributes">
    <attribute name="options">{"end_date_field":"biocreto_fecha_vaceo_fin","numeric":true}</attribute>
  </xpath>
</data>
```

> **Por qué esto importa más de lo que parece:** `priority = 160` frente al `16` de las
> vistas del módulo. **Studio se aplica al final**, así que su `required="True"` **pisa**
> cualquier cosa que el módulo declare sobre ese atributo. Si un prompt futuro intenta
> hacer `biocreto_street` opcional editando el XML del módulo, **no funcionará**: hay que
> tocar el registro de Studio.

**Registros con el campo vacío hoy: 7 de 25.**

```
 total | street_vacio
-------+--------------
    25 |            7
```

> Esas 7 órdenes son **anteriores** al `required` de Studio (el `required` de vista no
> valida registros ya guardados, solo bloquea nuevos guardados desde el formulario). Si
> alguien abre una de ellas y pulsa Guardar, **no podrá** sin rellenar la dirección.

### 4.5 Viabilidad técnica de la resolución de enlaces

#### Salida HTTPS — **revalidada, OK**

```
GET  https://nominatim.openstreetmap.org/status.php  -> 200
GET  https://www.google.com/generate_204             -> 204
GET  https://maps.google.com/                        -> 200
```

Sin proxy, sin bloqueo. Ejecutado con `C:/Users/Diego/anaconda3/envs/PruebasOdoo19/python.exe`,
el mismo intérprete que corre el servidor.

#### `requests` — **disponible**

```
requests 2.31.0
urllib3  2.0.7
python   3.12.12
```

#### Comportamiento real de los enlaces cortos — **matiz importante**

```
HEAD https://maps.app.goo.gl/abc123XYZ  -> 404 | Location: None
HEAD https://goo.gl/maps/abc123         -> 404 | Location: None
HEAD https://maps.app.goo.gl/           -> 400 | Location: None
```

> **Lectura honesta:** la petición **sale y el servidor responde** — la conectividad está
> probada. Pero los códigos que usé son inventados, así que Google devuelve 404 sin
> `Location`. **`DESCONOCIDO — no pude verificar que un enlace corto REAL devuelva un 301/302
> con la cabecera Location apuntando a las coordenadas, porque no dispongo de un enlace
> real generado por el usuario.`**
>
> Esto no es un detalle menor: el diseño de la funcionalidad depende de **cómo** entrega
> Google el destino. Puede ser un `301` con `Location` (fácil: basta `allow_redirects=False`
> y leer la cabecera), o un `200` con el destino embebido en JavaScript (mucho más frágil).
> **Antes de escribir el prompt de implementación hace falta un enlace real para probarlo.**
> Ver pregunta 12 del §6.

#### API keys ya configuradas

```sql
SELECT key, value FROM ir_config_parameter
WHERE key ILIKE '%geo%' OR key ILIKE '%map%' OR key ILIKE '%google%';
```
```
              key              | value
-------------------------------+-------
 base_geolocalize.geo_provider | 1
```

**Un único parámetro, sin personalizar.** No hay API key de Google Maps ni token de Mapbox.
El proveedor `1` es el primero del catálogo de `base_geolocalize` (Nominatim/OSM en Odoo 19,
que no requiere clave).

#### ¿Existe ya código que haga llamadas HTTP salientes? — **NO**

```
$ grep -rn "import requests\|urllib\|urlopen\|http.client" custom_addons/ --include=*.py
custom_addons/biocreto_sale_extension/models/sale_order.py:1:      from urllib.parse import quote
custom_addons/biocreto_sale_report_cotizacion/models/sale_order.py:1: from urllib.parse import quote_plus
```

**Las dos son `urllib.parse` — codificación de URL, no red.** Sus usos:

```python
# biocreto_sale_extension/models/sale_order.py:160
                destino = quote(order.biocreto_direccion_completa)
```

```python
# biocreto_sale_report_cotizacion/models/sale_order.py:68-70
    def biocreto_cot_qr_url(self):
        self.ensure_one()
        return quote_plus(self.get_base_url() + self.get_portal_url())
```

> **Conclusión: no existe ni un solo precedente de llamada HTTP saliente en el proyecto.**
> No hay patrón de timeouts, reintentos, manejo de errores ni logging que copiar. Habrá que
> establecerlo desde cero, y decidir qué pasa cuando el servicio externo no responde
> (pregunta 13 del §6).
>
> El precedente más cercano en **estructura de código** es el manejo de errores tolerante de
> `biocreto_pdf_engine` (`models/ir_actions_report.py:109-121`): `try/except` amplio,
> `_logger.exception` con contexto, y **degradación en lugar de aborto**. Es el criterio que
> yo replicaría, pero es una observación de estilo, no una verificación.

---

## 5. DESCONOCIDOS que persisten

| # | Qué no se pudo verificar | Por qué | Qué haría falta |
|---|---|---|---|
| 1 | **De dónde sale "CONCRETOS ECOLOGICOS"** | El literal no existe en código, ni en BD, ni en los mockups. La compañía se llama `Biocreto` y el bloque bancario no imprime titular | Que el usuario indique la razón social real y si debe reemplazar a `Biocreto` o solo mostrarse en el bloque |
| 2 | **Si un enlace corto REAL de Maps devuelve 301 con `Location`** | `DESCONOCIDO — no pude verificarlo porque no dispongo de un enlace real; los códigos inventados dan 404 sin Location.` La conectividad sí está probada | Un enlace real pegado por el usuario, para hacerle un `HEAD` y ver la respuesta |
| 3 | **Dónde se imprime hoy el RUC en la cotización** | No recorrí entero el `cot_layout` (líneas 79-460). Sí está verificado que **no** está en el bloque bancario | La consulta SQL del §2.4 sobre `arch_db LIKE '%vat%'`, o leer `cot_layout` |
| 4 | **Si el orden de las cuentas importa al negocio** | Las 4 tienen `sequence = 10` empatado; hoy salen por `id` por casualidad | Decisión del usuario (pregunta 6) |
| 5 | **Por qué 7 órdenes tienen `biocreto_street` vacío** | Son anteriores al `required` de Studio, pero no verifiqué caso por caso | Revisarlas si se quiere backfill |
| 6 | **Si las tildes inconsistentes de los departamentos rompen el matching** | Depende del texto que devuelva el servicio de mapas, que aún no conozco | Resolver primero el desconocido #2 |
| 7 | **Formato exacto del CCI esperado** | En BD hay tres formatos distintos conviviendo: `002 355 005028342090  64` (doble espacio), `011 237 00010004562050`, `009 423 000004455922 57`. Los mockups usan guiones en algunos | Decisión del usuario sobre si normalizar |
| 8 | **Comportamiento del PDF con 6 columnas en A4** | No rendericé el PDF con columnas añadidas (implicaría modificar el template) | Probarlo tras implementar; el aviso de `break-inside` está en `report_cotizacion.xml:822-826` |

---

## 6. DECISIONES PARA EL USUARIO

### Bloque bancario y RUC (lo que se implementa primero)

1. **★ "CONCRETOS ECOLOGICOS": ¿cuál es exactamente la razón social?** No existe en el sistema — la compañía se llama `Biocreto`. ¿Hay que (a) cambiar el nombre de la compañía en Odoo, (b) dejar la compañía como está y poner el literal solo en el bloque bancario, o (c) usar `acc_holder_name` de cada cuenta, que hoy dice `Biocreto`?

2. **★ ¿Qué dos datos exactamente se añaden al bloque?** Entiendo que son **titular** y **RUC**, pero conviene confirmarlo. Y sobre todo: **¿como columnas nuevas de la tabla, o como una línea de texto encima de ella?** Con 4 columnas a 8.5pt en A4 la tabla ya va justa; añadir dos columnas comprime el CCI (24 caracteres) y puede partirlo. Una línea del tipo `CONCRETOS ECOLOGICOS S.A.C. · RUC 20605252401` sobre la tabla es visualmente más segura y respeta el separador `·` que ya usa el título.

3. **★ ¿El bloque debe aparecer también en la cotización "menor envergadura"?** Hoy **no sale**: vive dentro de `cot_body_mayor`. Si el cliente de una obra pequeña también necesita las cuentas para pagar, hay que moverlo a `cot_body_common` o duplicarlo en `cot_body_menor`.

4. **¿Se factoriza el bloque en una plantilla QWeb compartida?** Está duplicado en cotización y contrato con el `<tbody>` idéntico y el envoltorio distinto. Sin factorizar, cada cambio hay que hacerlo dos veces.

5. **Moneda: ¿se deja "Soles" fijo o se lee de la cuenta?** Las 4 cuentas tienen `currency_id = PEN`. Ojo: `bank.currency_id.name` imprimiría **`PEN`**, no `Soles`. Para conservar "Soles" habría que mapear el código a un nombre legible. Y son **tres** sitios a cambiar (título, `<td>`, términos y condiciones).

6. **¿Importa el orden de las cuentas?** Las 4 tienen `sequence = 10`; hoy salen BCP → BBVA → Scotiabank por desempate de `id`, no por configuración. Si el orden es deliberado, hay que asignar `sequence` distintos (es un cambio de datos, no de código).

7. **RUC: ¿con qué formato se imprime?** ¿`20605252401` a secas, `RUC 20605252401`, o `RUC: 20605252401`? No existe ningún formateador — el literal irá en el QWeb.

### Slump

8. **★ Ese `required` condicional, ¿a cuál de los campos nuevos pasa?** Hoy `biocreto_slump` es obligatorio cuando la categoría es Concreto, **en ambas vistas**. Con rango: ¿obligatorio el mínimo, el máximo, o los dos?

9. **Las 4 líneas ya facturadas.** Un contrato firmado dice hoy `Slump 6"`. Con rango y migración `min = max = 6`, ¿el reporte debe imprimir `6"` (detectando `min == max`) o `6" – 6"`? Si no se contempla, **documentos ya firmados cambiarán de aspecto al reimprimirse.**

10. **¿El rango llega al ensayo de laboratorio?** `biocreto.slump.valor` es una **medición real** (por mixer, en planta u obra) — un ensayo da un número, no un rango. Lo natural es dejarlo como valor único y compararlo contra el rango de la línea. ¿Se confirma?

11. **¿El rango aplica a `biocreto_slump_bombeable`?** Hoy tiene 8 líneas, todas con el mismo valor `6.00`, y **no** es obligatorio.

### Ubicación

12. **★ Un enlace de Maps real, para probar.** Es lo que bloquea el diseño: necesito ver si Google devuelve `301` + `Location` (fácil de resolver en servidor) o un `200` con el destino en JavaScript (frágil). Con un enlace real lo verifico en un minuto.

13. **¿Qué pasa si el servicio externo no responde?** No hay ningún precedente de llamada HTTP saliente en el proyecto. ¿El guardado se bloquea con un error, o se acepta el enlace y se deja las coordenadas vacías con un aviso?

14. **¿Qué debe rellenar el enlace?** ¿Solo `biocreto_latitud`/`biocreto_longitud`, o también intentar deducir distrito/provincia/departamento? Lo segundo es posible —la jerarquía completa está cargada— pero exige matching por texto, y los departamentos tienen tildes inconsistentes (`Junin` sin tilde, `Áncash` con ella).

15. **¿Dónde se pega el enlace?** ¿Campo nuevo dedicado, o reutilizando alguno existente? **Aviso:** `biocreto_street` está `required=True` por Studio con `priority=160`, que pisa al módulo — y hay 7 órdenes con ese campo vacío que no se podrán volver a guardar sin rellenarlo.

16. **¿El enlace se guarda o solo se usa y se descarta?** Guardarlo permite reprocesarlo; no guardarlo evita almacenar URLs que caducan.

---

## 7. Criterio de aceptación

```
$ git status --short
?? RECON_BIOCRETO.md
?? RECON_COMPLEMENTO.md
?? custom_addons/LogoReq.svg
?? custom_addons/PruebaLaboratorio.svg
?? custom_addons/biocreto_fabricacion/
?? custom_addons/biocreto_laboratorio/
?? custom_addons/biocreto_requerimientos/
?? custom_addons/draw_planta.svg
?? custom_addons/icono_fabrica.svg
?? custom_addons/mixer_truck.svg

$ git diff --name-only
(vacío)
```

**Cero archivos modificados.** Las únicas entradas nuevas son los dos informes de recon.
No se ejecutó ningún `-u` ni `-i`. Todas las consultas a base de datos fueron `SELECT`.
