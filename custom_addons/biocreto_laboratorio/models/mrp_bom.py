from odoo import fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    # Related almacenado para agrupar Disenos por resistencia f'c del producto
    # (el campo esta en product.template, aportado por biocreto_base).
    biocreto_fc_resistencia = fields.Integer(
        related='product_tmpl_id.biocreto_fc_resistencia',
        store=True,
        string="Resistencia f'c (kg/cm²)",
    )
