from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ─────────────────────────────────────────────────────────────────
    # Selección extendida: agrega 'programado' entre 'contract' y 'sale'.
    # 'contract' ya fue agregado por este mismo módulo en v1.0.x; el
    # selection_add lo conserva (no rompe datos previos).
    #
    # El ORDEN visual del statusbar lo controla statusbar_visible en la
    # vista (paso obligado: selection_add por sí solo no garantiza el
    # orden visual deseado en la statusbar).
    # ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection_add=[
            ('contract', 'Contrato'),
            ('programado', 'Programado'),
            ('sale',),
        ],
        ondelete={
            'contract': 'set default',
            'programado': 'set default',
        },
    )

    def _biocreto_format_now(self):
        """Devuelve la fecha/hora actual en zona del usuario, formato DD/MM/YYYY HH:MM."""
        self.ensure_one()
        return fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        ).strftime('%d/%m/%Y %H:%M')

    # ─────────────────────────────────────────────────────────────────
    # Helper: ¿faltan diseños de mezcla en líneas Concreto?
    # Reutiliza el criterio del proyecto (biocreto_product_categ).
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_falta_diseno(self):
        self.ensure_one()
        concreto_sin_bom = self.order_line.filtered(
            lambda l: not l.display_type
            and l.biocreto_product_categ == 'Concreto'
            and not l.bom_id
        )
        return bool(concreto_sin_bom)

    # ─────────────────────────────────────────────────────────────────
    # _confirmation_error_message: ahora la entrada legítima a action_confirm
    # del nativo es desde 'programado' (no desde 'contract'). El super sólo
    # acepta draft/sent → adaptamos para 'programado' como en v1.0.x se hacía
    # para 'contract'. Conservamos la rama 'contract' por compatibilidad
    # (órdenes históricas o cualquier flujo legacy que aún la dispare).
    # ─────────────────────────────────────────────────────────────────
    def _confirmation_error_message(self):
        self.ensure_one()
        if self.state in ('contract', 'programado'):
            if any(
                not line.display_type
                and not line.is_downpayment
                and not line.product_id
                for line in self.order_line
            ):
                return _(
                    "Algunas líneas no tienen producto. Debes corregirlas "
                    "antes de confirmar."
                )
            return False
        return super()._confirmation_error_message()

    # ─────────────────────────────────────────────────────────────────
    # TRANSICIÓN  Contrato → Programado
    # Botón "Pasar a Programación". Método público (también puede ser
    # invocado desde el portal en una iteración futura).
    # ─────────────────────────────────────────────────────────────────
    def action_biocreto_pasar_programado(self):
        for order in self:
            if order.state != 'contract':
                continue
            # Re-validamos por seguridad (mismo helper de la extension).
            order._biocreto_validate_before_confirm()
            order.write({'state': 'programado'})
            order.message_post(body=_(
                "Orden movida a Programado por %(user)s el %(date)s.",
                user=self.env.user.name,
                date=order._biocreto_format_now(),
            ))
        return True

    # ─────────────────────────────────────────────────────────────────
    # TRANSICIÓN  Programado → Orden de Venta  (botón Confirmar)
    # Evalúa el candado de diseño según parámetro de la Compañía.
    # Llama action_confirm para que el flujo nativo (genera OF) corra.
    # ─────────────────────────────────────────────────────────────────
    def action_biocreto_confirmar_ov(self):
        for order in self:
            if order.state != 'programado':
                continue
            candado = order.company_id.biocreto_candado_diseno
            if candado and order._biocreto_falta_diseno():
                raise ValidationError(_(
                    "No se puede pasar a Orden de Venta: faltan Diseños de mezcla "
                    "en líneas de Concreto. Asigne el diseño o desactive el candado "
                    "en la configuración de la compañía."
                ))
            order.action_confirm()
        return True

    # ─────────────────────────────────────────────────────────────────
    # action_confirm: orquesta las transiciones que llegan a 'sale'.
    #
    # Cadena final del módulo:
    #   draft/sent  → contract     (en este action_confirm, sin super)
    #   contract    → programado   (vía action_biocreto_pasar_programado)
    #   programado  → sale         (en este action_confirm, vía super)
    #
    # ¿Por qué la rama draft/sent → contract NO llama super?
    # Porque el super del nativo (sale.action_confirm) escribiría state='sale'
    # directamente y se saltarían los dos estados intermedios. La rama 'contract'
    # solo hace el write — y delega las validaciones BIOCRETO en el helper.
    #
    # ¿Por qué desde 'programado' SÍ llamamos super?
    # Porque ahí queremos disparar todo el flujo nativo (genera OF, secuencia OV,
    # commitment_date, etc.). El super de la extension correrá su propio
    # action_confirm que vuelve a invocar el helper de validación.
    # ─────────────────────────────────────────────────────────────────
    def action_confirm(self):
        orders_to_contract = self.filtered(lambda o: o.state in ('draft', 'sent'))
        orders_to_sale = self.filtered(lambda o: o.state == 'programado')
        # Mantén una rama de compatibilidad: si alguien (legacy o RPC) invoca
        # action_confirm sobre una orden en 'contract', la llevamos a sale
        # respetando el mismo flujo nativo. NO la pasamos por 'programado'
        # forzosamente — el botón "Pasar a Programación" cumple ese rol en UI.
        orders_legacy_contract = self.filtered(lambda o: o.state == 'contract')

        if orders_to_contract:
            orders_to_contract._biocreto_validate_before_confirm()
            orders_to_contract.write({'state': 'contract'})
            user_name = self.env.user.name
            for order in orders_to_contract:
                order.message_post(body=_(
                    "Cotización movida a estado Contrato por %(user)s el %(date)s.",
                    user=user_name,
                    date=order._biocreto_format_now(),
                ))

        to_super = orders_to_sale | orders_legacy_contract
        if to_super:
            result = super(SaleOrder, to_super).action_confirm()
            user_name = self.env.user.name
            for order in to_super:
                order.message_post(body=_(
                    "Orden confirmada a Orden de Venta por %(user)s el %(date)s.",
                    user=user_name,
                    date=order._biocreto_format_now(),
                ))
            return result

        return True

    def _action_cancel(self):
        """Loguea cancelación cuando la orden estaba en Contrato o Programado."""
        affected = self.filtered(lambda o: o.state in ('contract', 'programado'))
        result = super()._action_cancel()
        if affected:
            user_name = self.env.user.name
            for order in affected:
                order.message_post(body=_(
                    "Orden cancelada por %(user)s el %(date)s.",
                    user=user_name,
                    date=order._biocreto_format_now(),
                ))
        return result

    # ─────────────────────────────────────────────────────────────────
    # CRON: auto-confirmar Programado → OV cuando el vaceo está dentro
    # del buffer parametrizado por compañía.
    #
    # Reglas:
    #   - Solo procesa órdenes en 'programado' con fecha_vaceo_inicio.
    #   - Buffer leído de la Compañía dueña de la orden (multi-compañía).
    #   - SIEMPRE respeta el candado de diseño (incluso si la Compañía
    #     tiene biocreto_candado_diseno=False). El cron es no-supervisado;
    #     el override manual del candado solo aplica al botón.
    #   - Errores quedan registrados en chatter; no abortan la corrida.
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _biocreto_cron_autoconfirmar(self):
        now = fields.Datetime.now()
        ordenes = self.search([('state', '=', 'programado')])
        for order in ordenes:
            if not order.biocreto_fecha_vaceo_inicio:
                continue
            buffer_h = order.company_id.biocreto_buffer_confirmacion_horas or 0
            umbral = order.biocreto_fecha_vaceo_inicio - relativedelta(hours=buffer_h)
            if now < umbral:
                continue
            if order._biocreto_falta_diseno():
                order.message_post(body=_(
                    "No confirmada automáticamente: falta Diseño de mezcla en "
                    "líneas de Concreto."
                ))
                continue
            try:
                order.action_confirm()
            except Exception as e:
                order.message_post(body=_(
                    "No confirmada automáticamente: %(err)s",
                    err=str(e),
                ))
        return True
