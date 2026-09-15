import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Hook que corre cuando el modulo se INSTALA (no en upgrades).

    El caso del `-u` lo cubre la <function> de
    data/biocreto_ai_agente.xml, que llama al MISMO metodo del modelo.
    """
    env['ai.agent']._biocreto_repuntar_agente_ask_ai()
