# RECON BIOCRETO — Bug de firma en contrato + 3 ajustes previos

> **Naturaleza de este documento:** recon de SOLO LECTURA ejecutado el 2026-08-20.
> Ningún archivo del proyecto fue modificado; este `.md` es el único creado.
> Ninguna consulta a base de datos fue inventada: todas se ejecutaron contra
> `Prueba` vía `psql` y su salida está pegada literal. Las pruebas en
> `odoo-bin shell` terminaron con `env.cr.rollback()`.

---

## 1. Resumen ejecutivo

1. **Las firmas del contrato NO son Odoo Sign.** Son dos campos `Binary(attachment=True)` en `sale.order` definidos en `biocreto_sale_extension/models/sale_order.py:102` y `:116`. No existe `sign_request_id` en `sale_order`, ni un solo `_inherit` de `sign.*` en el proyecto.
2. **El typo `frima` NO existe.** Cero ocurrencias en código y cero en BD (`ir_ui_view`, `ir_act_server`, `ir_model_fields`, `ir_act_report_xml`). Esa hipótesis queda descartada con evidencia.
3. **El reporte lee cada firma de forma directa e independiente** (`report_contrato.xml:889` y `:898`): dos `t-if` + `image_data_uri`, sin `t-foreach`, sin índice fijo, sin comparar nombres. No hay caché de PDF (`attachment_use` y `attachment` NULL en la acción 1179).
4. **Modo de fallo REPRODUCIDO:** con `bin_size=True` en el contexto de render, el reporte emite `src="data:image/png;base64,31.47 Kb"` — la firma queda invisible aunque el dato esté intacto. Es exactamente la forma del síntoma reportado.
5. **No hay en la base ninguna orden firmada "una por una":** las dos únicas firmadas (20 y 28) tienen fecha y `file_size` idénticos en ambas firmas → se firmaron con "Firmar Ambos", un solo `write`. El caso del bug no existe hoy en BD, por lo que **el diferencial A vs B no se puede aislar sin correr el protocolo del §4.4**.
6. Cuentas bancarias: **no están hardcodeadas**, salen de `o.company_id.bank_ids` en dos reportes. El número `2045643545646` no existe ni en código ni en BD.
7. Slump: **dos campos `Float` en `sale.order.line`** + un modelo de ensayo `biocreto.slump`. 16 líneas con valor, 4 valores distintos. No existe ningún campo de rango/min/max en el proyecto.
8. Ubicación de obra: dos `Float` en `sale.order` + botón GPS OWL propio. **No hay modelo de "obra"**. El proceso Odoo **sí tiene salida a internet**.

---

## 2. Entorno (Paso 2)

| Punto | Valor |
|---|---|
| Raíz del proyecto | `D:\DIEGO\htdocs\Biocretodoo` |
| Config en uso | `odoo19.conf` |
| Versión Odoo | **19.0 final** — `odoo/release.py:15` → `version_info = (19, 0, 0, FINAL, 0, '')` |
| ¿Enterprise? | **Sí.** `addons/web_enterprise/__manifest__.py` existe y `addons/sign` (Enterprise) está instalado |
| Base de datos | `Prueba` @ `localhost:5432`, usuario `odoobiocreto`, PostgreSQL 17.2 |
| `psql` | **Disponible** en `C:\Program Files\PostgreSQL\17\bin` (no está en `PATH`; se invocó por ruta absoluta). Probado: `SELECT version()` → OK |
| `odoo-bin shell` | **Disponible.** Probado: registry cargado en 3.87 s, 299 módulos |
| Intérprete | `C:/Users/Diego/anaconda3/envs/PruebasOdoo19/python.exe` — Python 3.12.12 |
| Salida a internet | **SÍ** (§8, E6) |

### `odoo19.conf` (passwords ocultos)

```ini
[options]
admin_passwd = ***OCULTO***
db_host = localhost
db_name = Prueba
list_db = False
db_port = 5432
db_user = odoobiocreto
db_password = ***OCULTO***
addons_path = D:\DIEGO\htdocs\Biocretodoo\addons,
              D:\DIEGO\htdocs\Biocretodoo\custom_addons
pg_path = C:\Program Files\PostgreSQL\17\bin
bin_path = C:\Program Files\wkhtmltopdf\bin
```

### `addons_path` EFECTIVO (el que reporta el servidor al arrancar, no el del `.conf`)

```
D:\DIEGO\htdocs\Biocretodoo\odoo\addons          <-- PRIMERO, gana en caso de duplicado
C:\Users\Diego\AppData\Local\OpenERP S.A.\Odoo\addons\19.0
d:\diego\htdocs\biocretodoo\addons
d:\diego\htdocs\biocretodoo\custom_addons
```

> **Ojo para futuros prompts:** `odoo/addons/` **precede** al `addons_path` del `.conf`.
> Cuando un módulo existe en las dos rutas (p. ej. `purchase`, `sign`), la copia que
> Odoo carga es la de `odoo/addons/`, no la de `addons/`.

### Git

| Punto | Valor |
|---|---|
| Rama | `master` |
| Último commit | `34b17794a` — *BIOCRETO COMPRAS REPORTE DE COTIZACION Y ORDEN TERMINADA* (2026-07-23) |
| Sin commitear | 8 entradas, todas `??` (untracked): `custom_addons/biocreto_fabricacion/`, `custom_addons/biocreto_laboratorio/`, `custom_addons/biocreto_requerimientos/`, `custom_addons/LogoReq.svg`, `custom_addons/PruebaLaboratorio.svg`, `custom_addons/draw_planta.svg`, `custom_addons/icono_fabrica.svg`, `custom_addons/mixer_truck.svg` |
| Modificados | **Ninguno.** Cero archivos tracked modificados antes y después de este recon |

---

## 3. Inventario de archivos (Paso 3)

### 3.1 Módulos `biocreto_*` en disco

| Módulo | Versión manifest | Depends | Archivos |
|---|---|---|---|
| `biocreto_base` | 19.0.1.3.0 | base, mail, contacts, product, l10n_pe, l10n_latam_base | 12 — `models/{product_template,res_company,res_partner,res_partner_bank,res_users}.py`, `views/{product_template,res_company,res_partner_bank,res_users}_views.xml` |
| `biocreto_compras` | 19.0.6.0.0 | purchase, purchase_stock, purchase_requisition, biocreto_base | 10 |
| `biocreto_compras_reporte` | 19.0.2.0.0 | purchase, purchase_stock, biocreto_compras, biocreto_base, biocreto_sig, biocreto_pdf_engine | 9 |
| `biocreto_encuestas` | 19.0.3.11.0 | biocreto_sale_extension, biocreto_sale_contract_state, survey, portal, sale_stock | 25 |
| `biocreto_encuestas_filtro` | 19.0.1.0.0 | biocreto_encuestas | 7 |
| `biocreto_encuestas_reporte` | 19.0.2.0.0 | biocreto_encuestas, biocreto_pdf_engine, biocreto_sig | 14 |
| `biocreto_fabricacion` | 19.0.1.1.0 | mrp, mrp_workorder, sale, sale_mrp, sale_stock, stock, fleet, mail, biocreto_sale_extension, biocreto_sale_contract_state | 30 |
| `biocreto_laboratorio` | 19.0.1.0.1 | sale, mrp, fleet, mail, biocreto_base, biocreto_sale_extension, biocreto_sale_contract_state | 21 — incluye `models/slump.py`, `views/slump_views.xml` |
| `biocreto_map_coord` | 19.0.1.0.3 | web_map | 5 — solo JS (`static/src/map_view/*.js`) |
| `biocreto_pdf_engine` | 19.0.1.0.7 | base, web | 4 — `models/ir_actions_report.py` |
| `biocreto_programacion` | 19.0.1.0.2 | biocreto_sale_contract_state, biocreto_map_coord | 6 — solo vistas + JS del popover |
| `biocreto_requerimientos` | 19.0.1.1.0 | mail, product, uom, biocreto_base, purchase, stock | 25 |
| `biocreto_sale_contract_state` | 19.0.1.2.3 | sale_management, biocreto_sale_extension | 8 |
| `biocreto_sale_extension` | 19.0.1.7.5 | sale_management, biocreto_base, fleet, mrp, base_address_extended, l10n_pe | 22 — incluye 4 scripts de migración y el widget `geo_button` |
| `biocreto_sale_portal` | 19.0.2.1.0 | sale_management, portal, biocreto_sale_extension, biocreto_sale_contract_state, biocreto_sale_reports_contrato | 9 |
| `biocreto_sale_report_cotizacion` | 19.0.2.0.13 | sale, sale_stock, biocreto_sale_extension, biocreto_sig, biocreto_base, biocreto_pdf_engine | 8 |
| `biocreto_sale_reports_contrato` | 19.0.1.5.0 | biocreto_sale_report_cotizacion, biocreto_sale_contract_state, biocreto_sig | 9 |
| `biocreto_sig` | 19.0.1.0.0 | mail | 9 |

### 3.2 Archivos y registros que participan en los 4 puntos

| Archivo o registro BD | Punto | Qué define |
|---|---|---|
| `biocreto_sale_extension/models/sale_order.py:102-107` | A firma | `biocreto_firma_jefe_obra` (Binary), `_por` (Char), `_fecha` (Datetime) |
| `biocreto_sale_extension/models/sale_order.py:116-126` | A firma | `biocreto_firma_contrato` (Binary), `_por`, `_fecha` |
| `biocreto_sale_extension/views/sale_order_views.xml:137-157` | A firma | Grupo backend "FIRMA CONTRATO" con los 6 campos |
| `biocreto_sale_contract_state/models/sale_order.py:43` | A firma | `biocreto_fecha_firma_contrato` (Date) — la fecha que imprime el reporte |
| `biocreto_sale_contract_state/models/sale_order.py:240-258` | A firma | `action_draft()` — **único** punto que borra las firmas |
| `biocreto_sale_portal/controllers/portal.py:185-309` | A firma | Ruta `/my/orders/<id>/sign_contract/<kind>` — el guardado |
| `biocreto_sale_portal/controllers/portal.py:322-343` | A firma | Ruta `/my/contracts/<id>/pdf` — la descarga desde el portal |
| `biocreto_sale_portal/views/portal_templates.xml:143-247` | A firma | Bloque portal: 3 botones + widget `portal.signature_form` |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:867-906` | A firma | **Los tres recuadros de firma del PDF** |
| `biocreto_sale_reports_contrato/report/report_contrato_actions.xml:41-48` | A firma | `ir.actions.report` id **1179** |
| `biocreto_sale_reports_contrato/models/ir_actions_report.py:32-42` | A firma | Override de `_render_qweb_pdf` (solo valida estado) |
| `biocreto_pdf_engine/models/ir_actions_report.py:74-122` | A firma | Motor PlutoPrint — override de `_render_qweb_pdf_prepare_streams` |
| BD `ir_act_report_xml` id **1179** | A firma | Único reporte de contrato. `attachment`/`attachment_use` NULL |
| BD `ir_ui_view` id **4092** (`biocreto_sale_reports_contrato.contrato_body`) | A + C | Cuerpo del contrato instalado en BD |
| `biocreto_sale_report_cotizacion/report/report_cotizacion.xml:874-903` | C banco | Banda "Cuentas Bancarias · Soles" de la cotización |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:681-710` | C banco | Cláusula 4.4 con la misma tabla de cuentas |
| `biocreto_base/models/res_partner_bank.py:7-10` | C banco | Campo `biocreto_cci` |
| `biocreto_sale_extension/models/sale_order_line.py:41-44` | D slump | `biocreto_slump` (Float) |
| `biocreto_sale_extension/models/sale_order_line.py:58-61` | D slump | `biocreto_slump_bombeable` (Float) |
| `biocreto_laboratorio/models/slump.py` | D slump | Modelo `biocreto.slump` (ensayo por mixer) |
| `biocreto_sale_extension/models/sale_order.py:62-72` | E ubicación | `biocreto_latitud`, `biocreto_longitud` |
| `biocreto_sale_extension/models/sale_order.py:142-161` | E ubicación | `biocreto_gmaps_url` (compute, no-store) |
| `biocreto_sale_extension/static/src/components/geo_button/geo_button.{js,xml}` | E ubicación | Widget "Obtener ubicación" |
| `biocreto_map_coord/static/src/map_view/*.js` | E ubicación | Vista mapa por coordenadas propias |
| BD `ir_ui_view` ids 4043/4044, 4069/4070, 4081/4082 | — | Plantillas QWeb de Studio **huérfanas** (ninguna acción de reporte las referencia) |

---

## 4. Bug de firma

### 4.1 Hallazgos con evidencia

#### A1 — Grep de los tres identificadores

**`biocreto_frima_jefe_obra` (con "frima"): CERO ocurrencias.** Ni en código ni en base de datos.

```
$ grep -rni "frima" custom_addons/
(sin resultados)
```

