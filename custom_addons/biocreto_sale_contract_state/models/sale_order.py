from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection_add=[
            ('contract', 'Contrato'),
            ('sale',),
        ],
        ondelete={'contract': 'set default'},
    )

    def _biocreto_format_now(self):
        """Devuelve la fecha/hora actual en zona del usuario, formato DD/MM/YYYY HH:MM."""
        self.ensure_one()
        return fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        ).strftime('%d/%m/%Y %H:%M')

    def _confirmation_error_message(self):
        """Permitir 'contract' como estado válido para llamar a action_confirm.

        El super sólo acepta draft/sent. Para que action_confirm pueda mover
        de contract → sale, validamos las líneas igual que el super pero
        sin exigir draft/sent.
        """
        self.ensure_one()
        if self.state == 'contract':
            if any(
                not line.display_type
                and not line.is_downpayment
                and not line.product_id
                for line in self.order_line
            ):
                return _(
                    "Algunas líneas no tienen producto. Debes corregirlas "
                    "antes de confirmar el contrato."
                )
            return False
        return super()._confirmation_error_message()

    def action_confirm(self):
        """Inserta el estado intermedio 'contract' en el flujo de confirmación.

        - draft/sent → contract (no llama al super, sólo escribe el estado).
        - contract → sale (delega al super, que ya hace la lógica nativa).
        """
        orders_to_contract = self.filtered(lambda o: o.state in ('draft', 'sent'))
        orders_to_sale = self.filtered(lambda o: o.state == 'contract')

        if orders_to_contract:
            orders_to_contract.write({'state': 'contract'})
            user_name = self.env.user.name
            for order in orders_to_contract:
                order.message_post(body=_(
                    "Cotización movida a estado Contrato por %(user)s el %(date)s.",
                    user=user_name,
                    date=order._biocreto_format_now(),
                ))

        if orders_to_sale:
            result = super(SaleOrder, orders_to_sale).action_confirm()
            user_name = self.env.user.name
            for order in orders_to_sale:
                order.message_post(body=_(
                    "Contrato confirmado y convertido a Orden de Venta por "
                    "%(user)s el %(date)s.",
                    user=user_name,
                    date=order._biocreto_format_now(),
                ))
            return result

        return True

    def _action_cancel(self):
        """Loguea cancelación cuando la orden estaba en estado Contrato."""
        contract_orders = self.filtered(lambda o: o.state == 'contract')
        result = super()._action_cancel()
        if contract_orders:
            user_name = self.env.user.name
            for order in contract_orders:
                order.message_post(body=_(
                    "Contrato cancelado por %(user)s el %(date)s.",
                    user=user_name,
                    date=order._biocreto_format_now(),
                ))
        return result
