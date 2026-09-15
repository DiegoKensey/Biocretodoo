from odoo import models

from .product_category import BIOCRETO_PATRON_CODIGO


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # ─────────────────────────────────────────────────────────────────
    # LA RED QUE ATRAPA EL CHOQUE DE VERDAD.
    #
    # `default_code` no tiene unicidad en Odoo: solo un índice normal
    # (`product_product__default_code_index`, comprobado en pg_indexes).
    # El único aviso de duplicado es un `onchange`
    # (product_template.py:416-428), que solo salta al teclear en el
    # formulario: un `create()` programático o un import lo saltan sin
    # enterarse.
    #
    # POR QUÉ UN ÍNDICE PARCIAL Y NO UN UNIQUE A SECAS
    # ------------------------------------------------
    # Un `UNIQUE(default_code)` impondría unicidad a TODO el catálogo,
    # incluidos los códigos de demo de Odoo (`COMM`, `FOOD`, `GIFT`…) y
    # cualquier referencia que alguien escriba a mano. El `WHERE` acota la
    # regla a los códigos que genera este módulo y deja el resto en paz.
    #
    # El precedente del core es `account.move._unique_name`
    # (account_move.py:780-783), que hace exactamente esto: índice único
    # con WHERE para no molestar a los asientos que aún no están
    # publicados.
    #
    # El literal del patrón es el MISMO que usa el buscador de huecos.
    # Viene de product_category.py; aquí no se reescribe.
    # ─────────────────────────────────────────────────────────────────
    _biocreto_codigo_uniq = models.UniqueIndex(
        "(default_code) WHERE default_code ~ '%s'" % BIOCRETO_PATRON_CODIGO,
        "Ya existe un producto con esa referencia interna.",
    )
