{
    'name': 'BIOCRETO - Portal del Cliente',
    'version': '19.0.1.5.0',
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

v19.0.1.2.0:
- Bloque "Contrato de Suministro" en /my/orders/<id> cuando la orden
  esta en contract/programado/sale.
- Boton "Descargar Contrato (PDF)" ruteado a PlutoPrint.
- 3 modos de firma: Cliente / Jefe de Obra / Ambos (reusan el widget
  nativo portal.signature_form, un widget activo a la vez).
- Ruta /my/orders/<id>/sign_contract/<kind> que escribe los campos
  biocreto_firma_contrato* y/o biocreto_firma_jefe_obra* segun kind.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'portal',
        'biocreto_sale_extension',
        'biocreto_sale_contract_state',
        'biocreto_sale_reports_contrato',
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
