{
    'name': 'BIOCRETO Compras Reporte',
    'version': '19.0.1.2.0',
    'category': 'Purchases',
    'summary': 'Reportes BIOCRETO de Solicitud de Cotizacion y Orden de Compra',
    'description': (
        "Reportes PDF con identidad BIOCRETO para compras: Solicitud de "
        "Cotizacion (BC-GL-FR-05) y Orden de Compra (stub). Reemplaza los "
        "templates document nativos de purchase con Opcion A pura y se "
        "suscribe al motor PlutoPrint de biocreto_pdf_engine para los dos "
        "canales de impresion (RFQ y PO)."
    ),
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'purchase_stock',
        'biocreto_compras',
        'biocreto_base',
        'biocreto_sig',
        'biocreto_pdf_engine',
    ],
    'data': [
        'data/documento_control_data.xml',
        'report/paperformat.xml',
        'report/report_compras.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'biocreto_compras_reporte/static/src/scss/report_compras.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
