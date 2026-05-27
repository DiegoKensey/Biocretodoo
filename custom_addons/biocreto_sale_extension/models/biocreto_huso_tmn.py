from odoo import fields, models


class BiocretoHusoTmn(models.Model):
    _name = 'biocreto.huso.tmn'
    _description = 'Huso TMN (BIOCRETO)'
    _order = 'sequence, name'

    name = fields.Char(
        string="Huso TMN",
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
