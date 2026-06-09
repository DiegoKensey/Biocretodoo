from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    biocreto_cci = fields.Char(
        string="CCI",
        help="Codigo de Cuenta Interbancario (CCI).",
    )
