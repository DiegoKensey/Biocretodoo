from odoo import api, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.depends('code')
    def _compute_display_name(self):
        # Nativo (mrp/models/mrp_bom.py:313) muestra "<code>: <producto>".
        # En BIOCRETO el producto es redundante porque el campo bom_id en la
        # línea ya está filtrado por biocreto_bom_domain (por product_tmpl_id),
        # así que el desplegable solo muestra Booms del producto seleccionado.
        # Aquí: si hay code, mostrar SOLO el code (ej. "D210H57-WG9800");
        # si no hay code, delegar al super para conservar el nativo.
        no_code = self.env['mrp.bom']
        for bom in self:
            if bom.code:
                bom.display_name = bom.code
            else:
                no_code |= bom
        if no_code:
            return super(MrpBom, no_code)._compute_display_name()
