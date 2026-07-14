from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # Suscripcion al motor PlutoPrint (biocreto_pdf_engine).
    # Match por report_name (verificado en shell contra Prueba):
    #   purchase.action_report_purchase_order  -> 'purchase.report_purchaseorder'
    #   purchase.report_purchase_quotation     -> 'purchase.report_purchasequotation'
    # Nota: el report_name del segundo reporte se escribe SIN underscore
    # entre "purchase" y "quotation" (concatenado). El XML ID de la accion
    # SI lleva underscore. Los dos report_name deben ir al set.
    def _biocreto_usa_plutoprint(self):
        res = super()._biocreto_usa_plutoprint()
        res.add('purchase.report_purchaseorder')
        res.add('purchase.report_purchasequotation')
        return res
