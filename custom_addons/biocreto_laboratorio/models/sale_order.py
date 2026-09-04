from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Contadores para smart buttons
    # ------------------------------------------------------------------
    biocreto_probeta_count = fields.Integer(
        string="Probetas",
        compute='_compute_biocreto_probeta_count',
    )
    biocreto_slump_count = fields.Integer(
        string="Slumps",
        compute='_compute_biocreto_slump_count',
    )

    @api.depends('order_line.biocreto_probeta_ids')
    def _compute_biocreto_probeta_count(self):
        for order in self:
            order.biocreto_probeta_count = self.env['biocreto.probeta'].search_count([
                ('sale_id', '=', order.id),
            ])

    def _compute_biocreto_slump_count(self):
        for order in self:
            order.biocreto_slump_count = self.env['biocreto.slump'].search_count([
                ('sale_id', '=', order.id),
            ])

    # ------------------------------------------------------------------
    # Generacion automatica de probetas al confirmar la OV.
    # super() PRIMERO (las validaciones del proyecto viven ahi).
    # Idempotente: si la linea ya tiene probetas, no crea mas.
    # ------------------------------------------------------------------
    def action_confirm(self):
        result = super().action_confirm()
        Probeta = self.env['biocreto.probeta'].sudo()
        for order in self:
            if order.state != 'sale':
                continue
            for line in order.order_line:
                if line.display_type:
                    continue
                if line.biocreto_product_categ != 'Concreto':
                    continue
                if line.biocreto_probetas_a_generar <= 0:
                    continue
                if line.biocreto_probeta_ids:
                    # Idempotente: no re-generar si ya existen.
                    continue
                for _i in range(line.biocreto_probetas_a_generar):
                    Probeta.create({'sale_line_id': line.id})
        return result

    # ------------------------------------------------------------------
    # Acciones de los smart buttons
    # ------------------------------------------------------------------
    def action_view_biocreto_probetas(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Probetas',
            'res_model': 'biocreto.probeta',
            'view_mode': 'list,form,kanban,calendar,activity',
            'domain': [('sale_id', '=', self.id)],
            'context': {'default_sale_id': self.id},
        }

    def action_view_biocreto_slumps(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Slumps',
            'res_model': 'biocreto.slump',
            'view_mode': 'list,form',
            'domain': [('sale_id', '=', self.id)],
            'context': {'default_sale_id': self.id},
        }
