from odoo import _, models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # ---------------------------------------------------------------------
    # Suscripcion al motor PlutoPrint (biocreto_pdf_engine).
    # Patron identico al de biocreto_sale_report_cotizacion: el motor
    # matchea por report_name y dispara PlutoPrint cuando se invoca este
    # reporte. Nuestro template raiz `report_contrato_document` define el
    # report_name `biocreto_sale_reports_contrato.report_contrato_document`
    # (ver report/report_contrato_actions.xml).
    # ---------------------------------------------------------------------
    _BIOCRETO_CONTRATO_REPORT = 'biocreto_sale_reports_contrato.report_contrato_document'

    def _biocreto_usa_plutoprint(self):
        res = super()._biocreto_usa_plutoprint()
        res.add(self._BIOCRETO_CONTRATO_REPORT)
        return res

    # ---------------------------------------------------------------------
    # Enforcement de estado para el reporte de Contrato.
    # ---------------------------------------------------------------------
    # Diseno: el Contrato es la misma sale.order en estado 'contract' o
    # posterior. Imprimir antes (draft/sent/cancel) carece de sentido de
    # negocio. Optamos por enforcement en backend (opcion b del spec)
    # antes que esconder el boton via JS/view: el render levanta un
    # UserError claro y reusable desde cualquier canal (boton, mail
    # template, portal). Solo afecta nuestro report_name.
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == self._BIOCRETO_CONTRATO_REPORT and res_ids:
            orders = self.env['sale.order'].browse(res_ids)
            bad = orders.filtered(lambda o: o.state in ('draft', 'sent', 'cancel'))
            if bad:
                raise UserError(_(
                    "No se puede imprimir el Contrato: la orden %s aun no esta en estado Contrato.",
                    ", ".join(bad.mapped('name')),
                ))
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
