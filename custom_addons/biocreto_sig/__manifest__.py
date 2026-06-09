{
    'name': 'BIOCRETO SIG',
    'version': '19.0.1.0.0',
    'category': 'BIOCRETO',
    'summary': 'Sistema Integrado de Gestion - Control de documentos (codigo, version, fecha)',
    'description': "Control de documentos del SIG: codigo, version vigente, fecha, historial de versiones y PDF oficial adjunto. Los reportes QWeb consultan por codigo_documento.",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/documento_control_views.xml',
        'views/sig_menus.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
