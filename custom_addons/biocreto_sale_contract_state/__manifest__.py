{
    'name': 'BIOCRETO - Estados Contrato y Programado en Cotizaciones',
    'version': '19.0.1.3.0',
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

v1.3.0:

- El estado nativo 'sent' se muestra como "Preprogramado" (sale.order y
  sale.report). La traducción la escribe un <function> en cada -u.
- Botones "Preprogramar" (Cotización → Preprogramado, exige fecha de
  vaceo) y "Regresar" (Preprogramado → Cotización).
- Sin envío de cotizaciones por correo: botones Enviar/Pro-forma ocultos,
  action_quotation_sent anulado, `mark_so_as_sent` neutralizado y las
  acciones "Mark Quotation as Sent" / "Send an email" solo para Ajustes.
- Filtro "Preprogramado".
- Migración: los pedidos que estaban en 'sent' vuelven a Cotización.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'biocreto_sale_extension'],
    'data': [
        'views/res_company_views.xml',
        'views/sale_order_views.xml',
        'data/ir_cron.xml',
        'data/ir_actions_server_data.xml',
        'data/sale_order_state_data.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
