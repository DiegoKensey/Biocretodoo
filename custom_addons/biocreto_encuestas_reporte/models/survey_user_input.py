"""
Override del boton "Imprimir" del statusbar de survey.user_input.

Nativo (survey/models/survey_user_input.py:195-206): devuelve un
`ir.actions.act_url` que abre la pagina HTML /survey/print. Para
encuestas BIOCRETO, redirigimos al PDF PlutoPrint ramificado (mismo
`action_report_encuesta` que usa el menu "Imprimir" del form/list).

Coherencia: las 3 vias de impresion BIOCRETO cuelgan del mismo
`ir.actions.report` (menu, statusbar, boton portal).
"""
from odoo import models


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    def action_print_answers(self):
        self.ensure_one()
        if self.biocreto_tipo_encuesta:
            return self.env.ref(
                'biocreto_encuestas_reporte.action_report_encuesta'
            ).report_action(self)
        return super().action_print_answers()
