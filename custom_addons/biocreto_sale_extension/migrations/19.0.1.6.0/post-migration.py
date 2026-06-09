"""Migración v19.0.1.5.x → v19.0.1.6.0

Parsea los valores del Char `biocreto_coordenadas` ("lat, lng") y los vuelca
a los dos Float nuevos (`biocreto_latitud`, `biocreto_longitud`). Luego
elimina la columna Char y limpia su registro en `ir_model_fields`.

Post-migration (no pre): en este punto los Float ya existen como columnas
(Odoo los creó al cargar el modelo nuevo) y la columna Char todavía vive
en la BD esperando ser leída antes de su drop.

Esta migración es idempotente: si la columna Char ya no existe (porque la
migración ya corrió en una upgrade previa, o porque la BD es nueva), no
hace nada y termina sin error.
"""

import logging

_logger = logging.getLogger(__name__)


def _parse_coords(text):
    """Parsea "lat, lng" (con o sin espacios) a (float, float).

    Devuelve (None, None) si:
      - El texto está vacío.
      - No hay exactamente una coma separadora.
      - alguno de los dos lados no es un float válido.
      - alguno está fuera de rango (lat -90..90, lng -180..180).
    """
    if not text:
        return None, None
    cleaned = text.replace(" ", "")
    parts = cleaned.split(",")
    if len(parts) != 2:
        return None, None
    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except ValueError:
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


def migrate(cr, version):
    # En install desde cero (no upgrade) version es None — nada que migrar.
    if not version:
        return

    # 1) ¿Existe aún la columna Char vieja?
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sale_order'
          AND column_name = 'biocreto_coordenadas'
    """)
    if not cr.fetchone():
        _logger.info(
            "[biocreto v6.0.0] columna sale_order.biocreto_coordenadas "
            "ya no existe; nada que migrar."
        )
        return

    # 2) Leer todos los valores con texto no vacío.
    cr.execute("""
        SELECT id, biocreto_coordenadas
        FROM sale_order
        WHERE biocreto_coordenadas IS NOT NULL
          AND biocreto_coordenadas <> ''
    """)
    filas = cr.fetchall()
    migrados, fallidos, sin_parsear = 0, 0, []
    for rec_id, texto in filas:
        lat, lng = _parse_coords(texto)
        if lat is None:
            fallidos += 1
            sin_parsear.append((rec_id, texto))
            continue
        cr.execute(
            "UPDATE sale_order "
            "SET biocreto_latitud = %s, biocreto_longitud = %s "
            "WHERE id = %s",
            (lat, lng, rec_id),
        )
        migrados += 1

    _logger.info(
        "[biocreto v6.0.0] Migración coordenadas: %s registros migrados, "
        "%s fallidos (texto no parseable / fuera de rango).",
        migrados, fallidos,
    )
    for rec_id, texto in sin_parsear:
        _logger.warning(
            "[biocreto v6.0.0] sale_order %s: coords no parseables %r — "
            "revisar manualmente y rellenar biocreto_latitud/longitud.",
            rec_id, texto,
        )

    # 3) Eliminar la columna Char y su definición ORM colgante.
    cr.execute("ALTER TABLE sale_order DROP COLUMN IF EXISTS biocreto_coordenadas")
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'sale.order' AND name = 'biocreto_coordenadas'
    """)
    _logger.info(
        "[biocreto v6.0.0] Columna biocreto_coordenadas eliminada y "
        "ir_model_fields limpiado."
    )