```sql
SELECT 'ir_ui_view' t, count(*) FROM ir_ui_view WHERE arch_db::text ILIKE '%frima%'
UNION ALL SELECT 'ir_act_server', count(*) FROM ir_act_server WHERE code ILIKE '%frima%'
UNION ALL SELECT 'ir_model_fields', count(*) FROM ir_model_fields WHERE name ILIKE '%frima%'
UNION ALL SELECT 'ir_act_report_xml', count(*) FROM ir_act_report_xml WHERE report_name ILIKE '%frima%';
```
```
         t         | count
-------------------+-------
 ir_ui_view        |     0
 ir_act_server     |     0
 ir_model_fields   |     0
 ir_act_report_xml |     0
```

> **Conclusión del punto A1:** las dos grafías **NO conviven**. Solo existe `firma`.
> La hipótesis del typo queda **REFUTADA** con evidencia. No hay que buscar por ahí.

**`biocreto_firma_contrato` — ocurrencias en código:**

| Archivo:línea | Rol |
|---|---|
| `biocreto_sale_extension/models/sale_order.py:116,119,122` | Definición de los 3 campos |
| `biocreto_sale_extension/views/sale_order_views.xml:141,143,144,145,146,147,148` | Vista backend |
| `biocreto_sale_contract_state/models/sale_order.py:249,250,251` | Reset en `action_draft` |
| `biocreto_sale_portal/controllers/portal.py:161,206,207,208,223,244,261` | Escritura desde el portal |
| `biocreto_sale_portal/views/portal_templates.xml:178,181,182` | Estado "firmado por X el Y" en el portal |
| `biocreto_sale_portal/__manifest__.py:22` | Documentación |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:883,889,890` | **Render del PDF** |

**`biocreto_firma_jefe_obra` — ocurrencias en código:**

| Archivo:línea | Rol |
|---|---|
| `biocreto_sale_extension/models/sale_order.py:102,106,107` | Definición de los 3 campos |
| `biocreto_sale_extension/views/sale_order_views.xml:151,152,153,154` | Vista backend |
| `biocreto_sale_contract_state/models/sale_order.py:252,253,254` | Reset en `action_draft` |
| `biocreto_sale_portal/controllers/portal.py:162,212,213,214,224,245,262` | Escritura desde el portal |
| `biocreto_sale_portal/views/portal_templates.xml:192,195,196` | Estado en el portal |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:898,899,903` | **Render del PDF** |

**En base de datos** (`ir_ui_view.arch_db`), simetría perfecta:

```
  id  |                              key                              |   model    | firma_contrato | FRIMA_jefe | firma_jefe
------+---------------------------------------------------------------+------------+----------------+------------+------------
 4032 | (sin key)                                                     | sale.order | t              | f          | t
 4092 | biocreto_sale_reports_contrato.contrato_body                  | -          | t              | f          | t
 4095 | biocreto_sale_portal.sale_order_portal_content_contract_block | -          | t              | f          | t
```

Las tres vistas que mencionan una firma mencionan **las dos**. Ninguna menciona `frima`.

#### A2 — Qué son esos identificadores

Opción **(b): campos técnicos en `sale.order`**, definidos en código (no Studio).

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:102-107
    biocreto_firma_jefe_obra = fields.Binary(
        string="Firma JO",
        attachment=True,
    )
    biocreto_firma_jefe_obra_por = fields.Char(string="Firmado por JO")
    biocreto_firma_jefe_obra_fecha = fields.Datetime(string="Firmado el (JO)")
```

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:116-126
    biocreto_firma_contrato = fields.Binary(
        string="Firma Contrato", attachment=True, copy=False,
    )
    biocreto_firma_contrato_por = fields.Char(
        string="Firmado por (Contrato)", copy=False,
    )
    biocreto_firma_contrato_fecha = fields.Datetime(
        string="Firmado el (Contrato)", copy=False,
    )
```

**NO son** `sign.item.role`, **NO son** `sign.item`, **NO son** ids ni clases del QWeb.

Confirmación de que Odoo Sign no participa:

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='sale_order' AND column_name ILIKE '%sign%';
```
```
    column_name
-------------------
 require_signature
 signed_by
 signed_on
```

No existe `sign_request_id`. Los tres que aparecen son los nativos de `sale` para la firma **de la cotización**, no del contrato.

#### A3 — Código del flujo de firma

**No existen** `action_send_contract` ni `action_sign_contract`. Barrido completo de definiciones de método relacionadas:

```
$ grep -rn "def .*firma\|def .*contract\|def .*contrato\|def .*sign" custom_addons/ --include=*.py
biocreto_sale_contract_state/models/sale_order.py:85:   def _confirmation_error_message(self)
biocreto_sale_contract_state/models/sale_order.py:136:  def action_biocreto_confirmar_ov(self)
biocreto_sale_contract_state/models/sale_order.py:271:  def _biocreto_cron_autoconfirmar(self)
biocreto_sale_extension/models/sale_order.py:452:       def biocreto_contrato_saldo(self)
biocreto_sale_extension/models/sale_order.py:459:       def biocreto_contrato_monto_palabras(self, amount)
biocreto_sale_extension/models/sale_order.py:514:       def _biocreto_contrato_dir_inline(self, partner)
biocreto_sale_extension/models/sale_order.py:533:       def biocreto_contrato_dir_cliente(self)
biocreto_sale_extension/models/sale_order.py:543:       def biocreto_contrato_dir_proveedor(self)
biocreto_sale_portal/controllers/portal.py:189:         def biocreto_sign_contract(...)
biocreto_sale_portal/controllers/portal.py:326:         def biocreto_contract_pdf(...)
```

Los cuatro de `biocreto_contrato_*` en `sale_extension` son helpers de formateo del reporte (saldo, monto en palabras, direcciones). Ninguno toca firmas.

**No hay `@api.depends` ni `@api.onchange` sobre los campos de firma.** El único `write()` sobreescrito en `sale.order` es:

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:271-276
    def write(self, vals):
        # Idem create: mantener commitment_date alineado con el inicio del
        # rango cuando el cliente edita la fecha desde cualquier canal.
        if 'biocreto_fecha_vaceo_inicio' in vals and 'commitment_date' not in vals:
            vals['commitment_date'] = vals['biocreto_fecha_vaceo_inicio']
        return super().write(vals)
```

No interfiere con las firmas.

##### ÚNICO método que borra firmas — `action_draft`

```python
# custom_addons/biocreto_sale_contract_state/models/sale_order.py:240-258
    def action_draft(self):
        result = super().action_draft()
        # action_draft nativo filtra state in ('cancel', 'sent') antes
        # de escribir state='draft'. Para mantener simetria, limpiamos
        # solo el conjunto de ordenes que el nativo efectivamente paso
        # a draft (si una orden no estaba en cancel/sent, action_draft
        # no la toco -> no debemos limpiar sus firmas tampoco).
        flipped = self.filtered(lambda o: o.state == 'draft')
        if flipped:
            flipped.write({
                'biocreto_firma_contrato': False,
                'biocreto_firma_contrato_por': False,
                'biocreto_firma_contrato_fecha': False,
                'biocreto_firma_jefe_obra': False,
                'biocreto_firma_jefe_obra_por': False,
                'biocreto_firma_jefe_obra_fecha': False,
            })
        return result
```

Borra **las dos a la vez**, nunca una sola. No puede producir el síntoma "falta una".

##### El método que GUARDA — íntegro, sin resumir

```python
# custom_addons/biocreto_sale_portal/controllers/portal.py:185-309
    @http.route(
        ['/my/orders/<int:order_id>/sign_contract/<string:kind>'],
        type='jsonrpc', auth='public', website=True,
    )
    def biocreto_sign_contract(self, order_id, kind, access_token=None,
                               name=None, signature=None, **kw):
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token,
            )
        except (AccessError, MissingError):
            return {'error': _('Pedido inválido.')}

        if not signature:
            return {'error': _('Falta la firma.')}

        now = fields.Datetime.now()
        vals = {}
        if kind in ('cliente', 'ambos'):
            vals.update({
                'biocreto_firma_contrato': signature,
                'biocreto_firma_contrato_por': name,
                'biocreto_firma_contrato_fecha': now,
            })
        if kind in ('jefe_obra', 'ambos'):
            vals.update({
                'biocreto_firma_jefe_obra': signature,
                'biocreto_firma_jefe_obra_por': name,
                'biocreto_firma_jefe_obra_fecha': now,
            })
        if not vals:
            return {'error': _('Tipo de firma inválido.')}

        # v19.0.1.4.0: SNAPSHOT del estado previo ANTES del write.
        # Lee los Binary attachment desde DB (confiable porque aun no
        # escribimos vals). bool(binary) en Odoo es True si el blob
        # esta poblado, False si esta vacio.
        cli_antes = bool(order_sudo.biocreto_firma_contrato)
        jo_antes = bool(order_sudo.biocreto_firma_jefe_obra)
        ya_completo_antes = cli_antes and jo_antes

        try:
            order_sudo.write(vals)
            # flush necesario para que _render_qweb_pdf vea las firmas
            # nuevas al renderizar el PDF que se adjuntara al chatter.
            request.env.cr.flush()
        except (TypeError, binascii.Error):
            return {'error': _('Datos de firma inválidos.')}

        # v19.0.1.4.0: FIX BUG A — completitud por vals, NO por read-back.
        # En v19.0.1.3.0 reusabamos `bool(order_sudo.biocreto_firma_*)`
        # post-write para inferir completitud. Los Binary con
        # attachment=True viven en ir.attachment; el read-back inmediato
        # dentro de la misma transaccion devuelve falsy aunque el blob
        # se acabe de escribir -> el guard caia siempre al else y nunca
        # disparaba la rama combinada con PDF. Solucion: derivar la
        # completitud actual del estado previo (confiable) + presencia
        # del campo en `vals` (el dict que acabamos de escribir).
        cli_ahora = cli_antes or ('biocreto_firma_contrato' in vals)
        jo_ahora = jo_antes or ('biocreto_firma_jefe_obra' in vals)
        ahora_completo = cli_ahora and jo_ahora

        author_id = (
            order_sudo.partner_id.id
            if request.env.user._is_public()
            else request.env.user.partner_id.id
        )

        if ahora_completo and not ya_completo_antes:
            # Rama combinada: paso de incompleto a completo en este firmado.
            # Adjunta PDF del contrato al chatter + un solo mensaje con el/los
            # firmante(s). Patron exacto de /accept (sale/controllers/portal.py:
            # 330-342): `_render_qweb_pdf(...)[0]` + `message_post(
            # attachments=[(filename, pdf_bytes)])`. PlutoPrint matchea por
            # report_name automaticamente via biocreto_pdf_engine.
            cli = (order_sudo.biocreto_firma_contrato_por or '').strip()
            jo = (order_sudo.biocreto_firma_jefe_obra_por or '').strip()
            if cli and jo and cli.lower() == jo.lower():
                firmantes = cli
            elif cli and jo:
                firmantes = _("%(cli)s y %(jo)s", cli=cli, jo=jo)
            else:
                firmantes = cli or jo or _("(sin nombre)")
            pdf_content, _ext = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'biocreto_sale_reports_contrato.report_contrato_document',
                [order_sudo.id],
            )
            filename = 'Contrato_%s.pdf' % (
                (order_sudo.name or str(order_sudo.id)).replace('/', '_')
            )
            order_sudo.message_post(
                body=_(
                    "Contrato %(num)s firmado por %(firmantes)s.",
                    num=order_sudo.name, firmantes=firmantes,
                ),
                attachments=[(filename, pdf_content)],
                author_id=author_id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        else:
            # Rama simple: firma parcial (aun falta una) o re-firma estando
            # ya completo. Mensaje corto sin PDF.
            etiqueta = {
                'cliente': _('el cliente'),
                'jefe_obra': _('el jefe de obra'),
                'ambos': _('el cliente y el jefe de obra'),
            }.get(kind, '')
            order_sudo.message_post(
                body=_(
                    "Contrato %(num)s firmado por %(quien)s (%(nombre)s).",
                    num=order_sudo.name, quien=etiqueta, nombre=name or '',
                ),
                author_id=author_id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        return {
            'force_refresh': True,
            'redirect_url': order_sudo.get_portal_url(
                query_string='&message=contract_signed',
            ),
        }
```

##### El método que DESCARGA el PDF desde el portal — íntegro

```python
# custom_addons/biocreto_sale_portal/controllers/portal.py:322-343
    @http.route(
        ['/my/contracts/<int:order_id>/pdf'],
        type='http', auth='public', website=True,
    )
    def biocreto_contract_pdf(self, order_id, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token,
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        pdf, _content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'biocreto_sale_reports_contrato.report_contrato_document',
            [order_sudo.id],
        )
        filename = 'Contrato_%s.pdf' % (order_sudo.name or order_sudo.id).replace('/', '_')
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', 'inline; filename="%s"' % filename),
        ])
