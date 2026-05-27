from odoo import fields, models


class BiocretoEstructura(models.Model):
    _name = 'biocreto.estructura'
    _description = 'Tipo de Estructura (BIOCRETO)'
    _order = 'sequence, name'

    name = fields.Char(
        string="Tipo de estructura",
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
