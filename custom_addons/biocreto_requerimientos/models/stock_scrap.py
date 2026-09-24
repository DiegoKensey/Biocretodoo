from odoo import fields, models


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    # ─────────────────────────────────────────────────────────────────
    # v19.0.3.0.0 — DE QUE LINEA DE CONTEO NACIO ESTA BAJA
    #
    # UNA sola clave ajena para las DOS direcciones de navegacion:
    #   · desde el desecho  -> este Many2one;
    #   · desde la linea    -> `biocreto_scrap_ids`, el One2many inverso.
    #
    # La alternativa era un Many2one en la linea del conteo, pero
    # entonces volver desde el desecho habria exigido un SEGUNDO campo
    # aqui, y dos claves para la misma relacion acaban divergiendo el dia
    # que alguien escriba una y no la otra.
    #
    # Apunta a la LINEA y no al conteo a proposito: una baja nace de un
    # producto concreto, y desde el desecho interesa saber de que
    # material y con que especificaciones se dio de baja, no solo de que
    # documento. El conteo se alcanza igual, por `.conteo_id`.
    #
    # `ondelete='set null'`: si algun dia se borra un conteo en borrador,
    # el desecho SOBREVIVE. Una baja de inventario ya movio stock real y
    # no puede desaparecer porque se borre el papel que la origino.
    #
    # `copy=False`: duplicar un desecho no duplica su origen.
    # ─────────────────────────────────────────────────────────────────
    biocreto_conteo_linea_id = fields.Many2one(
        'biocreto.inventario.conteo.linea', string="Línea del conteo",
        ondelete='set null', copy=False, index='btree_not_null')
    biocreto_conteo_id = fields.Many2one(
        'biocreto.inventario.conteo', string="Conteo de activos",
        related='biocreto_conteo_linea_id.conteo_id', store=True, readonly=True,
        help="Conteo de inventario de activos que generó esta baja.")
