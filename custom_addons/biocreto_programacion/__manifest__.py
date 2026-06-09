{
    'name': 'BIOCRETO Programación',
    'version': '19.0.1.0.2',
    'category': 'Sales',
    'summary': 'Reconfigura el calendario de Ventas por fecha de vaceo + botón Ir a (módulo invisible).',
    'description': """
BIOCRETO Programación
=====================
Módulo INVISIBLE (sin menú propio, sin app, sin acción de ventana propia).
Modifica las vistas nativas de Ventas:

- Calendario de sale.order por fecha de vaceo (con hora) en lugar de
  actividades. Reemplaza el chip de actividades por el estado de diseño
  en el popup.
- Botón "Ir a" en el footer del popover del calendario, que abre Google
  Maps Directions hacia las coordenadas (o dirección) de la obra.

NO toca la vista mapa (queda para un módulo futuro). El campo
biocreto_gmaps_url vive en biocreto_sale_extension v19.0.1.5.5+, no aquí.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        # contract_state arrastra biocreto_sale_extension v6.0+ (donde vive
        # biocreto_gmaps_url + biocreto_latitud/longitud) y el resto de la
        # pila (sale, mrp, fleet…).
        'biocreto_sale_contract_state',
        # map_coord aporta el js_class biocreto_coord_map que el mapa de
        # ventas usa para ubicar las órdenes por coords propias.
        'biocreto_map_coord',
    ],
    'data': [
        'views/sale_order_calendar_views.xml',
        'views/sale_order_map_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biocreto_programacion/static/src/js/calendar_popover_ir_a.js',
            'biocreto_programacion/static/src/xml/calendar_popover_ir_a.xml',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
