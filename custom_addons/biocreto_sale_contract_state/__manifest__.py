{
    'name': 'BIOCRETO - Estado Contrato en Cotizaciones',
    'version': '19.0.1.0.4',
    'category': 'Sales',
    'summary': 'Estado intermedio "Contrato" entre Enviada y Orden de Venta para BIOCRETO.',
    'description': """
BIOCRETO - Estado Contrato
===========================
Inserta un estado intermedio 'contract' (Contrato) en el flujo de sale.order:
Borrador → Enviada → Contrato → Orden de Venta.

Toda cotización debe pasar por Contrato antes de ser Orden de Venta.
Aplica tanto al flujo backend como al flujo del portal.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'biocreto_sale_extension'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
