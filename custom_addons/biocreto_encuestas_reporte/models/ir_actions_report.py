"""
Suscripcion al motor PlutoPrint (biocreto_pdf_engine) para los reportes
de encuestas. Mismo patron que biocreto_sale_reports_contrato:
  _biocreto_usa_plutoprint() -> set() de report_names que el motor
  enruta a PlutoPrint en vez de wkhtmltopdf.

Si este reporte NO esta en el set, el motor cae al super() inmediato
(_render_qweb_pdf_prepare_streams nativo). Aislamiento total.
"""
from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # report_name (modulo.id_template_raiz) -> el motor matchea por aqui.
    _BIOCRETO_ENC_SAT = 'biocreto_encuestas_reporte.report_encuesta_satisfaccion_document'

    def _biocreto_usa_plutoprint(self):
        res = super()._biocreto_usa_plutoprint()
        res.add(self._BIOCRETO_ENC_SAT)
        return res
