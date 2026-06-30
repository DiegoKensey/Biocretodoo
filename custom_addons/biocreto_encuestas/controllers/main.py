from odoo import _, fields, http
from odoo.http import request
from odoo.addons.survey.controllers.main import Survey


class BiocretoSurvey(Survey):
    """Endpoint de captura de firma para encuestas BIOCRETO.

    v19.0.3.1.0 — FIX: orden invertido (firma -> submit nativo).

    El bug anterior cortaba el `super.submitForm` al pulsar "Enviar" para
    abrir el modal de firma, y luego `/biocreto_finalize` escribia la
    firma + `_mark_done`. Como las encuestas BIOCRETO usan
    `page_per_section` con 1 sola seccion, el unico POST a /survey/submit
    es el final — cortarlo dejaba 0 lines (respuestas) en BD.

    Ahora el JS:
      1) abre el modal de firma (sin cortar inputs del DOM);
      2) al confirmar, llama a este endpoint que SOLO escribe firma
         (sin _mark_done);
      3) luego re-llama `_super(submitForm)(options)` -> el flujo nativo
         hace el POST a /survey/submit -> _save_lines persiste respuestas
         -> _mark_done marca `done`. El candado de _mark_done pasa porque
         la firma ya esta escrita.
    """

    @http.route('/survey/<string:survey_token>/<string:answer_token>/biocreto_save_signature',
                type='jsonrpc', auth='public', website=True)
    def biocreto_survey_save_signature(self, survey_token, answer_token,
                                       name=None, signature=None, **kw):
        access_data = self._get_access_data(
            survey_token, answer_token, ensure_token=True)
        if access_data['validity_code'] is not True:
            return {'error': access_data['validity_code']}

        answer_sudo = access_data['answer_sudo']
        survey_sudo = access_data['survey_sudo']

        if not survey_sudo.biocreto_tipo_encuesta:
            return {'error': 'not_a_biocreto_survey'}
        if answer_sudo.state == 'done':
            return {'error': 'already_done'}
        if not name or not signature:
            return {'error': _("Firma y nombre son obligatorios.")}

        f_img, f_por, f_fecha = answer_sudo._biocreto_campos_firma()
        if not f_img:
            return {'error': 'not_a_biocreto_survey'}

        answer_sudo.write({
            f_img: signature,
            f_por: name,
            f_fecha: fields.Datetime.now(),
        })
        # IMPORTANTE: NO se llama _mark_done() aqui.
        # El flujo nativo /survey/submit (que el JS reanuda con
        # _super(options) tras esta respuesta) hara:
        #   1) _save_lines() para persistir las respuestas
        #   2) _mark_done() — pasara el candado porque la firma ya esta.
        return {'success': True}
