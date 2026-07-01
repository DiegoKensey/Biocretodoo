{
    'name': 'BIOCRETO Encuestas - Reportes QWeb (PlutoPrint)',
    'version': '19.0.1.4.0',
    'category': 'Marketing/Surveys',
    'summary': 'Informes PDF SIG por participante: satisfaccion (BC-GC-FR-16) y reclamo (BC-GC-FR-03 - en prompt 2).',
    'description': 'Informes QWeb PDF que replican el aspecto del print nativo de Survey con marco BIOCRETO: header tricolor + cuadrito SIG (codigo/version/fecha) + footer con codigo SIG + numeracion + apartado final Ley 29733 + firma del cliente. Reusa biocreto_pdf_engine (PlutoPrint) y biocreto_sig (registro de control de documentos).',
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
        'report/report_encuestas_actions.xml',
    ],
    'assets': {
        # SCSS de los reportes va en web.report_assets_common
        # (mismo bundle que biocreto_sale_reports_contrato). PlutoPrint
        # inlinea este bundle al renderizar (biocreto_pdf_engine
        # _biocreto_inline_assets).
        'web.report_assets_common': [
            'biocreto_encuestas_reporte/static/src/scss/report_encuestas.scss',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
