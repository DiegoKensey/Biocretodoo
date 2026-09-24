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

    # ─────────────────────────────────────────────────────────────────
    # v19.0.2.0.0 — CARACTERISTICAS FISICAS (INVENTARIO DE ACTIVOS)
    #
    # Cinco `Char` opcionales que alimentan el formato BC-GL-FR-15. Se
    # guardan en la FICHA y no en la linea del conteo: son propiedades
    # del bien, no del recuento. La linea las lee por `related` readonly,
    # asi que corregir una marca mal escrita se hace una sola vez y se
    # refleja en todos los conteos, pasados y futuros.
    #
    # Van en product.template por el mismo motivo que `biocreto_es_activo`:
    # las variantes de un mismo producto comparten marca y modelo.
    #
    # `biocreto_color` y NO `color`: en product.template ya existe un
    # campo `color`, de tipo INTEGER y almacenado, que es el indice de
    # color de la vista kanban (base: _fields['color'] -> integer,
    # string='Color Index'). Declarar aqui un Char llamado `color`
    # SOBREESCRIBIRIA el nativo y rompería el kanban de productos. El
    # prefijo del proyecto no es aqui una convencion de estilo: es
    # obligatorio.
    # ─────────────────────────────────────────────────────────────────
    biocreto_marca = fields.Char(string="Marca")
    biocreto_modelo = fields.Char(string="Modelo")
    biocreto_serie = fields.Char(string="N° de serie")
    biocreto_color = fields.Char(
        string="Color",
        help="Color del bien, en texto libre. NO es el índice de color del "
             "kanban (ese es el campo nativo «Color Index», que se conserva "
             "intacto).")
    biocreto_dimensiones = fields.Char(
        string="Dimensiones",
        help="Largo × ancho × alto, en texto libre. Ejemplo: 4,00 × 2,40 × 3,00")
