{
    'name': 'BIOCRETO - Reportes de Ventas',
    'version': '19.0.1.0.1',
    'category': 'Sales/Reports',
    'summary': 'Formato custom de cotización BC-GC-FR-09 / BC-GC-FR-10 y nomenclatura de cotizaciones BIOCRETO.',
    'description': """
BIOCRETO - Reportes de Ventas
==============================
- Reemplaza el name nativo de sale.order por formato AÑO-CFC-NV-0001.
- Crea secuencias por empresa, reinicio anual.
- Reporte QWeb condicional menor/mayor envergadura (BC-GC-FR-09 / BC-GC-FR-10).
- Tabla de concreto y tabla de bombeo separadas por categoría de producto.
- Firma del cliente jalada del campo signature del portal.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'biocreto_sale_portal',
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/paperformat_data.xml',
        'report/sale_order_report.xml',
        'report/sale_order_report_template.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
