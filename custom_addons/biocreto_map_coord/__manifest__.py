{
    'name': 'BIOCRETO Map Coord',
    'version': '19.0.1.0.3',
    'category': 'Technical',
    'summary': 'Vista mapa que ubica registros por coordenadas propias (no por res.partner).',
    'description': """
BIOCRETO Map Coord
==================
Registra el js_class 'biocreto_coord_map': extiende el MapModel nativo de
web_map para tomar latitud/longitud de campos del propio registro
(configurables por context lat_field/lng_field; defaults
biocreto_latitud/biocreto_longitud).

Diseño consciente:
- Renderer, Controller y ArchParser quedan NATIVOS → popup, lista lateral
  y botones idénticos al mapa de res.partner.
- Solo se sustituye el Model. El override toca dos métodos:
    · _getRecordSpecification → pide lat/lng al webSearchRead sin
      declararlos en el <map> (evita ensuciar el popup).
    · _addPartnerToRecord → reemplaza record.partner por un objeto
      SINTÉTICO con las coords del propio registro, conservando el resto
      (display_name, contact_address_complete) del partner real.
- El js_class solo afecta a vistas que lo declaren explícitamente
  (js_class="biocreto_coord_map") → cero impacto en Contactos, CRM,
  Project, etc.

Reutilizable. Cualquier modelo que tenga dos Float de coordenadas puede
declarar este js_class en su <map> y pasar lat_field/lng_field por
context si los nombres difieren de los defaults.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['web_map'],
    'assets': {
        # web.assets_backend_lazy: MISMO bundle que web_map (donde se definen
        # MapModel y mapView). Cargar nuestro override en assets_backend
        # provoca el warning "needed by other modules but have not been
        # defined" en consola al arrancar, porque los imports a @web_map/...
        # no resuelven hasta que el bundle lazy se descarga al abrir un mapa.
        #
        # Patrón verificado contra:
        #   odoo/addons/web_map/__manifest__.py:17       (canonical)
        #   odoo/addons/stock_enterprise/__manifest__.py:22
        #   odoo/addons/project_enterprise/__manifest__.py:37-38
        #     (carga proyect_task_map/** en assets_backend_lazy)
        'web.assets_backend_lazy': [
            'biocreto_map_coord/static/src/**/*',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
