from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ─────────────────────────────────────────────────────────────────
    # v19.0.1.6.0 — Activo vs. consumible (ENTREGAS DE MATERIAL)
    #
    # MUDADO desde product.category. El motivo: una misma categoria
    # mezcla las dos naturalezas. En "Utiles de oficina" conviven una
    # silla (activo) y un paquete de hojas (consumible), y con el flag en
    # la categoria no habia forma de distinguirlas.
    #
    # Va en product.template y NO en product.product: las variantes de un
    # mismo producto comparten naturaleza. Un casco no es activo en talla
    # M y consumible en talla L. product.product delega los campos de su
    # plantilla (_inherits = {'product.template': 'product_tmpl_id'}), asi
    # que `linea.product_id.biocreto_es_activo` lee el valor de la
    # plantilla sin necesidad de un related propio.
    #
    # Boolean sin default -> False -> consumible. Es el valor prudente:
    # un producto recien creado sale del inventario al entregarse, que es
    # el comportamiento que ya tenian todos los que no estaban en una
    # categoria marcada.
    # ─────────────────────────────────────────────────────────────────
    biocreto_es_activo = fields.Boolean(
        string="Es activo",
        help="Marcado: al entregarse va a la ubicación de activos del área y "
             "sigue contando en el inventario. Desmarcado: se trata como "
             "consumible y sale del inventario al entregarse.")
