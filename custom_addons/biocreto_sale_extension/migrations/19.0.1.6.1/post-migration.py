"""Migración v19.0.1.6.0 → v19.0.1.6.1

El compute de `biocreto_direccion_completa` cambió el ORDEN de los componentes
(antes "zona - calle", ahora "calle - zona"). Como el campo es store=True, los
valores guardados en BD reflejan el orden viejo hasta que alguien edite la
calle/distrito/etc y el compute se redispare por @api.depends.

Para refrescar TODOS los registros con el nuevo orden de inmediato, esta
post-migration fuerza el recompute. Es safe sobre BD vacías (recordset vacío
→ no-op).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['sale.order'].search([])
    if not orders:
        _logger.info("[biocreto v6.1.1] No hay sale.order — nada que recomputar.")
        return
    orders._compute_biocreto_direccion_completa()
    orders.flush_recordset(['biocreto_direccion_completa'])
    _logger.info(
        "[biocreto v6.1.1] biocreto_direccion_completa recomputado en "
        "%s sale.order.", len(orders),
    )
