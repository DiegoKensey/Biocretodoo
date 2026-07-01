"""
Suscripcion al motor PlutoPrint (biocreto_pdf_engine) para el reporte
UNICO de encuestas (v19.0.2.0.0). Antes eran 2 report_names (sat +
reclamo); ahora es UNO solo, y el despachador (`report_encuesta_document`)
ramifica por tipo en el propio template.

Aislamiento total: si `report_name` no esta en el set, el motor cae al
super() (_render_qweb_pdf_prepare_streams nativo).
"""
from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # report_name (modulo.id_template_raiz) del despachador ramificado.
    _BIOCRETO_ENC = 'biocreto_encuestas_reporte.report_encuesta_document'

    def _biocreto_usa_plutoprint(self):
        res = super()._biocreto_usa_plutoprint()
        res.add(self._BIOCRETO_ENC)
        return res
