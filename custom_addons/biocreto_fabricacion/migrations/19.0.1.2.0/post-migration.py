"""Migración v19.0.1.1.0 → v19.0.1.2.0 — recalcular los datos de guía.

`biocreto_datos_guia` es un computado ALMACENADO que incrusta el slump de
la línea de venta. En v19.0.1.8.0 de `biocreto_sale_extension` el slump
pasó de valor único a rango, y con él cambió el texto:

    antes:  "Slump: 6"        (Float formateado con %g)
    ahora:  "Slump: 6\""      (el computado biocreto_slump_rango)

Cambiar un `@api.depends` NO recalcula los registros existentes: Odoo solo
recalcula cuando alguna de las dependencias se escribe. Sin este script,
las guías ya generadas conservarían el texto viejo y convivirían dos
formatos distintos en el mismo sistema — el usuario vería "Slump: 6" en
un picking antiguo y "Slump: 6\"" en uno nuevo.

Se invalida el valor almacenado y se fuerza el recálculo por ORM. Nada
más: el resto del texto de la guía (placa, resistencia, huso, cantidad,
presinto, hora) se reconstruye idéntico a partir de las mismas fuentes.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Picking = env['stock.picking']

    pickings = Picking.search([('biocreto_datos_guia', '!=', False)])
    if not pickings:
        _logger.info(
            "BIOCRETO guia: no hay pickings con datos de guía; nada que hacer."
        )
        return

    campo = Picking._fields['biocreto_datos_guia']
    env.add_to_compute(campo, pickings)
    env.flush_all()

    _logger.info(
        "BIOCRETO guia: recalculados los datos de guía de %d picking(s) "
        "tras el cambio de slump a rango.", len(pickings),
    )
