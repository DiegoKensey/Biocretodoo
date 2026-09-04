"""Enlace estable entre el modulo y la categoria de producto "Concreto".

La categoria vive en la base del cliente, creada a mano desde la interfaz, y
por eso no tiene xmlid. Sin xmlid, `data/product_category_data.xml` crearia
una SEGUNDA categoria "Concreto": los productos existentes seguirian
apuntando a la vieja y el campo f'c no apareceria en ninguno.

Para impedirlo se le crea su `ir.model.data` ANTES de que ese data se procese.
Hay dos entradas, mutuamente excluyentes (Odoo 19, odoo/modules/loading.py):

  - Instalacion  -> `pre_init_hook`, loading.py:180. Solo corre cuando
    `update_operation == 'install'`, antes de cargar los data del modulo.
  - Actualizacion -> `migrations/19.0.1.4.0/pre-migration.py`, disparado por
    `migrations.migrate_module(package, 'pre')` en loading.py:175, tambien
    antes de los data. Es el UNICO camino en bases donde biocreto_base ya
    esta instalado, porque ahi el pre_init_hook no vuelve a dispararse nunca.

La busqueda por nombre corre una sola vez y nunca mas: es migracion, no
logica de negocio. A partir de ese momento la referencia es el xmlid, que
sobrevive a renombrar la categoria desde la interfaz (lo protege el
`noupdate="1"`) y a recrear la base.
"""

import logging

_logger = logging.getLogger(__name__)

XMLID_MODULE = 'biocreto_base'
XMLID_NAME = 'product_category_concreto'
NOMBRE_LEGADO = 'Concreto'


def adoptar_categoria_concreto(env):
    """Da xmlid a la categoria "Concreto" preexistente, si aun no lo tiene.

    Idempotente y silenciosa en los dos casos en que no hay nada que hacer:
    el xmlid ya existe, o no hay ninguna categoria con ese nombre (base
    limpia), y entonces el data del modulo la crea el mismo.
    """
    imd = env['ir.model.data'].sudo()
    ya = imd.search([('module', '=', XMLID_MODULE), ('name', '=', XMLID_NAME)])
    if ya:
        _logger.info(
            "biocreto_base: %s.%s ya apunta a product.category %s; no se toca.",
            XMLID_MODULE, XMLID_NAME, ya[0].res_id)
        return

    categorias = env['product.category'].sudo().search(
        [('name', '=', NOMBRE_LEGADO)], order='id asc')
    if not categorias:
        _logger.info(
            "biocreto_base: no existe la categoria %r; la creara el data "
            "del modulo.", NOMBRE_LEGADO)
        return
    if len(categorias) > 1:
        _logger.warning(
            "biocreto_base: hay %s categorias llamadas %r (ids %s). Se adopta "
            "la mas antigua, id %s. Revisar y fusionar a mano.",
            len(categorias), NOMBRE_LEGADO, categorias.ids, categorias[0].id)

    categoria = categorias[0]
    imd.create({
        'module': XMLID_MODULE,
        'name': XMLID_NAME,
        'model': 'product.category',
        'res_id': categoria.id,
        'noupdate': True,
    })
    _logger.info(
        "biocreto_base: %s.%s adoptado por la categoria existente id %s (%r).",
        XMLID_MODULE, XMLID_NAME, categoria.id, categoria.display_name)


def pre_init_hook(env):
    """Solo en instalacion limpia. Ver el docstring del modulo."""
    adoptar_categoria_concreto(env)
