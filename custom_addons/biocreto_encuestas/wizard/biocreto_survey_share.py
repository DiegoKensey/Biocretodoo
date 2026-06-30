from odoo import api, fields, models
from odoo.tools.urls import urljoin


class BiocretoSurveyShare(models.TransientModel):
    """v19.0.3.5.0 — Wizard de compartir encuesta BIOCRETO.

    Reemplaza al wizard nativo survey.invite para encuestas BIOCRETO. El
    nativo oculta el campo del link cuando access_mode != 'public' (las
    BIOCRETO son 'token'); ademas, su URL es la GENERICA del survey,
    no la del participante (recon hallazgo). Este wizard expone las
    URLs especificas del user_input con su answer_token, usando el
    widget nativo CopyClipboardURL.
    """
    _name = 'biocreto.survey.share'
    _description = 'BIOCRETO - Compartir encuesta con token del participante'

    user_input_id = fields.Many2one(
        'survey.user_input', required=True, readonly=True)
    survey_title = fields.Char(
        related='user_input_id.survey_id.title', readonly=True)
    partner_name = fields.Char(
        related='user_input_id.partner_id.name', readonly=True)
    state = fields.Selection(
        related='user_input_id.state', readonly=True)
    share_url = fields.Char(
        'Enlace para responder',
        readonly=True, compute='_compute_share_url')
    review_url = fields.Char(
        'Enlace para ver respuestas',
        readonly=True, compute='_compute_share_url')

    # user_input.get_start_url() -> /survey/start/<st>?answer_token=<at>
    #   (responder; redirige al thank-you si state='done').
    # user_input.get_print_url() -> /survey/print/<st>?answer_token=<at>
    #   (ver respuestas en modo lectura; agregamos &review=True para
    #   forzar el formato de review nativo).
    # urljoin de odoo.tools.urls compone el dominio del servidor con el
    # path para tener URLs absolutas (copy-pasteables).
    @api.depends('user_input_id')
    def _compute_share_url(self):
        for wiz in self:
            ui = wiz.user_input_id
            if not ui:
                wiz.share_url = False
                wiz.review_url = False
                continue
            base = ui.get_base_url()
            wiz.share_url = urljoin(base, ui.get_start_url())
            wiz.review_url = urljoin(base, ui.get_print_url() + '&review=True')
