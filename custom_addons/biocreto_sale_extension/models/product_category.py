import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Las tres categorías de producto que BIOCRETO vende.
#
# POR QUÉ POR NOMBRE Y NO POR ID
# ------------------------------
# El id de la categoría es distinto en cada base: en desarrollo
# `Servicios adicionales` es la 28, en producción será otra. Y no tiene
# xmlid al que anclarse — decisión del usuario: se crea por hook, sin
# xmlid. Así que el nombre es el único identificador estable que hay.
#
# El literal está verificado contra la base: sin tilde, con la `a` de
# "adicionales" en minúscula. `product.category.name` NO es traducible
# (odoo/addons/product/models/product_category.py:17 lo declara como
# `fields.Char('Name', index='trigram', required=True)`, sin
# `translate=True`), así que un `=` contra este literal es exacto e
# independiente del idioma de quien corra el `-u`.
#
# Los nombres de Concreto y Bombeo ya se comparaban literalmente en 39
# puntos del proyecto antes de este archivo; aquí solo se les da un sitio
# con nombre. No se migra nada: es explícitamente lo que el usuario pidió
# dejar como está.
# ──────────────────────────────────────────────────────────────────────
BIOCRETO_CATEG_CONCRETO = 'Concreto'
BIOCRETO_CATEG_BOMBEO = 'Bombeo'
BIOCRETO_CATEG_SERVICIOS = 'Servicios adicionales'

BIOCRETO_CATEGORIAS_VENTA = (
    BIOCRETO_CATEG_CONCRETO,
    BIOCRETO_CATEG_BOMBEO,
    BIOCRETO_CATEG_SERVICIOS,
)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model
    def _biocreto_asegurar_servicios_adicionales(self):
        """Crea la categoría `Servicios adicionales` solo si no existe.

        Idempotente por construcción: busca primero y solo crea cuando no
        hay ninguna. Correrla mil veces deja una sola categoría.

        Se invoca desde dos sitios, y hacen falta los dos:
          - `post_init_hook`, que cubre la INSTALACIÓN del módulo
            (odoo/modules/loading.py: el hook solo corre en install).
          - la `<function>` de `data/biocreto_categorias.xml`, que se
            reejecuta en cada `-u`, que es el caso operativo real.
        Los dos llaman a ESTE método: una sola fuente de verdad. Mismo
        patrón que `_biocreto_cot_sembrar_textos` (hooks.py) y que
        `data/biocreto_cot_textos.xml`.

        Devuelve el recordset de la categoría, exista o se acabe de crear.
        """
        categoria = self.search(
            [('name', '=', BIOCRETO_CATEG_SERVICIOS)], limit=1)
        if categoria:
            _logger.info(
                "biocreto_sale_extension: la categoría de producto %r ya "
                "existe (id=%s); no se crea nada.",
                BIOCRETO_CATEG_SERVICIOS, categoria.id,
            )
            return categoria

        categoria = self.create({'name': BIOCRETO_CATEG_SERVICIOS})
        _logger.info(
            "biocreto_sale_extension: creada la categoría de producto %r "
            "(id=%s).",
            BIOCRETO_CATEG_SERVICIOS, categoria.id,
        )
        return categoria