```

> **Anotar:** esta respuesta **no lleva ninguna cabecera de caché**. Sin `Cache-Control`
> ni `ETag` ni `Last-Modified`, la reutilización de la respuesta queda a criterio del
> navegador. Ver hipótesis H2 en §4.3.

#### A4 — Identificación del reporte

**Un único reporte de contrato.** `ir.actions.report` con `model='sale.order'`:

```
  id  |          name          |                       report_name                       | report_type | attachment_use | attachment
------+------------------------+---------------------------------------------------------+-------------+----------------+------------
  544 | PRO-FORMA Invoice      | sale.report_saleorder_pro_forma                         | qweb-pdf    |                |
  596 | Quotation / Order      | sale.report_saleorder_raw                               | qweb-pdf    |                |
 1176 | PDF Quote              | sale.report_saleorder                                   | qweb-pdf    |                |
 1179 | Contrato de Suministro | biocreto_sale_reports_contrato.report_contrato_document | qweb-pdf    |                |
```

| Punto | Valor |
|---|---|
| Nombre técnico | `biocreto_sale_reports_contrato.action_report_contrato` |
| `report_name` | `biocreto_sale_reports_contrato.report_contrato_document` |
| ¿Studio? | **NO.** Es del módulo: `biocreto_sale_reports_contrato/report/report_contrato_actions.xml:41-48` |
| Template QWeb | `biocreto_sale_reports_contrato/report/report_contrato.xml`, raíz en la línea 1048 |
| `binding_model_id` | 685 (`sale.order`), `binding_type = report` → sí aparece en el menú Imprimir |
| `print_report_name` | `'Contrato - %s' % (object.name)` |
| **`attachment` / `attachment_use`** | **NULL las dos** → **el PDF NO se cachea; se re-renderiza en cada impresión** |

> Esto **refuta** de entrada la hipótesis "Odoo devuelve un PDF viejo guardado como
> adjunto del reporte". Ese mecanismo está desactivado.

Los tres reportes de Studio en BD (`ir_ui_view` 4043/4044, 4069/4070, 4081/4082) son **huérfanos**: ninguna fila de `ir_act_report_xml` los referencia, y sus `arch_db` miden 298 y 882 caracteres (esqueletos vacíos).

Cadena de render:

```
_render_qweb_pdf                                  <- override de biocreto_sale_reports_contrato (solo valida estado)
  -> _pre_render_qweb_pdf
       -> _render_qweb_pdf_prepare_streams        <- override de biocreto_pdf_engine (PlutoPrint)
            -> _biocreto_render_one_pdf
                 -> _render_qweb_html(report_ref, [res_id])
                 -> _biocreto_inline_assets(html)
                 -> plutoprint Book.write_to_pdf
```

El override del módulo de contrato **no toca las firmas**:

```python
# custom_addons/biocreto_sale_reports_contrato/models/ir_actions_report.py:32-42
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == self._BIOCRETO_CONTRATO_REPORT and res_ids:
            orders = self.env['sale.order'].browse(res_ids)
            bad = orders.filtered(lambda o: o.state in ('draft', 'sent', 'cancel'))
            if bad:
                raise UserError(_(
                    "No se puede imprimir el Contrato: la orden %s aun no esta en estado Contrato.",
                    ", ".join(bad.mapped('name')),
                ))
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
```

#### A5 — ★ NÚCLEO: cómo el reporte lee las firmas

Fragmento EXACTO, `biocreto_sale_reports_contrato/report/report_contrato.xml:867-906`:

```xml
        <div class="firmas">
            <div class="firma-recuadro">
                <div class="firma-linea">
                    <img t-if="o.company_id.manager_id.biocreto_firma"
                         t-att-src="image_data_uri(o.company_id.manager_id.biocreto_firma)"
                         class="firma-img"/>
                </div>
                <p class="firma-label">BIOCRETO</p>
                <p class="firma-meta"><t t-out="o.company_id.name or ''"/></p>
                <p class="firma-meta"><t t-out="o.company_id.manager_id.name or ''"/></p>
                <p class="firma-meta"><t t-out="o.company_id.manager_id.partner_id.function or 'Gerente de Sede'"/></p>
            </div>
            <div class="firma-recuadro">
                <div class="firma-linea">
                    <!--
                        v19.0.1.4.0: la fuente paso de o.signature (nativo,
                        compartido con la firma online de la cotizacion) a
                        o.biocreto_firma_contrato (campo propio del contrato,
                        en biocreto_sale_extension). Si el contrato no esta
                        firmado -> el t-if descarta el <img> y queda la
                        linea en blanco; cuando se firme -> aparecera SOLO
                        la firma del contrato, sin pisar la de cotizacion.
                    -->
                    <img t-if="o.biocreto_firma_contrato"
                         t-att-src="image_data_uri(o.biocreto_firma_contrato)"
                         class="firma-img"/>
                </div>
                <p class="firma-label">EL CLIENTE</p>
                <p class="firma-meta"><t t-out="cp.name or ''"/></p>
            </div>
            <div class="firma-recuadro">
                <div class="firma-linea">
                    <img t-if="o.biocreto_firma_jefe_obra"
                         t-att-src="image_data_uri(o.biocreto_firma_jefe_obra)"
                         class="firma-img"/>
                </div>
                <p class="firma-label">V°B° JEFE DE OBRA</p>
                <p class="firma-meta"><t t-out="o.biocreto_firma_jefe_obra_por or ''"/></p>
            </div>
        </div>
```

Lectura línea por línea:

| Línea | Qué hace |
|---|---|
| 869-871 | Recuadro 1 (BIOCRETO): lee `o.company_id.manager_id.biocreto_firma`. **Es una tercera firma**, la del gerente, definida en `biocreto_base/models/res_users.py`. No participa en el bug reportado pero **se rompe por el mismo mecanismo** (ver H1) |
| 889 | Recuadro 2 (CLIENTE): `t-if="o.biocreto_firma_contrato"` — lee el campo Binary **directo del `sale.order`** |
| 890 | `image_data_uri(o.biocreto_firma_contrato)` — construye el `data:` URI |
| 895 | El nombre impreso bajo la firma del cliente **NO es `biocreto_firma_contrato_por`**, es `cp.name`, y `cp` se define en la línea 373 como `o.partner_id.commercial_partner_id`. Es decir: **el nombre que el cliente teclea al firmar no se imprime**; se imprime la razón social del partner |
| 898 | Recuadro 3 (JEFE DE OBRA): `t-if="o.biocreto_firma_jefe_obra"` |
| 899 | `image_data_uri(o.biocreto_firma_jefe_obra)` |
| 903 | Aquí sí se imprime `o.biocreto_firma_jefe_obra_por` — asimetría respecto de la línea 895 |

Respuestas puntuales a lo preguntado:

| Pregunta | Respuesta |
|---|---|
| ¿Lee de un campo Binary en `sale.order`? | **SÍ**, las dos |
| ¿Lee de `sign.item.value` / `sign.request.request_item_ids`? | **NO.** Odoo Sign no interviene |
| ¿Recorre items con `t-foreach` filtrando por rol o nombre? | **NO.** Dos bloques independientes escritos a mano |
| ¿Usa índice fijo `[0]` / `[1]`? | **NO.** Cero índices en todo el bloque de firmas |
| ¿Hay `t-if` que oculten una firma según algún estado? | **Solo** el `t-if` sobre el propio valor del campo. No hay ninguna condición sobre `state`, ni sobre `sign.request`, ni sobre fechas |
| ¿Compara contra el nombre del item? | **NO** |
| ¿Devuelve el PDF completado por Odoo Sign? | **NO.** Se renderiza íntegro desde QWeb |

##### Prueba de render ejecutada (solo lectura, con `rollback()`)

Sobre la orden 20, que tiene las dos firmas guardadas:

```
--- lectura SIN bin_size en contexto ---
  contrato : bytes len=42964 head=b'iVBORw0KGgoA'
  jefe_obra: bytes len=42964 head=b'iVBORw0KGgoA'
--- lectura CON bin_size=True ---
  contrato : bytes len=8 head=b'31.47 Kb'
  jefe_obra: bytes len=8 head=b'31.47 Kb'
--- cache keys ---
  _depends_context: ('bin_size',)
  key sin bin_size  : (False,)
  key bin_size=False: (False,)
  key bin_size=True : (True,)
--- render HTML del contrato ---
  [sin bin_size]   imgs firma-img=3  data-uri=3
      src[:40]= data:image/png;base64,iVBORw0KGgoAAAANSU
      src[:40]= data:image/png;base64,iVBORw0KGgoAAAANSU
      src[:40]= data:image/png;base64,iVBORw0KGgoAAAANSU
  [bin_size=True]  imgs firma-img=3  data-uri=3
      src[:40]= data:image/png;base64,24.12 Kb
      src[:40]= data:image/png;base64,31.47 Kb
      src[:40]= data:image/png;base64,31.47 Kb
ROLLBACK OK - nada escrito
```

> **Modo de fallo REPRODUCIDO.** Con `bin_size=True` el `<img>` **sí se emite** (el `t-if`
> pasa, porque `b'31.47 Kb'` es truthy) pero su `src` es basura: `data:image/png;base64,31.47 Kb`.
> El navegador / PlutoPrint no puede decodificarlo → **hueco en blanco donde debería ir la firma,
> con el dato perfectamente guardado en la base.** Esa es, letra por letra, la descripción
> que dio el usuario: *"internamente la firma y el nombre SÍ quedan guardados; el reporte no lo muestra"*.

También queda **refutada** una sospecha razonable: las claves de caché `sin bin_size` y
`bin_size=False` son la misma `(False,)`, así que no hay desincronización de caché entre
el `write()` (que fuerza `bin_size=False`, `odoo/orm/fields_binary.py:185`) y una lectura posterior.

Dónde se inyecta `bin_size=True` en el framework:

```python
# odoo/addons/web/controllers/action.py:45-46
        if action_type == 'ir.actions.report':
            request.update_context(bin_size=True)
```

```js
// odoo/addons/web/static/src/model/relational_model/relational_model.js:651
                context: { bin_size: true, ...context },
```

Y el punto por donde ese contexto podría llegar al render:

```python
# odoo/addons/web/controllers/report.py:34-41
        if data.get('context'):
            data['context'] = json.loads(data['context'])
            context.update(data['context'])
        ...
        elif converter == 'pdf':
            pdf = report.with_context(context)._render_qweb_pdf(reportname, docids, data=data)[0]
```

El contexto que el cliente web manda en el flujo estándar es:

```js
// odoo/addons/web/static/src/webclient/actions/action_service.js:1362-1365
                const downloadContext = { ...user.context };
                if (action.context) {
                    Object.assign(downloadContext, action.context);
                }
```

→ `user.context` (lang, tz, uid, allowed_company_ids) más el contexto de la acción.
**En el camino estándar `bin_size` no debería llegar.** Por eso H1 es una hipótesis y no
un hecho: falta comprobar con qué contexto real se renderiza en el momento del fallo (§4.4).

#### A6 — Estructura real en base de datos

**`sign.template` / `sign.item` / `sign.item.value` / `sign.request`: NO APLICA.**
El módulo `sign` está instalado (`ir_module_module.state = 'installed'`) pero el contrato
de BIOCRETO no lo usa: `sale_order` no tiene `sign_request_id` (ver A2) y no existe ningún
`_inherit` de `sign.*` en el proyecto (ver A8).

**Órdenes con firma de contrato en la base — LAS DOS ÚNICAS:**

```sql
SELECT so.id, so.name, so.state,
       so.biocreto_firma_contrato_por,  so.biocreto_firma_contrato_fecha,
       so.biocreto_firma_jefe_obra_por, so.biocreto_firma_jefe_obra_fecha
FROM sale_order so
WHERE so.biocreto_firma_contrato_fecha IS NOT NULL
   OR so.biocreto_firma_jefe_obra_fecha IS NOT NULL;
```
```
 id |       name       |   state    | firma_contrato_por    | firma_contrato_fecha | firma_jefe_obra_por   | firma_jefe_obra_fecha
----+------------------+------------+-----------------------+----------------------+-----------------------+-----------------------
 20 | 2026-ECO-PS-0020 | sale       | Piter Parker Suares   | 2026-07-01 18:05:18  | Piter Parker Suares   | 2026-07-01 18:05:18
 28 | 2026-ECO-PS-0028 | programado | Felipe Marquez Solis  | 2026-08-07 02:55:03  | Felipe Marquez Solis  | 2026-08-07 02:55:03
```

**Los blobs de firma** (`res_field` no nulo = campo Binary con `attachment=True`):

```
  id  | res_field                | res_id | file_size | create_date                | write_date                 | db_datas | store_fname
