{
    'name': 'Fabricación',
    'version': '19.0.1.2.0',
    'category': 'BIOCRETO',
    'summary': 'Centro de control del plantero BIOCRETO',
    'description': (
        'Centro de control de planta para BIOCRETO: panel OWL de ordenes de '
        'fabricacion con cargas parciales por mixer, dosificacion editable y '
        'descuento real de inventario.'
    ),
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'mrp',
        'mrp_workorder',
        'sale',
        'sale_mrp',
        'sale_stock',
        'stock',
        'fleet',
        'mail',
        'biocreto_sale_extension',
        'biocreto_sale_contract_state',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/biocreto_carga_views.xml',
        'views/planta_search_views.xml',
        'views/planta_action.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biocreto_fabricacion/static/src/**/*.js',
            'biocreto_fabricacion/static/src/**/*.xml',
            'biocreto_fabricacion/static/src/**/*.scss',
        ],
    },
    'installable': True,
    'application': True,
}
