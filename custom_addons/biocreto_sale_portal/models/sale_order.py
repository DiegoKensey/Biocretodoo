from odoo import _, api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('state')
    def _compute_type_name(self):
        """Etiqueta dinámica por estado, incluyendo 'Contrato'."""
        super()._compute_type_name()
        for record in self:
            if record.state == 'contract':
                record.type_name = _("Contrato")

    def action_confirm(self):
        """Notifica al asesor cuando la confirmación viene del portal y deja la orden en Contrato.

        La transición de estado la maneja biocreto_sale_contract_state.
        Aquí solo agregamos la notificación al user_id si el flag de contexto está presente.
        """
        from_portal = self.env.context.get('biocreto_from_portal', False)
        result = super().action_confirm()

        if from_portal:
            for order in self.filtered(lambda o: o.state == 'contract' and o.user_id):
                order.message_post(
                    body=_(
                        "El cliente firmó. Debes preparar el contrato BC-GC-FR-05."
                    ),
                    partner_ids=[order.user_id.partner_id.id],
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )
        return result
