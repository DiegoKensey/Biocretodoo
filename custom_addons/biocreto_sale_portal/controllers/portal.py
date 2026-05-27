from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.sale.controllers.portal import CustomerPortal


class BiocretoCustomerPortal(CustomerPortal):

    def _prepare_contracts_domain(self, partner):
        return [
            ('partner_id', 'child_of', [partner.commercial_partner_id.id]),
            ('state', '=', 'contract'),
        ]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'contract_count' in counters:
            partner = request.env.user.partner_id
            SaleOrder = request.env['sale.order']
            values['contract_count'] = (
                SaleOrder.search_count(self._prepare_contracts_domain(partner))
                if SaleOrder.has_access('read') else 0
            )
        return values

    @http.route(
        ['/my/orders/<int:order_id>/accept'],
        type='jsonrpc', auth='public', website=True,
    )
    def portal_quote_accept(self, order_id, access_token=None, name=None, signature=None):
        """Inyecta flag de contexto para que action_confirm sepa que viene del portal."""
        request.update_context(biocreto_from_portal=True)
        return super().portal_quote_accept(
            order_id, access_token=access_token, name=name, signature=signature,
        )

    @http.route(
        ['/my/contracts', '/my/contracts/page/<int:page>'],
        type='http', auth='user', website=True,
    )
    def portal_my_contracts(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """Lista de cotizaciones firmadas en estado 'contract' del cliente actual."""
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order']
        values = self._prepare_portal_layout_values()

        domain = self._prepare_contracts_domain(partner)
        searchbar_sortings = self._get_sale_searchbar_sortings()
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        url_args = {'date_begin': date_begin, 'date_end': date_end}
        if len(searchbar_sortings) > 1:
            url_args['sortby'] = sortby

        pager_values = portal_pager(
            url='/my/contracts',
            total=SaleOrder.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args=url_args,
        )
        contracts = SaleOrder.search(
            domain,
            order=sort_order,
            limit=self._items_per_page,
            offset=pager_values['offset'],
        )
        request.session['my_contracts_history'] = contracts.ids[:100]

        values.update({
            'date': date_begin,
            'contracts': contracts.sudo(),
            'page_name': 'contract',
            'pager': pager_values,
            'default_url': '/my/contracts',
        })
        if len(searchbar_sortings) > 1:
            values.update({
                'sortby': sortby,
                'searchbar_sortings': searchbar_sortings,
            })

        return request.render('biocreto_sale_portal.portal_my_contracts', values)
