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
        related='sale_line_id.order_id',
        store=True,
        string="Orden",
        index=True,
    )
    partner_id = fields.Many2one(
        related='sale_id.partner_id',
        store=True,
        string="Cliente",
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
        related='sale_id.company_id',
        store=True,
        string="Compañía",
    )

    # ------------------------------------------------------------------
    # Nomenclatura: L{pos}-{correlativo}-{fc}-M{n}-SLP0{1|2}
    #   pos, correlativo, fc: mismas reglas que biocreto.probeta
    #   M{n}: 1-based por mixer DISTINTO dentro de la orden, en el
    #         ORDEN en que aparecen los slumps (primer mixer visto = M1).
    #   SLP01 = planta ; SLP02 = obra
    # ------------------------------------------------------------------
    @api.model
    def _biocreto_mixer_index(self, sale_id, mixer_id):
        if not sale_id:
            return 1
        # Lista de mixers UNICOS en el orden de creacion de los slumps existentes.
        siblings = self.search([('sale_id', '=', sale_id)], order='id asc')
        seen = []
        for s in siblings:
            mid = s.mixer_id.id
            if mid and mid not in seen:
                seen.append(mid)
        if mixer_id and mixer_id not in seen:
            seen.append(mixer_id)
        try:
            return seen.index(mixer_id) + 1 if mixer_id else 1
        except ValueError:
            return len(seen) + 1

    @api.model
    def _biocreto_build_name(self, line, mixer_id, tipo):
        Probeta = self.env['biocreto.probeta']
        pos = Probeta._biocreto_posicion_linea_concreto(line)
        corr = Probeta._biocreto_correlativo_orden(line.order_id)
        fc = line.product_id.product_tmpl_id.biocreto_fc_resistencia or 0
        m_idx = self._biocreto_mixer_index(line.order_id.id, mixer_id)
        slp = '01' if tipo == 'planta' else '02'
        return f"L{pos}-{corr}-{fc}-M{m_idx}-SLP{slp}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                line = self.env['sale.order.line'].browse(vals.get('sale_line_id'))
                vals['name'] = self._biocreto_build_name(
                    line,
                    vals.get('mixer_id'),
                    vals.get('tipo') or 'planta',
                )
        return super().create(vals_list)
