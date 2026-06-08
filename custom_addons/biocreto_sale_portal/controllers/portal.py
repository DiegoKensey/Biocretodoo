import binascii

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError
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
        """Reescritura del portal_quote_accept de sale para:
        - Inyectar 'biocreto_from_portal=True' (lo necesita action_confirm BIOCRETO).
        - Cambiar el body del message_post: 'Order signed by ...' → BIOCRETO.

        Estrategia B (reescritura): el helper que devuelve el texto no existe
        en el nativo (verificado: no hay '_get_portal_order_signature_message'
        ni '_portal_quote_signed' en addons/sale). El body se construye
        inline en sale/controllers/portal.py:339. Replicamos el resto del
        método tal cual.

        Si en una futura versión de Odoo este método cambia, esta
        reescritura debe re-sincronizarse contra el nuevo nativo.
        """
        request.update_context(biocreto_from_portal=True)
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token,
            )
        except (AccessError, MissingError):
            return {'error': _('Invalid order.')}

        if not order_sudo._has_to_be_signed():
            return {'error': _('The order is not in a state requiring customer signature.')}
        if not signature:
            return {'error': _('Signature is missing.')}

        try:
            order_sudo.write({
                'signed_by': name,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
            })
            # flush para que el PDF disponga de la firma
            request.env.cr.flush()
        except (TypeError, binascii.Error):
            return {'error': _('Invalid signature data.')}

        if not order_sudo._has_to_be_paid():
            order_sudo._validate_order()

        pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'sale.action_report_saleorder', [order_sudo.id],
        )[0]

        order_sudo.message_post(
            attachments=[('%s.pdf' % order_sudo.name, pdf)],
            author_id=(
                order_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body=_(
                "Cotización %(numero)s firmada por %(nombre)s",
                numero=order_sudo.name,
                nombre=name,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        query_string = '&message=sign_ok'
        if order_sudo._has_to_be_paid():
            query_string += '&allow_payment=yes'
        return {
            'force_refresh': True,
            'redirect_url': order_sudo.get_portal_url(query_string=query_string),
        }

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
