from odoo import fields, models


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    biocreto_tipo_encuesta = fields.Selection(
        selection=[
            ('satisfaccion', 'Satisfaccion'),
            ('reclamo', 'Reclamo'),
        ],
        string='Tipo de encuesta BIOCRETO',
        help='Distingue la encuesta de satisfaccion de la de reclamo en el flujo BIOCRETO.',
    )
