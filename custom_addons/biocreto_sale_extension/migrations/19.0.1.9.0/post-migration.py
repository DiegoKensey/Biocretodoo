"""Migración v19.0.1.8.0 → v19.0.1.9.0 — el bombeo deja el catálogo.

En v19.0.1.8.0 el slump de bombeo apuntaba a un catálogo compartido
(`biocreto.slump.rango`). Ese diseño se descartó por un defecto real y
observado: un registro de catálogo es COMPARTIDO, así que editarlo cambia
retroactivamente TODAS las líneas que lo referencian — facturas emitidas
incluidas. Se comprobó en pruebas: editar un registro de `6"` a `7" - 8"`
alteró de golpe ocho líneas ya facturadas.

    biocreto_slump_bombeable_id (M2o catálogo)
        -> biocreto_slump_bombeable_line_id (M2o a la línea de CONCRETO
           de la misma orden)

Este script solo actúa en bases que pasaron por 19.0.1.8.0 con catálogo.
En una base que venga de 19.0.1.7.x, la migración de 1.8.0 ya deja el
campo nuevo puesto y aquí no hay ni columna ni tabla que tratar: no-op.

Idempotente y conservador: si algo no casa, deja la columna vieja y la
tabla del catálogo en su sitio para poder reintentar.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_TABLA_INFORME = 'biocreto_slump_migracion_19_0_1_9_0'
_TOL = 0.001
_UMBRAL_FALLO = 0.20


def _existe_columna(cr, tabla, columna):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (tabla, columna))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    if not _existe_columna(cr, 'sale_order_line', 'biocreto_slump_bombeable_id'):
        _logger.info(
            "BIOCRETO slump: no hay columna de catálogo; nada que convertir."
        )
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Linea = env['sale.order.line']

    cr.execute("DROP TABLE IF EXISTS %s" % _TABLA_INFORME)
    cr.execute("""
        CREATE TABLE %s (
            bomb_line_id integer,
            order_id     integer,
            order_name   varchar,
            order_state  varchar,
            cat_id       integer,
            cat_min      numeric,
            cat_max      numeric,
            conc_line_id integer,
            conc_rango   varchar,
            candidatos   integer,
            resultado    varchar
        )
    """ % _TABLA_INFORME)

    # ═════════════════════════════════════════════════════════════════
    # Fuente del valor a emparejar. El ORDEN IMPORTA:
    #
    #   1º  `bombeable_viejo` del respaldo de 19.0.1.8.0 — el Float
    #       ORIGINAL de la línea, anterior a cualquier catálogo.
    #   2º  el rango del registro de catálogo, solo para líneas creadas
    #       DESPUÉS de 1.8.0 (no tienen fila de respaldo).
    #
    # Por qué el respaldo manda: el registro de catálogo es compartido y
    # EDITABLE. Si alguien lo cambió (caso observado en pruebas: un
    # registro pasó de `6"` a `7" - 8"`), su rango ya no representa lo que
    # la línea decía originalmente, y emparejar por él asignaría mal —o
    # no asignaría— ocho líneas. El respaldo es inmutable y es la única
    # fuente fiable del dato original.
    # ═════════════════════════════════════════════════════════════════
    hay_respaldo = bool(cr.execute(
        "SELECT to_regclass('biocreto_slump_backup_19_0_1_8_0')"
    ) or cr.fetchone()[0])

    if hay_respaldo:
        cr.execute("""
            SELECT l.id, l.order_id, so.name, so.state, r.id,
                   COALESCE(b.bombeable_viejo, r.slump_min) AS vmin,
                   COALESCE(b.bombeable_viejo, r.slump_max) AS vmax
              FROM sale_order_line l
              JOIN sale_order so ON so.id = l.order_id
              JOIN biocreto_slump_rango r ON r.id = l.biocreto_slump_bombeable_id
              LEFT JOIN biocreto_slump_backup_19_0_1_8_0 b
                     ON b.line_id = l.id AND b.bombeable_viejo <> 0
             WHERE l.biocreto_slump_bombeable_id IS NOT NULL
             ORDER BY l.id
        """)
    else:
        cr.execute("""
            SELECT l.id, l.order_id, so.name, so.state,
                   r.id, r.slump_min, r.slump_max
              FROM sale_order_line l
              JOIN sale_order so ON so.id = l.order_id
              JOIN biocreto_slump_rango r ON r.id = l.biocreto_slump_bombeable_id
             WHERE l.biocreto_slump_bombeable_id IS NOT NULL
             ORDER BY l.id
        """)
    bombeos = cr.fetchall()

    univocas = ambiguas = sin_match = 0
    for bomb_id, order_id, order_name, order_state, cat_id, cmin, cmax in bombeos:
        cr.execute("""
            SELECT c.id, c.biocreto_slump_rango
              FROM sale_order_line c
             WHERE c.order_id = %s
               AND c.id <> %s
               AND c.biocreto_slump_min IS NOT NULL
               AND c.biocreto_slump_min <> 0
               AND abs(c.biocreto_slump_min - %s) < %s
               AND abs(c.biocreto_slump_max - %s) < %s
             ORDER BY c.sequence, c.id
        """, (order_id, bomb_id, cmin, _TOL, cmax, _TOL))
        candidatas = cr.fetchall()

        if len(candidatas) == 1:
            elegida, rango = candidatas[0]
            resultado = 'univoca'
            univocas += 1
        elif len(candidatas) > 1:
            elegida, rango = candidatas[0]
            resultado = 'AMBIGUA'
            ambiguas += 1
            _logger.warning(
                "BIOCRETO slump: bombeo %s (orden %s) casa con %d líneas de "
                "concreto. Se apunta a la primera por sequence (id=%s). "
                "REVISAR MANUALMENTE.",
                bomb_id, order_name, len(candidatas), elegida,
            )
        else:
            elegida, rango = None, None
            resultado = 'SIN MATCH'
            sin_match += 1
            _logger.warning(
                "BIOCRETO slump: bombeo %s (orden %s) referenciaba el rango "
                "de catálogo %s (%s-%s) y ninguna línea de concreto de esa "
                "orden coincide. Se deja vacío; asígnelo a mano.",
                bomb_id, order_name, cat_id, cmin, cmax,
            )

        cr.execute(
            "INSERT INTO %s VALUES (%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s)"
            % _TABLA_INFORME,
            (bomb_id, order_id, order_name, order_state, cat_id, cmin, cmax,
             elegida, rango, len(candidatas), resultado),
        )
        if elegida:
            Linea.browse(bomb_id).write({
                'biocreto_slump_bombeable_line_id': elegida,
            })
    env.flush_all()

    total = len(bombeos)
    fallidas = ambiguas + sin_match
    _logger.info(
        "BIOCRETO slump: catálogo -> línea: %d unívocas, %d ambiguas, "
        "%d sin match (de %d). Detalle en %s.",
        univocas, ambiguas, sin_match, total, _TABLA_INFORME,
    )
    if total and (fallidas / float(total)) > _UMBRAL_FALLO:
        _logger.error(
            "BIOCRETO slump: %.0f%% del bombeo no se pudo convertir de forma "
            "unívoca (umbral %.0f%%). NO se elimina la columna de catálogo ni "
            "la tabla. Revise %s y relance el upgrade.",
            100.0 * fallidas / total, 100.0 * _UMBRAL_FALLO, _TABLA_INFORME,
        )
        return

    # ── Limpieza: fuera la columna del catálogo y el catálogo entero ──
    cr.execute(
        "ALTER TABLE sale_order_line DROP COLUMN IF EXISTS "
        "biocreto_slump_bombeable_id"
    )
    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model = 'sale.order.line' AND name = 'biocreto_slump_bombeable_id'
    """)
    cr.execute("DROP TABLE IF EXISTS biocreto_slump_rango CASCADE")
    cr.execute("DELETE FROM ir_model_fields WHERE model = 'biocreto.slump.rango'")
    cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.model' "
               "AND res_id IN (SELECT id FROM ir_model "
               "               WHERE model = 'biocreto.slump.rango')")
    cr.execute("DELETE FROM ir_model WHERE model = 'biocreto.slump.rango'")

    _logger.info(
        "BIOCRETO slump: conversión COMPLETA. Catálogo biocreto.slump.rango "
        "eliminado; el bombeo referencia ahora la línea de concreto."
    )