------+--------------------------+--------+-----------+----------------------------+----------------------------+----------+-------------
 1257 | biocreto_firma_contrato  |     20 |     32222 | 2026-07-01 18:05:18.296874 | 2026-07-01 18:05:18.296874 | NULL     | sí
 1258 | biocreto_firma_jefe_obra |     20 |     32222 | 2026-07-01 18:05:18.296874 | 2026-07-01 18:05:18.296874 | NULL     | sí
 1255 | signature                |     20 |     17746 | 2026-07-01 17:57:34.590229 | 2026-07-01 17:57:34.590229 | NULL     | sí
 1388 | biocreto_firma_contrato  |     28 |     20726 | 2026-08-07 02:55:03.475240 | 2026-08-07 02:55:03.475240 | NULL     | sí
 1389 | biocreto_firma_jefe_obra |     28 |     20726 | 2026-08-07 02:55:03.475240 | 2026-08-07 02:55:03.475240 | NULL     | sí
 1386 | signature                |     28 |     19951 | 2026-08-07 02:54:12.467763 | 2026-08-07 02:54:12.467763 | NULL     | sí
```

> **HALLAZGO DECISIVO PARA EL PLAN DE PRUEBAS.** En las dos órdenes:
> · `create_date` **idéntico al microsegundo** en las dos firmas;
> · `file_size` **idéntico** (32222 / 32222 y 20726 / 20726) → el mismo trazo replicado;
> · `write_date == create_date` → nunca se re-escribieron.
>
> Es decir: **las dos se firmaron con el botón "Firmar Ambos"** (`kind='ambos'`, un solo
> `write`). **NO existe en esta base una sola orden firmada una-por-una**, que es
> justamente el escenario B. Por eso el diferencial A vs B **no se puede aislar con los
> datos actuales** y hace falta el protocolo del §4.4.

Todas las firmas están **en el filestore** (`db_datas` NULL, `store_fname` poblado).
Relevante: la lectura pasa por disco, no por la columna `bytea`.

Roles: **no hay `sign.item.role`** que consultar (no aplica). Los "roles" de este flujo
son literales de Python en `portal.py:204-215`: `'cliente'`, `'jefe_obra'`, `'ambos'`.

#### A7 — ¿Se regenera el documento?

**No se crea ningún `sign.request`** (no existe el concepto aquí). Lo que sí ocurre es que
al completarse la segunda firma se **renderiza un PDF y se adjunta al chatter**
(`portal.py:269-285`). Adjuntos NO-campo de las dos órdenes:

```
  id  | res_id |             name              |    mimetype     | file_size | create_date
------+--------+-------------------------------+-----------------+-----------+----------------------------
 1256 |     20 | 2026-ECO-PS-0020.pdf          | application/pdf |    180057 | 2026-07-01 17:57:34.590229
 1259 |     20 | Contrato_2026-ECO-PS-0020.pdf | application/pdf |    459018 | 2026-07-01 18:05:18.296874
 1387 |     28 | 2026-ECO-PS-0028.pdf          | application/pdf |    176159 | 2026-08-07 02:54:12.467763
 1390 |     28 | Contrato_2026-ECO-PS-0028.pdf | application/pdf |    442836 | 2026-08-07 02:55:03.475240
```

Lectura:

- `<orden>.pdf` = PDF de la **cotización**, adjuntado por `/accept` (`portal.py:76-94`), 7-8 minutos antes.
- `Contrato_<orden>.pdf` = PDF del **contrato**, adjuntado en la rama combinada, mismo microsegundo que los blobs de firma.
- **Un solo `Contrato_*.pdf` por orden. Sin duplicados.**

**Consecuencia operativa importante:** ese `Contrato_*.pdf` del chatter se genera **una
única vez**, en el instante de completarse la firma, y **nunca se regenera**. Si en ese
render faltó una firma, el adjunto queda mal **para siempre**, aunque el dato esté bien y
aunque el reporte impreso posteriormente salga correcto. Cualquier prueba tiene que
distinguir **el PDF del chatter** del **PDF impreso en vivo**: no son el mismo objeto.

En el escenario B además hay una asimetría de comportamiento: **la primera firma NO
adjunta ningún PDF** (cae en la rama `else`, `portal.py:286-302`); solo la segunda lo hace.

#### A8 — Overrides de Sign

```
$ grep -rn "_inherit.*sign\.\|sign\.request\|sign\.template\|sign\.item\|/sign/" custom_addons/
(sin resultados)
```

**Cero.** No hay herencia de `sign.request`, `sign.request.item`, `sign.template`,
`sign.item`, `sign.item.value`, ni de ningún controller `/sign/...`.

---

### 4.2 Flujo de firma tal como está en el código, sin idealizar

1. La orden llega a `state='contract'`. En esa transición, `action_confirm` de
   `biocreto_sale_contract_state` escribe `biocreto_fecha_firma_contrato = hoy`
   (`sale_order.py:185`) — **la fecha se estampa al entrar al estado, no al firmar**.
   El reporte imprime esa fecha (`report_contrato.xml:394` → `:860-866`), no la de la
   firma real. Si el contrato se firma otro día, el PDF muestra el día equivocado.

2. El cliente entra a `/my/orders/<id>?access_token=...`. El bloque
   "Contrato de Suministro" se renderiza si `state in ('contract','programado','sale')`
   (`portal_templates.xml:149`).

3. Ve tres botones: **Firmar como Cliente**, **Firmar como Jefe de Obra**, **Firmar Ambos**
   (`portal_templates.xml:212-226`). No son modales: **cada botón recarga la página** con
   `?sign=<kind>`, y solo entonces se renderiza **un** widget `portal.signature_form`
   (`:229-252`). La decisión está documentada en el propio template: evitar colisión de
   IDs del componente OWL si hubiera dos widgets a la vez.

4. Al enviar, el OWL llama `/my/orders/<id>/sign_contract/<kind>` con `name` y `signature`
   (base64 puro, sin prefijo `data:`).

5. El controller (`portal.py:189`):
   - arma `vals` según `kind`. **Con `kind='ambos'` el MISMO trazo se replica a los dos
     juegos de campos** (`portal.py:204-215`) — de ahí los `file_size` idénticos del §A6;
   - toma el snapshot `cli_antes` / `jo_antes` **antes** del write;
   - `write(vals)` + `cr.flush()`;
   - recalcula la completitud **desde `vals`**, no releyendo (fix documentado en el propio
     código, `portal.py:235-243`);
   - si acaba de pasar de incompleto a completo → **renderiza el PDF dentro de la misma
     transacción** y lo adjunta al chatter;
   - si no → mensaje corto **sin PDF**;
   - redirige con `&message=contract_signed`.

6. El PDF se puede obtener por tres caminos distintos, y **no son intercambiables**:
   - **chatter**: `Contrato_*.pdf`, generado una sola vez (§A7);
   - **portal**: `/my/contracts/<id>/pdf`, re-renderiza en cada visita, **sin cabeceras de caché**;
   - **backend**: botón Imprimir → `/report/download` → acción 1179, re-renderiza siempre.

7. En los tres casos el render pasa por PlutoPrint
   (`biocreto_pdf_engine/models/ir_actions_report.py:74`), que renderiza **un HTML por
   `res_id`** y hace fallback silencioso a wkhtmltopdf si algo revienta
   (`:109-121`, con `_logger.exception`). **Un fallo de PlutoPrint no aborta: degrada.**

**Puntos frágiles del flujo, dichos sin adornos:**

- El nombre del cliente que se teclea al firmar (`biocreto_firma_contrato_por`) **no se
  imprime en el PDF**; el recuadro EL CLIENTE muestra `cp.name` (`report_contrato.xml:895`).
  El del jefe de obra sí se imprime (`:903`). Asimetría no documentada.
- La fecha impresa es la de entrada al estado, no la de la firma (punto 1).
- El PDF del chatter se congela en el primer render.
- La descarga del portal no manda cabeceras de caché.
- El render del chatter ocurre **dentro de la transacción de escritura**.

---

### 4.3 HIPÓTESIS DEL BUG

> **Advertencia previa, honesta:** ninguna de las tres hipótesis explica hoy, por sí sola
> y con la evidencia disponible, **por qué el escenario A funciona y el B no**. El motivo
> es concreto y verificable: **no existe en la base ninguna orden firmada una-por-una**
> (§A6) — las dos que hay se firmaron con "Firmar Ambos". Sin ese dato no se puede
> comparar. Las hipótesis están ordenadas por fuerza de la evidencia que las sostiene, y
> el §4.4 está diseñado exactamente para elegir entre ellas.
>
> Lo que **sí** está establecido: **no es un typo** (A1), **no es un índice fijo** (A5),
> **no es Odoo Sign** (A2/A8), **no es caché de reporte de Odoo** (A4), y **no es
> `action_draft`** (A3, borra las dos a la vez).

---

#### H1 — El render del reporte recibe `bin_size=True` y las firmas salen como `data:image/png;base64,31.47 Kb`

**Qué la sustenta:**
- **Está reproducido.** Render real de la orden 20 con `bin_size=True` en el contexto:
  `src="data:image/png;base64,31.47 Kb"` (§A5). `<img>` presente, imagen invisible, dato
  intacto en BD. Es exactamente la forma del síntoma.
- `odoo/orm/fields_binary.py:39` — `_depends_context = ('bin_size',)`; `:100-108` —
  con `bin_size` el valor se sustituye por `human_size(...)`.
- `odoo/addons/web/controllers/action.py:45-46` — Odoo **inyecta `bin_size=True`
  deliberadamente** cuando la acción cargada es de tipo reporte.
- `odoo/addons/web/static/src/model/relational_model/relational_model.js:651,680` — el
  cliente web lee los registros con `bin_size: true`.
- `odoo/addons/web/controllers/report.py:34-41` — el contexto que llega del cliente se
  **mezcla** en el contexto de render: `context.update(data['context'])`.
- `odoo/tools/image.py:556-564` — `image_data_uri` no valida: concatena lo que reciba.

**Qué la refutaría:**
- Que en el PDF fallido **falte el `<img>` entero** en lugar de aparecer un `<img>` roto.
  Con `bin_size` el `t-if` **pasa** (la cadena es truthy), así que la etiqueta existe.
  Extraer el HTML intermedio o inspeccionar el PDF fallido lo dirime en un minuto.
- Que fallen **una sola** firma y no las tres. En mi prueba `bin_size` afecta a las tres
  a la vez (BIOCRETO, CLIENTE, JEFE DE OBRA). Si el usuario confirma que la firma
  "BIOCRETO" (la del gerente) **sí sale** en el PDF fallido, H1 queda muy debilitada.

**Qué la confirmaría:**
- Loguear el contexto efectivo en el momento del render fallido y ver `bin_size: True`.
- Reproducir con `bin_size=True` y comparar el PDF resultante con el que reporta el usuario.
- Que en el PDF fallido las **tres** firmas estén ausentes (no dos).

---

#### H2 — El PDF que el usuario mira en el escenario B es una respuesta cacheada por el navegador

**Qué la sustenta:**
- `portal.py:339-343` — la respuesta de `/my/contracts/<id>/pdf` lleva **solo**
  `Content-Type`, `Content-Length` y `Content-Disposition`. **Ni `Cache-Control`, ni
  `ETag`, ni `Last-Modified`, ni un parámetro que cambie la URL.** La URL es idéntica
  antes y después de firmar.
- `portal_templates.xml:158-162` — el enlace de descarga abre `target="_blank"`. En el
  escenario B ("firmar uno → salir → volver → firmar el otro") es natural haber abierto
  ese PDF entre medias; en el A ("de corrido") no se abre hasta el final.
- **Esto sí discrimina A de B**, que es justo lo que a H1 le falta: el escenario B tiene
  una descarga intermedia que el A no tiene.
- Encaja con "el dato SÍ está guardado": el servidor está bien; lo que se mira es viejo.

**Qué la refutaría:**
- Que el fallo se reproduzca con `Ctrl+Shift+R`, en ventana de incógnito o desde otro
  navegador. Si con caché limpia sigue faltando la firma, H2 muere.
- Que el fallo aparezca al imprimir **desde el backend** (otra URL, otro flujo).

**Qué la confirmaría:**
- Que el PDF salga completo al forzar recarga o al añadir un parámetro cualquiera a la URL.
- Ver un `304` o `(from disk cache)` en la pestaña Network del navegador.

---

#### H3 — El usuario está mirando el `Contrato_*.pdf` del chatter, que se congela en el primer render

**Qué la sustenta:**
- `portal.py:254` — el PDF se adjunta **solo** cuando se pasa de incompleto a completo, y
  **una sola vez**. Nada lo regenera después.
- BD (§A7): exactamente **un** `Contrato_*.pdf` por orden, `create_date` = microsegundo de
  la firma. Sin duplicados, sin regeneraciones.
- El render ocurre **dentro de la misma transacción del `write`** (`portal.py:228-272`).
  El propio módulo documenta en `portal.py:235-243` que en la v19.0.1.3.0 el read-back
  inmediato de estos `Binary(attachment=True)` **devolvía falsy** en este mismo camino de
  código; se corrigió el *guard* derivándolo de `vals`, pero **el render sigue leyendo del
  ORM** — si esa lectura vuelve a fallar, `t-if` descarta el `<img>` y esa firma no sale.
- En el escenario B, la primera firma **no adjunta PDF** (rama `else`), así que el único
  PDF del chatter es el de la segunda — precisamente el render en riesgo.

**Qué la refutaría:**
- Que el usuario esté imprimiendo desde el botón del backend o desde el enlace del portal,
  no abriendo el adjunto del chatter. Basta preguntárselo.
- Que el `Contrato_*.pdf` del chatter salga correcto y el impreso en vivo no.

**Qué la confirmaría:**
- Que el PDF **del chatter** tenga la firma faltante pero al pulsar Imprimir en el backend
  el PDF salga completo. Eso localiza el fallo en el render en-transacción y deja limpio
  todo lo demás.
- El `flush()` de `portal.py:231` fue añadido precisamente para este problema; que siga
  ocurriendo indicaría que no basta.

---

### 4.4 Protocolo de prueba A/B (Paso 5) — para ejecutar

> **Objetivo:** aislar si la diferencia entre A y B está en el **dato guardado** o en el
> **renderizado**, y de paso decidir entre H1/H2/H3.
>
> **Regla de oro:** en cada impresión, anotar **por cuál de los tres caminos** se obtuvo
> el PDF, porque son objetos distintos (§A7):
> **(a)** adjunto `Contrato_*.pdf` del chatter · **(b)** botón *Descargar Contrato (PDF)*
> del portal · **(c)** botón Imprimir → *Contrato de Suministro* en el backend.

#### Preparación

0. Crear **dos** cotizaciones equivalentes y llevarlas a estado **Contrato**. Anotar sus
   ids. Llamarlas ORDEN_A y ORDEN_B.
1. Abrir el navegador en **incógnito** para la ORDEN_B (neutraliza H2 en la primera pasada;
   luego se repite sin incógnito para probarla).

#### ESCENARIO A — firmar los dos de corrido

1. Entrar a `/my/orders/<ID_A>?access_token=...`.
2. **Firmar como Cliente** → firmar → enviar.
3. Sin salir del portal, **Firmar como Jefe de Obra** → firmar → enviar.
4. Imprimir por los **tres** caminos (a), (b), (c) y guardar los tres PDF con nombres
   `A_chatter.pdf`, `A_portal.pdf`, `A_backend.pdf`.
5. Anotar, para cada uno, **cuántos de los tres recuadros** (BIOCRETO / EL CLIENTE /
   V°B° JEFE DE OBRA) muestran firma. **El recuadro BIOCRETO importa**: es el discriminador
   de H1.

#### ESCENARIO B — firmar uno por uno, saliendo en medio

1. Entrar a `/my/orders/<ID_B>?access_token=...`.
2. **Firmar como Cliente** → firmar → enviar.
3. **Imprimir por (b)** y guardar como `B1_portal.pdf`. *(Esto crea la condición de H2.)*
4. **Cerrar el navegador por completo.**
5. Volver a entrar a `/my/orders/<ID_B>?access_token=...`.
6. **Firmar como Jefe de Obra** → firmar → enviar.
7. Imprimir por los tres caminos: `B2_chatter.pdf`, `B2_portal.pdf`, `B2_backend.pdf`.
8. **Repetir el paso 7 con `Ctrl+Shift+R`** (recarga forzada) → `B2_portal_nocache.pdf`.

#### Consultas a correr DESPUÉS de cada escenario

Reemplazar `<ID>` por el id de la orden. Se corren con:

```
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -p 5432 -U odoobiocreto -d Prueba
```

**Q1 — estado de los campos de firma (¿el dato está?):**

```sql
SELECT id, name, state,
       biocreto_firma_contrato_por,  biocreto_firma_contrato_fecha,
       biocreto_firma_jefe_obra_por, biocreto_firma_jefe_obra_fecha,
       biocreto_fecha_firma_contrato
