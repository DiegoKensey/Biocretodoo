from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    biocreto_carga_ids = fields.One2many(
        'biocreto.carga', 'production_id',
        string="Cargas",
    )
    biocreto_producido_cadena = fields.Float(
        string="Producido acumulado (cadena)",
        compute='_compute_biocreto_producido_cadena',
        digits='Product Unit of Measure',
        help="Suma del volumen operativo de cargas terminadas de toda la cadena.",
    )
    biocreto_total_cadena = fields.Float(
        string="Total planificado (cadena)",
        compute='_compute_biocreto_producido_cadena',
        digits='Product Unit of Measure',
    )
    biocreto_estado_cadena = fields.Selection(
        [
            ('confirmada', 'Confirmada'),
            ('en_proceso', 'En proceso'),
            ('terminada', 'Terminada'),
            ('cancelada', 'Cancelada'),
        ],
        string="Estado de cadena",
        compute='_compute_biocreto_estado_cadena',
    )

    @api.depends('production_group_id.production_ids.biocreto_carga_ids.volumen_operativo',
                 'production_group_id.production_ids.biocreto_carga_ids.estado',
                 'production_group_id.production_ids.product_qty',
                 'product_qty')
    def _compute_biocreto_producido_cadena(self):
        for mo in self:
            group = mo.production_group_id
            if not group:
                mo.biocreto_producido_cadena = sum(
                    c.volumen_operativo for c in mo.biocreto_carga_ids
                    if c.estado == 'terminada'
                )
                mo.biocreto_total_cadena = mo.product_qty
                continue
            all_cargas = group.production_ids.mapped('biocreto_carga_ids')
            mo.biocreto_producido_cadena = sum(
                c.volumen_operativo for c in all_cargas if c.estado == 'terminada'
            )
            # Total = suma product_qty de todas las MOs de la cadena (cerradas + abiertas).
            # Tras un backorder Odoo parte qty original en (parcial cerrado + resto abierto).
            mo.biocreto_total_cadena = sum(p.product_qty for p in group.production_ids)

    @api.depends('production_group_id.production_ids.state')
    def _compute_biocreto_estado_cadena(self):
        for mo in self:
            group = mo.production_group_id
            states = group.production_ids.mapped('state') if group else [mo.state]
            if states and all(s == 'done' for s in states):
                mo.biocreto_estado_cadena = 'terminada'
            elif states and all(s in ('done', 'cancel') for s in states) and any(s == 'cancel' for s in states):
                mo.biocreto_estado_cadena = 'cancelada'
            elif any(s in ('progress', 'to_close') for s in states):
                mo.biocreto_estado_cadena = 'en_proceso'
            else:
                mo.biocreto_estado_cadena = 'confirmada'

    def biocreto_get_cadena_activa(self):
        """Devuelve la MO abierta actual de la cadena (mayor backorder_sequence en estado abierto)."""
        self.ensure_one()
        group = self.production_group_id
        if not group:
            return self
        activas = group.production_ids.filtered(
            lambda p: p.state in ('draft', 'confirmed', 'progress', 'to_close')
        )
        if not activas:
            return self.env['mrp.production']
        return activas.sorted(lambda p: p.backorder_sequence or 0, reverse=True)[:1]

    def action_biocreto_cancelar_cadena(self):
        """Cancela todas las OF abiertas de la cadena."""
        for mo in self:
            group = mo.production_group_id
            abiertas = (group.production_ids if group else mo).filtered(
                lambda p: p.state not in ('done', 'cancel')
            )
            abiertas.action_cancel()
