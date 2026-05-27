{
    'name': 'BIOCRETO - Base',
    'version': '19.0.1.0.0',
    'category': 'Localization/Peru',
    'summary': 'Capa base para la implementación BIOCRETO: campos de planta y lógica DNI/RUC.',
    'description': """
BIOCRETO - Base
===============
Módulo base de la serie biocreto_*. Provee:
- Campos custom en res.company (plant_code, manager_id).
- Autoselección de tipo de identificación DNI/RUC en res.partner para Perú.
- Validación ligera de longitud para DNI (8) y RUC (11).
""",
    'author': 'Diego Orcón Gómez',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts', 'l10n_pe', 'l10n_latam_base'],
    'data': [
        'views/res_company_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
