from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        ondelete='cascade',
        index='btree_not_null',
        copy=False,
    )
    biocreto_firma_encuesta = fields.Binary(
        string='Firma del cliente',
        attachment=True,
        copy=False,
    )
    biocreto_firma_encuesta_por = fields.Char(
        string='Firmado por',
        copy=False,
    )
    biocreto_firma_encuesta_fecha = fields.Datetime(
        string='Fecha de firma',
        copy=False,
    )

    # v19.0.3.0.0 — firma del cliente para encuestas de RECLAMO (set
    # separado del de satisfaccion).
    biocreto_firma_reclamo = fields.Binary(
        string='Firma reclamo del cliente',
        attachment=True,
        copy=False,
    )
    biocreto_firma_reclamo_por = fields.Char(
        string='Firmado por (reclamo)',
        copy=False,
    )
    biocreto_firma_reclamo_fecha = fields.Datetime(
        string='Fecha de firma (reclamo)',
        copy=False,
    )

    # v19.0.3.0.0 — helpers para enrutar la firma al set correcto segun
    # el tipo de encuesta.
    def _biocreto_campos_firma(self):
        """Devuelve los 3 nombres de campos de firma (imagen, por, fecha)
        segun biocreto_tipo_encuesta. Tuple de None si el survey no es
        BIOCRETO."""
        self.ensure_one()
        tipo = self.survey_id.biocreto_tipo_encuesta
        if tipo == 'satisfaccion':
            return ('biocreto_firma_encuesta',
                    'biocreto_firma_encuesta_por',
                    'biocreto_firma_encuesta_fecha')
        if tipo == 'reclamo':
            return ('biocreto_firma_reclamo',
                    'biocreto_firma_reclamo_por',
                    'biocreto_firma_reclamo_fecha')
        return (None, None, None)

    def _biocreto_tiene_firma(self):
        self.ensure_one()
        f_img, _f_por, _f_fecha = self._biocreto_campos_firma()
        return bool(f_img and self[f_img])

    # v19.0.2.0.0 — reseteo para el caso OV cancelada -> reconfirmada
    # (recon Hueco H: no existe metodo nativo de "reabrir"; replicamos
    # la receta validada en el recon).
    # v19.0.3.0.0: limpiar AMBOS sets de firma (sat + reclamo).
    def _biocreto_reset(self):
        self.ensure_one()
        self.user_input_line_ids.sudo().unlink()
        self.sudo().write({
            'state': 'new',
            'start_datetime': False,
            'end_datetime': False,
            'last_displayed_page_id': False,
            'survey_first_submitted': False,
            'biocreto_firma_encuesta': False,
            'biocreto_firma_encuesta_por': False,
            'biocreto_firma_encuesta_fecha': False,
            'biocreto_firma_reclamo': False,
            'biocreto_firma_reclamo_por': False,
            'biocreto_firma_reclamo_fecha': False,
        })
        # NO regenerar access_token (el link viejo sigue valido).

    # v19.0.3.0.0 — candado server-side: bloquea _mark_done si es un
    # survey BIOCRETO sin firma. Doble candado contra bypass del modal
    # JS (Approach B' del recon). El flujo normal pasa el candado porque
    # /biocreto_finalize escribe la firma ANTES de llamar _mark_done.
    def _mark_done(self):
        for user_input in self:
            if (user_input.survey_id.biocreto_tipo_encuesta
                    and not user_input._biocreto_tiene_firma()):
                raise UserError(_(
                    "No se puede completar la encuesta sin la firma del cliente."))
        return super()._mark_done()

    # v19.0.3.5.0 — accion del boton "Compartir encuesta" (form de
    # survey.user_input). Abre el wizard biocreto.survey.share con las
    # URLs especificas del participante (con su answer_token). Reemplaza
    # al "Reenviar invitacion" nativo, que (a) muestra el link generico
    # del survey, no el del participante, y (b) oculta el link cuando
    # access_mode != 'public' (las BIOCRETO son 'token').
    def action_biocreto_compartir(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Compartir encuesta'),
            'res_model': 'biocreto.survey.share',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_input_id': self.id},
        }

    # v19.0.2.0.0 — wrapper del boton "Nuevo reclamo" en el header de la
    # list propia (biocreto_survey_user_input_view_list). El boton vive
    # sobre survey.user_input, asi que necesitamos el metodo aqui; lee la
    # OV del context (biocreto_sale_order_id) y delega.
    #
    # v19.0.3.3.0 — FIX: quitar @api.model. Un boton type="object" en el
    # <header> de una list view en v19 es multi-registro: el framework
    # envia args=[resIds] al RPC /web/dataset/call_button. El server
    # (odoo/service/model.py:82-97) hace:
    #   if method._api_model: recs = model (no consume args[0])
    #   else: ids, args = args[0], args[1:]; recs = browse(ids)
    # Con @api.model, el [] de resIds queda en args y se pasa como
    # argumento posicional extra -> TypeError "takes 1 positional argument
    # but 2 were given". Sin @api.model, ese [] se consume como ids del
    # recordset (self queda vacio, no nos importa: leemos del context).
    def action_biocreto_nuevo_reclamo(self):
        order_id = self.env.context.get('biocreto_sale_order_id')
        if not order_id:
            raise UserError(_(
                "Este boton solo se puede usar abriendo la lista desde "
                "el stat button 'Encuestas' de una orden de venta."))
        order = self.env['sale.order'].browse(order_id)
        return order.action_biocreto_nuevo_reclamo()
