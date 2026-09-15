import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# El agente que Odoo crea al instalar `ai` con el modelo ya caducado
# (ai/data/ai_agent_data.xml:8-12). Se busca por XMLID, nunca por nombre:
# el `name` es un `related` de `partner_id.name` y el usuario puede
# renombrarlo desde la interfaz sin que nada se lo impida.
XMLID_AGENTE = 'ai.ai_agent_natural_language_search'

# Solo se repunta si sigue exactamente en este modelo. Cualquier otro
# valor se considera una elección deliberada de alguien y no se toca.
MODELO_CADUCADO = 'gemini-2.5-flash'
MODELO_NUEVO = 'gemini-3.7-flash'


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    @api.model
    def _biocreto_repuntar_agente_ask_ai(self):
        """Pasa el agente «Ask AI» de gemini-2.5-flash a gemini-3.7-flash.

        POR QUÉ HACE FALTA, Y POR QUÉ HACE FALTA EN CADA `-u`
        ----------------------------------------------------
        `ai/data/ai_agent_data.xml` **no lleva `noupdate`**, así que
        cualquier `-u ai` —o un `-u all`, o una actualización del core que
        lo arrastre— reescribe `llm_model` de vuelta a `gemini-2.5-flash`,
        que es justo el modelo que Google ya cerró a proyectos nuevos. La
        corrección hecha a mano en la interfaz se pierde sin avisar.

        Por eso este método se invoca desde DOS sitios:
          - `post_init_hook`, que cubre la INSTALACIÓN
            (odoo/modules/loading.py: el hook solo corre en install).
          - la `<function>` de `data/biocreto_ai_agente.xml`, que se
            reejecuta en CADA `-u`, y es la que devuelve el modelo a su
            sitio después de un `-u ai`.
        Los dos llaman a ESTE método: una sola fuente de verdad. Mismo
        patrón que `biocreto_sale_extension`.

        NUNCA PISA UNA ELECCIÓN MANUAL: si el agente está en cualquier
        modelo que no sea `gemini-2.5-flash`, se sale sin tocar nada.
        """
        agente = self.env.ref(XMLID_AGENTE, raise_if_not_found=False)
        if not agente:
            _logger.info(
                "biocreto_ai: el agente %s no existe en esta base; "
                "no hay nada que repuntar.", XMLID_AGENTE,
            )
            return False

        actual = agente.llm_model
        if actual != MODELO_CADUCADO:
            _logger.info(
                "biocreto_ai: el agente %s está en %r, no en %r; se respeta "
                "la elección y no se toca nada.",
                XMLID_AGENTE, actual, MODELO_CADUCADO,
            )
            return False

        agente.llm_model = MODELO_NUEVO
        _logger.info(
            "biocreto_ai: el agente %s pasa de %r a %r.",
            XMLID_AGENTE, MODELO_CADUCADO, MODELO_NUEVO,
        )
        return True
