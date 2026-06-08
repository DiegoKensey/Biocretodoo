from odoo import _, api, fields, models


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
    # Volumen operativo y costo compensado (sólo Concreto).
    # Fase 1: costo compensado se calcula con el VOLUMEN OPERATIVO
    # PLANEADO. La fase 2 (producido real) la añade biocreto_fabricacion
    # extendiendo este @api.depends y la lógica del compute.
    # ─────────────────────────────────────────────────────────────────
    biocreto_volumen_operativo = fields.Float(
        string="Volumen operativo",
        digits='Product Unit of Measure',
        help="Volumen real de producción (m³). Base del costo compensado.",
    )
    biocreto_costo_compensado = fields.Float(
        string="Costo compensado",
        compute='_compute_biocreto_costo_compensado',
        store=True,
        digits='Product Price',
        help="Precio efectivo por m³ entregado. "
             "Fase 1: usa el volumen operativo planeado. "
             "biocreto_fabricacion extenderá este compute para usar el "
             "producido real cuando la OF esté terminada.",
    )

    @api.depends('price_unit', 'product_uom_qty', 'biocreto_volumen_operativo')
    def _compute_biocreto_costo_compensado(self):
        for line in self:
            divisor = line.biocreto_volumen_operativo
            line.biocreto_costo_compensado = (
                (line.price_unit * line.product_uom_qty) / divisor
            ) if divisor else 0.0

    # ─────────────────────────────────────────────────────────────────
    # Boom (Lista de materiales nativa de mrp). Se asigna desde Laboratorio.
    # El domain por producto se aplica en la vista (reacciona a product_id).
    # ─────────────────────────────────────────────────────────────────
    bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        string="Diseño de mezcla",
        help="Diseño de mezcla (lista de materiales nativa). "
             "Se asigna en Laboratorio cuando la orden pasa al estado Programado.",
    )

    # ─────────────────────────────────────────────────────────────────
    # Tipo de colocación (sólo Concreto). Sección "Especificaciones de envío".
    # ─────────────────────────────────────────────────────────────────
    biocreto_tipo_colocacion = fields.Selection(
        selection=[
            ('directo', 'Directo'),
            ('pluma', 'Pluma'),
        ],
        string="Tipo de colocación",
    )

    # ─────────────────────────────────────────────────────────────────
    # Dominios dinámicos para Vehículo y Boom.
    #
    # Patrón canónico Odoo 19 para domains que dependen de otros campos:
    # un Binary computed sirve como contenedor del domain y la vista
    # lo referencia por nombre (domain="<field_name>"). Verificado en
    # account/models/account_tax.py:4952 (tag_ids_domain) y
    # account_intrastat/views (intrastat_code_domain).
    #
    # ¿Por qué Binary y no Char/escribir el domain como lista?
    # El widget many2one lee el campo como list-of-tuples directamente,
    # sin pasar por safe_eval del string XML. Esto permite:
    #   - usar identificadores Python normales (no hay que serializar)
    #   - retornar [] cuando no hay filtro (= mostrar todos)
    #   - retornar [('id','in',[])] para "ninguno" si fuera necesario
    # ─────────────────────────────────────────────────────────────────
    biocreto_vehiculo_domain = fields.Binary(
        compute='_compute_biocreto_vehiculo_domain',
        help="Domain dinámico para biocreto_vehiculo_id: filtra por la "
             "categoría de Bomba parametrizada en la Compañía. Si la Compañía "
             "no tiene categoría configurada, retorna [] (muestra todos).",
    )
    biocreto_bom_domain = fields.Binary(
        compute='_compute_biocreto_bom_domain',
        help="Domain dinámico para bom_id: BoMs del producto de la línea. "
             "Si no hay producto seleccionado, retorna [] (muestra todas).",
    )

    @api.depends('company_id', 'company_id.biocreto_bomba_categ_id')
    def _compute_biocreto_vehiculo_domain(self):
        for line in self:
            categ = line.company_id.biocreto_bomba_categ_id
            line.biocreto_vehiculo_domain = (
                [('category_id', '=', categ.id)] if categ else []
            )

    @api.depends('product_id', 'product_id.product_tmpl_id')
    def _compute_biocreto_bom_domain(self):
        for line in self:
            tmpl = line.product_id.product_tmpl_id
            line.biocreto_bom_domain = (
                [('product_tmpl_id', '=', tmpl.id)] if tmpl else []
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
