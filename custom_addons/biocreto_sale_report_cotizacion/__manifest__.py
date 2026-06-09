{
    'name': 'BIOCRETO Sale Report Cotizacion',
    'version': '19.0.1.0.2',
    'category': 'BIOCRETO',
    'summary': 'Reporte QWeb de cotizacion BIOCRETO (FR-09 menor / FR-10 mayor)',
    'description': "Reporte imprimible de cotizacion BIOCRETO. Un boton enruta menor/mayor segun biocreto_tipo_proyecto. Header/footer SVG a sangre con repeticion nativa, consumo del SIG, QR al portal.",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['biocreto_sale_extension', 'biocreto_sig', 'biocreto_base'],
    'data': [
        'report/paperformat.xml',
        'report/report_action.xml',
        'report/report_cotizacion.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'biocreto_sale_report_cotizacion/static/src/scss/report_cotizacion.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
