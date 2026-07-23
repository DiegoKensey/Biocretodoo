{
    'name': 'BIOCRETO Compras',
    'version': '19.0.6.0.0',
    'category': 'Supply Chain/Purchase',
    'summary': 'Estado "Registro" en purchase.order, numeracion CP-AAAA-PLANTA-####, ajustes de UI (precios/impuestos/incoterm ocultos), Alternativas hasta Registro.',
    'description': (
        "Lote 1 del flujo BIOCRETO Compras: introduce el estado intermedio 'Registro' "
        "entre 'sent' y 'to approve/purchase', numeracion propia CP-AAAA-PLANTA-#### "
        "con reset anual por compania (mismo patron que biocreto_sale_extension), "
        "oculta columnas de precio/impuestos/subtotal en draft/sent, oculta Incoterm "
        "siempre, renombra botones (Enviar / Confirmar / Enviar OC), badge ambar del "
        "estado Registro en la lista de RFQs, y amplia el dominio de alternative_po_ids "
        "de purchase_requisition para incluir 'registro'."
    ),
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'purchase_stock',
        'purchase_requisition',
        'biocreto_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/biocreto_medio_pago_views.xml',
        'views/purchase_order_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
