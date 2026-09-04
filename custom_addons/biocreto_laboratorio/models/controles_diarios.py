from odoo import fields, models


class BiocretoLabHumedad(models.Model):
    _name = 'biocreto.lab.humedad'
    _description = 'Control de humedad de agregados (BIOCRETO)'
    _order = 'fecha desc, id desc'

    tipo_agregado = fields.Selection([
        ('arena_rio', 'Arena de Río'),
        ('arena_cerro', 'Arena de Cerro'),
        ('piedra_12', 'Piedra 1/2"'),
        ('piedra_34', 'Piedra 3/4"'),
    ], string="Tipo de agregado", required=True)
    humedad = fields.Float(string="Humedad (%)", digits=(6, 2))
    fecha = fields.Datetime(default=fields.Datetime.now, required=True, string="Fecha")
    observaciones = fields.Text()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )


class BiocretoLabPozaTemp(models.Model):
    _name = 'biocreto.lab.poza.temp'
    _description = 'Temperatura de poza (BIOCRETO)'
    _order = 'fecha desc, id desc'

    temperatura = fields.Float(string="Temperatura (°C)", digits=(5, 2))
    fecha = fields.Datetime(default=fields.Datetime.now, required=True, string="Fecha")
    observaciones = fields.Text()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )


class BiocretoLabPh(models.Model):
    _name = 'biocreto.lab.ph'
    _description = 'Control de pH (BIOCRETO)'
    _order = 'fecha desc, id desc'

    ph = fields.Float(string="pH", digits=(4, 2))
    fecha = fields.Datetime(default=fields.Datetime.now, required=True, string="Fecha")
    observaciones = fields.Text()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )
