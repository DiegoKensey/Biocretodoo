from odoo import api, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    @api.depends_context('biocreto_bank_display')
    def _compute_display_name(self):
        if not self.env.context.get('biocreto_bank_display'):
            return super()._compute_display_name()
        for bank in self:
            banco = bank.bank_id.name or bank.bank_name or ''
            cuenta = bank.acc_number or ''
            bank.display_name = ('%s - %s' % (banco, cuenta)).strip(' -')
