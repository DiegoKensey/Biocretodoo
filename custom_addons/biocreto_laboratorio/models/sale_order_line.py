from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ------------------------------------------------------------------
    # Especificaciones de laboratorio (aparecen en el popup, solo Concreto)
    # ------------------------------------------------------------------
    biocreto_probetas_a_generar = fields.Integer(
        string="Probetas a generar",
        default=3,
        help="Numero de probetas que se crearan automaticamente al confirmar la OV.",
    )
    biocreto_probeta_ids = fields.One2many(
        comodel_name='biocreto.probeta',
        inverse_name='sale_line_id',
        string="Probetas",
    )
    biocreto_probetas_generadas = fields.Integer(
        string="Probetas generadas",
        compute='_compute_biocreto_probetas_generadas',
        store=False,
    )

    @api.depends('biocreto_probeta_ids')
    def _compute_biocreto_probetas_generadas(self):
        for line in self:
            line.biocreto_probetas_generadas = len(line.biocreto_probeta_ids)

    # ------------------------------------------------------------------
    # Related para la Cola de Diseños (calendario por fecha de vaceo).
    # sale.order.line no expone la fecha de vaceo — la agregamos aqui.
    # ------------------------------------------------------------------
    biocreto_fc_resistencia_line = fields.Integer(
        related='product_id.product_tmpl_id.biocreto_fc_resistencia',
        store=True,
        string="Resistencia f'c",
    )
    biocreto_fecha_vaceo_inicio = fields.Datetime(
        related='order_id.biocreto_fecha_vaceo_inicio',
        store=True,
        string="Fecha de vaceo",
    )
    biocreto_fecha_vaceo_fin = fields.Datetime(
        related='order_id.biocreto_fecha_vaceo_fin',
        store=True,
        string="Fin de vaceo",
    )

    # ------------------------------------------------------------------
    # Estado de diseño per-LINEA para la Cola de laboratorio: badge rojo/verde.
    # Coexiste con sale.order.biocreto_estado_diseno (per-orden, agregado con
    # all(bom_id)) declarado en biocreto_sale_extension/models/sale_order.py.
    # Aca es per-linea porque la cola muestra sale.order.line: cada linea
    # tiene su propio bom_id y merece su propio color. Labels canonicas del
    # proyecto (identicas a las del per-orden) para consistencia visual.
    # ------------------------------------------------------------------
    biocreto_estado_diseno = fields.Selection(
        selection=[
            ('pendiente', 'Pendiente de diseño'),
            ('asignado', 'Diseño asignado'),
        ],
        string="Estado de diseño",
        compute='_compute_biocreto_estado_diseno',
        store=False,
    )

    @api.depends('bom_id')
    def _compute_biocreto_estado_diseno(self):
        for line in self:
            line.biocreto_estado_diseno = 'asignado' if line.bom_id else 'pendiente'
