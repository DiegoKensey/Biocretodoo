"""Migracion v19.0.1.3.0 -> v19.0.1.4.0 - adopcion de la categoria Concreto.

En bases donde biocreto_base ya esta instalado el `pre_init_hook` no vuelve a
dispararse, asi que la asociacion del xmlid a la categoria preexistente tiene
que hacerse aqui. El stage 'pre' corre antes de cargar los data del modulo
(odoo/modules/loading.py:175), que es justo lo que hace falta para que
`data/product_category_data.xml` encuentre el xmlid ya resuelto y no cree una
segunda categoria "Concreto".

Idempotente: si el xmlid ya existe, no hace nada. No escribe sobre ningun
producto ni toca `biocreto_fc_resistencia`.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    from odoo.addons.biocreto_base.hooks import adoptar_categoria_concreto
    adoptar_categoria_concreto(api.Environment(cr, SUPERUSER_ID, {}))