FROM sale_order WHERE id = <ID>;
```

**Q2 — los blobs (¿existen, con qué tamaño, escritos cuándo?):**

```sql
SELECT id, res_field, res_id, file_size, create_date, write_date,
       (db_datas IS NOT NULL) AS en_columna,
       (store_fname IS NOT NULL) AS en_filestore, checksum
FROM ir_attachment
WHERE res_model = 'sale.order' AND res_id = <ID> AND res_field IS NOT NULL
ORDER BY res_field;
```

> **Qué mirar:** en el escenario B los dos `create_date` deben **diferir** (eso confirma
> que se firmó una por una, a diferencia de las órdenes 20 y 28). Si los `checksum` de
> ambas firmas son iguales, se firmó el mismo trazo. Si un `file_size` es 0 o la fila
> falta, el problema es de **guardado** y no de reporte.

**Q3 — PDFs adjuntos generados (¿cuántos, cuándo, de qué tamaño?):**

```sql
SELECT id, name, mimetype, file_size, create_date
FROM ir_attachment
WHERE res_model = 'sale.order' AND res_id = <ID> AND res_field IS NULL
ORDER BY create_date;
```

**Q4 — mensajes del chatter (¿qué rama del controller se ejecutó?):**

```sql
SELECT m.id, m.date, m.body, count(a.id) AS adjuntos
FROM mail_message m
LEFT JOIN message_attachment_rel r ON r.message_id = m.id
LEFT JOIN ir_attachment a ON a.id = r.attachment_id
WHERE m.model = 'sale.order' AND m.res_id = <ID>
GROUP BY m.id, m.date, m.body ORDER BY m.date;
```

> **Qué mirar:** el cuerpo *"firmado por el cliente (...)"* con **0 adjuntos** = rama
> simple; *"firmado por X y Z"* con **1 adjunto** = rama combinada. En B deben verse
> las dos, en ese orden. Si en B **nunca** aparece la rama combinada, el fallo está en
> el guard de completitud (`portal.py:244-246`), no en el reporte.

**Q5 — comparar A contra B de un vistazo:**

```sql
SELECT so.id, so.name,
       (SELECT count(*) FROM ir_attachment a
         WHERE a.res_model='sale.order' AND a.res_id=so.id AND a.res_field LIKE 'biocreto_firma%') AS blobs_firma,
       (SELECT count(*) FROM ir_attachment a
         WHERE a.res_model='sale.order' AND a.res_id=so.id AND a.res_field IS NULL
           AND a.name LIKE 'Contrato_%') AS pdfs_contrato,
       (SELECT string_agg(to_char(a.create_date,'HH24:MI:SS.US'), ' | ' ORDER BY a.res_field)
          FROM ir_attachment a
         WHERE a.res_model='sale.order' AND a.res_id=so.id AND a.res_field LIKE 'biocreto_firma%') AS momentos
FROM sale_order so WHERE so.id IN (<ID_A>, <ID_B>);
```

#### Tabla de decisión

| Observación | Conclusión |
|---|---|
| Q2 muestra **las dos filas con `file_size > 0`** y aun así falta una firma en algún PDF | El guardado está bien → **es render**. Seguir con las filas de abajo |
| Falta una fila en Q2, o `file_size = 0` | Es **guardado**, no reporte. Descartar H1/H2/H3 y mirar `portal.py:228` |
| En el PDF fallido faltan **las TRES** firmas (incluida BIOCRETO) | **H1** (`bin_size`) |
| Falta solo una y la de BIOCRETO **sí sale** | H1 debilitada → mirar **H2/H3** |
| `B2_portal.pdf` falla pero `B2_portal_nocache.pdf` sale bien | **H2** (caché de navegador) |
| `B2_chatter.pdf` falla pero `B2_backend.pdf` sale bien | **H3** (render en-transacción) |
| Los tres PDF de B fallan igual y con caché limpia | Ni H2 ni H3 → **H1** o algo no contemplado; capturar el HTML intermedio |
| En Q4 de B **nunca** aparece un mensaje con adjunto | El guard de completitud no dispara → `portal.py:244-246` |

---

## 5. Campos Studio vs código (Bloque B)

### B1 — `ir.model.fields` con `state='manual'`

```sql
SELECT model, name, field_description->>'en_US' AS label, ttype, relation,
       related, store, selectable, required, readonly
FROM ir_model_fields WHERE state='manual' ORDER BY model, name;
```
```
 model | name | label | ttype | relation | related | store | selectable | required | readonly
-------+------+-------+-------+----------+---------+-------+------------+----------+----------
(0 filas)
```

**CERO campos manuales en TODA la base**, no ya en `sale.order` / `sale.order.line` /
`res.partner` / `crm.lead`. La consulta de valores de selección manual también devuelve 0 filas.

> **Conclusión limpia: no hay un solo campo de Studio en el proyecto. Todo es código.**

### B2 — Vistas de `studio_customization`

```
        module        |  id  |           model            | type | inherit_id | active | arch_len
----------------------+------+----------------------------+------+------------+--------+----------
 studio_customization | 4046 | sale.order                 | form |       1469 | t      |      391
 studio_customization | 4062 | biocreto.documento.control | form |       4060 | t      |      204
 studio_customization | 4137 | purchase.order             | form |       1654 | t      |      181
 studio_customization | 4197 | biocreto.requerimiento     | form |       4196 | t      |      483
 studio_customization | 4043 | (qweb, sin modelo)         | qweb |            | t      |      298
 studio_customization | 4044 | (qweb, sin modelo)         | qweb |            | t      |      882
 studio_customization | 4069 | (qweb, sin modelo)         | qweb |            | t      |      298
 studio_customization | 4070 | (qweb, sin modelo)         | qweb |            | t      |      882
 studio_customization | 4081 | (qweb, sin modelo)         | qweb |            | t      |      298
 studio_customization | 4082 | (qweb, sin modelo)         | qweb |            | t      |      882
```

Las cuatro vistas form son **retoques cosméticos**, y ninguna toca firmas, banco, slump ni
ubicación salvo un `required` sobre la calle:

```xml
<!-- ir_ui_view 4046 — sale.order form, hereda 1469 -->
<data>
  <xpath expr="/form//field[@name='biocreto_street']" position="attributes">
    <attribute name="required">True</attribute>
  </xpath>
  <xpath expr="/form//field[@name='biocreto_fecha_vaceo_inicio']" position="attributes">
    <attribute name="options">{"end_date_field":"biocreto_fecha_vaceo_fin","numeric":true}</attribute>
  </xpath>
</data>
```

```xml
<!-- 4137 purchase.order --> date_order -> options {"numeric":true}
<!-- 4062 biocreto.documento.control --> fecha_version -> options {"numeric":true}
<!-- 4197 biocreto.requerimiento --> fecha, fecha_inicio, fecha_fin -> options {"numeric":true}
```

> **Ojo con la 4046:** hace `biocreto_street` **obligatorio** desde Studio. Si mañana se
> toca la dirección de obra (punto E), este `required` invisible en el código es lo que
> hará fallar un guardado sin explicación aparente.

Las seis vistas qweb son **huérfanas**: ninguna fila de `ir_act_report_xml` las referencia
(consulta ejecutada, 0 filas), y sus `arch` de 298/882 caracteres son los esqueletos que
Studio crea al empezar un reporte y abandonarlo.

### B3 — Studio vs código

| Campo personalizado | ¿Studio o código? | Modelo | Archivo/registro |
|---|---|---|---|
| `biocreto_firma_contrato` (+ `_por`, `_fecha`) | **Código** | `sale.order` | `biocreto_sale_extension/models/sale_order.py:116-126` |
| `biocreto_firma_jefe_obra` (+ `_por`, `_fecha`) | **Código** | `sale.order` | `biocreto_sale_extension/models/sale_order.py:102-107` |
| `biocreto_fecha_firma_contrato` | **Código** | `sale.order` | `biocreto_sale_contract_state/models/sale_order.py:43` |
| `biocreto_slump` | **Código** | `sale.order.line` | `biocreto_sale_extension/models/sale_order_line.py:41-44` |
| `biocreto_slump_bombeable` | **Código** | `sale.order.line` | `biocreto_sale_extension/models/sale_order_line.py:58-61` |
| `biocreto_latitud`, `biocreto_longitud` | **Código** | `sale.order` | `biocreto_sale_extension/models/sale_order.py:62-72` |
| `biocreto_gmaps_url` | **Código** (compute, no-store) | `sale.order` | `biocreto_sale_extension/models/sale_order.py:142-161` |
| `biocreto_street`, `biocreto_direccion_completa`, `biocreto_state_id`, `biocreto_city_id`, `biocreto_district_id` | **Código** | `sale.order` | `biocreto_sale_extension/models/sale_order.py:20-42` |
| `biocreto_cci` | **Código** | `res.partner.bank` | `biocreto_base/models/res_partner_bank.py:7-10` |
| `biocreto_firma` (del gerente) | **Código** | `res.users` | `biocreto_base/models/res_users.py` |
| `plant_code`, `manager_id` | **Código** | `res.company` | `biocreto_base/models/res_company.py` |
| — cualquier campo de Studio — | **NO EXISTE** | — | 0 filas en `ir_model_fields` con `state='manual'` |
| `biocreto_street` obligatorio | **Studio (atributo, no campo)** | `sale.order` | `ir_ui_view` **4046** |

---

## 6. Bloque de cuentas bancarias (Bloque C)

### C1 — Localización

**En código**, el bloque aparece en **dos** reportes:

| Archivo:línea | Reporte |
|---|---|
| `biocreto_sale_report_cotizacion/report/report_cotizacion.xml:874-903` | Cotización — banda "Cuentas Bancarias · Soles" |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:681-710` | Contrato — cláusula **4.4** |

