{
    'name': 'BIOCRETO - Estados Contrato y Programado en Cotizaciones',
    'version': '19.0.1.2.1',
    'category': 'Sales',
    'summary': 'Estados Contrato y Programado + cron de auto-confirmación + candado de diseño.',
    'description': """
BIOCRETO - Estados intermedios Contrato y Programado
=====================================================
v1.0.x: Estado 'contract' entre 'sent' y 'sale'.

v1.1.0:
- Nuevo estado 'programado' entre 'contract' y 'sale'.
- Botón "Pasar a Programación" (contract → programado).
- Botón "Confirmar" (programado → sale).
- Cron de auto-confirmación con buffer parametrizable por compañía.
- Candado opcional: exigir Diseño de mezcla antes de OV.
- Colores tree: Programado amarillo, Contrato azul.
- Filtros "En Contrato" y "En Programación".
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'biocreto_sale_extension'],
    'data': [
        'views/res_company_views.xml',
        'views/sale_order_views.xml',
        'data/ir_cron.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
