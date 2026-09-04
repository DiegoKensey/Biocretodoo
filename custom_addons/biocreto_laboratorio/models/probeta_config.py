from odoo import fields, models


class BiocretoProbetaEdad(models.Model):
    _name = 'biocreto.probeta.edad'
    _description = 'Edad de probeta (BIOCRETO)'
    _order = 'sequence, valor, id'

    name = fields.Char(string="Etiqueta", required=True, translate=False)
    valor = fields.Integer(
        string="Días",
        required=True,
        help="Numero de dias para calcular la fecha de rotura programada.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class BiocretoProbetaTamano(models.Model):
    _name = 'biocreto.probeta.tamano'
    _description = 'Tamaño de probeta (BIOCRETO)'
    _order = 'sequence, name'

    name = fields.Char(string="Tamaño", required=True, translate=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
