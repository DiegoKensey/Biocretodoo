from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    biocreto_fc_resistencia = fields.Integer(
        string="Resistencia f'c (kg/cm²)",
        help="Resistencia característica del concreto. Dato maestro leído por "
             "Ventas, Laboratorio y Fabricación. Ej.: 210, 175.",
    )
