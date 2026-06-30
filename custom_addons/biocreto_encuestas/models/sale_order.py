from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    biocreto_encuesta_ids = fields.One2many(
        'survey.user_input',
        'sale_order_id',
        string='Encuestas',
    )
    biocreto_encuesta_count = fields.Integer(
        string='Numero de encuestas',
        compute='_compute_biocreto_encuesta_count',
    )

    @api.depends('biocreto_encuesta_ids')
    def _compute_biocreto_encuesta_count(self):
        for order in self:
            order.biocreto_encuesta_count = len(order.biocreto_encuesta_ids)

    # ------------------------------------------------------------------
    # Creacion automatica de la encuesta de SATISFACCION al confirmar
    # ------------------------------------------------------------------
    # IMPORTANTE: la cadena de overrides de action_confirm en BIOCRETO
    # tiene una rama que NO llama super() (biocreto_sale_contract_state:
    # cuando state esta en draft/sent, hace write('contract') y return
    # True sin invocar super). Por eso este modulo depende explicitamente
    # de biocreto_sale_contract_state (manifest), garantizando que el
    # override de aqui quede ENCIMA en la MRO y siempre se ejecute, sin
    # importar a que estado intermedio se llegue.
    #
    # Se crea/resetea la encuesta DESPUES del super(): si la OV no cambia
    # de estado (no hubo confirm efectivo) no queremos crear encuesta;
    # filtramos por order.state in ('contract','sale','done').
    def action_confirm(self):
        res = super().action_confirm()
        for order in self.filtered(lambda o: o.state in ('contract', 'sale', 'done')):
            order._biocreto_crear_o_reusar_satisfaccion()
        return res

    def _biocreto_get_survey(self, tipo):
        """Busca el survey corporativo por su tipo BIOCRETO. NO usa XML
        ID porque las encuestas son `noupdate="1"` y el cliente puede
        editar/borrar; el lookup por tipo es mas robusto."""
        self.ensure_one()
        survey = self.env['survey.survey'].sudo().search(
            [('biocreto_tipo_encuesta', '=', tipo)], limit=1)
        if not survey:
            raise ValidationError(_(
                "No existe la encuesta base de tipo '%s'. Verifique que el "
                "modulo biocreto_encuestas este instalado correctamente.",
            ) % tipo)
        return survey

    def _biocreto_crear_o_reusar_satisfaccion(self):
        """1 satisfaccion por OV:
          - Si NO existe -> crear via survey._create_answer (sale_order_id
            viaja por additional_vals, recon survey_survey.py:535/584).
          - Si YA existe -> reusar y resetear (caso cancelar->reconfirmar)
            con _biocreto_reset.
        El partner es commercial_partner_id para que cuadre con la
        validacion _check_validity y con el patron del portal (un usuario
        por empresa)."""
        self.ensure_one()
        survey = self._biocreto_get_survey('satisfaccion')
        existente = self.biocreto_encuesta_ids.filtered(
            lambda u: u.survey_id == survey)
        if existente:
            existente[0]._biocreto_reset()
            return existente[0]
        partner = self.partner_id.commercial_partner_id
        return survey._create_answer(
            partner=partner,
            email=partner.email,
            sale_order_id=self.id,
            check_attempts=False,
        )

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    # v19.0.3.4.0 — eliminado action_biocreto_open_encuestas (Python).
    # La apertura de la lista filtrada por OV ahora la hace una
    # ir.actions.act_window XML estatica (biocreto_action_encuestas_from_so)
    # con domain="[('sale_order_id','=',active_id)]". Motivo: las
    # mutaciones runtime de action['domain'] NO se persisten en el state
    # del web client (action_service.js:_controllersFromState solo persiste
    # actionId+active_id+model+resId), asi que un F5 perdia el filtro.
    # El active_id SI se persiste, por lo que el patron XML sobrevive F5.
    # Patron tomado del nativo: sale_expense.hr_expense_action_from_sale_order.

    def action_biocreto_nuevo_reclamo(self):
        """Crea un user_input de tipo RECLAMO ligado a esta OV. N reclamos
        permitidos (recon Hueco C: no hay constraint de unicidad
        survey_id+partner_id+sale_order_id).

        v19.0.3.4.0 — devuelve soft_reload en lugar de reabrir la accion.
        Razon: si devolviera self.action_biocreto_open_encuestas() (o
        equivalente con la accion XML), empujaria un controller nuevo en
        el actionStack -> breadcrumb duplicado ("Cotizacion > Encuestas >
        Encuestas"). El soft_reload recarga el controller actual (la
        lista ya esta filtrada por active_id), mostrando el reclamo
        recien creado sin duplicar breadcrumb. El active_id del
        controller permanece, asi que el filtro sigue activo.
        """
        self.ensure_one()
        survey = self._biocreto_get_survey('reclamo')
        partner = self.partner_id.commercial_partner_id
        survey._create_answer(
            partner=partner,
            email=partner.email,
            sale_order_id=self.id,
            check_attempts=False,
        )
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
