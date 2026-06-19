{
    'name': 'BIOCRETO - Información de Suministro en Cotizaciones',
    'version': '19.0.1.7.3',
    'category': 'Sales',
    'summary': 'Datos de obra, vaceo, volumen operativo, costo compensado, Boom, diseño y filtro de bomba.',
    'description': """
BIOCRETO - Información de Suministro v1.5
==========================================
v1.4:
- Dirección estructurada de obra (Departamento/Provincia/Distrito/Calle) con cascada.
- Coordenadas GPS con geolocalización.
- Catálogos configurables por empresa (Estructura, Cemento, Huso TMN).
- Vehículo de bombeo (Flota).
- Naming custom de cotizaciones.

v1.5:
- Fecha de vaceo (rango fecha+hora, daterange) sincronizada a commitment_date.
- Volumen operativo y costo compensado (fase 1 planeado) por línea Concreto.
- Boom (Many2one a mrp.bom) por línea Concreto.
- Estado de diseño (tag rojo/verde) en la cabecera.
- Tipo de colocación (Directo/Pluma) por línea Concreto.
- Parámetro de Compañía: categoría Bomba Telescópica (fleet).
- Filtro del Vehículo Asignado por la categoría parametrizada.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'biocreto_base',
        'fleet',
        'mrp',
        'base_address_extended',
        'l10n_pe',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/biocreto_catalog_views.xml',
        'views/res_company_views.xml',
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