**En BD**, las mismas dos plantillas instaladas: `ir_ui_view` **4089**
(`biocreto_sale_report_cotizacion.cot_body_mayor`) y **4092**
(`biocreto_sale_reports_contrato.contrato_body`). Ninguna de Studio.

**`2045643545646`: CERO ocurrencias.** Ni en código, ni en `ir_ui_view.arch_db`, ni en
`res_partner_bank.acc_number`. Ese número **no existe en este proyecto** — o viene de una
versión anterior, o de otra base, o de un documento en papel.

*(Nota: el grep inicial por `CCI` da mucho ruido porque `ILIKE '%cci%'` también matchea
"acción"/"accion". Los resultados de arriba son con la búsqueda afinada a `biocreto_cci`.)*

### C2 — Fragmento completo

**Cotización** — `biocreto_sale_report_cotizacion/report/report_cotizacion.xml:874-903`
(módulo, no Studio):

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

Comentario del propio autor unas líneas antes (`:824-826`):

```
cuentas bancarias el bloque deja de caber en una A4, hay que
relajar `break-inside: avoid` a las cuentas (que pueden
partirse). Por ahora confiamos en que cabe (max 4 cuentas).
```

> Hay exactamente **4** cuentas en la base, 3 de ellas de BIOCRETO. El margen está agotado.

**Contrato** — `biocreto_sale_reports_contrato/report/report_contrato.xml:681-710`,
misma tabla dentro de la cláusula 4.4:

```xml
            <li>
                <span class="num">4.4.</span>
                <span class="text">
                    Los pagos pueden realizarse directamente en nuestras cuentas corrientes siguientes:
                    <table class="cuentas-table">
                        <thead>
                            <tr><th>Banco</th><th>Moneda</th><th>Cta. Corriente</th><th>CCI</th></tr>
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
                </span>
            </li>
```

Son **dos copias literales**. Un cambio de diseño hay que aplicarlo en los dos sitios.

### C3 — ¿Hardcodeado o de registros?

**De registros.** Origen exacto:

| Columna impresa | De dónde sale |
|---|---|
| Banco | `res.partner.bank.bank_id.name` (modelo `res.bank`), con fallback a `bank_name` |
| Moneda | **HARDCODEADA** — el literal `Soles` en el `<td>`. **No** lee `bank.currency_id` |
| Cta. Corriente | `res.partner.bank.acc_number` |
| CCI | `res.partner.bank.biocreto_cci` — campo propio de BIOCRETO |
| Qué cuentas se listan | `o.company_id.bank_ids` → **todas** las cuentas del partner de la compañía |

```python
# custom_addons/biocreto_base/models/res_partner_bank.py:7-10
    biocreto_cci = fields.Char(
        string="CCI",
        help="Codigo de Cuenta Interbancario (CCI).",
    )
```

> **Dos cosas que hay que saber antes de tocar esto:**
> 1. **"Soles" es texto fijo.** Si algún día hay una cuenta en dólares, se imprimirá
>    igualmente como Soles. Y el título de la cotización dice "Cuentas Bancarias · Soles".
> 2. **No hay filtro por moneda ni por compañía.** `company_id.bank_ids` trae todas las
>    cuentas del partner de la compañía. Hoy da 3 y salen bien; el día que se añada una
>    cuenta en otra moneda, entrará al PDF sin avisar.

### C4 — Dump de BD

**`res.partner.bank` — 4 registros:**

```
 id |     acc_number      |       biocreto_cci       | bank_id |             banco              | partner_id | titular  | currency_id | company_id | allow_out_payment
----+---------------------+--------------------------+---------+--------------------------------+------------+----------+-------------+------------+-------------------
  1 | 355 5028342 0 90    | 002 355 005028342090  64 |      20 | Banco de Crédito del  Perú BCP |          1 | Biocreto |         156 |     (NULL) | t
  2 | 0011 02370100045620 | 011 237 00010004562050   |      21 | Banco Continental  BBVA        |          1 | Biocreto |         156 |     (NULL) | t
  3 | 0004455922          | 009 423 000004455922 57  |      22 | Scotiabank  Perú               |          1 | Biocreto |         156 |     (NULL) | t
  4 | 194-1234567-0-00    | 002-194-001234567000-95  |      20 | Banco de Crédito del  Perú BCP |         18 | UNACEM   |         156 |     (NULL) | t
```

Notas sobre los datos, tal cual están:
- **3 cuentas de BIOCRETO** (partner 1) → son las que salen en los PDF. La 4ª es de UNACEM (proveedor) y **no** sale.
- `company_id` es **NULL en las cuatro** → cuentas no asignadas a compañía.
- `currency_id = 156` en las cuatro. Los nombres de banco tienen **dobles espacios**
  ("Crédito del  Perú", "Continental  BBVA", "Scotiabank  Perú") — se imprimen tal cual.

**`res.company` — 1 registro. Instalación MONOCOMPAÑÍA:**

```
 id |   name   |     vat     | currency_id | l10n_latam_identification_type_id | plant_code
----+----------+-------------+-------------+-----------------------------------+------------
  1 | Biocreto | 20605252401 |         156 |                                 4 | ECO
```

### C5 — Localización peruana

```
         name          |    state    | latest_version
-----------------------+-------------+----------------
 l10n_pe               | installed   | 19.0.3.1
 l10n_pe_edi           | installed   | 19.0.0.1
 l10n_pe_reports       | installed   | 19.0.1.0
 l10n_pe_edi_pos       | uninstalled |
 l10n_pe_edi_stock     | uninstalled |
 l10n_pe_pos           | uninstalled |
 l10n_pe_reports_lib   | uninstalled |
 l10n_pe_reports_stock | uninstalled |
```

| Pregunta | Respuesta |
|---|---|
| ¿Dónde se guarda el RUC? | En el campo nativo **`res_partner.vat`** (`= '20605252401'`), con el **tipo** de documento en `res_partner.l10n_latam_identification_type_id` (= 4). No hay campo propio de RUC |
| ¿Cuántas compañías? | **UNA: `Biocreto`** (id 1, `plant_code='ECO'`). **No es multiempresa** |

`biocreto_base` complementa esto autoseleccionando DNI/RUC según `is_company` cuando el
país es Perú (`biocreto_base/models/res_partner.py:10`).

---

## 7. Slump: inventario de usos (Bloque D)

### D1 — Grep

`slump` / `asentamiento` / `revenimiento` / `x_studio_slump`, sin distinguir mayúsculas:

- **`x_studio_slump`: CERO ocurrencias.** No es un campo de Studio (coherente con B1: no hay ninguno).
- **`revenimiento`: CERO ocurrencias.**
- `asentamiento`: 2 ocurrencias, **solo texto legal** en el contrato
  (`report_contrato.xml:563` y `:565`), sin relación con el campo.
- `slump`: las que se detallan abajo.

### D2 — Definición

**Hay TRES campos y un modelo. No es uno solo.**

**(1) `sale.order.line.biocreto_slump` — el principal**

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
| Tipo | `Float`, `digits=(5, 2)` |
| `string` | `"Slump (pulg.)"` |
| `help` | **ninguno** |
| `required` | **No** (la obligatoriedad se aplica en `_biocreto_validate_before_confirm`) |
| Unidad implícita | **PULGADAS**, declarada solo en el `string` |
| Origen | **Código** |

**(2) `sale.order.line.biocreto_slump_bombeable`**

```python
# custom_addons/biocreto_sale_extension/models/sale_order_line.py:58-61
    biocreto_slump_bombeable = fields.Float(
        string="Slump bombeable (pulg.)",
        digits=(5, 2),
    )
```

Mismo tipo y precisión, sección de **BOMBEO**. Código.

**(3) `biocreto.slump.valor` — el ensayo de laboratorio**

```python
# custom_addons/biocreto_laboratorio/models/slump.py:37
    valor = fields.Float(string="Slump (pulg.)", digits=(5, 2))
```

Modelo propio `biocreto.slump` (`slump.py:4-44`): ensayo por mixer, con `sale_line_id`
(required, ondelete cascade), `mixer_id` (`fleet.vehicle`), `tipo` (Selection
`planta`/`obra`, default `planta`), `fecha`, `observaciones`, y `name` autogenerado con el
patrón `L{pos}-{corr}-{fc}-M{n}-SLP0{1|2}` (`slump.py:71-79`).

**(4) `sale.order.biocreto_slump_count`** — `Integer` compute, no almacenado, solo para el
stat button (`biocreto_laboratorio/models/sale_order.py:14-16`).

> **Ninguno es `Selection`.** No hay lista de valores posibles que pegar.
> **Ninguno es de Studio.**

### D3 — Inventario exhaustivo de usos

| Archivo:línea | Tipo de uso | Detalle |
|---|---|---|
| `biocreto_sale_extension/models/sale_order_line.py:41-44` | **Definición** | `biocreto_slump` (Float) |
| `biocreto_sale_extension/models/sale_order_line.py:58-61` | **Definición** | `biocreto_slump_bombeable` (Float) |
| `biocreto_laboratorio/models/slump.py:37` | **Definición** | `biocreto.slump.valor` (Float) |
| `biocreto_laboratorio/models/sale_order.py:14-16` | **Definición** | `biocreto_slump_count` (Integer compute) |
| `biocreto_sale_extension/models/sale_order.py:364-365` | **Python — validación** | En `_biocreto_validate_before_confirm`: `if not line.biocreto_slump: faltantes.append("Slump")` → **bloquea la confirmación** si falta |
| `biocreto_laboratorio/models/sale_order.py:26-28` | **Python — compute** | `_compute_biocreto_slump_count` vía `search_count` sobre `biocreto.slump` |
| `biocreto_laboratorio/models/sale_order.py:71-76` | **Python — acción** | `action_view_biocreto_slumps` abre la lista de ensayos |
| `biocreto_laboratorio/models/slump.py:53-79` | **Python — naming** | `_biocreto_mixer_index` + `_biocreto_build_name` |
| `biocreto_laboratorio/models/slump.py:81-91` | **Python — create** | Autogenera `name` |
| `biocreto_fabricacion/models/stock_picking.py:27` | **Python — `@api.depends`** | Depende de `biocreto_carga_ids.sale_line_id.biocreto_slump` |
| `biocreto_fabricacion/models/stock_picking.py:47,62` | **Python — texto de guía** | Formatea `f'{line.biocreto_slump:g}'` e imprime `"Slump: {slump}\n"` en la nota del picking |
| `biocreto_sale_extension/views/sale_order_views.xml:223` | **Vista form** (backend) | `biocreto_slump` en la sección Concreto |
| `biocreto_sale_extension/views/sale_order_views.xml:251` | **Vista form** | `biocreto_slump_bombeable` en la sección Bombeo |
| `biocreto_sale_extension/views/sale_order_views.xml:355` | **Vista form** | `biocreto_slump` — 2ª aparición (otro bloque del form) |
| `biocreto_sale_extension/views/sale_order_views.xml:378` | **Vista form** | `biocreto_slump_bombeable` — 2ª aparición |
| `biocreto_laboratorio/views/sale_order_views.xml:70-75` | **Stat button** | Botón "Slump" con `widget="statinfo"` |
| `biocreto_laboratorio/views/slump_views.xml:4-19` | **Vista list** | `biocreto.slump` |
| `biocreto_laboratorio/views/slump_views.xml:21-52` | **Vista form** | `biocreto.slump` |
| `biocreto_laboratorio/views/slump_views.xml:54-71` | **Vista search** | `biocreto.slump` |
| `biocreto_laboratorio/views/slump_views.xml:73-78` | **Acción** | `action_biocreto_slump` |
| `biocreto_laboratorio/views/menus.xml:25-29` | **Menú** | Laboratorio → Slump |
| `biocreto_laboratorio/security/ir.model.access.csv:5` | **ACL** | `base.group_user` con 1,1,1,1 sobre `biocreto.slump` |
| `biocreto_sale_report_cotizacion/report/report_cotizacion.xml:584` | **Reporte QWeb** | Cotización, tabla A. Concreto: `'%g' % (line.biocreto_slump or 0)` |
| `biocreto_sale_report_cotizacion/report/report_cotizacion.xml:637` | **Reporte QWeb** | Cotización, tabla B. Bombeo: `biocreto_slump_bombeable` |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:498,510` | **Reporte QWeb** | Contrato: columna `<th>Slump Bomb.</th>` + `'%g' % (line.biocreto_slump_bombeable or 0)` |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:563-565` | **Texto legal** | Menciona "asentamiento" y NTP 339.114 — **texto fijo, no lee el campo** |
| `biocreto_sale_reports_contrato/report/report_contrato.xml:821` | **Texto legal** | "ensayo de cono de Abrams (slump) según ASTM C 143" — texto fijo |
| BD `ir_ui_view` 4032 (`sale.order`), 4033 (`sale.order.line`), 4178 (`sale.order`) | **Vistas en BD** | Las vistas de arriba, instaladas |
| BD `ir_ui_view` 4086, 4089 (cotización), 4092 (contrato) | **Reportes en BD** | Los reportes de arriba, instalados |
| BD `ir_ui_view` 4162, 4163 (`biocreto.slump`) | **Vistas en BD** | list / form del ensayo |

