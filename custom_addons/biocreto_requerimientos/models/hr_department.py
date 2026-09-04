from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    # ─────────────────────────────────────────────────────────────────
    # Ubicaciones destino de las entregas de material del area.
    #
    # El destino de un stock.move se resuelve SIEMPRE desde estos dos
    # campos. Esta prohibido buscarlo por nombre, por id fijo o por
    # xmlid: los nombres de las ubicaciones los escribe el usuario y no
    # hay xmlid para las que creo a mano (verificado: las 8 ubicaciones
    # bajo `Consumo/` y las 8 bajo `WH/Areas/` nacieron desde la UI y
    # no tienen ir.model.data).
    #
    # DOMINIOS — por que son distintos:
    #
    #   biocreto_ubicacion_activos -> [('usage', '=', 'internal')]
    #     Un activo entregado SIGUE contando en el inventario de la
    #     compania; solo cambia de ubicacion. Eso exige usage='internal'
    #     (es el unico usage que suma a qty_available junto con
    #     'transit'). Las 7 `WH/Areas/<Area>` ya son internal.
    #
    #   biocreto_ubicacion_consumo -> [('usage', '!=', 'view')]
    #     Un consumible SALE del inventario, asi que aqui vale cualquier
    #     usage que no sea 'view' ('customer', 'inventory', 'production'
    #     o incluso 'internal' si la planta quiere seguir controlandolo).
    #     Lo que NO se puede es 'view': stock/models/stock_quant.py:608
    #     lanza ValidationError -- "You cannot take products from or
    #     deliver products to a location of type view". Por eso el
    #     dominio excluye 'view' en vez de fijar un usage concreto.
    #
    # check_company=True: las ubicaciones de la planta A no deben poder
    # asignarse a un departamento de la planta B.
    # ─────────────────────────────────────────────────────────────────
    biocreto_ubicacion_activos = fields.Many2one(
        'stock.location', string="Ubicación de activos",
        domain="[('usage', '=', 'internal')]", check_company=True,
        help="Destino de los productos cuya categoría está marcada como "
             "«Es activo». Siguen contando en el inventario de la compañía: "
             "solo cambian de ubicación.")
    biocreto_ubicacion_consumo = fields.Many2one(
        'stock.location', string="Ubicación de consumo", check_company=True,
        domain="[('usage', '!=', 'view')]",
        help="Destino de los productos consumibles (categoría sin «Es activo»). "
             "Salen del inventario al entregarse. No puede ser una ubicación de "
             "tipo «Vista»: Odoo prohíbe mover existencias hacia ellas.")
