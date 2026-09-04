"""Migración v19.0.1.7.x → v19.0.1.8.0 — slump de valor único a RANGO.

    biocreto_slump           (Float) -> biocreto_slump_min / _max (Float)
    biocreto_slump_bombeable (Float) -> biocreto_slump_bombeable_line_id
                                        (M2o a la línea de CONCRETO de la
                                         misma orden)

POST y no pre: aquí los campos nuevos ya existen como columnas (Odoo las
creó al cargar el modelo nuevo) y las viejas TODAVÍA viven en la base —
Odoo nunca borra columnas huérfanas por su cuenta.

CRITERIO CENTRAL del concreto: cada valor viejo se vuelca a min == max.
El helper de formato imprime entonces `6"` y NO `6" - 6"`, así que un
documento ya emitido se reimprime igual. Hay líneas facturadas: es el
requisito que manda.

Se escribe por ORM y no por SQL a propósito: `biocreto_slump_rango` es un
computado ALMACENADO y solo el ORM dispara su recálculo. Un UPDATE crudo
dejaría la columna del rango vacía.

ABORTA los DROP (sin perder dato) si queda alguna línea sin migrar o si
más del 20% del bombeo queda sin emparejar. Reintentable.

Idempotente: si las columnas viejas ya no existen, no hace nada.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_TABLA_BACKUP = 'biocreto_slump_backup_19_0_1_8_0'
_TABLA_INFORME = 'biocreto_slump_migracion_19_0_1_8_0'

# Misma tolerancia que el helper de formato. No se importa para que la
# migración no dependa del código de la versión que la ejecuta.
_TOL = 0.001

# Umbral del Paso 5.3: por encima de esto la migración del bombeo se
# considera poco fiable y NO se borran las columnas viejas.
_UMBRAL_FALLO = 0.20


def _columnas_viejas(cr):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'sale_order_line'
           AND column_name IN ('biocreto_slump', 'biocreto_slump_bombeable')
    """)
    return {r[0] for r in cr.fetchall()}


