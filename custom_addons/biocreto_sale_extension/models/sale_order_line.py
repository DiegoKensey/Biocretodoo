from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ─────────────────────────────────────────────────────────────────
    # Campo puente: lee la categoría del producto automáticamente
    # Invisible en UI. Sirve solo para condiciones de visibilidad.
    # ─────────────────────────────────────────────────────────────────
    biocreto_product_categ = fields.Char(
        related='product_id.categ_id.name',
        string="Categoría del producto",
        store=False,
    )

    # ─────────────────────────────────────────────────────────────────
    # Campos de CONCRETO — ahora Many2one a catálogos por empresa.
    # check_company=True garantiza que el valor pertenezca a la misma
    # empresa que el sale.order.line (vía order_id.company_id).
    # El domain replica esa misma restricción en la UI.
    # ─────────────────────────────────────────────────────────────────
    biocreto_estructura = fields.Many2one(
        comodel_name='biocreto.estructura',
        string="Estructura",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    biocreto_tipo_cemento = fields.Many2one(
        comodel_name='biocreto.tipo.cemento',
        string="Tipo de cemento",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    biocreto_huso_tmn = fields.Many2one(
        comodel_name='biocreto.huso.tmn',
        string="Huso TMN",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    biocreto_slump = fields.Float(
        string="Slump (pulg.)",
        digits=(5, 2),
    )

    # ─────────────────────────────────────────────────────────────────
    # Campos de BOMBEO
    # ─────────────────────────────────────────────────────────────────
    biocreto_vehiculo_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Vehículo Asignado",
        help="Vehículo de la flota asignado al servicio de bombeo.",
    )
    biocreto_tuberia_adicional = fields.Integer(
        string="Tuberías adicionales (m)",
        default=0,
    )
    biocreto_slump_bombeable = fields.Float(
        string="Slump bombeable (pulg.)",
        digits=(5, 2),
    )

    # ─────────────────────────────────────────────────────────────────
    # Acceso al detalle de la línea como dialog modal
    # ─────────────────────────────────────────────────────────────────
    def action_open_biocreto_line_form(self):
        """Abre el form standalone con los grupos BIOCRETO en dialog modal.

        Al ser type="object" en una list editable, Odoo persiste la cotización
        (y la línea) ANTES de invocar el método. Esto NO genera bucle porque
        la validación dura de campos técnicos vive en action_confirm
        (sale_order.py), no en @api.constrains: guardar un borrador con
        campos técnicos vacíos no falla.
        """
        self.ensure_one()
        view = self.env.ref(
            'biocreto_sale_extension.sale_order_line_view_form_biocreto'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Detalle de línea"),
            'res_model': 'sale.order.line',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
        }
