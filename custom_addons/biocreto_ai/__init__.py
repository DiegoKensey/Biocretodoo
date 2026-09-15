# ──────────────────────────────────────────────────────────────────────
# PARCHE EN CALIENTE sobre una constante de un módulo ENTERPRISE.
#
# Sí: esto muta `PROVIDERS`, una constante de `odoo/addons/ai`, que es
# código de Odoo S.A. con licencia OEEL-1. No es una decisión estética.
# Es la única vía que existe, y conviene dejar escrito por qué, para que
# nadie lo "limpie" pensando que hay una forma más ortodoxa.
#
# POR QUÉ NO SE PUEDE CON `_inherit`
# ----------------------------------
# El campo se declara así (ai/models/ai_agent.py:261-289):
#
#     @api.model
#     def _get_llm_model_selection(self):
#         selection = []
#         for provider in PROVIDERS:
#             selection.extend(provider.llms)
#         return selection
#     …
#     llm_model = fields.Selection(selection=_get_llm_model_selection, …)
#
# A `selection=` se le pasa el OBJETO FUNCIÓN, no su nombre en cadena. El
# campo se queda con esa referencia, así que redefinir
# `_get_llm_model_selection` en un modelo heredado no cambia nada: se
# sigue ejecutando la función original.
#
# POR QUÉ NO SE PUEDE CON `selection_add`
# ---------------------------------------
# `selection_add` solo opera sobre selecciones declaradas como lista
# literal. Sobre un `selection` invocable no aplica.
#
# POR QUÉ NO BASTA CON REDECLARAR EL CAMPO
# ----------------------------------------
# Aunque se redeclarara `llm_model` con otro invocable, el modelo nuevo
# reventaría en la primera petición: `get_provider()`
# (ai/utils/llm_providers.py:66-71, llamado desde ai_agent.py:373)
# recorre TAMBIÉN `PROVIDERS` para saber a qué proveedor mandar la
# llamada, y lanzaría `UserError("No provider found for the selected
# model")`.
#
# Ampliar `PROVIDERS[…].llms` resuelve las tres cosas de una vez: el
# desplegable, la resolución de proveedor y la lista de embeddings.
# `Provider` es un `NamedTuple` (inmutable), pero `llms` es una lista
# normal y sí admite `append` — comprobado en proceso contra la versión
# instalada.
#
# CUÁNDO SE PUEDE TIRAR ESTE MÓDULO
# ---------------------------------
# El día que Odoo publique una versión de `ai` que ya traiga los modelos
# de la serie 3.x en `PROVIDERS`, este módulo sobra: se desinstala y
# `llm_model` vuelve a la lista de origen. Mientras tanto, el guardia
# `not in` de abajo evita que la entrada salga duplicada si esa versión
# llega antes de que nadie se acuerde de desinstalarlo.
# ──────────────────────────────────────────────────────────────────────
import logging

from odoo.addons.ai.utils import llm_providers

from . import models
from .hooks import post_init_hook

_logger = logging.getLogger(__name__)

# Solo el 3.7. GA desde el 13 de agosto de 2026, perfil "workhorse".
# El 3.6 es el que nombra el mensaje de error de Google, pero ya va dos
# generaciones por detrás; el 3.8 está orientado a tareas de horizonte
# largo y consume más de lo que este uso necesita.
BIOCRETO_MODELO_GEMINI = ("gemini-3.7-flash", "Gemini 3.7 Flash")


def _biocreto_ampliar_modelos_google():
    """Añade el modelo a la lista del proveedor Google. Idempotente."""
    for proveedor in llm_providers.PROVIDERS:
        if proveedor.name != 'google':
            continue
        if BIOCRETO_MODELO_GEMINI in proveedor.llms:
            _logger.info(
                "biocreto_ai: %r ya está en la lista del proveedor Google; "
                "no se añade nada.", BIOCRETO_MODELO_GEMINI[0],
            )
            return
        proveedor.llms.append(BIOCRETO_MODELO_GEMINI)
        _logger.info(
            "biocreto_ai: añadido %r a los modelos del proveedor Google.",
            BIOCRETO_MODELO_GEMINI[0],
        )
        return
    _logger.warning(
        "biocreto_ai: no se encontró el proveedor 'google' en PROVIDERS; "
        "el modelo %r NO se ha añadido.", BIOCRETO_MODELO_GEMINI[0],
    )


_biocreto_ampliar_modelos_google()
