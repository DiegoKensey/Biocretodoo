from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Categoría de fleet.vehicle (modelo 'fleet.vehicle.model.category')
    # usada para filtrar el Vehículo Asignado en líneas de Bombeo.
    # Verificado en fleet/models/fleet_vehicle.py: fleet.vehicle.category_id
    # apunta a 'fleet.vehicle.model.category'.
    biocreto_bomba_categ_id = fields.Many2one(
        comodel_name='fleet.vehicle.model.category',
        string="Categoría Bomba Telescópica",
        help="Categoría de la flota usada para filtrar el Vehículo Asignado "
             "en líneas de Bombeo. El usuario crea la categoría en Flota → "
             "Configuración → Categorías y la selecciona aquí.",
    )
