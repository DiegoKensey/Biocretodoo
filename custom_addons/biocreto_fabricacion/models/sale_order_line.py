from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    biocreto_carga_ids = fields.One2many(
        'biocreto.carga', 'sale_line_id',
        string="Cargas producidas",
    )
    biocreto_produccion_real = fields.Float(
        string="Produccion real (m3)",
        compute='_compute_biocreto_produccion_real',
        store=True,
        digits='Product Unit of Measure',
        help="Suma de volumen_operativo de cargas terminadas de las OF ligadas a la linea.",
    )

    @api.depends('biocreto_carga_ids.volumen_operativo', 'biocreto_carga_ids.estado')
    def _compute_biocreto_produccion_real(self):
        for line in self:
            line.biocreto_produccion_real = sum(
                c.volumen_operativo for c in line.biocreto_carga_ids
                if c.estado == 'terminada'
            )

    # ------------------------------------------------------------------
    # Fase 2 del costo compensado (anunciada en el help de sale_extension):
    # cuando hay produccion real, usarla como divisor en lugar del volumen
    # operativo planeado.
    # ------------------------------------------------------------------
    @api.depends('price_unit', 'product_uom_qty',
                 'biocreto_volumen_operativo', 'biocreto_produccion_real')
    def _compute_biocreto_costo_compensado(self):
        for line in self:
            divisor = line.biocreto_produccion_real or line.biocreto_volumen_operativo
            line.biocreto_costo_compensado = (
                (line.price_unit * line.product_uom_qty) / divisor
            ) if divisor else 0.0
