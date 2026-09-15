import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Hook que corre cuando el modulo se INSTALA (no en upgrades).

    El caso del `-u` lo cubre la <function> de
    data/biocreto_categorias_codigo.xml, que llama al MISMO metodo.
    """
    env['product.category']._biocreto_sembrar_categorias()
