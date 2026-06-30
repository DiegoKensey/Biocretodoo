from odoo.addons.portal.controllers import portal
from odoo.http import request, route


class CustomerPortal(portal.CustomerPortal):

    # ------------------------------------------------------------------
    # Contadores del home (patron sign, recon Hueco G)
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id.commercial_partner_id
        UserInput = request.env['survey.user_input'].sudo()
        if 'biocreto_encuestas_pendientes_count' in counters:
            values['biocreto_encuestas_pendientes_count'] = UserInput.search_count([
                ('partner_id', '=', partner.id),
                ('state', '=', 'new'),
                ('sale_order_id', '!=', False),
            ])
        if 'biocreto_encuestas_count' in counters:
            values['biocreto_encuestas_count'] = UserInput.search_count([
                ('partner_id', '=', partner.id),
                ('sale_order_id', '!=', False),
            ])
        return values

    # ------------------------------------------------------------------
    # /my/surveys: lista de encuestas del cliente
    # ------------------------------------------------------------------
    @route(['/my/surveys'], type='http', auth='user', website=True)
    def biocreto_portal_my_surveys(self, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        user_inputs = request.env['survey.user_input'].sudo().search([
            ('partner_id', '=', partner.id),
            ('sale_order_id', '!=', False),
        ], order='create_date desc')
        values = self._prepare_portal_layout_values()
        values.update({
            'user_inputs': user_inputs,
            'page_name': 'biocreto_surveys',
        })
        return request.render(
            'biocreto_encuestas.portal_my_surveys', values)
