from odoo import fields, models


class BiocretoTipoCemento(models.Model):
    _name = 'biocreto.tipo.cemento'
    _description = 'Tipo de Cemento (BIOCRETO)'
    _order = 'sequence, name'

    name = fields.Char(
        string="Tipo de cemento",
        required=True,
        translate=False,
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