**Tipos de uso SIN ocurrencias** (verificado explícitamente):

| Tipo | Estado |
|---|---|
| Vistas kanban | **Sin ocurrencias** |
| Vistas search del backend sobre `sale.order`/`sale.order.line` | **Sin ocurrencias** (solo hay search de `biocreto.slump`) |
| Templates del portal del cliente | **Sin ocurrencias** |
| Páginas o formularios de website | **Sin ocurrencias** |
| Dominios, filtros guardados (`ir_filters`) | **Sin ocurrencias** — 0 filas |
| Agrupaciones (`group_by`) | **Sin ocurrencias** |
| `base.automation` / server actions (`ir_act_server.code`) | **Sin ocurrencias** — 0 filas |
| Listas de exportación guardadas (`ir_exports_line`) | **Sin ocurrencias** — 0 filas |
| `@api.constrains` sobre slump | **Sin ocurrencias** |
| `@api.onchange` sobre slump | **Sin ocurrencias** |
| `default=` en la definición | **Sin ocurrencias** (no tienen default) |
| Módulos de calidad (`quality_*`) | **Sin ocurrencias** |
| MRP / Inventario | **Una sola:** `biocreto_fabricacion/models/stock_picking.py` (nota de la guía) |

### D4 — Impacto de migrar a rango

```sql
SELECT 'sale_order_line.biocreto_slump' campo,
       count(*) FILTER (WHERE biocreto_slump IS NOT NULL AND biocreto_slump<>0) AS con_valor,
       count(*) AS total FROM sale_order_line
UNION ALL
SELECT 'sale_order_line.biocreto_slump_bombeable',
       count(*) FILTER (WHERE biocreto_slump_bombeable IS NOT NULL AND biocreto_slump_bombeable<>0),
       count(*) FROM sale_order_line;
```
```
                  campo                   | con_valor | total
------------------------------------------+-----------+-------
 sale_order_line.biocreto_slump           |        16 |    33
 sale_order_line.biocreto_slump_bombeable |         8 |    33
```

**Distribución de `biocreto_slump`:**

```
 biocreto_slump | count
----------------+-------
           5.00 |     1
           6.00 |    13
           7.00 |     1
           8.00 |     1
```

**Distribución de `biocreto_slump_bombeable`:**

```
 biocreto_slump_bombeable | count
--------------------------+-------
                     6.00 |     8
```

**Ensayos de laboratorio:**

```
 total | con_valor
-------+-----------
     0 |         0
```

> **Lectura para la migración a rango:**
> · Solo **16 filas** que migrar en `biocreto_slump` y **8** en `_bombeable`.
> · **4 valores distintos**, todos enteros, todos en 5-8 pulgadas. `6.00` concentra 13 de 16.
> · **Ningún ensayo `biocreto.slump` registrado** — el modelo de laboratorio está vacío,
>   así que un cambio de rango allí no arrastra datos.
> · El migrador natural (`valor` → `min = max = valor`) es trivial a esta escala.
> · **El punto caro no son los datos, son los consumidores:** 4 apariciones en el form,
>   3 celdas de reporte QWeb, 1 validación de confirmación y 1 nota de guía de remisión
>   que hoy hacen `'%g' % valor`. Todos hay que reescribirlos a "min–max".

### D5 — ¿Existe ya algún campo de rango / min / max / tolerancia?

```
$ grep -rn "_min\|_max\|tolerancia\|rango\|_desde\|_hasta" custom_addons/*/models/*.py | grep "fields\."
custom_addons/biocreto_requerimientos/models/consolidado.py:53:  fecha_desde = fields.Date(...)
custom_addons/biocreto_requerimientos/models/consolidado.py:54:  fecha_hasta = fields.Date(...)
```

**No existe ningún precedente de rango numérico en el proyecto.** Lo único con forma de
"desde/hasta" son dos campos `Date` de un filtro de requerimientos, sin relación.

El precedente **más cercano** en patrón (no en semántica) es el rango de fecha de vaceo,
`biocreto_fecha_vaceo_inicio` / `_fin` (`sale_order.py:88-89`), que usa el widget
`daterange` con `options="{'end_date_field': ...}"`. Es el modelo mental a copiar
—dos campos + un widget que los une— pero **no hay equivalente nativo para floats**.

---

## 8. Ubicación de obra (Bloque E)

### E1 — Grep

| Término | Resultado |
|---|---|
| `latitude` / `longitude` | Solo dentro de `biocreto_map_coord` (JS) y `geo_button.js`, como nombres de la API del navegador y como claves `partner_latitude`/`partner_longitude` inyectadas al modelo del mapa |
| `partner_latitude` / `partner_longitude` | `biocreto_map_coord/static/src/map_view/biocreto_coord_map_model.js:110-111` |
| `google.com/maps` | `biocreto_sale_extension/models/sale_order.py:152` y un comentario en `biocreto_coord_map_model.js:98` |
| `geolocaliz` | `geo_button.js:13,48,86`, `sale_order.py:45`, `sale_order_views.xml:48,54` |
| `goo.gl` | **CERO ocurrencias** |
| `mapbox` | Solo un comentario en `biocreto_coord_map_model.js:28` |
| `ubicacion` / `ubicación` | `geo_button.js:75`, `geo_button.xml:16` ("Obtener ubicación") |
| `maps` | Los ya citados |

### E2 — "Jalar mi ubicación": dónde está

| Punto | Valor |
|---|---|
| Código | `biocreto_sale_extension/static/src/components/geo_button/geo_button.js` (+ `.xml`) |
| Tipo | Widget OWL de campo, registrado como **`biocreto_geo_field`** |
| Modelo destino | `sale.order` |
| Campos que escribe | `biocreto_latitud` (al que se ancla) y `biocreto_longitud` (vía `options.lng_field`) |
| Tipo y precisión | Los dos `Float` con `digits=(10, 7)` → 7 decimales ≈ **1 cm** |
| Dónde aparece | Form de `sale.order`, `biocreto_sale_extension/views/sale_order_views.xml:66-70` |
| Assets | `biocreto_sale_extension/__manifest__.py:43-48`, bundle `web.assets_backend` |
| Controller | **Ninguno.** Todo cliente; el guardado va por el `write` normal del form |
| API | `navigator.geolocation.getCurrentPosition` con `enableHighAccuracy: true, timeout: 10000, maximumAge: 0` |

Código completo:

```js
/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class BiocretoGeoField extends Component {
    static template = "biocreto_sale_extension.GeoField";
    static props = {
        ...standardFieldProps,
        lngField: { type: String, optional: true },
    };

    setup() {
        this.notification = useService("notification");
    }

    onClickGetLocation() {
        if (!navigator.geolocation) {
            this.notification.add(
                _t("Este navegador no soporta geolocalización. Ingrese las coordenadas manualmente."),
                { type: "warning", sticky: false }
            );
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = parseFloat(position.coords.latitude.toFixed(7));
                const lng = parseFloat(position.coords.longitude.toFixed(7));
                if (
                    isNaN(lat) || isNaN(lng) ||
                    Math.abs(lat) > 90 || Math.abs(lng) > 180
                ) {
                    this.notification.add(
                        _t("Coordenadas fuera de rango. No se guardaron."),
                        { type: "danger", sticky: false }
                    );
                    return;
                }
                const lngFieldName = this.props.lngField || "biocreto_longitud";
                this.props.record.update({
                    [this.props.name]: lat,
                    [lngFieldName]: lng,
                });
            },
            () => {
                this.notification.add(
                    _t("No se pudo obtener la ubicación. Ingrese las coordenadas manualmente."),
                    { type: "warning", sticky: false }
                );
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }
}

export const biocretoGeoField = {
    component: BiocretoGeoField,
    displayName: _t("Geolocalización GPS"),
    supportedTypes: ["float"],
    supportedOptions: [
        {
            label: _t("Longitude field"),
            name: "lng_field",
            type: "field",
            availableTypes: ["float"],
            help: _t("Float field for longitude that the GPS button will fill in along with the latitude."),
        },
    ],
    extractProps: ({ options }) => ({
        lngField: options.lng_field,
    }),
};

registry.category("fields").add("biocreto_geo_field", biocretoGeoField);
```

```xml
<!-- geo_button.xml -->
<t t-name="biocreto_sale_extension.GeoField">
    <button t-if="!props.readonly"
            type="button"
            class="btn btn-sm btn-secondary text-nowrap"
            title="Obtener coordenadas GPS actuales"
            t-on-click="onClickGetLocation">
        <i class="fa fa-map-marker me-1"/>Obtener ubicación
    </button>
</t>
```

Cómo se declara en la vista (`sale_order_views.xml:48-72`) — **`biocreto_latitud` aparece
DOS veces** en el mismo form: una como input normal y otra como botón:

```xml
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
```

> **Anotar para cualquier prompt que toque esta vista:** por ese campo duplicado,
> `biocreto_sale_contract_state/views/sale_order_views.xml:147-153` necesita xpaths
> discriminados por widget:
> `//field[@name='biocreto_latitud'][not(@widget)]` y `//field[@name='biocreto_latitud'][@widget='biocreto_geo_field']`.
> Un xpath simple sobre `biocreto_latitud` **fallará por ambigüedad**.

### E3 — Dónde vive hoy la ubicación de obra

**En `sale.order` directamente. NO en `res.partner`. NO hay modelo de obra.**

```
$ grep -rn "_name = " custom_addons/*/models/*.py | grep -i "obra\|proyect\|project"
(sin resultados)
```

Campos de ubicación en `sale.order` (`biocreto_sale_extension/models/sale_order.py:14-72`):

```python
    biocreto_state_id = fields.Many2one('res.country.state', string="Departamento",
        domain="[('country_id.code', '=', 'PE')]")
    biocreto_city_id = fields.Many2one('res.city', string="Provincia",
        domain="[('state_id', '=', biocreto_state_id)]")
    biocreto_district_id = fields.Many2one('l10n_pe.res.city.district', string="Distrito",
        domain="[('city_id', '=', biocreto_city_id)]")
    biocreto_street = fields.Char(string="Calle / Dirección",
        help="Calle, avenida, jirón y número de la obra.")
    biocreto_direccion_completa = fields.Char(string="Dirección completa",
        compute='_compute_biocreto_direccion_completa', store=True,
        help="Línea concatenada de la dirección de obra para el reporte.")

    biocreto_latitud = fields.Float(string="Latitud", digits=(10, 7),
        help="Latitud de la obra en grados decimales. Ej.: -12.0653000")
    biocreto_longitud = fields.Float(string="Longitud", digits=(10, 7),
        help="Longitud de la obra en grados decimales. Ej.: -75.2049000")
```

Columnas confirmadas en la tabla:

```
         column_name         |     data_type
-----------------------------+-------------------
 biocreto_direccion_completa | character varying
 biocreto_latitud            | numeric
 biocreto_longitud           | numeric
 biocreto_street             | character varying
```

Historia relevante: antes era **un solo `Char` `biocreto_coordenadas`** con formato
`"lat, lng"`; se partió en dos `Float` en la v19.0.1.6.0, con migrador en
`biocreto_sale_extension/migrations/19.0.1.6.0/post-migration.py`.

El generador de URL de Google Maps (compute, **no almacenado**):

```python
# custom_addons/biocreto_sale_extension/models/sale_order.py:142-161
    biocreto_gmaps_url = fields.Char(
        string="URL Google Maps",
        compute='_compute_biocreto_gmaps_url',
        help="URL de Google Maps Directions hacia la obra. ...",
    )

    @api.depends('biocreto_latitud', 'biocreto_longitud', 'biocreto_direccion_completa')
    def _compute_biocreto_gmaps_url(self):
        base = "https://www.google.com/maps/dir/?api=1&destination="
        for order in self:
            lat = order.biocreto_latitud
            lng = order.biocreto_longitud
            destino = False
            if lat and lng and -90 <= lat <= 90 and -180 <= lng <= 180:
                destino = f"{lat},{lng}"
            elif order.biocreto_direccion_completa:
                destino = quote(order.biocreto_direccion_completa)
            order.biocreto_gmaps_url = (base + destino) if destino else False
```

Reglas: `(0,0)` se trata como ausencia; fallback a la dirección textual URL-encoded;
si no hay nada → `False` y el botón "Ir a" no se renderiza.

