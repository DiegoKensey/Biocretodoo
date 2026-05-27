{
    'name': 'BIOCRETO - Información de Suministro en Cotizaciones',
    'version': '19.0.1.3.0',
    'category': 'Sales',
    'summary': 'Datos de obra, naming custom, catálogos configurables y vehículo de bombeo para cotizaciones BIOCRETO.',
    'description': """
BIOCRETO - Información de Suministro v1.3
==========================================
- Pestaña "Información de Suministro" con grupo "Datos de Obra".
- Widget OWL de geolocalización para coordenadas GPS.
- Catálogos configurables POR EMPRESA: Estructura, Tipo de cemento, Huso TMN.
- Campo Vehículo Asignado (Flota) en líneas de Bombeo.
- Identificación automática Concreto/Bombeo por categoría del producto.
- Naming custom de cotizaciones: AÑO-CFC-NV-0001.
- Validación: campos técnicos de Concreto obligatorios al confirmar.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'biocreto_base', 'fleet'],
    'data': [
        'security/ir.model.access.csv',
        'views/biocreto_catalog_views.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biocreto_sale_extension/static/src/components/geo_button/geo_button.js',
            'biocreto_sale_extension/static/src/components/geo_button/geo_button.xml',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
