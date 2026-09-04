from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    biocreto_fc_resistencia = fields.Integer(
        string="Resistencia f'c (kg/cm²)",
        help="Resistencia característica del concreto. Dato maestro leído por "
             "Ventas, Laboratorio y Fabricación. Ej.: 210, 175.",
    )
    biocreto_categ_es_fc = fields.Boolean(
        string="Categoría con f'c",
        compute='_compute_biocreto_categ_es_fc',
        help="Técnico. Verdadero cuando el producto pertenece a la categoría "
             "Concreto. Solo alimenta la visibilidad de la resistencia f'c en "
             "el formulario; no se almacena ni se lee desde ningún otro sitio.",
    )

    @api.depends('categ_id')
    def _compute_biocreto_categ_es_fc(self):
        # Referencia por xmlid: sobrevive a renombres y a recrear la base.
        # Cuando se quiera hacer flexible (varias categorías con f'c), este
        # compute se reemplaza por un booleano configurable en product.category,
        # sin tocar la vista.
        categoria = self.env.ref(
            'biocreto_base.product_category_concreto', raise_if_not_found=False)
        for producto in self:
            producto.biocreto_categ_es_fc = bool(
                categoria and producto.categ_id == categoria
            )
