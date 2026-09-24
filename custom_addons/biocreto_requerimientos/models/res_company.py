from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ─────────────────────────────────────────────────────────────────
    # v19.0.3.0.0 — LA UBICACION DE DESECHO
    #
    # Adonde van los activos que un conteo da de baja.
    #
    # POR QUE UN CAMPO Y NO EL DEFECTO DE ODOO
    # ----------------------------------------
    # `stock.scrap` sabe elegir destino solo, pero elige mal para este
    # caso: `_compute_scrap_location_id` (odoo/addons/stock/models/
    # stock_scrap.py:87-98) toma la ubicacion de tipo `inventory` de
    # MENOR ID de la compania. En esta base eso es «Inventory
    # adjustment» (id 11), que es la contrapartida de los AJUSTES de
    # inventario. Dejar caer las bajas ahi las mezclaria con las
    # correcciones de stock y haria ilegible el historico de ajustes.
    # Ademas compiten por ese minimo las siete `Consumo/*`, que tambien
    # son `inventory`: el destino dependeria del orden de creacion.
    #
    # POR QUE EN LA COMPANIA Y NO EN EL ALMACEN
    # -----------------------------------------
    # La baja sale de una ubicacion de area, que NO pertenece a ningun
    # almacen (`Activo/Areas/...` vive fuera de `WH` desde el 22/09/2026).
    # Colgar el destino del almacen obligaria a resolver de que almacen
    # es un area que no tiene ninguno. La compania siempre existe, y es
    # el mismo criterio que usa el propio Odoo en su compute.
    #
    # `check_company=True` y dominio `inventory`: una ubicacion de
    # desecho de otra planta no debe poder elegirse, y una `internal`
    # seria un sitio donde el activo SEGUIRIA contando en inventario --
    # lo contrario de una baja.
    #
    # Sin `default`: es deliberado. Quien valide sin tenerla configurada
    # recibe un UserError que dice donde se configura
    # (`_biocreto_ubicacion_desecho`), en vez de una baja silenciosa en
    # la ubicacion equivocada. En Concepcion y Comuneros sera otra.
    # ─────────────────────────────────────────────────────────────────
    biocreto_ubicacion_desecho = fields.Many2one(
        'stock.location', string="Ubicación de desecho",
        domain="[('usage', '=', 'inventory')]", check_company=True,
        help="Destino de los activos que un conteo de inventario da de baja. "
             "Tiene que ser de tipo «Pérdida de inventario». Sin ella no se "
             "puede validar un conteo que tenga unidades en Malogrado.")
