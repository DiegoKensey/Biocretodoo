{
    'name': 'BIOCRETO Encuestas - Reportes QWeb (PlutoPrint)',
    'version': '19.0.2.0.0',
    'category': 'Marketing/Surveys',
    'summary': 'Informe unico PDF SIG por participante ramificado por tipo (satisfacción BC-GC-FR-16 / reclamo BC-GC-FR-03).',
    'description': 'Un solo ir.actions.report "Encuesta" que ramifica por biocreto_tipo_encuesta y genera el PDF de satisfacción o reclamo (mismo layout, distinto body + SIG). Certificaciones ocultas en BIOCRETO. Botones de impresión (menú Participantes, statusbar del form, botón /survey/print) unificados al mismo reporte con nombre de archivo condicional.',
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'biocreto_encuestas',
        'biocreto_pdf_engine',
        'biocreto_sig',
    ],
    'data': [
        'data/sig_encuestas_data.xml',
        'report/report_encuestas_layout.xml',
        'report/report_encuesta_satisfaccion.xml',
        'report/report_encuesta_reclamo.xml',
        'report/report_encuesta_dispatcher.xml',
        'report/report_encuestas_actions.xml',
        'views/survey_page_print_inherit.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'biocreto_encuestas_reporte/static/src/scss/report_encuestas.scss',
        ],
        # v19.0.2.0.0 — patch de SurveyPrint (Interaction del portal
        # /survey/print). Va en survey.survey_assets porque es donde
        # vive el JS nativo que patcheamos (survey_print.js).
        'survey.survey_assets': [
            'biocreto_encuestas_reporte/static/src/interactions/biocreto_survey_print.js',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
