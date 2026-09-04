from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BiocretoProbeta(models.Model):
    _name = 'biocreto.probeta'
    _description = 'Probeta de laboratorio (BIOCRETO)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sale_id desc, name'

    # ------------------------------------------------------------------
    # Identidad
    # name = L{pos}-{correlativo-orden}-{fc}-PRB{nn}
    #   pos            = posicion de la linea Concreto en la orden (1..N)
    #                    Regla: SOLO se cuentan lineas de Concreto. Producto
    #                    no-concreto, secciones y notas no consumen slot.
    #   correlativo    = ultimo segmento del o.name tras el ultimo '-'
    #                    (formato biocreto '2026-CFC-DO-0023' -> '0023')
    #   fc             = biocreto_fc_resistencia del producto (int, kg/cm2)
    #   nn             = correlativo dentro de la linea (01, 02...)
    # ------------------------------------------------------------------
    name = fields.Char(readonly=True, index=True, copy=False)

    sale_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string="Línea de venta",
        required=True,
        ondelete='cascade',
        index=True,
    )
    sale_id = fields.Many2one(
        related='sale_line_id.order_id',
        store=True,
        index=True,
        string="Orden",
    )
    partner_id = fields.Many2one(
        related='sale_id.partner_id',
        store=True,
        string="Cliente",
    )
    company_id = fields.Many2one(
        related='sale_id.company_id',
        store=True,
        string="Compañía",
    )

    # Datos que viajan por related (readonly)
    bom_id = fields.Many2one(
        related='sale_line_id.bom_id',
        store=True,
        string="Diseño de mezcla",
    )
    estructura = fields.Many2one(
        related='sale_line_id.biocreto_estructura',
        store=True,
        string="Estructura",
    )
    biocreto_fc_resistencia = fields.Integer(
        related='sale_line_id.product_id.product_tmpl_id.biocreto_fc_resistencia',
        store=True,
        string="Resistencia f'c",
    )

    # Editable por lab
    tamano = fields.Many2one('biocreto.probeta.tamano', string="Tamaño")
    edad = fields.Many2one('biocreto.probeta.edad', string="Edad")
    fecha_moldeo = fields.Date(string="Fecha de moldeo", tracking=True)
    fecha_rotura_programada = fields.Date(
        string="Rotura programada",
        compute='_compute_fecha_rotura_programada',
        store=True,
    )
    resistencia_obtenida = fields.Float(
        string="Resistencia obtenida (kg/cm²)",
        digits=(10, 2),
    )
    observaciones = fields.Text()

    estado = fields.Selection([
        ('en_proceso', 'En proceso'),
        ('moldeada', 'Moldeada'),
        ('roturada', 'Roturada'),
        ('certificada', 'Certificada'),
    ], default='en_proceso', tracking=True, required=True, string="Estado")

    # ------------------------------------------------------------------
    # Compute: fecha_rotura_programada
    # ------------------------------------------------------------------
    @api.depends('fecha_moldeo', 'edad.valor')
    def _compute_fecha_rotura_programada(self):
        for p in self:
            if p.fecha_moldeo and p.edad and p.edad.valor:
                p.fecha_rotura_programada = p.fecha_moldeo + timedelta(days=p.edad.valor)
            else:
                p.fecha_rotura_programada = False

    # ------------------------------------------------------------------
    # Actividad "Rotura de probeta" — sincronizada con fecha_rotura_programada
    # (crear si no existe, reprogramar si cambia, sin duplicar).
    # ------------------------------------------------------------------
    def _biocreto_activity_type_rotura(self):
        # Reusamos mail.mail_activity_data_todo (existe en toda instalacion).
        # Si el proyecto agrega en el futuro un tipo custom "Rotura", basta
        # con reapuntar aqui.
        return self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

    def _biocreto_sync_actividad_rotura(self):
        act_type = self._biocreto_activity_type_rotura()
        if not act_type:
            return
        for probeta in self:
            if not probeta.fecha_rotura_programada or probeta.estado in ('roturada', 'certificada'):
                continue
            # Buscar actividad existente del mismo type sobre esta probeta.
            dom = [
                ('res_model', '=', 'biocreto.probeta'),
                ('res_id', '=', probeta.id),
                ('activity_type_id', '=', act_type.id),
                ('summary', '=', _("Rotura de probeta")),
            ]
            existente = self.env['mail.activity'].search(dom, limit=1)
            if existente:
                if existente.date_deadline != probeta.fecha_rotura_programada:
                    existente.write({'date_deadline': probeta.fecha_rotura_programada})
            else:
                probeta.activity_schedule(
                    'mail.mail_activity_data_todo',
                    date_deadline=probeta.fecha_rotura_programada,
                    summary=_("Rotura de probeta"),
                )

    # ------------------------------------------------------------------
    # Nomenclatura: L{pos}-{correlativo}-{fc}-PRB{nn}
    # ------------------------------------------------------------------
    @api.model
    def _biocreto_correlativo_orden(self, order):
        if not order or not order.name:
            return '----'
        return order.name.rsplit('-', 1)[-1]

    @api.model
    def _biocreto_posicion_linea_concreto(self, line):
        """1-based position within the CONCRETO lines of the order.
        Se cuentan solo lineas de Concreto (biocreto_product_categ == 'Concreto');
        secciones, notas y productos no-Concreto NO consumen slot."""
        if not line or not line.order_id:
            return 0
        concretos = line.order_id.order_line.filtered(
            lambda l: not l.display_type and l.biocreto_product_categ == 'Concreto'
        ).sorted(key=lambda l: (l.sequence, l.id))
        for idx, l in enumerate(concretos, start=1):
            if l.id == line.id:
                return idx
        return 0

    @api.model
    def _biocreto_next_nn(self, sale_line_id):
        """Siguiente nn para probetas de esta linea."""
        existing = self.search([('sale_line_id', '=', sale_line_id)])
        return len(existing) + 1

    @api.model
    def _biocreto_build_name(self, line, nn=None):
        pos = self._biocreto_posicion_linea_concreto(line)
        corr = self._biocreto_correlativo_orden(line.order_id)
        fc = line.product_id.product_tmpl_id.biocreto_fc_resistencia or 0
        if nn is None:
            nn = self._biocreto_next_nn(line.id)
        return f"L{pos}-{corr}-{fc}-PRB{nn:02d}"

    def _biocreto_resync_names(self):
        """Renombra las probetas de una misma linea manteniendo el orden por
        id (mas viejas primero) para que el nn quede secuencial 01, 02, ...
        Se dispara tras borrado."""
        by_line = {}
        for p in self:
            by_line.setdefault(p.sale_line_id.id, True)
        for line_id in by_line:
            hermanas = self.search([('sale_line_id', '=', line_id)], order='id asc')
            for idx, sib in enumerate(hermanas, start=1):
                new_name = self._biocreto_build_name(sib.sale_line_id, nn=idx)
                if sib.name != new_name:
                    sib.name = new_name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                line = self.env['sale.order.line'].browse(vals.get('sale_line_id'))
                vals['name'] = self._biocreto_build_name(line)
        records = super().create(vals_list)
        records._biocreto_sync_actividad_rotura()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(k in vals for k in ('fecha_moldeo', 'edad', 'estado')):
            self._biocreto_sync_actividad_rotura()
        return result

    def unlink(self):
        # Snapshot de las lineas afectadas antes de borrar, para resyncear
        # los names de las hermanas restantes.
        lineas = self.mapped('sale_line_id')
        res = super().unlink()
        if lineas:
            hermanas = self.env['biocreto.probeta'].search([
                ('sale_line_id', 'in', lineas.ids)
            ])
            hermanas._biocreto_resync_names()
        return res

    # ------------------------------------------------------------------
    # Acciones de estado
    # ------------------------------------------------------------------
    def action_biocreto_moldear(self):
        for p in self:
            if p.estado != 'en_proceso':
                continue
            if not p.fecha_moldeo or not p.edad:
                raise UserError(_(
                    "Para moldear la probeta debe registrar Fecha de moldeo y Edad."
                ))
            p.estado = 'moldeada'

    def action_biocreto_roturar(self):
        for p in self:
            if p.estado != 'moldeada':
                continue
            if not p.resistencia_obtenida:
                raise UserError(_(
                    "Para roturar la probeta debe registrar la Resistencia obtenida."
                ))
            p.estado = 'roturada'

    def action_biocreto_certificar(self):
        self.ensure_one()
        if self.estado != 'roturada':
            raise UserError(_("Solo se pueden certificar probetas Roturadas."))
        self.estado = 'certificada'
        return {
            'effect': {
                'fadeout': 'slow',
                'message': _('Probeta certificada'),
                'type': 'rainbow_man',
            }
        }
