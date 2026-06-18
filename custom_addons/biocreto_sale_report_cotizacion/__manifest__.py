{
    'name': 'BIOCRETO - Reporte Cotizacion FR-09/FR-10',
    'version': '19.0.2.0.13',
    'category': 'Sales/Reports',
    'summary': 'Reporte QWeb de cotizacion BC-GC-FR-09/FR-10 con render PlutoPrint (running header/footer) suscrito a biocreto_pdf_engine; sobrescribe sale.report_saleorder_document via Opcion A para cubrir Imprimir/Correo/Portal.',
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'sale_stock',
        'biocreto_sale_extension',
        'biocreto_sig',
        'biocreto_base',
        'biocreto_pdf_engine',
    ],
    'data': [
        'report/paperformat.xml',
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
