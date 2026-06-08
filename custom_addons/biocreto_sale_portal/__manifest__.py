{
    'name': 'BIOCRETO - Portal del Cliente',
    'version': '19.0.1.1.0',
    'category': 'Sales',
    'summary': 'Personalización del portal cliente para el flujo Cotización → Contrato → Orden de Venta.',
    'description': """
BIOCRETO - Portal del Cliente
==============================
Personaliza el portal del cliente para reflejar el estado intermedio "Contrato":
- Banner verde post-firma con texto custom.
- Etiquetas dinámicas por estado (Cotización / Contrato / Orden de venta).
- Nueva entrada "Contratos" en el menú lateral del portal con contador.
- Notificación al asesor en el chatter cuando el cliente firma.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'portal',
        'biocreto_sale_contract_state',
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
