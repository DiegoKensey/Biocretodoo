from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    # ─────────────────────────────────────────────────────────────────
    # v19.0.1.3.0: sale.report tiene su PROPIA selección de estado
    # (odoo/addons/sale/report/sale_report.py:27), independiente de la de
    # sale.order. Sin esta extensión los informes mostraban 'sent' como
    # "Cotización enviada" y 'contract'/'programado' como el valor crudo,
    # porque no figuraban en la selección del informe.
    #
    # Mismo orden que sale.order. Sin `ondelete`: sale.report es una
    # vista SQL (_auto=False) y el ORM ignora el ondelete en esos modelos
    # (odoo/addons/base/models/ir_model.py:1767). Precedente nativo:
    # pos_sale/report/sale_report.py:16-22.
    # ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection_add=[
            ('sent', 'Preprogramado'),
            ('contract', 'Contrato'),
            ('programado', 'Programado'),
            ('sale',),
        ],
    )
