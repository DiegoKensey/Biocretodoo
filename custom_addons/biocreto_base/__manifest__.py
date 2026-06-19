{
    'name': 'BIOCRETO - Base',
    'version': '19.0.1.3.0',
    'category': 'Localization/Peru',
    'summary': 'Capa base para la implementacion BIOCRETO: campos de planta, DNI/RUC, atributos maestros de producto, CCI y firma de usuario.',
    'description': "Modulo base de la serie biocreto_*. Provee campos custom en res.company (plant_code, manager_id), autoseleccion DNI/RUC en res.partner para Peru, validacion de longitud DNI(8)/RUC(11), atributo maestro biocreto_fc_resistencia en product.template, CCI en res.partner.bank y firma cargable en res.users (estilo v18).",
    'author': 'Diego Orcon Gomez',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts', 'product', 'l10n_pe', 'l10n_latam_base'],
    'data': [
        'views/res_company_views.xml',
        'views/product_template_views.xml',
        'views/res_partner_bank_views.xml',
        'views/res_users_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
