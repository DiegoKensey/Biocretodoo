{
    'name': 'BIOCRETO - Base',
    'version': '19.0.1.1.0',
    'category': 'Localization/Peru',
    'summary': 'Capa base para la implementación BIOCRETO: campos de planta, DNI/RUC y atributos maestros de producto.',
    'description': """
BIOCRETO - Base
===============
Módulo base de la serie biocreto_*. Provee:
- Campos custom en res.company (plant_code, manager_id).
- Autoselección de tipo de identificación DNI/RUC en res.partner para Perú.
- Validación ligera de longitud para DNI (8) y RUC (11).
- Atributo maestro biocreto_fc_resistencia (Integer) en product.template.
""",
    'author': 'Diego Orcón Gómez',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts', 'product', 'l10n_pe', 'l10n_latam_base'],
    'data': [
        'views/res_company_views.xml',
        'views/product_template_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
