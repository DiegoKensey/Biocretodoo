{
    'name': 'BIOCRETO - Recepción de materiales',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Documentos de sustento, evidencia de ingreso, transporte y flete en las recepciones.',
    'description': """
BIOCRETO - Recepción de materiales
==================================

Añade a las recepciones (`incoming`) una pestaña propia con:

  * **Documentos de sustento**: tabla de líneas con tipo, número y
    archivo. Se pueden agregar varias del mismo tipo, y se pueden agregar
    a una recepción YA VALIDADA — la factura del proveedor llega semanas
    después. El archivo se guarda con el nombre
    `{REFERENCIA}_{TIPO}_{RUC}_{NUMERO}.{ext}` y se renombra solo si se
    corrige el número o el tipo.
  * **Ingreso**: N° de control, evidencia fotográfica y la fecha y hora
    reales de entrada a planta, distinta de la fecha de validación.
  * **Transporte**: placa, conductor (contacto hijo del proveedor),
    cantera, flete y responsable del flete.
  * Marca de **sin comprobante**, con su filtro en la búsqueda.

Ningún campo es obligatorio y ninguno bloquea la validación de la
transferencia. La única validación del módulo es que no se puede adjuntar
un archivo sin haber escrito antes el número del documento, porque el
número forma parte del nombre del archivo.

El flete es informativo: NO se suma al costo del material.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        # `biocreto_base` aporta `biocreto_identificador_partner`, el helper
        # compartido con `biocreto_compras` para el RUC/DNI del nombre de
        # archivo.
        'biocreto_base',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
