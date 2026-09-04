from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class BiocretoRequerimiento(models.Model):
    _name = 'biocreto.requerimiento'
    _description = 'Requerimiento Interno'
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
    _order = 'create_date desc'

    _check_company_auto = True

    name = fields.Char(string="Código / Asunto", tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    categoria_id = fields.Many2one(
        'biocreto.requerimiento.categoria', string="Categoría", required=True)
    categoria_image = fields.Binary(related='categoria_id.image')

    # NO related a la categoria: la categoria es compartida entre plantas, la
    # planta de la solicitud sale del usuario que la crea.
    company_id = fields.Many2one(
        'res.company', string="Planta", required=True, index=True,
        default=lambda self: self.env.company)
    solicitante_id = fields.Many2one(
        'res.users', string="Solicitante", check_company=True,
        default=lambda self: self.env.user)

    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado'),
        ('en_proceso', 'En proceso'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ], string="Estado", default='borrador', required=True,
        store=True, index=True, tracking=True, copy=False, group_expand=True)

    # Se llena sola con la fecha y hora del momento de creacion. El default se
    # aplica aunque la categoria tenga has_date = 'no' y el campo no se pinte:
    # los defaults del ORM no dependen de la visibilidad en la vista.
    fecha = fields.Datetime(string="Fecha", default=fields.Datetime.now)
    fecha_inicio = fields.Datetime(string="Desde")
    fecha_fin = fields.Datetime(string="Hasta")
    cantidad = fields.Float(string="Cantidad")
    ubicacion = fields.Char(string="Ubicación")
    partner_id = fields.Many2one('res.partner', string="Contacto", check_company=True)
    referencia = fields.Char(string="Referencia")
    importe = fields.Float(string="Importe")
    motivo = fields.Html(string="Descripción")
    fecha_enviado = fields.Datetime(string="Fecha de envío", readonly=True, copy=False)

    linea_ids = fields.One2many(
        'biocreto.requerimiento.linea', 'requerimiento_id',
        string="Líneas", check_company=True)

    attachment_ids = fields.One2many(
        comodel_name='ir.attachment', inverse_name='res_id',
        domain=[('res_model', '=', 'biocreto.requerimiento')], string="Adjuntos")
    attachment_number = fields.Integer(
        string="Número de adjuntos", compute='_compute_attachment_number')

    # Bloque related a la categoria, patron de approval_request.py:66-79.
    # Conducen los invisible/required del formulario.
    # Campo de apoyo para las expresiones de la lista embebida de lineas:
    # evita repetir la condicion larga en cada columna. Se declara invisible en
    # el formulario para que las celdas lo puedan leer como `parent.…`.
    puede_editar_lineas = fields.Boolean(
        string="Puede editar las líneas", compute='_compute_puede_editar_lineas')

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_puede_editar_lineas(self):
        es_encargado = self.env.user.has_group(
            'biocreto_requerimientos.group_requerimiento_user')
        for requerimiento in self:
            requerimiento.puede_editar_lineas = (
                es_encargado and requerimiento.state in ('enviado', 'en_proceso'))

    # === BIOCRETO CONSOLIDADO v1 — INICIO (bloque PERMANENTE, no borrar en la
    #     reversión) ===
    # Contador del stat button "Compras". Deriva de las líneas, no de un campo
    # propio: el enlace vive en biocreto.requerimiento.linea.purchase_order_id.
    purchase_order_ids = fields.Many2many(
        'purchase.order', string="Órdenes de compra",
        compute='_compute_purchase_order_ids')
    purchase_order_count = fields.Integer(
        string="Número de compras", compute='_compute_purchase_order_ids')

    # v19.0.1.2.0 - ENTREGAS DE MATERIAL
    entrega_ids = fields.One2many(
        'biocreto.requerimiento.entrega', 'requerimiento_id', string="Entregas")
    entrega_count = fields.Integer(
        string="Numero de entregas", compute='_compute_entrega_count')

    @api.depends('entrega_ids')
    def _compute_entrega_count(self):
        for requerimiento in self:
            requerimiento.entrega_count = len(requerimiento.entrega_ids)

    @api.depends('linea_ids.purchase_order_id')
    def _compute_purchase_order_ids(self):
        for requerimiento in self:
            ordenes = requerimiento.linea_ids.purchase_order_id
            requerimiento.purchase_order_ids = ordenes
            requerimiento.purchase_order_count = len(ordenes)

    def action_ver_compras(self):
        """Stat button: abre las OC generadas desde este requerimiento."""
        self.ensure_one()
        ordenes = self.purchase_order_ids
        accion = {
            'type': 'ir.actions.act_window',
            'name': _("Compras"),
            'res_model': 'purchase.order',
            'domain': [('id', 'in', ordenes.ids)],
            'view_mode': 'list,form',
        }
        if len(ordenes) == 1:
            accion.update({
                'res_id': ordenes.id,
                'view_mode': 'form',
                'views': [[False, 'form']],
            })
        return accion
    # === BIOCRETO CONSOLIDADO v1 — FIN (bloque PERMANENTE) ===

    has_date = fields.Selection(related='categoria_id.has_date')
    has_period = fields.Selection(related='categoria_id.has_period')
    has_quantity = fields.Selection(related='categoria_id.has_quantity')
    has_amount = fields.Selection(related='categoria_id.has_amount')
    has_reference = fields.Selection(related='categoria_id.has_reference')
    has_partner = fields.Selection(related='categoria_id.has_partner')
    has_location = fields.Selection(related='categoria_id.has_location')
    has_product = fields.Selection(related='categoria_id.has_product')
    requirer_document = fields.Selection(related='categoria_id.requirer_document')
    automated_sequence = fields.Boolean(related='categoria_id.automated_sequence')

    # ─────────────────────────────────────────────────────────────────
    # Numeracion PLANTA-AAAA-CODIGO#### (ej. ECO-2026-SLT0001)
    # Patron replicado de biocreto_compras/models/purchase_order.py:180-217.
    # Diferencia: el correlativo es independiente por par (categoria, planta),
    # no solo por planta, y el prefijo literal lo escribe el usuario en la
    # categoria (sequence_code) en vez de estar fijado en el codigo.
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _biocreto_build_name_requerimiento(self, categoria, company_id):
        """Construye CODIGO-PLANTA-AAAA-NNNN, ej. REQ-ECO-2026-0058.

        v19.0.1.7.0: cambia SOLO el orden y los separadores. Antes era
        PLANTA-AAAA-CODIGONNNN (ECO-2026-SLTD0058), con el codigo pegado al
        correlativo; ahora el codigo abre el numero y el correlativo queda
        suelto detras del anio. El mecanismo de secuencia no se toca: sigue
        siendo una ir.sequence por par (categoria, compania), padding 4 y
        use_date_range con reinicio anual.

        Si la compañía no tiene plant_code, se omite ese tramo
        (REQ-2026-0058) en vez de romper la creación.
        """
        company = self.env['res.company'].browse(company_id)
        code = (categoria.sequence_code or '').strip().upper()
        if not code:
            return None
        sequence = self._biocreto_ensure_sequence_requerimiento(categoria, company_id)
        correlative = sequence.with_company(company_id).next_by_id()
        year = str(fields.Date.context_today(self).year)
        plant = (company.plant_code or '').upper()
        if plant:
            return f"{code}-{plant}-{year}-{correlative}"
        return f"{code}-{year}-{correlative}"

    @api.model
    def _biocreto_ensure_sequence_requerimiento(self, categoria, company_id):
        """Una ir.sequence por (categoria, compania), creada en lazy.
        Prefijo vacio, padding 4, use_date_range=True -> reinicio anual
        automatico. Mismo patron que
        biocreto_compras._biocreto_ensure_sequence_compras.
        """
        Sequence = self.env['ir.sequence'].sudo()
        seq_code = f'biocreto.requerimiento.{categoria.id}.{company_id}'
        sequence = Sequence.search(
            [('code', '=', seq_code), ('company_id', '=', company_id)], limit=1)
        if not sequence:
            company = self.env['res.company'].browse(company_id)
            sequence = Sequence.create({
                'name': f'BIOCRETO Requerimientos {categoria.name} - {company.name}',
                'code': seq_code,
                'company_id': company_id,
                'padding': 4,
                'number_increment': 1,
                'implementation': 'standard',
                'use_date_range': True,
                'prefix': '',
            })
        return sequence

    # ─────────────────────────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────────────────────────
    def _compute_attachment_number(self):
        """Copiado de approvals/models/approval_request.py:94-99."""
        domain = [('res_model', '=', 'biocreto.requerimiento'), ('res_id', 'in', self.ids)]
        data = self.env['ir.attachment']._read_group(domain, ['res_id'], ['__count'])
        mapped = dict(data)
        for requerimiento in self:
            requerimiento.attachment_number = mapped.get(requerimiento.id, 0)

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        for requerimiento in self:
            if (requerimiento.fecha_inicio and requerimiento.fecha_fin
                    and requerimiento.fecha_inicio > requerimiento.fecha_fin):
                raise ValidationError(_("La fecha inicial debe ser anterior a la final."))

    # ─────────────────────────────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────────────────────────────
    def copy_data(self, default=None):
        """Copiado de approvals/models/approval_request.py:107-109."""
        vals_list = super().copy_data(default=default)
        return [
            dict(vals, name=self.env._("%s (copia)", requerimiento.name))
            for requerimiento, vals in zip(self, vals_list)
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            categoria_id = vals.get('categoria_id')
            categoria = categoria_id and self.env[
                'biocreto.requerimiento.categoria'].browse(categoria_id)
            if categoria and categoria.automated_sequence:
                company_id = vals.get('company_id') or self.env.company.id
                custom_name = self._biocreto_build_name_requerimiento(categoria, company_id)
                if custom_name:
                    vals['name'] = custom_name
        records = super().create(vals_list)
        for record in records:
            record.message_subscribe(partner_ids=record.solicitante_id.partner_id.ids)
        return records

    def write(self, vals):
        """Guardarrail: una solicitud entregada ya no se edita.

        Adaptado de approvals/models/approval_request.py:339-350. Se permite
        siempre archivar/desarchivar y los cambios que vengan de un metodo de
        accion (marcados con el contexto biocreto_state_transition).
        """
        if not self.env.is_admin() and not self.env.context.get('biocreto_state_transition'):
            editable_keys = {'active', 'message_follower_ids', 'message_ids',
                             'activity_ids', 'attachment_ids'}
            if set(vals.keys()) - editable_keys:
                for requerimiento in self.filtered(lambda r: r.state == 'entregado'):
                    raise AccessError(_(
                        "El requerimiento %s ya fue entregado y no se puede modificar.",
                        requerimiento.display_name))

        if 'solicitante_id' in vals:
            for requerimiento in self:
                requerimiento.message_unsubscribe(
                    partner_ids=requerimiento.solicitante_id.partner_id.ids)

        res = super().write(vals)

        if 'solicitante_id' in vals:
            for requerimiento in self:
                requerimiento.message_subscribe(
                    partner_ids=requerimiento.solicitante_id.partner_id.ids)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_attachments(self):
        """Copiado de approvals/models/approval_request.py:122-129."""
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'biocreto.requerimiento'),
            ('res_id', 'in', self.ids),
        ])
        if attachments:
            attachments.unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_entregado(self):
        for requerimiento in self:
            if requerimiento.state == 'entregado':
                raise UserError(_(
                    "No se puede eliminar un requerimiento entregado. Archívelo en su lugar."))

    # ─────────────────────────────────────────────────────────────────
    # Metodos de accion (maquina de estados)
    # Las validaciones van AQUI, antes de escribir, nunca en @api.constrains.
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_write_state(self, state):
        return self.with_context(biocreto_state_transition=True).write({'state': state})

    def action_enviar(self):
        for requerimiento in self:
            if requerimiento.state != 'borrador':
                raise UserError(_(
                    "Solo se puede enviar un requerimiento en borrador."))
            # Comparacion POSITIVA contra 'required', no una negacion de
            # 'optional'. Es lo que permite que el tercer valor 'no'
            # (v19.0.1.5.0) no exija adjunto: con `!= 'optional'` habria
            # pasado a exigirlo, justo lo contrario de lo buscado.
            if requerimiento.requirer_document == 'required' and not requerimiento.attachment_number:
                raise UserError(_("Debe adjuntar al menos un documento."))
            # Solo se exigen lineas cuando la categoria las marca como
            # obligatorias. Con 'optional' la solicitud puede ir sin lineas.
            if requerimiento.has_product == 'required' and not requerimiento.linea_ids:
                raise UserError(_("Debe agregar al menos una línea de producto."))
        self.with_context(biocreto_state_transition=True).write({
            'state': 'enviado',
            'fecha_enviado': fields.Datetime.now(),
        })

    def action_procesar(self):
        for requerimiento in self:
            if requerimiento.state != 'enviado':
                raise UserError(_(
                    "Solo se puede procesar un requerimiento enviado."))
        return self._biocreto_write_state('en_proceso')

    # v19.0.1.2.0: `action_entregar` ELIMINADO. El paso a 'entregado' ya
    # no es un boton manual: lo decide `_biocreto_cerrar_desde_entregas`
    # cuando la ultima linea deja de estar pendiente o parcial.
    def _biocreto_cerrar_desde_entregas(self, lineas_tocadas):
        """Refresca el estado de las lineas entregadas y cierra si toca.

        `cantidad_entregada_requerimiento` es un compute ALMACENADO que
        depende del state de la entrega; quien llame aqui ya debe haber
        hecho flush para que el valor este al dia.

        El requerimiento pasa a 'entregado' cuando ninguna linea queda en
        'pendiente' ni en 'parcial'. Las canceladas no cuentan, asi que
        un requerimiento con una linea cancelada y el resto atendidas
        tambien cierra.
        """
        for requerimiento in self:
            for linea in lineas_tocadas & requerimiento.linea_ids:
                nuevo_estado = linea._biocreto_estado_por_entregas()
                if nuevo_estado != linea.estado:
                    linea.with_context(
                        biocreto_state_transition=True).estado = nuevo_estado
            abiertas = requerimiento.linea_ids.filtered(
                lambda linea: linea.estado in ('pendiente', 'parcial'))
            if not abiertas and requerimiento.state == 'en_proceso':
                requerimiento._biocreto_write_state('entregado')

    def action_registrar_entrega(self):
        """Abre el modal de entrega SIN crear el registro todavia.

        Se pasa `default_requerimiento_id` por contexto en vez de crear
        un borrador y devolver su res_id: asi, si el usuario descarta, no
        queda ninguna entrega huerfana en la base. El One2many de lineas
        se rellena solo porque es un compute almacenado con
        precompute=True, y el cliente web evalua los computes almacenados
        tambien en registros sin guardar -- mismo mecanismo que el
        asistente de devolucion de stock
        (stock/wizard/stock_picking_return.py:103).
        """
        self.ensure_one()
        if self.state != 'en_proceso':
            raise UserError(_(
                "Solo se pueden registrar entregas de un requerimiento en proceso."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Registrar entrega"),
            'res_model': 'biocreto.requerimiento.entrega',
            'view_mode': 'form',
            # xmlid explicito, no [[False, 'form']]: el modelo de entrega
            # tiene DOS vistas formulario (el asistente y el dialogo de
            # firma) y dejar que Odoo elija por prioridad es apostar a que
            # nadie las toque.
            'views': [[self.env.ref(
                'biocreto_requerimientos.'
                'biocreto_requerimiento_entrega_view_form').id, 'form']],
            'target': 'new',
            'context': {'default_requerimiento_id': self.id},
        }

    def action_ver_entregas(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Entregas de %s", self.name or ''),
            'res_model': 'biocreto.requerimiento.entrega',
            'view_mode': 'list,form',
            'domain': [('requerimiento_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_cancelar(self):
        es_encargado = self.env.user.has_group(
            'biocreto_requerimientos.group_requerimiento_user')
        for requerimiento in self:
            if requerimiento.state == 'entregado':
                raise UserError(_(
                    "No se puede cancelar un requerimiento ya entregado."))
            if requerimiento.state == 'cancelado':
                raise UserError(_("El requerimiento ya está cancelado."))
            if not es_encargado and requerimiento.state not in ('borrador', 'enviado'):
                raise UserError(_(
                    "Solo un encargado puede cancelar un requerimiento en proceso."))
        return self._biocreto_write_state('cancelado')

    def action_volver_borrador(self):
        for requerimiento in self:
            if requerimiento.state != 'cancelado':
                raise UserError(_(
                    "Solo se puede volver a borrador un requerimiento cancelado."))
        self.linea_ids.with_context(biocreto_state_transition=True).write({
            'estado': 'pendiente',
            'motivo': False,
        })
        return self._biocreto_write_state('borrador')

    def action_get_attachment_view(self):
        """Copiado de approvals/models/approval_request.py:141-146."""
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [
            ('res_model', '=', 'biocreto.requerimiento'), ('res_id', 'in', self.ids)]
        res['context'] = {
            'default_res_model': 'biocreto.requerimiento', 'default_res_id': self.id}
        return res

    def _track_subtype(self, init_values):
        """Copiado de approvals/models/approval_request.py:373-377."""
        self.ensure_one()
        if 'state' in init_values:
            return self.env.ref('biocreto_requerimientos.mt_requerimiento_state')
        return super()._track_subtype(init_values)
