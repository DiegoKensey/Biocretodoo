"""Migración v19.0.1.9.0 → v19.0.1.9.1 — reconstruir el bombeo desde el respaldo.

Red de seguridad para las líneas de bombeo que quedaron SIN referencia a
la línea de concreto. Cubre dos situaciones reales:

  a) El paso por el catálogo de 19.0.1.8.0. Cuando la conversión
     catálogo→línea de 19.0.1.9.0 abortó por el umbral del 20%, Odoo ya
     había eliminado la columna `biocreto_slump_bombeable_id` (el campo
     había desaparecido del modelo), así que la referencia se perdió.

  b) Una migración de 19.0.1.8.0 en la que el emparejamiento dejó líneas
     vacías y después se corrigió el slump del concreto.

En ambos casos la fuente de verdad es la MISMA y es inmutable: el valor
Float original guardado en `biocreto_slump_backup_19_0_1_8_0`. No se
recurre al catálogo, que es editable y ya demostró no ser fiable.

Solo TOCA líneas que estén vacías. Nunca pisa una referencia existente:
si alguien ya la asignó a mano, esa asignación manda.

Aprovecha para eliminar la tabla huérfana del catálogo, si sigue ahí.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_TABLA_BACKUP = 'biocreto_slump_backup_19_0_1_8_0'
_TABLA_INFORME = 'biocreto_slump_migracion_19_0_1_9_1'
_TOL = 0.001


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT to_regclass(%s)", (_TABLA_BACKUP,))
    if not cr.fetchone()[0]:
        _logger.info(
            "BIOCRETO slump: sin tabla de respaldo; nada que reconstruir."
        )
    else:
        env = api.Environment(cr, SUPERUSER_ID, {})
        Linea = env['sale.order.line']

        cr.execute("DROP TABLE IF EXISTS %s" % _TABLA_INFORME)
        cr.execute("""
            CREATE TABLE %s (
                bomb_line_id integer, order_id integer, order_name varchar,
                order_state varchar, valor_original numeric,
                conc_line_id integer, conc_rango varchar,
                candidatos integer, resultado varchar
            )
        """ % _TABLA_INFORME)

        # Solo líneas de bombeo SIN referencia y CON valor original.
        cr.execute("""
            SELECT l.id, l.order_id, so.name, so.state, b.bombeable_viejo
              FROM sale_order_line l
              JOIN sale_order so ON so.id = l.order_id
              JOIN %s b ON b.line_id = l.id
             WHERE b.bombeable_viejo IS NOT NULL AND b.bombeable_viejo <> 0
               AND l.biocreto_slump_bombeable_line_id IS NULL
             ORDER BY l.id
        """ % _TABLA_BACKUP)
        pendientes = cr.fetchall()

        univocas = ambiguas = sin_match = 0
        for bomb_id, order_id, order_name, order_state, valor in pendientes:
            cr.execute("""
                SELECT c.id, c.biocreto_slump_rango
                  FROM sale_order_line c
                 WHERE c.order_id = %s AND c.id <> %s
                   AND c.biocreto_slump_min IS NOT NULL
                   AND c.biocreto_slump_min <> 0
                   AND abs(c.biocreto_slump_min - %s) < %s
                   AND abs(c.biocreto_slump_max - %s) < %s
                 ORDER BY c.sequence, c.id
            """, (order_id, bomb_id, valor, _TOL, valor, _TOL))
            candidatas = cr.fetchall()

            if len(candidatas) == 1:
                elegida, rango = candidatas[0]
                resultado, univocas = 'univoca', univocas + 1
            elif len(candidatas) > 1:
                elegida, rango = candidatas[0]
                resultado, ambiguas = 'AMBIGUA', ambiguas + 1
                _logger.warning(
                    "BIOCRETO slump: bombeo %s (orden %s) casa con %d líneas "
                    "de concreto con slump %s. Se apunta a la primera por "
                    "sequence (id=%s). REVISAR MANUALMENTE.",
                    bomb_id, order_name, len(candidatas), valor, elegida,
                )
            else:
                elegida, rango = None, None
                resultado, sin_match = 'SIN MATCH', sin_match + 1
                _logger.warning(
                    "BIOCRETO slump: bombeo %s (orden %s) con valor original "
                    "%s sin línea de concreto que coincida. Queda vacío.",
                    bomb_id, order_name, valor,
                )

            cr.execute(
                "INSERT INTO %s VALUES (%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s)"
                % _TABLA_INFORME,
                (bomb_id, order_id, order_name, order_state, valor,
                 elegida, rango, len(candidatas), resultado),
            )
            if elegida:
                Linea.browse(bomb_id).write({
                    'biocreto_slump_bombeable_line_id': elegida,
                })
        env.flush_all()

        _logger.info(
            "BIOCRETO slump: reconstrucción desde respaldo -> %d unívocas, "
            "%d ambiguas, %d sin match (de %d pendientes). Detalle en %s.",
            univocas, ambiguas, sin_match, len(pendientes), _TABLA_INFORME,
        )

    # Tabla huérfana del catálogo descartado. El modelo ya no existe en el
    # código, así que la tabla no la usa nadie.
    cr.execute("SELECT to_regclass('biocreto_slump_rango')")
    if cr.fetchone()[0]:
        cr.execute("DROP TABLE IF EXISTS biocreto_slump_rango CASCADE")
        cr.execute("DELETE FROM ir_model_fields WHERE model = 'biocreto.slump.rango'")
        cr.execute("DELETE FROM ir_model WHERE model = 'biocreto.slump.rango'")
        _logger.info(
            "BIOCRETO slump: tabla huérfana biocreto_slump_rango eliminada."
        )
