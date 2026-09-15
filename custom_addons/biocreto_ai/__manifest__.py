{
    'name': 'BIOCRETO - Modelos de IA vigentes',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Añade Gemini 3.7 Flash a la lista de modelos y repunta el agente Ask AI.',
    'description': """
BIOCRETO - Modelos de IA vigentes
=================================

Google cerró los modelos `gemini-2.5-*` a los proyectos nuevos antes de su
fecha oficial de retirada (16 de octubre de 2026). El agente «Ask AI» que
Odoo crea al instalar el módulo `ai` nace con `gemini-2.5-flash` y falla
con un 404: "This model is no longer available to new users".

La lista de modelos de `ai` es una constante Python cerrada
(`ai/utils/llm_providers.py`) y no incluye ningún modelo de la serie 3.x.

Este módulo:
  * Añade `gemini-3.7-flash` a los modelos del proveedor Google, sin
    tocar una sola línea bajo `odoo/addons/`.
  * Repunta el agente «Ask AI» a ese modelo, y solo si sigue en el
    caducado — una elección manual nunca se pisa.
  * Lo hace tanto al instalar como en cada `-u`, porque el dato de origen
    de Odoo no lleva `noupdate` y un `-u ai` revierte el modelo.

El día que Odoo publique una versión de `ai` con los modelos 3.x, este
módulo se puede desinstalar sin más.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        # Solo `ai`: es donde viven PROVIDERS, ai.agent y la llamada a
        # Google. `ai_app` es unicamente la capa de menus y vistas, y no
        # aporta nada a este cambio.
        'ai',
    ],
    'data': [
        'data/biocreto_ai_agente.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
