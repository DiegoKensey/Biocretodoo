from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # -----------------------------------------------------------------
    # Suscripcion al motor PlutoPrint (biocreto_pdf_engine).
    # v19.0.2.0.0: pivote a Opcion A pura. Nuestra plantilla
    # `report_cotizacion_document` heredera con position="replace"
    # del nativo `sale.report_saleorder_document` SUSTITUYE el
    # contenido pero conserva el report_name del nativo:
    #   sale.action_report_saleorder.report_name == 'sale.report_saleorder'
    # (verificado en
    # odoo/addons/sale/report/ir_actions_report_templates.xml:362).
    #
    # Por eso aqui registramos 'sale.report_saleorder' (no un nombre
    # propio): el motor matchea por report_name y dispara PlutoPrint
    # en los tres canales que apuntan a la misma accion nativa:
    #   - Boton Imprimir   addons/sale/views/sale_order_views.xml:317
    #   - Mail templates   addons/sale/data/mail_template_data.xml
    #                       :51, :340, :394 (report_template_ids ref'd)
    #   - Portal cliente   addons/sale/controllers/portal.py:144, :330
    # -----------------------------------------------------------------
    def _biocreto_usa_plutoprint(self):
        res = super()._biocreto_usa_plutoprint()
        res.add('sale.report_saleorder')
        return res
