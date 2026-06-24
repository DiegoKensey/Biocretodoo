{
    'name': 'BIOCRETO - Reporte Contrato de Suministro',
    'version': '19.0.1.5.0',
    'category': 'Sales/Reports',
    'summary': 'Reporte QWeb del Contrato de Suministro de Concreto BC-GC-FR-05 (PlutoPrint) suscrito al motor biocreto_pdf_engine.',
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'biocreto_sale_report_cotizacion',
        'biocreto_sale_contract_state',
        'biocreto_sig',
    ],
    'data': [
        'data/sig_contrato_data.xml',
        'report/report_contrato_actions.xml',
        'report/report_contrato.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'biocreto_sale_reports_contrato/static/src/scss/report_contrato.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
