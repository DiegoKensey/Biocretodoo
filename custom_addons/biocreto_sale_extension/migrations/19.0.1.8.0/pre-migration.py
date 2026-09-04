"""Migración v19.0.1.7.x → v19.0.1.8.0 — RESPALDO previo del slump.

El slump pasa de valor único a rango:
    biocreto_slump            (Float) -> biocreto_slump_min / _max (Float)
    biocreto_slump_bombeable  (Float) -> biocreto_slump_bombeable_id (M2o)

Este script NO migra nada. Solo levanta la red de seguridad ANTES de que
la post-migration toque un solo dato:

  1. Una TABLA de respaldo `biocreto_slump_backup_19_0_1_8_0` con el
     estado exacto de cada línea afectada. Sobrevive al upgrade y se
     puede consultar con SQL meses después.
  2. Un CSV en el `data_dir` de Odoo, por si hiciera falta el dato fuera
     de la base.

Por qué en PRE y no en POST: aquí las columnas viejas están garantizadas
intactas y nadie ha escrito todavía. En post-migration ya se habrían
creado las columnas nuevas y el margen de error es mayor.

Idempotente: si la tabla de respaldo ya existe (la migración ya corrió),
no la pisa — el primer respaldo es el bueno.
"""

import csv
import logging
import os

_logger = logging.getLogger(__name__)

_TABLA_BACKUP = 'biocreto_slump_backup_19_0_1_8_0'


def migrate(cr, version):
    if not version:
        # Instalación nueva, no upgrade: no hay nada que respaldar.
        return

    # ¿Existen todavía las columnas viejas? Si no, la migración ya corrió.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'sale_order_line'
           AND column_name IN ('biocreto_slump', 'biocreto_slump_bombeable')
    """)
    columnas = {r[0] for r in cr.fetchall()}
    if not columnas:
        _logger.info(
            "BIOCRETO slump: las columnas viejas ya no existen; "
            "nada que respaldar."
        )
        return

    cr.execute("SELECT to_regclass(%s)", (_TABLA_BACKUP,))
    if cr.fetchone()[0]:
        _logger.warning(
            "BIOCRETO slump: la tabla de respaldo %s YA existe; se conserva "
            "la original y no se sobrescribe.", _TABLA_BACKUP,
        )
        return

    # Respaldo completo: linea, orden, estado y los dos valores viejos.
    cr.execute("""
        CREATE TABLE %s AS
        SELECT l.id                        AS line_id,
               l.order_id                  AS order_id,
               so.name                     AS order_name,
               so.state                    AS order_state,
               l.qty_invoiced              AS qty_invoiced,
               l.product_id                AS product_id,
               l.biocreto_slump            AS slump_viejo,
               l.biocreto_slump_bombeable  AS bombeable_viejo,
               now()                       AS backup_date
          FROM sale_order_line l
          JOIN sale_order so ON so.id = l.order_id
         WHERE (l.biocreto_slump IS NOT NULL AND l.biocreto_slump <> 0)
            OR (l.biocreto_slump_bombeable IS NOT NULL
                AND l.biocreto_slump_bombeable <> 0)
    """ % _TABLA_BACKUP)

    cr.execute("SELECT count(*) FROM %s" % _TABLA_BACKUP)
    total = cr.fetchone()[0]
    _logger.info(
        "BIOCRETO slump: respaldadas %d líneas en la tabla %s",
        total, _TABLA_BACKUP,
    )

    # Copia adicional en CSV dentro del data_dir de Odoo. Un fallo aquí NO
    # aborta el upgrade: la tabla de respaldo ya es la red de seguridad
    # real, el CSV es una comodidad.
    try:
        from odoo.tools import config
        destino = os.path.join(
            config['data_dir'], 'biocreto_slump_backup_19_0_1_8_0.csv',
        )
        cr.execute("""
            SELECT line_id, order_id, order_name, order_state, qty_invoiced,
                   product_id, slump_viejo, bombeable_viejo
              FROM %s ORDER BY line_id
        """ % _TABLA_BACKUP)
        filas = cr.fetchall()
        with open(destino, 'w', newline='', encoding='utf-8') as fh:
            escritor = csv.writer(fh)
            escritor.writerow([
                'line_id', 'order_id', 'order_name', 'order_state',
                'qty_invoiced', 'product_id', 'slump_viejo', 'bombeable_viejo',
            ])
            escritor.writerows(filas)
        _logger.info("BIOCRETO slump: respaldo CSV escrito en %s", destino)
    except Exception as exc:  # noqa: BLE001 - el CSV es opcional
        _logger.warning(
            "BIOCRETO slump: no se pudo escribir el CSV de respaldo (%s). "
            "La tabla %s SÍ se creó, que es lo que importa.",
            exc, _TABLA_BACKUP,
        )
