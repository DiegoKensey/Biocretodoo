from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BiocretoRequerimientoLinea(models.Model):
    _name = 'biocreto.requerimiento.linea'
    _description = 'Línea de Requerimiento'

    _check_company_auto = True

    requerimiento_id = fields.Many2one(
        'biocreto.requerimiento', string="Requerimiento",
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        string="Compañía", related='requerimiento_id.company_id',
        store=True, readonly=True, index=True)

    # Los tres computes siguen el patron canonico v19 de
    # approvals/models/approval_product_line.py:22-35:
    # store=True, readonly=False, precompute=True -> se autollenan al elegir
    # producto pero el usuario puede sobrescribirlos. NO se usa @api.onchange.
    categoria_producto_id = fields.Many2one(
        'product.category', string="Categoría",
        compute='_compute_categoria_producto_id',
        store=True, readonly=False, precompute=True)
    categoria_color = fields.Integer(
        related='categoria_producto_id.color', string="Color de categoría")

    # OJO con el nombre: el widget many2one_uom resuelve el modelo de producto
    # leyendo del registro un campo cuyo nombre viene de la prop `productField`,
    # que por defecto vale literalmente 'product_id'
    # (uom/static/src/components/many2one_uom/many2one_uom_field.js:47) y que
    # getProductRelatedModel usa para sacar la relacion
    # (many2x_uom_tags/many2x_uom_tags.js:11-19). Con otro nombre el widget
    # lanza una excepcion en el setup y rompe el ciclo de vida de OWL.
    # Se usan los nombres nativos de approval.product.line.
    product_id = fields.Many2one(
        'product.product', string="Producto", check_company=True)
    descripcion = fields.Char(
        string="Descripción", required=True,
        compute='_compute_descripcion', store=True, readonly=False, precompute=True)
    sin_producto = fields.Boolean(
        string="Sin producto", compute='_compute_sin_producto',
        help="Marcado cuando la línea no tiene producto asociado: logística debe "
             "dar de alta el SKU.")
    cantidad = fields.Float(string="Cantidad", default=1.0)
    product_uom_id = fields.Many2one(
        'uom.uom', string="Unidad",
        compute='_compute_product_uom_id', store=True, readonly=False, precompute=True)
    observacion = fields.Char(
        string="Observación", help="Talla, especificación, placa, etc.")

    # Campo de candidatos que alimenta el domain de product_id en las vistas.
    # No se usa ('categ_id','child_of', categoria_producto_id) directamente
    # porque con la categoria vacia el operador se optimiza a FALSE
    # (odoo/orm/domains.py:1721-1722: `if value is False: return _FALSE_DOMAIN`)
    # y el desplegable de producto sale sin resultados. Patron canonico v19,
    # el mismo de account/views/account_payment_view.xml:277
    # (available_journal_ids) y helpdesk/views/helpdesk_ticket_views.xml:292
    # (domain_user_ids). Compute NO almacenado.
    producto_candidato_ids = fields.Many2many(
        'product.product', string="Productos disponibles",
        compute='_compute_producto_candidato_ids')

    # v19.0.1.2.0: se anade 'parcial'. Anadir un valor a un Selection NO
    # requiere migracion: la columna es varchar y las filas existentes
    # conservan su valor. El orden importa solo para el desplegable.
    estado = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('parcial', 'Parcial'),
        ('atendido', 'Atendido'),
        ('cancelado', 'Cancelado'),
    ], string="Estado", default='pendiente', required=True)
    motivo = fields.Char(string="Motivo", help="Motivo de cancelación de la línea.")

    # ═════════════════════════════════════════════════════════════════
    # v19.0.1.2.0 — ENTREGA DE MATERIALES
    # ═════════════════════════════════════════════════════════════════
    entrega_linea_ids = fields.One2many(
        'biocreto.requerimiento.entrega.linea', 'requerimiento_linea_id',
        string="Líneas de entrega")

    # Almacenado porque alimenta `estado`, `cantidad_pendiente` y la
    # decision de cerrar el requerimiento: se lee en cada apertura del
    # modal y en cada confirmacion. Solo cuentan las entregas
    # CONFIRMADAS -- un borrador abandonado no debe descontar nada.
    cantidad_entregada_requerimiento = fields.Float(
        string="Entregado", digits='Product Unit', readonly=True,
        compute='_compute_cantidad_entregada_requerimiento', store=True)
    cantidad_pendiente = fields.Float(
        string="Pendiente", digits='Product Unit',
        compute='_compute_cantidad_pendiente')

    # NO almacenado: el stock cambia por fuera del modulo (fabricacion,
    # compras, ajustes) y un stored quedaria rancio al instante.
    stock_disponible = fields.Float(
        string="Stock disponible", digits='Product Unit',
        compute='_compute_stock_disponible')

    # `is_storable` es LO QUE DECIDE si el movimiento descuenta algo.
    # NO se usa `type`: en v19 vale ('consu', 'service', 'combo') y un
    # 'consu' con is_storable=False recorre _action_done entero, queda
    # en state='done' y genera CERO quants -- exito falso, verificado
    # empiricamente en el recon.
    afecta_inventario = fields.Boolean(
        string="Afecta inventario", compute='_compute_afecta_inventario')
    puede_entregarse = fields.Boolean(
        string="Puede entregarse", compute='_compute_puede_entregarse')

    @api.depends('entrega_linea_ids.cantidad_entregar',
                 'entrega_linea_ids.entrega_id.state')
    def _compute_cantidad_entregada_requerimiento(self):
        for linea in self:
            linea.cantidad_entregada_requerimiento = sum(
                el.cantidad_entregar for el in linea.entrega_linea_ids
                if el.entrega_id.state == 'confirmado')

    @api.depends('cantidad', 'cantidad_entregada_requerimiento')
    def _compute_cantidad_pendiente(self):
        for linea in self:
            linea.cantidad_pendiente = max(
                0.0, linea.cantidad - linea.cantidad_entregada_requerimiento)

    @api.depends('product_id')
    def _compute_afecta_inventario(self):
        for linea in self:
            linea.afecta_inventario = bool(
                linea.product_id and linea.product_id.is_storable)

    @api.depends('product_id', 'company_id')
    def _compute_stock_disponible(self):
        """qty_available por ALMACEN, no por ubicacion.

        Se usa `warehouse_id` en el contexto y NO `location_id`: el
        almacen agrega todas sus ubicaciones internas hijas
        (stock/models/product.py, _get_domain_locations), asi que el dato
        no se rompe cuando el material esta repartido. Tampoco se toca
        `allowed_company_ids`: eso alteraria las reglas multicompania de
        toda la transaccion.
        """
        for linea in self:
            if not linea.product_id or not linea.product_id.is_storable:
                linea.stock_disponible = 0.0
                continue
            company = linea.company_id or self.env.company
            almacen = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)], limit=1)
            if not almacen:
                linea.stock_disponible = 0.0
                continue
            linea.stock_disponible = linea.product_id.with_company(
                company).with_context(warehouse_id=almacen.id).qty_available

    @api.depends('product_id', 'estado', 'cantidad_pendiente')
    def _compute_puede_entregarse(self):
        for linea in self:
            linea.puede_entregarse = bool(
                linea.product_id
                and linea.estado != 'cancelado'
                and linea.cantidad_pendiente > 0)

    def _biocreto_estado_por_entregas(self):
        """Estado que le corresponde a la linea segun lo ya entregado.

        `cancelado` es terminal: se devuelve intacto y NUNCA se pisa.
        """
        self.ensure_one()
        if self.estado == 'cancelado':
            return 'cancelado'
        entregado = self.cantidad_entregada_requerimiento
        if entregado <= 0:
            return 'pendiente'
        if entregado >= self.cantidad:
            return 'atendido'
        return 'parcial'

    # === BIOCRETO CONSOLIDADO v1 — INICIO (bloque PERMANENTE, no borrar en la
    #     reversión) ===
    # Trazabilidad requerimiento -> compra. El enlace es a nivel de LINEA,
    # igual que el nativo approvals (approval_product_line.py:28), no a nivel
    # de cabecera: una misma solicitud puede repartirse entre varias OC.
    # Sobrevive aunque se descarte el consolidado: si mañana la compra se
    # genera de otra forma, este es el campo que se rellena.
    purchase_line_id = fields.Many2one(
        'purchase.order.line', string="Línea de compra",
        readonly=True, copy=False, index=True)
    purchase_order_id = fields.Many2one(
        related='purchase_line_id.order_id', string="Orden de compra",
        store=True)
    # === BIOCRETO CONSOLIDADO v1 — FIN (bloque PERMANENTE) ===

    # Indice de color del badge de estado. El widget selection_badge NO admite
    # decoration-* (su extractProps solo toma domain, size y color_field:
    # list_badge_selection_field.js:38-46), asi que el color se pasa con un
    # Integer. Indices de $o-colors verificados en
    # web/static/src/scss/secondary_variables.scss:8-9 ->
    # 0 = #a2a2a2 gris, 3 = #e8bb1d amarillo, 10 = #61c36e verde.
    estado_color = fields.Integer(
        string="Color del estado", compute='_compute_estado_color')

    # Version autonoma del permiso: se usa en el modal y en la tarjeta kanban,
    # donde no existe `parent`. En la lista embebida se usa en su lugar
    # parent.puede_editar_lineas, que evalua lo mismo.
    # Patron de approval.approver.can_edit (approval_approver.py:39, 74-80).
    puede_editar_estado = fields.Boolean(
        string="Puede editar el estado", compute='_compute_puede_editar_estado')

    @api.depends('estado')
    def _compute_estado_color(self):
        # Indices de $o-colors verificados en
        # web/static/src/scss/secondary_variables.scss:8-9:
        #   0 = #a2a2a2 gris | 2 = #dc8534 naranja
        #   3 = #e8bb1d amarillo | 10 = #61c36e verde
        mapa = {'pendiente': 3, 'parcial': 2, 'atendido': 10, 'cancelado': 0}
        for linea in self:
            linea.estado_color = mapa.get(linea.estado, 0)

    @api.depends('requerimiento_id.state')
    @api.depends_context('uid')
    def _compute_puede_editar_estado(self):
        es_encargado = self.env.user.has_group(
            'biocreto_requerimientos.group_requerimiento_user')
        for linea in self:
            linea.puede_editar_estado = (
                es_encargado
                and linea.requerimiento_id.state in ('enviado', 'en_proceso'))

    @api.depends('product_id')
    def _compute_descripcion(self):
        for linea in self:
            if linea.product_id:
                linea.descripcion = (
                    linea.product_id.description_purchase
                    or linea.product_id.display_name)
            else:
                linea.descripcion = linea.descripcion or False

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for linea in self:
            if linea.product_id:
                linea.product_uom_id = linea.product_id.uom_id
            else:
                linea.product_uom_id = linea.product_uom_id or False

    @api.depends('product_id')
    def _compute_categoria_producto_id(self):
        """Si el usuario elige primero el producto, la categoría se autollena.
        Si elige primero la categoría, el compute no la pisa porque el producto
        aún está vacío (y el campo es readonly=False)."""
        for linea in self:
            if linea.product_id:
                linea.categoria_producto_id = linea.product_id.categ_id
            else:
                linea.categoria_producto_id = linea.categoria_producto_id or False

    @api.depends('product_id')
    def _compute_sin_producto(self):
        for linea in self:
            linea.sin_producto = not linea.product_id

    @api.depends('categoria_producto_id')
    def _compute_producto_candidato_ids(self):
        Product = self.env['product.product']
        for linea in self:
            if linea.categoria_producto_id:
                linea.producto_candidato_ids = Product.search(
                    [('categ_id', 'child_of', linea.categoria_producto_id.id)])
            else:
                linea.producto_candidato_ids = Product.search([])

    def _biocreto_check_motivo(self, vals_estado, vals_motivo):
        """Motivo obligatorio al cancelar una línea.

        Se valida aquí y no en @api.constrains por la restricción del Paso 13.
        """
        for linea in self:
            estado = vals_estado if vals_estado is not None else linea.estado
            motivo = vals_motivo if vals_motivo is not None else linea.motivo
            if estado == 'cancelado' and not (motivo or '').strip():
                raise UserError(_(
                    "Indique el motivo para cancelar la línea «%s».",
                    linea.descripcion or ''))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._biocreto_check_motivo(None, None)
        return records

    def write(self, vals):
        if 'estado' in vals or 'motivo' in vals:
            self._biocreto_check_motivo(vals.get('estado'), vals.get('motivo'))
        return super().write(vals)

    def action_atender(self):
        return self.write({'estado': 'atendido'})

    def action_abrir_linea(self):
        """Abre la línea en un diálogo de Odoo.

        `target: 'new'` es lo que la muestra como modal. El mecanismo nativo
        `open_form_view="True"` no sirve aquí: su switchToForm hace doAction
        SIN target (x2many_field.js:269-281), o sea target 'current', y navega
        a la página completa.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Detalle de la línea"),
            'res_model': 'biocreto.requerimiento.linea',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }
