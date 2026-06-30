{
    'name': 'BIOCRETO Encuestas',
    'version': '19.0.3.8.0',
    'category': 'Marketing/Surveys',
    'summary': 'Encuestas BIOCRETO (Satisfaccion y Reclamos) atadas a ordenes de venta.',
    'description': 'Fases 0-3 + Lotes A/B/B.2: extension de survey.user_input con sale_order_id + 2 sets de firma; siembra de las 2 encuestas base BC-GC-FR-16 y BC-GC-FR-03; stat button "Encuestas" en la OV, creacion automatica de satisfaccion al confirmar, "Nuevo reclamo" desde la lista, tarjetas en el portal y pagina /my/surveys; modal de firma DarkBlue al completar (Approach B client-side trigger), ruta /biocreto_finalize, doble candado server-side; recoloreo BIOCRETO del frontend de respuesta + modal de confirmacion + pantalla print + cabecera tabla respuestas (no_scoring).',
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'biocreto_sale_extension',
        'biocreto_sale_contract_state',
        'survey',
        'portal',
        'sale_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/survey_satisfaccion.xml',
        'data/survey_reclamo.xml',
        'wizard/biocreto_survey_share_views.xml',
        'views/survey_survey_views.xml',
        'views/survey_user_input_views.xml',
        'views/sale_order_views.xml',
        'views/portal_templates.xml',
        'views/survey_templates.xml',
    ],
    'assets': {
        # CRITICO (recon hallazgo #1): el JS DEBE ir en
        # survey.survey_assets, no en web.assets_frontend. Si fuera en
        # web.assets_frontend, el patch(SurveyForm.prototype, ...) correria
        # antes de que SurveyForm este definido y fallaria.
        'survey.survey_assets': [
            'biocreto_encuestas/static/src/interactions/biocreto_survey_signature.js',
            # v19.0.3.7.0: SCSS de recoloreo del frontend de respuesta.
            # Va DESPUES del JS (y por extension despues de los SCSS nativos
            # cargados por el bundle, incluyendo survey_templates_form.scss
            # del manifest del addon survey) para ganar la cascada CSS.
            'biocreto_encuestas/static/src/scss/biocreto_survey_colors.scss',
        ],
        # v19.0.3.7.0: SCSS para el alert del home del portal. Va aqui
        # porque el portal vive en web.assets_frontend (NO en
        # survey.survey_assets); afecta solo a .o_portal_my_home.
        # v19.0.3.8.0: SCSS del modal de confirmacion de envio. Va aqui
        # (NO en survey.survey_assets) porque ConfirmationDialog se monta
        # en document.body fuera de `.o_survey_form`. Scopeado con
        # `:has(.o_biocreto_survey_confirm)` -> CERO contaminacion en
        # otros dialogs del frontend.
        'web.assets_frontend': [
            'biocreto_encuestas/static/src/scss/biocreto_portal_colors.scss',
            'biocreto_encuestas/static/src/scss/biocreto_survey_dialog.scss',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
