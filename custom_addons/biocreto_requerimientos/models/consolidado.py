# ═══════════════════════════════════════════════════════════════════════
# === BIOCRETO CONSOLIDADO v1 — INICIO (archivo completo reversible) ===
#
# Consolidado mensual de requerimientos -> solicitud de compra.
#
# ARCHIVO EXCLUSIVO DEL CONSOLIDADO: se elimina entero en una reversion.
# Ver REVERSION_CONSOLIDADO.md en la raiz del modulo.
#
# Arquitectura (decidida tras el recon, ver REVERSION_CONSOLIDADO.md):
#   - La lista agrupada NO puede vivir embebida en un formulario: StaticList
#     (web/static/src/model/relational_model/static_list.js:78) no implementa
#     isGrouped ni groupBy, y x2many_field.js nunca lee defaultGroupBy -> el
#     atributo default_group_by se ignora en silencio dentro de un x2many.
#     Por eso la pantalla principal es una VISTA LISTA SUELTA del modelo de
#     linea, como l10n_in/views/account_invoice_views.xml:107.
#   - purchase.order.partner_id es required=True
#     (odoo/addons/purchase/models/purchase_order.py:91-94) y ademas NOT NULL
#     en la tabla -> el proveedor se elige en un dialogo propio al generar la
#     cotizacion (BiocretoRequerimientoCotizacionWizard, al final del archivo).
#
# v19.0.1.3.0 — el periodo dejo de ser un parametro del calculo:
#   - el calculo trae TODAS las lineas candidatas y el recorte lo hace el
#     filtro "Este mes" de la vista de busqueda, que el usuario puede quitar;
#   - por eso desaparecen fecha_desde/fecha_hasta y el dialogo "Configurar";
#   - la fila del consolidado guarda `fecha_requerimiento` (la mas reciente de
#     las solicitudes que agrupa) para que ese filtro tenga contra que medir.
# ═══════════════════════════════════════════════════════════════════════
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BiocretoRequerimientoConsolidado(models.TransientModel):
    _name = 'biocreto.requerimiento.consolidado'
    _description = 'Consolidado mensual de requerimientos'

    # El default de transient_age_limit es 1 hora: un consolidado abierto en
    # una pestana mas de una hora seria barrido por _transient_vacuum
    # (odoo/orm/models_transient.py:56-58) y el usuario perderia sus ediciones
    # de "A comprar". 12 h cubre una jornada completa.
    _transient_max_hours = 12.0

    company_id = fields.Many2one(
        'res.company', string="Planta", required=True,
        default=lambda self: self.env.company)

    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Almacén",
        compute='_compute_warehouse_id', readonly=True)

    linea_ids = fields.One2many(
        'biocreto.requerimiento.consolidado.linea', 'consolidado_id',
        string="Líneas")

    total_solicitado = fields.Float(
        string="Total solicitado", compute='_compute_totales')
    total_a_comprar = fields.Float(
        string="Total a comprar", compute='_compute_totales')
    sin_producto_count = fields.Integer(
        string="Líneas sin producto", compute='_compute_sin_producto')
    sin_producto_texto = fields.Text(
        string="Detalle sin producto", compute='_compute_sin_producto')

    # Se escribe en action_calcular (no es compute): recoge incidencias del
    # calculo que el usuario debe conocer — planta sin almacen, mas de un
    # almacen, conversiones de UdM aplicadas.
    aviso_tecnico = fields.Text(string="Avisos del cálculo", readonly=True)

    # Many2many y no Many2one: desde un mismo consolidado se pueden generar
    # VARIAS cotizaciones (proveedores distintos, o una segunda tanda sobre
    # filas que entraron despues). `relation` explicito para no pasar de los
    # 63 caracteres de PostgreSQL (odoo/orm/utils.py:102).
    purchase_ids = fields.Many2many(
        'purchase.order', string="Solicitudes de compra", readonly=True,
        relation='biocreto_consolidado_purchase_rel',
        column1='consolidado_id', column2='purchase_id')

    # ─────────────────────────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────────────────────────
    @api.depends('company_id')
    def _compute_warehouse_id(self):
        """Almacen de la planta. Si hay varios se toma el de menor id
        (decision cerrada del Paso 1); si no hay ninguno queda vacio y
        stock_actual sale 0 en todas las lineas."""
        # sudo(): un group_requerimiento_user no es necesariamente usuario de
        # Inventario, y sin ese permiso ni siquiera puede leer stock.warehouse.
        # Es una lectura informativa de la planta en la que ya trabaja.
        Warehouse = self.env['stock.warehouse'].sudo()
        for consolidado in self:
            consolidado.warehouse_id = Warehouse.search(
                [('company_id', '=', consolidado.company_id.id)],
                order='id', limit=1)

    @api.depends('linea_ids.cantidad_solicitada', 'linea_ids.cantidad_comprar')
    def _compute_totales(self):
        for consolidado in self:
            consolidado.total_solicitado = sum(
                consolidado.linea_ids.mapped('cantidad_solicitada'))
            consolidado.total_a_comprar = sum(
                consolidado.linea_ids.mapped('cantidad_comprar'))

    @api.depends('linea_ids.sin_producto', 'linea_ids.descripcion')
    def _compute_sin_producto(self):
        for consolidado in self:
            faltantes = consolidado.linea_ids.filtered('sin_producto')
            consolidado.sin_producto_count = len(faltantes)
            consolidado.sin_producto_texto = "\n".join(
                "- %s (%s)" % (linea.descripcion, linea.usuarios_texto or '')
                for linea in faltantes)

    # ─────────────────────────────────────────────────────────────────
    # Calculo
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_domain_lineas(self):
        """Lineas de requerimiento elegibles para el consolidado.

        SIN recorte por fecha: el periodo lo aplica el filtro "Este mes" de la
        vista de busqueda, sobre `fecha_requerimiento` de la fila resultante.
        Consecuencia buscada: los subtotales por grupo y el total al pie
        reflejan solo lo filtrado, porque el cliente los calcula sobre las
        filas visibles.

        SIN descartar `purchase_line_id`: las filas ya cotizadas siguen
        apareciendo, con su distintivo de estado. Cuando la compra se recibe,
        sube el stock y `cantidad_comprar` cae sola.
        """
        self.ensure_one()
        return [
            ('requerimiento_id.company_id', '=', self.company_id.id),
            ('requerimiento_id.state', 'in', ('enviado', 'en_proceso')),
            # Solo se excluyen las canceladas: 'parcial' y 'atendido' entran,
            # porque haber entregado de stock no significa no tener que comprar.
            ('estado', '!=', 'cancelado'),
        ]

    @api.model
    def _biocreto_normaliza(self, texto):
        """Clave de agrupacion de las lineas sin SKU: minusculas y espacios
        colapsados."""
        return ' '.join((texto or '').lower().split())

    def action_calcular(self):
        """Reconstruye las lineas del consolidado. Idempotente."""
        self.ensure_one()
        self.linea_ids.unlink()

        avisos = []
        almacenes = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], order='id')
        if not almacenes:
            avisos.append(_(
                "La planta %s no tiene ningún almacén configurado: el stock "
                "actual se muestra como 0 en todas las líneas.",
                self.company_id.display_name))
        elif len(almacenes) > 1:
            avisos.append(_(
                "La planta %(planta)s tiene %(n)s almacenes; se usa "
                "%(usado)s (el de menor id).",
                planta=self.company_id.display_name, n=len(almacenes),
                usado=almacenes[0].display_name))

        origen = self.env['biocreto.requerimiento.linea'].search(
            self._biocreto_domain_lineas())

        grupos = {}
        for linea in origen:
            if linea.product_id:
                clave = ('producto', linea.product_id.id)
            else:
                clave = ('descripcion', self._biocreto_normaliza(linea.descripcion))

            grupo = grupos.get(clave)
            if grupo is None:
                # UdM destino: la de referencia del producto cuando lo hay
                # (criterio del Paso 6); en las lineas sin SKU, la de la
                # primera linea del grupo.
                uom_destino = (linea.product_id.uom_id if linea.product_id
                               else linea.product_uom_id)
                grupo = grupos[clave] = {
                    'product_id': linea.product_id.id,
                    'descripcion': (linea.product_id.display_name
                                    if linea.product_id else linea.descripcion),
                    'categoria_producto_id': (
                        linea.product_id.categ_id.id if linea.product_id
                        else linea.categoria_producto_id.id),
                    'uom': uom_destino,
                    'cantidad': 0.0,
                    'por_usuario': {},
                    'origen_ids': [],
                    # La MAS RECIENTE de las solicitudes que agrupa la fila:
                    # asi la fila sigue apareciendo mientras alguna de sus
                    # solicitudes caiga dentro del filtro de periodo.
                    'fecha': False,
                }

            cantidad = linea.cantidad
            uom_origen = linea.product_uom_id
            uom_destino = grupo['uom']
            if uom_origen and uom_destino and uom_origen != uom_destino:
                # v19: _compute_quantity convierte por `factor` absoluto y NO
                # lanza excepcion (uom/models/uom_uom.py:147-176); el parametro
                # raise_if_failure quedo sin uso en la implementacion, y ya no
                # existe uom.category_id. Por eso la incompatibilidad se
                # detecta comparando la raiz del parent_path.
                cantidad = uom_origen._compute_quantity(
                    linea.cantidad, uom_destino, rounding_method='HALF-UP')
                raiz_origen = (uom_origen.parent_path or '').split('/')[0]
                raiz_destino = (uom_destino.parent_path or '').split('/')[0]
                if raiz_origen != raiz_destino:
                    avisos.append(_(
                        "«%(desc)s»: %(qty)s %(origen)s no pertenece a la "
                        "misma familia que %(destino)s. Se sumó el valor "
                        "convertido por factor: %(res)s.",
                        desc=grupo['descripcion'], qty=linea.cantidad,
                        origen=uom_origen.display_name,
                        destino=uom_destino.display_name, res=cantidad))
                else:
                    avisos.append(_(
                        "«%(desc)s»: %(qty)s %(origen)s convertidos a "
                        "%(res)s %(destino)s.",
                        desc=grupo['descripcion'], qty=linea.cantidad,
                        origen=uom_origen.display_name, res=cantidad,
                        destino=uom_destino.display_name))

            grupo['cantidad'] += cantidad
            fecha_linea = linea.requerimiento_id.create_date
            if fecha_linea and (not grupo['fecha'] or fecha_linea > grupo['fecha']):
                grupo['fecha'] = fecha_linea
            solicitante = linea.requerimiento_id.solicitante_id
            nombre = solicitante.display_name or _("Sin solicitante")
            grupo['por_usuario'][nombre] = (
                grupo['por_usuario'].get(nombre, 0.0) + cantidad)
            grupo['origen_ids'].append(linea.id)

        Linea = self.env['biocreto.requerimiento.consolidado.linea']
        vals_list = []
        for grupo in grupos.values():
            stock = self._biocreto_stock(grupo['product_id'])
            vals_list.append({
                'consolidado_id': self.id,
                'product_id': grupo['product_id'],
                'descripcion': grupo['descripcion'],
                'categoria_producto_id': grupo['categoria_producto_id'],
                'product_uom_id': grupo['uom'].id if grupo['uom'] else False,
                'cantidad_solicitada': grupo['cantidad'],
                # Precarga pedida en el Paso 5 del prompt original. Se escribe
                # como VALOR (no como compute readonly=False) para que la
                # edicion manual del usuario nunca sea pisada por un recompute.
                'cantidad_comprar': max(0.0, grupo['cantidad'] - stock),
                'usuarios_texto': self._biocreto_usuarios_texto(grupo['por_usuario']),
                'fecha_requerimiento': grupo['fecha'],
                'requerimiento_linea_ids': [(6, 0, grupo['origen_ids'])],
            })
        if vals_list:
            Linea.create(vals_list)

        self.aviso_tecnico = "\n".join(avisos) or False
        return True

    def _biocreto_stock(self, product_id):
        """Stock del producto en el almacen de la planta.

        warehouse_id en el contexto es la via correcta: _get_domain_locations
        (odoo/addons/stock/models/product.py:357-362) lo traduce a
        warehouse.view_location_id, que incluye las ubicaciones hijas. Sin esa
        clave, el fallback (:377-379) suma TODOS los almacenes de
        env.companies.

        sudo(): qty_available se calcula sobre stock.quant y stock.move, cuyas
        ACL exigen el grupo Inventario/Usuario. Un Encargado de requerimientos
        no lo tiene por defecto, y sin sudo el consolidado ni siquiera se
        puede abrir (AccessError en _compute_quantities). Se expone solo un
        numero de existencias de la planta en la que el usuario ya trabaja.
        """
        self.ensure_one()
        if not product_id or not self.warehouse_id:
            return 0.0
        producto = self.env['product.product'].sudo().browse(product_id)
        return producto.with_company(self.company_id).with_context(
            warehouse_id=self.warehouse_id.id).qty_available

    @api.model
    def _biocreto_usuarios_texto(self, por_usuario):
        """`Nombre N · Nombre N`, de mayor a menor cantidad."""
        ordenados = sorted(por_usuario.items(), key=lambda kv: (-kv[1], kv[0]))
        partes = []
        for nombre, cantidad in ordenados:
            # Sin decimales cuando la cantidad es entera: "Max Sandoval 8",
            # no "Max Sandoval 8.0".
            if cantidad == int(cantidad):
                texto = '%d' % int(cantidad)
            else:
                texto = ('%.2f' % cantidad).rstrip('0').rstrip('.')
            partes.append("%s %s" % (nombre, texto))
        return " · ".join(partes)

    # ─────────────────────────────────────────────────────────────────
    # Apertura desde el menu
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def action_abrir_consolidado(self):
        """Crea el consolidado, lo calcula y devuelve la accion sobre su
        lista de lineas.

        Lo invoca el ir.actions.server del menu Logística > Consolidado.
        Ya NO recibe periodo: trae todo y el recorte lo hace el filtro.
        """
        consolidado = self.create({'company_id': self.env.company.id})
        consolidado.action_calcular()
        return consolidado._action_ver_lineas()

    def _action_ver_lineas(self):
        """Accion sobre la lista suelta de lineas (arquitectura B2).

        `name` minimo y `no_breadcrumbs`: el titulo largo con el periodo ya no
        tiene sentido (el periodo lo pone el filtro) y ademas ocupaba la barra
        entera. `no_breadcrumbs` lo consume action_service.js:450-452 y hace
        que control_panel.xml:39 no pinte el componente Breadcrumbs.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Consolidado"),
            'res_model': 'biocreto.requerimiento.consolidado.linea',
            'view_mode': 'list',
            'views': [[self.env.ref(
                'biocreto_requerimientos.consolidado_linea_view_list').id, 'list']],
            'domain': [('consolidado_id', '=', self.id)],
            'context': {
                'default_consolidado_id': self.id,
                'biocreto_consolidado_id': self.id,
                'create': False,
                'delete': False,
                'no_breadcrumbs': True,
                # Filtro de periodo activo de salida. Va como search_default_
                # y NO como domain de la accion, justamente para que se pueda
                # quitar desde la barra de busqueda.
                'search_default_mes_actual': 1,
            },
            'target': 'current',
        }

    # ─────────────────────────────────────────────────────────────────
    # Generacion de la cotizacion
    # Validaciones en los metodos de accion, nunca en @api.constrains.
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_crear_cotizacion(self, lineas, partner):
        """Crea UNA purchase.order en borrador con `lineas`.

        Devuelve (orden, filas_omitidas). Se omiten las filas cuyas lineas de
        origen estan TODAS cotizadas ya: no queda nada nuevo que pedir y una
        linea de compra sin origen al que enlazar rompe la trazabilidad. Las
        filas `parcial` si entran, enlazando solo lo que aun no esta cotizado.
        """
        self.ensure_one()

        # El nativo approvals_purchase no hace sudo(): exige que quien genera
        # la OC tenga permisos de compras. Se conserva ese criterio, pero con
        # un mensaje legible en vez de un AccessError crudo.
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_(
                "Necesita permisos de Compras para generar la cotización. "
                "Pida al administrador que le asigne el acceso «Compras: "
                "Usuario»."))

        pendientes = {}
        omitidas = self.env['biocreto.requerimiento.consolidado.linea']
        for linea in lineas:
            sin_cotizar = linea.requerimiento_linea_ids.filtered(
                lambda origen: not origen.purchase_line_id)
            if not sin_cotizar:
                omitidas |= linea
                continue
            pendientes[linea] = sin_cotizar

        if not pendientes:
            raise UserError(_(
                "Todas las filas marcadas están ya cotizadas por completo. "
                "No queda nada que pedir en ellas.\n\n"
                "Si necesita volver a comprar lo mismo, recalcule el "
                "consolidado desde el menú: las solicitudes nuevas entrarán "
                "como filas por cotizar."))

        requerimientos = self.env['biocreto.requerimiento']
        for origen in pendientes.values():
            requerimientos |= origen.requerimiento_id
        referencia = ', '.join(sorted(r.name for r in requerimientos if r.name))

        PurchaseOrder = self.env['purchase.order'].with_company(self.company_id)
        # state='draft' explicito: verificado que el override de create de
        # biocreto_compras (purchase_order.py:170-178) solo toca `name`, asi
        # que la SC nace en el primer estado del flujo BIOCRETO y recibe su
        # codigo CP-AAAA-PLANTA-NNNN.
        orden = PurchaseOrder.create({
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'state': 'draft',
            'origin': referencia or False,
        })

        PurchaseOrderLine = self.env['purchase.order.line']
        for linea, sin_cotizar in pendientes.items():
            # Un producto sin proveedor configurado entra igual: _select_seller
            # no encuentra nada y _prepare_purchase_order_line deja
            # price_unit = 0 (purchase_order_line.py:633-634). NO se copia
            # _check_products_vendor de approvals_purchase (decision cerrada).
            vals = PurchaseOrderLine._prepare_purchase_order_line(
                linea.product_id,
                linea.cantidad_comprar,
                linea.product_uom_id or linea.product_id.uom_id,
                self.company_id,
                partner,
                orden,
            )
            vals['order_id'] = orden.id
            nueva = PurchaseOrderLine.create(vals)
            # Trazabilidad a nivel de linea, igual que el nativo
            # (approvals/models/approval_product_line.py:28). Se escribe SOLO
            # sobre lo que aun no estaba cotizado: la SC anterior no se toca.
            sin_cotizar.write({'purchase_line_id': nueva.id})

        self.purchase_ids = [(4, orden.id)]

        # Los requerimientos que seguian en 'enviado' pasan a 'en_proceso'.
        por_procesar = requerimientos.filtered(lambda r: r.state == 'enviado')
        if por_procesar:
            por_procesar.action_procesar()

        for requerimiento in requerimientos:
            requerimiento.message_post(body=_(
                "Consolidado de compras: se generó la cotización <b>%s</b>.",
                orden.display_name))
        cuerpo = _(
            "Generada desde el consolidado de requerimientos:<br/>%s",
            "<br/>".join("- %s" % r.display_name for r in requerimientos))
        if omitidas:
            cuerpo += _(
                "<br/><br/>No se incluyeron, por estar ya cotizadas por "
                "completo:<br/>%s",
                "<br/>".join("- %s" % linea.descripcion for linea in omitidas))
        orden.message_post(body=cuerpo)

        return orden, omitidas


class BiocretoRequerimientoConsolidadoLinea(models.TransientModel):
    _name = 'biocreto.requerimiento.consolidado.linea'
    _description = 'Línea del consolidado de requerimientos'
    _order = 'categoria_producto_id, descripcion'

    _transient_max_hours = 12.0

    consolidado_id = fields.Many2one(
        'biocreto.requerimiento.consolidado', string="Consolidado",
        required=True, ondelete='cascade', index=True)
    categoria_producto_id = fields.Many2one(
        'product.category', string="Categoría")
    product_id = fields.Many2one('product.product', string="Producto (SKU)")
    # La columna visible es esta, no product_id: asi las lineas sin SKU se
    # leen igual que las que lo tienen.
    descripcion = fields.Char(string="Producto")
    product_uom_id = fields.Many2one('uom.uom', string="Unidad")
    cantidad_solicitada = fields.Float(string="Total", readonly=True)
    cantidad_comprar = fields.Float(string="A comprar")
    usuarios_texto = fields.Char(string="Usuario", readonly=True)

    # Fecha contra la que mide el filtro de periodo de la vista. Es la MAS
    # RECIENTE de las solicitudes que agrupa la fila (ver action_calcular):
    # con la mas antigua, una fila con pedidos viejos y nuevos se caeria del
    # mes en curso pese a seguir viva. `index=True` porque es la columna que
    # ordena y recorta el filtro por defecto.
    fecha_requerimiento = fields.Datetime(
        string="Fecha del requerimiento", readonly=True, index=True)

    # Estado de COTIZACION. No es un estado nuevo ni se guarda en ningun
    # sitio: se deriva de `purchase_line_id`, que ya existia.
    #
    # OJO: es INDEPENDIENTE del `estado` de la linea de requerimiento
    # (pendiente / parcial / atendido / cancelado). Aquel dice si el material
    # llego a manos del solicitante; este dice si se mando a cotizar. Una
    # linea puede estar 'atendido' sin haberse cotizado nunca (se entrego de
    # stock) y 'pendiente' estando ya cotizada. NO se sincronizan.
    #
    # El valor intermedio hace falta porque una fila agrupa varias lineas de
    # requerimiento: si se cotiza hoy y manana entra un pedido nuevo del
    # mismo producto, la fila queda mezclada.
    estado_cotizacion = fields.Selection([
        ('por_cotizar', 'Por cotizar'),
        ('parcial', 'Parcialmente cotizado'),
        ('cotizado', 'Cotizado'),
    ], string="Cotización", compute='_compute_estado_cotizacion')
    # `relation` explicito: el nombre derivado por convencion
    # (biocreto_requerimiento_consolidado_linea_biocreto_requerimiento_linea_rel,
    # 71 caracteres) supera el limite de 63 de PostgreSQL y check_pg_name
    # (odoo/orm/utils.py:102) aborta el arranque.
    requerimiento_linea_ids = fields.Many2many(
        'biocreto.requerimiento.linea', string="Líneas de origen",
        relation='biocreto_consolidado_linea_origen_rel',
        column1='consolidado_linea_id', column2='requerimiento_linea_id')
    sin_producto = fields.Boolean(
        string="Sin producto", compute='_compute_sin_producto', store=True)

    # stock_actual NO puede llevar sum="..." en la vista: es un compute no
    # almacenado y su _description_aggregator devuelve None
    # (odoo/orm/fields.py:942-955), asi que el cliente ni siquiera lo pide al
    # servidor en el read_group. Las decoraciones si funcionan: se evaluan
    # por registro, no por grupo.
    stock_actual = fields.Float(
        string="Stock actual", compute='_compute_stock_actual', readonly=True)
    stock_suficiente = fields.Boolean(
        string="Stock suficiente", compute='_compute_stock_actual')

    @api.depends('product_id')
    def _compute_sin_producto(self):
        for linea in self:
            linea.sin_producto = not linea.product_id

    @api.depends('requerimiento_linea_ids.purchase_line_id')
    def _compute_estado_cotizacion(self):
        for linea in self:
            origen = linea.requerimiento_linea_ids
            cotizadas = origen.filtered('purchase_line_id')
            if not cotizadas:
                linea.estado_cotizacion = 'por_cotizar'
            elif len(cotizadas) == len(origen):
                linea.estado_cotizacion = 'cotizado'
            else:
                linea.estado_cotizacion = 'parcial'

    @api.depends('product_id', 'cantidad_solicitada',
                 'consolidado_id.warehouse_id')
    def _compute_stock_actual(self):
        for linea in self:
            linea.stock_actual = linea.consolidado_id._biocreto_stock(
                linea.product_id.id)
            linea.stock_suficiente = (
                linea.stock_actual >= linea.cantidad_solicitada)

    # ─────────────────────────────────────────────────────────────────
    # El consolidado al que pertenecen las filas.
    #
    # Se resuelve desde `self` cuando hay filas marcadas, y desde el contexto
    # de la accion cuando no: MultiRecordViewButton llama al metodo con el
    # recordset VACIO si el boton se declara display="always" y nadie ha
    # marcado nada (getResIds(true) devuelve this.selection, vacia:
    # dynamic_list.js:115-129). El boton actual ya no es "always", pero el
    # respaldo por contexto se conserva: no cuesta nada y cubre el caso.
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_get_consolidado(self):
        Consolidado = self.env['biocreto.requerimiento.consolidado']
        if self:
            consolidados = self.consolidado_id
            if len(consolidados) > 1:
                raise UserError(_(
                    "Las líneas seleccionadas pertenecen a consolidados "
                    "distintos."))
            return consolidados
        consolidado_id = (self.env.context.get('biocreto_consolidado_id')
                          or self.env.context.get('default_consolidado_id'))
        if not consolidado_id:
            raise UserError(_(
                "No se pudo identificar el consolidado. Vuelva a abrirlo "
                "desde el menú Logística > Consolidado."))
        consolidado = Consolidado.browse(consolidado_id).exists()
        if not consolidado:
            raise UserError(_(
                "El consolidado caducó. Vuelva a abrirlo desde el menú "
                "Logística > Consolidado."))
        return consolidado

    # ─────────────────────────────────────────────────────────────────
    # Accion de lote sobre las filas marcadas.
    #
    # Se declara como <button> del <header> SIN display="always": con el
    # valor por defecto ("selection", web/static/src/views/utils.js:236) el
    # cliente lo pinta como BOTON DIRECTO en la barra de seleccion, junto al
    # contador de filas marcadas (list_controller.xml:63-79), y no dentro del
    # desplegable del engranaje. MultiRecordViewButton le pasa las filas
    # marcadas via getResIds(true), que ademas resuelve el caso "seleccionar
    # todo lo que casa con el dominio" (dynamic_list.js:115-129).
    # ─────────────────────────────────────────────────────────────────
    def action_generar_cotizacion(self):
        """Valida las filas marcadas y abre el diálogo del proveedor.

        Las validaciones van AQUI, antes de abrir nada: no tiene sentido pedir
        el proveedor para después avisar de que falta crear un producto.
        """
        if not self:
            raise UserError(_(
                "Marque al menos una fila antes de generar la cotización."))

        consolidado = self._biocreto_get_consolidado()

        sin_producto = self.filtered('sin_producto')
        if sin_producto:
            raise UserError(_(
                "No se puede generar la cotización: hay %(n)s fila(s) sin "
                "producto creado.\n\n%(detalle)s\n\n"
                "Logística debe dar de alta el producto, asignarlo en la "
                "línea del requerimiento y recalcular el consolidado.",
                n=len(sin_producto),
                detalle="\n".join(
                    "- %s (%s)" % (linea.descripcion, linea.usuarios_texto or '')
                    for linea in sin_producto)))

        sin_cantidad = self.filtered(lambda linea: linea.cantidad_comprar <= 0)
        if sin_cantidad:
            raise UserError(_(
                "Indique la cantidad a comprar en estas filas, o "
                "desmárquelas:\n\n%s",
                "\n".join("- %s" % linea.descripcion for linea in sin_cantidad)))

        return {
            'type': 'ir.actions.act_window',
            'name': _("Generar cotización"),
            'res_model': 'biocreto.requerimiento.cotizacion.wizard',
            'view_mode': 'form',
            'views': [[self.env.ref(
                'biocreto_requerimientos.consolidado_cotizacion_view_form').id,
                'form']],
            'target': 'new',
            'context': {
                'default_consolidado_id': consolidado.id,
                'default_linea_ids': self.ids,
            },
        }


class BiocretoRequerimientoCotizacionWizard(models.TransientModel):
    _name = 'biocreto.requerimiento.cotizacion.wizard'
    _description = 'Generar cotización desde el consolidado'

    consolidado_id = fields.Many2one(
        'biocreto.requerimiento.consolidado', string="Consolidado",
        required=True, ondelete='cascade')
    # `relation` explicito: el nombre por convencion pasaria de los 63
    # caracteres de PostgreSQL (odoo/orm/utils.py:102).
    linea_ids = fields.Many2many(
        'biocreto.requerimiento.consolidado.linea', string="Líneas",
        relation='biocreto_cotizacion_wizard_linea_rel',
        column1='wizard_id', column2='linea_id', required=True)

    # required=True EN EL MODELO DEL DIALOGO: el cliente no deja pulsar
    # "Generar" sin proveedor, asi que partner_id nunca puede llegar vacio al
    # create de purchase.order — que lo tiene required=True y ademas NOT NULL
    # en la tabla (verificado). Si el usuario cierra el diálogo, no se crea
    # nada: este registro es transitorio y la SC solo nace en action_generar.
    #
    # El dominio se queda: hay 4 res.partner con supplier_rank > 0 en esta
    # base (UNACEM, Alca Company S.A.C., ...) y son los que usan las 23
    # ordenes de compra existentes.
    partner_id = fields.Many2one(
        'res.partner', string="Proveedor", required=True,
        domain="[('supplier_rank', '>', 0)]")

    def action_generar(self):
        self.ensure_one()
        orden, omitidas = self.consolidado_id._biocreto_crear_cotizacion(
            self.linea_ids, self.partner_id)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Cotización"),
            'res_model': 'purchase.order',
            'res_id': orden.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

# === BIOCRETO CONSOLIDADO v1 — FIN ===