def migrate(cr, version):
    if not version:
        return

    columnas = _columnas_viejas(cr)
    if not columnas:
        _logger.info(
            "BIOCRETO slump: columnas viejas ausentes; migración ya aplicada."
        )
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Linea = env['sale.order.line']

    # ═════════════════════════════════════════════════════════════════
    # 1. CONCRETO: biocreto_slump -> min = max = valor
    # ═════════════════════════════════════════════════════════════════
    migradas_concreto = 0
    if 'biocreto_slump' in columnas:
        cr.execute("""
            SELECT id, biocreto_slump FROM sale_order_line
             WHERE biocreto_slump IS NOT NULL AND biocreto_slump <> 0
             ORDER BY id
        """)
        for line_id, valor in cr.fetchall():
            # write por ORM -> recalcula biocreto_slump_rango (store=True).
            Linea.browse(line_id).write({
                'biocreto_slump_min': valor,
                'biocreto_slump_max': valor,
            })
            migradas_concreto += 1
        env.flush_all()
        _logger.info(
            "BIOCRETO slump: %d líneas de concreto migradas a min == max",
            migradas_concreto,
        )

    # ═════════════════════════════════════════════════════════════════
    # 2. BOMBEO: emparejar con la línea de concreto de LA MISMA orden
    #    cuyo slump coincida (con tolerancia, nunca `==`).
    # ═════════════════════════════════════════════════════════════════
    univocas = ambiguas = sin_match = sin_concreto = 0
    if 'biocreto_slump_bombeable' in columnas:
        cr.execute("DROP TABLE IF EXISTS %s" % _TABLA_INFORME)
        cr.execute("""
            CREATE TABLE %s (
                bomb_line_id  integer,
                order_id      integer,
                order_name    varchar,
                order_state   varchar,
                valor_viejo   numeric,
                conc_line_id  integer,
                conc_rango    varchar,
                candidatos    integer,
                resultado     varchar
            )
        """ % _TABLA_INFORME)

        cr.execute("""
            SELECT l.id, l.order_id, so.name, so.state, l.biocreto_slump_bombeable
              FROM sale_order_line l
              JOIN sale_order so ON so.id = l.order_id
             WHERE l.biocreto_slump_bombeable IS NOT NULL
               AND l.biocreto_slump_bombeable <> 0
             ORDER BY l.id
        """)
        bombeos = cr.fetchall()

        for bomb_id, order_id, order_name, order_state, valor in bombeos:
            # Candidatas: líneas de concreto de la MISMA orden con
            # min ≈ valor y max ≈ valor. Ordenadas por sequence para que
            # "la primera" sea determinista.
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
            """, (order_id, bomb_id, valor, _TOL, valor, _TOL))
            candidatas = cr.fetchall()

            # ¿La orden tiene alguna línea de concreto con slump?
            cr.execute("""
                SELECT count(*) FROM sale_order_line c
                 WHERE c.order_id = %s AND c.biocreto_slump_min IS NOT NULL
                   AND c.biocreto_slump_min <> 0
            """, (order_id,))
            hay_concreto = cr.fetchone()[0]

            if len(candidatas) == 1:
                elegida, rango = candidatas[0]
                resultado = 'univoca'
                univocas += 1
            elif len(candidatas) > 1:
                elegida, rango = candidatas[0]
                resultado = 'AMBIGUA'
                ambiguas += 1
                _logger.warning(
                    "BIOCRETO slump: línea de bombeo %s (orden %s) tiene %d "
                    "líneas de concreto con slump %s. Se apunta a la primera "
                    "por sequence (id=%s). REVISAR MANUALMENTE.",
                    bomb_id, order_name, len(candidatas), valor, elegida,
                )
            else:
                elegida, rango = None, None
                if hay_concreto:
                    resultado = 'SIN MATCH'
                    sin_match += 1
                    _logger.warning(
                        "BIOCRETO slump: línea de bombeo %s (orden %s) con "
                        "slump %s sin línea de concreto que coincida. Se deja "
                        "vacía.", bomb_id, order_name, valor,
                    )
                else:
                    resultado = 'SIN CONCRETO'
                    sin_concreto += 1
                    _logger.warning(
                        "BIOCRETO slump: la orden %s no tiene líneas de "
                        "concreto con slump; su bombeo (línea %s) queda vacío.",
                        order_name, bomb_id,
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

        total = len(bombeos)
        fallidas = sin_match + sin_concreto + ambiguas
        _logger.info(
            "BIOCRETO slump: bombeo -> %d unívocas, %d ambiguas, %d sin match, "
            "%d sin concreto (de %d). Detalle en la tabla %s.",
            univocas, ambiguas, sin_match, sin_concreto, total, _TABLA_INFORME,
        )
        if total and (fallidas / float(total)) > _UMBRAL_FALLO:
            _logger.error(
                "BIOCRETO slump: %.0f%% del bombeo quedó sin emparejar de "
                "forma unívoca (umbral %.0f%%). NO se eliminan las columnas "
                "viejas. Revise la tabla %s y relance el upgrade.",
                100.0 * fallidas / total, 100.0 * _UMBRAL_FALLO, _TABLA_INFORME,
            )
            return

    # ═════════════════════════════════════════════════════════════════
    # 3. VERIFICACIÓN del concreto. Nada se borra hasta el 100%.
    # ═════════════════════════════════════════════════════════════════
    problemas = []
    if 'biocreto_slump' in columnas:
        cr.execute("""
            SELECT count(*) FROM sale_order_line
             WHERE biocreto_slump IS NOT NULL AND biocreto_slump <> 0
               AND (biocreto_slump_min IS NULL OR biocreto_slump_min = 0
                 OR biocreto_slump_max IS NULL OR biocreto_slump_max = 0)
        """)
        n = cr.fetchone()[0]
        if n:
            problemas.append("%d línea(s) de concreto sin min/max" % n)
        cr.execute("""
            SELECT count(*) FROM sale_order_line
             WHERE biocreto_slump_min IS NOT NULL AND biocreto_slump_min <> 0
               AND (biocreto_slump_rango IS NULL OR biocreto_slump_rango = '')
        """)
        n = cr.fetchone()[0]
        if n:
            problemas.append("%d línea(s) sin biocreto_slump_rango" % n)

    if problemas:
        _logger.error(
            "BIOCRETO slump: MIGRACIÓN INCOMPLETA, no se eliminan las columnas "
            "viejas. Problemas: %s. Respaldo en %s.",
            "; ".join(problemas), _TABLA_BACKUP,
        )
        return

    # ═════════════════════════════════════════════════════════════════
    # 4. LIMPIEZA. Solo con verificación en verde.
    # ═════════════════════════════════════════════════════════════════
    for columna in ('biocreto_slump', 'biocreto_slump_bombeable'):
        if columna in columnas:
            cr.execute(
                "ALTER TABLE sale_order_line DROP COLUMN IF EXISTS %s" % columna
            )
            _logger.info("BIOCRETO slump: columna %s eliminada", columna)

    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model = 'sale.order.line'
           AND name IN ('biocreto_slump', 'biocreto_slump_bombeable')
    """)

    _logger.info(
        "BIOCRETO slump: migración COMPLETA. Concreto: %d líneas. "
        "Bombeo: %d unívocas de %d. Respaldo en %s.",
        migradas_concreto, univocas, univocas + ambiguas + sin_match + sin_concreto,
        _TABLA_BACKUP,
    )
