from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    # Campo aditivo. product.category NO tiene `color` nativo en v19
    # (verificado en odoo/addons/product/models/product_category.py y contra
    # information_schema). Alimenta el badge de color de la columna Categoria
    # en las lineas de requerimiento via el `color_field` del widget badge.
    # Rango util: 0..11 -> clases o_badge_color_0 .. o_badge_color_11
    # (odoo/addons/web/static/src/core/badge/badge.scss:1-8, sobre $o-colors,
    # que tiene 12 entradas en secondary_variables.scss:8-9).
    color = fields.Integer(string="Color")