Y la vista mapa (`biocreto_map_coord`) ubica los registros por **coordenadas propias**,
no por `res.partner`, inyectando `partner_latitude`/`partner_longitude` sintéticos:

```js
// biocreto_map_coord/static/src/map_view/biocreto_coord_map_model.js:42-46,110-111
        return this.metaData.context?.lat_field || "biocreto_latitud";
        return this.metaData.context?.lng_field || "biocreto_longitud";
        ...
                partner_latitude: lat,
                partner_longitude: lng,
```

### E4 — `base_geolocalize` y parámetros

```
 name             | state
------------------+-----------
 base_geolocalize | installed
```

```sql
SELECT key, value FROM ir_config_parameter
WHERE key ILIKE '%geo%' OR key ILIKE '%map%' OR key ILIKE '%google%';
```
```
              key              | value
-------------------------------+-------
 base_geolocalize.geo_provider | 1
```

**Un único parámetro.** No hay API key de Google, ni token de Mapbox, ni `web.base.url`
relacionada con mapas. El proveedor `1` es el primero del catálogo de `base_geolocalize`
(nominatim / openstreetmap por defecto en Odoo 19) — **el valor no se ha personalizado**.

### E5 — ¿Se imprime o se muestra en el portal?

| Canal | ¿Aparece la ubicación? |
|---|---|
| Reporte de **cotización** | **La dirección SÍ**, las coordenadas NO. `report_cotizacion.xml:548-549`: `<span class="cliente-label">Dirección obra</span>` + `o.biocreto_direccion_completa` |
| Reporte de **contrato** | Solo la **ZONA** (el distrito): `report_contrato.xml:399-400`, `o.biocreto_district_id.name`. **Sin coordenadas y sin enlace** |
| **Portal del cliente** | **NO.** Cero ocurrencias de `biocreto_latitud`, `biocreto_longitud` o `biocreto_gmaps_url` en `biocreto_sale_portal/views/portal_templates.xml` |
| **Calendario** (backend) | **SÍ**, botón "Ir a" en el popover: `biocreto_programacion/static/src/js/calendar_popover_ir_a.js:24-30` lee `rec.biocreto_gmaps_url` del rawRecord; el campo se declara `invisible="1"` en `sale_order_calendar_views.xml:84` para que llegue al cliente |
| **Vista mapa** (backend) | **SÍ**, `biocreto_programacion/views/sale_order_map_views.xml` sobre `biocreto_map_coord` |

> Resumen: **la coordenada existe y se usa en el backend (calendario y mapa), pero NO se
> imprime en ningún PDF ni se muestra al cliente en el portal.**

### E6 — Salida a internet del proceso

Ejecutado con el intérprete del entorno de Odoo (`PruebasOdoo19`, el mismo que corre el servidor):

```
OK   204 https://www.google.com/generate_204
OK   200 https://maps.google.com/
OK   200 https://nominatim.openstreetmap.org/status.php
--- redireccion de link corto goo.gl ---
resultado: HTTPError HTTP Error 404: Not Found   (código inventado; la petición SALIÓ y el servidor respondió)
```

**Hay salida a internet, sin proxy ni bloqueo.** El 404 del enlace corto es el esperado
para un código inexistente: lo relevante es que la petición llegó a `goo.gl` y volvió con
respuesta HTTP.

> **Conclusión: resolver enlaces cortos de Google Maps del lado servidor es VIABLE.**
> Salvedad honesta: la prueba se hizo con el intérprete de Python del entorno, no dentro
> de un worker HTTP de Odoo en marcha. Es la misma máquina, el mismo Python y la misma
> pila de red, pero un proxy configurado a nivel de servicio de Odoo (no lo hay en
> `odoo19.conf`) podría diferir.

---

## 9. LISTA DE DESCONOCIDOS

| # | Qué no se pudo verificar | Por qué | Qué haría falta |
|---|---|---|---|
| 1 | **Cuál de las dos firmas falta en el reporte** (¿cliente o jefe de obra?) | El usuario dijo "falta una de las dos" sin precisar cuál | Que lo indique, o correr el §4.4 |
| 2 | **Qué diferencia técnicamente el escenario A del B** | `DESCONOCIDO — no pude verificarlo porque no existe en la base ninguna orden firmada una-por-una:` las órdenes 20 y 28 tienen `create_date` y `file_size` idénticos en ambas firmas, o sea "Firmar Ambos" | Correr el §4.4 y comparar Q2 entre A y B |
| 3 | **Por cuál de los 3 caminos imprime el usuario** (chatter / portal / backend) | No consta en el reporte del síntoma. Son objetos distintos (§A7) | Preguntarlo. Decide entre H2 y H3 |
| 4 | **Si el `<img>` fallido está ausente o roto en el PDF** | No dispongo de un PDF fallido | El PDF fallido, o el HTML intermedio del render |
| 5 | **Si la firma "BIOCRETO" (del gerente) también falla** | Nadie la ha mirado; es el discriminador de H1 | Mirar los tres recuadros del PDF fallido |
| 6 | **El contexto efectivo en el momento del render fallido** | `DESCONOCIDO — no pude verificarlo porque haría falta instrumentar el código, y este recon es de solo lectura` | Un log temporal de `self.env.context` en `_render_qweb_pdf` |
| 7 | **Si PlutoPrint cayó a wkhtmltopdf en algún render** | Se registra con `_logger.exception` (`biocreto_pdf_engine/models/ir_actions_report.py:113`), pero no tengo los logs del servidor | Buscar `biocreto_pdf_engine: PlutoPrint fallo` en el log del día del fallo |
| 8 | **Comportamiento real del read-back post-`write` de un `Binary(attachment=True)`** dentro de la transacción del portal | Comprobarlo exige **escribir** una firma. `odoo/orm/fields_binary.py:184-230` sugiere que con el `flush()` de `portal.py:231` debería funcionar, pero el comentario del propio módulo (`portal.py:235-243`) documenta que en la v19.0.1.3.0 no funcionaba | Un test que escriba y renderice en la misma transacción — fuera del alcance de un recon |
| 9 | **Origen del número `2045643545646`** | No existe en código ni en BD | Preguntar al usuario de dónde lo sacó |
| 10 | **Multiplanta** | Una sola `res.company` (`Biocreto`, id 1). No hay con qué probar aislamiento entre plantas | Una segunda compañía |
| 11 | **Unidad real del slump: pulgadas o cm** | Solo consta en el `string` ("pulg.") y en el `help` de ejemplo. No hay UdM ni validación de rango. Los valores en BD (5-8) son coherentes con pulgadas, pero es inferencia, no verificación | Confirmación del usuario |
| 12 | **Si algún reporte de Studio estuvo activo alguna vez** | Existen 3 pares de plantillas QWeb de Studio huérfanas; ninguna acción las referencia hoy. Lo que hubo antes no es reconstruible | — (probablemente irrelevante) |
| 13 | **Impacto de la doble aparición de slump en el form** | Hay 4 `<field>` de slump en `sale_order_views.xml` (223, 251, 355, 378). No verifiqué si son dos vistas distintas o dos bloques de la misma | Abrir el form; importa al migrar a rango |

---

## 10. PREGUNTAS PARA EL USUARIO

### Sobre el bug de firma (bloqueantes para escribir la corrección)

1. **¿Cuál de las dos firmas falta?** ¿La de EL CLIENTE o la de V°B° JEFE DE OBRA? ¿Es siempre la misma o varía?
2. **¿Falta también la firma de BIOCRETO (la del gerente, el primer recuadro)?** Esta es la pregunta más informativa de todo el recon: si también falta, apunta a H1; si sale bien, la descarta casi por completo.
3. **¿Desde dónde imprime?** (a) abriendo el adjunto `Contrato_*.pdf` del chatter, (b) el botón "Descargar Contrato (PDF)" del portal, o (c) el botón Imprimir del backend. **Son tres PDF distintos** y el diagnóstico cambia con la respuesta.
4. **En el PDF fallido, ¿el recuadro está totalmente vacío o se ve un icono de imagen rota?** Vacío → el `t-if` descartó el `<img>`; roto → el `src` llegó corrupto (H1).
5. **¿"De corrido" significa el botón "Firmar Ambos", o firmar Cliente y luego Jefe de Obra seguidos sin salir?** Son dos rutas distintas del controller y el diagnóstico difiere.
6. **En el escenario B, ¿descarga o abre el PDF entre la primera y la segunda firma?** Es la condición que dispara H2.
7. **¿Ha probado el mismo caso en incógnito o con `Ctrl+Shift+R`?** Si con eso sale bien, H2 queda confirmada y la corrección es trivial.

### Sobre decisiones que no se pueden tomar leyendo código

8. **Fecha del contrato:** hoy se imprime `biocreto_fecha_firma_contrato`, que se estampa al **entrar al estado Contrato**, no al firmar (`biocreto_sale_contract_state/models/sale_order.py:185`). ¿Debe imprimirse la fecha de la firma real (`biocreto_firma_contrato_fecha`)?
9. **Nombre del cliente en el PDF:** el recuadro EL CLIENTE imprime `cp.name` (razón social del partner), **no** el nombre que la persona teclea al firmar (`report_contrato.xml:895`). El de jefe de obra sí imprime el tecleado (`:903`). ¿Se unifica? ¿En qué sentido?
10. **PDF del chatter:** se genera una sola vez y nunca se regenera (§A7). ¿Debe regenerarse si se vuelve a firmar, o se acepta que sea una foto del momento?
11. **Cuentas bancarias — moneda:** el `<td>` dice `Soles` **hardcodeado** y no lee `bank.currency_id`. ¿Se deja fijo o se pasa a leer la moneda real de la cuenta?
12. **Cuentas bancarias — filtro:** hoy se imprimen **todas** las de `company_id.bank_ids` (3 en la base). ¿Se quieren todas siempre, o solo algunas marcadas para impresión?
13. **Cuentas bancarias — dónde:** el bloque está duplicado literalmente en cotización y contrato. ¿Se factoriza en una plantilla QWeb compartida, o se mantienen independientes a propósito?
14. **`2045643545646`:** no existe en este proyecto. ¿De dónde sale ese número? ¿Es una cuenta que **debería** estar y no está?
15. **Slump como rango:** ¿un solo rango (`min`–`max`) o un valor objetivo más una tolerancia (`6" ± 1"`)? Cambia el modelo de datos y todos los formateos de reporte.
16. **Slump — alcance:** ¿el rango aplica también a `biocreto_slump_bombeable` y al `valor` del ensayo `biocreto.slump`, o solo al principal?
17. **Slump — validación de confirmación:** hoy `_biocreto_validate_before_confirm` exige que `biocreto_slump` sea distinto de cero (`sale_order.py:364-365`). Con rango, ¿se exige el mínimo, el máximo o los dos?
18. **Slump — impresión:** hoy los reportes imprimen `'%g' % valor`. Con rango, ¿`6 – 8"`? ¿`6"–8"`? ¿`7" ± 1"`? Define el formato exacto que va al PDF.
19. **Slump — unidad:** ¿pulgadas confirmado? Solo consta en el `string` del campo, no hay UdM ni validación.
20. **Ubicación — enlaces cortos:** ¿el objetivo es pegar un enlace de `maps.app.goo.gl` y que el sistema extraiga las coordenadas? Es **viable** (§E6), pero implica una llamada saliente por cada pegado. ¿Se acepta esa dependencia de red, y qué debe pasar si Google no responde?
21. **Ubicación — dónde se pega:** ¿en un campo nuevo, o reutilizando `biocreto_street`? Cuidado: `biocreto_street` está marcado **`required=True` por Studio** (`ir_ui_view` 4046).
22. **Ubicación — impresión:** hoy las coordenadas **no salen en ningún PDF ni en el portal**. ¿Deben imprimirse en el contrato y/o en la cotización? ¿Como coordenadas, como enlace, o como QR?
23. **Ubicación — modelo de obra:** no existe ninguno; la obra vive como campos sueltos en `sale.order`. ¿Se mantiene así, o hay intención de crear un modelo `biocreto.obra` reutilizable entre cotizaciones?

---

## 11. Criterio de aceptación (Paso 8)

```
$ git status --short
?? RECON_BIOCRETO.md
?? custom_addons/LogoReq.svg
?? custom_addons/PruebaLaboratorio.svg
?? custom_addons/biocreto_fabricacion/
?? custom_addons/biocreto_laboratorio/
?? custom_addons/biocreto_requerimientos/
?? custom_addons/draw_planta.svg
?? custom_addons/icono_fabrica.svg
?? custom_addons/mixer_truck.svg
```

**Cero archivos modificados.** La única entrada nueva es este informe. Las 8 restantes ya
estaban sin commitear antes de empezar (§2, Git).

No se ejecutó ningún `-u` ni `-i`. La única sesión de `odoo-bin shell` fue de lectura y
terminó con `env.cr.rollback()`. Todas las consultas `psql` fueron `SELECT`.
