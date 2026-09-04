"""Migración v19.0.1.9.1 → v19.0.1.9.2 — un solo campo de bombeable.

Elimina `biocreto_slump_bombeable_rango`, el Char relacionado y
almacenado que acompañaba a `biocreto_slump_bombeable_line_id`.

Decisión de diseño: UN SOLO campo de bombeable en el modelo y uno solo en
el formulario. El rango se lee siempre a través de la relación:

    line.biocreto_slump_bombeable_line_id.biocreto_slump_rango

Consecuencia asumida: el bombeable deja de poder agruparse por rango en
tablas dinámicas (agruparía por línea). El concreto conserva esa
capacidad vía `biocreto_slump_rango`, que sigue almacenado.

NO se pierde ningún dato: el campo era `related`, es decir, un espejo. El
original vive en la línea de concreto referenciada y sigue intacto. Las
referencias `biocreto_slump_bombeable_line_id` no se tocan.

Idempotente: si la columna ya no existe, no hace nada.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'sale_order_line'
           AND column_name = 'biocreto_slump_bombeable_rango'
    """)
    if not cr.fetchone():
        _logger.info(
            "BIOCRETO slump: la columna del related ya no existe; nada que hacer."
        )
        return

    # Comprobación previa: que ninguna línea dependa SOLO del espejo. Si
    # una tiene rango espejado pero no referencia, perderíamos el dato al
    # borrar la columna, así que se avisa y NO se borra.
    cr.execute("""
        SELECT count(*) FROM sale_order_line
         WHERE biocreto_slump_bombeable_rango IS NOT NULL
           AND biocreto_slump_bombeable_rango <> ''
           AND biocreto_slump_bombeable_line_id IS NULL
    """)
    huerfanas = cr.fetchone()[0]
    if huerfanas:
        _logger.error(
            "BIOCRETO slump: %d línea(s) tienen rango de bombeo espejado pero "
            "NINGUNA referencia a línea de concreto. Borrar la columna "
            "perdería ese dato. NO se elimina. Revise:\n"
            "  SELECT id, order_id, biocreto_slump_bombeable_rango\n"
            "    FROM sale_order_line\n"
            "   WHERE biocreto_slump_bombeable_rango <> ''\n"
            "     AND biocreto_slump_bombeable_line_id IS NULL;",
            huerfanas,
        )
        return

    cr.execute(
        "ALTER TABLE sale_order_line "
        "DROP COLUMN IF EXISTS biocreto_slump_bombeable_rango"
    )
    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model = 'sale.order.line'
           AND name = 'biocreto_slump_bombeable_rango'
    """)
    _logger.info(
        "BIOCRETO slump: columna biocreto_slump_bombeable_rango eliminada. "
        "El bombeable queda con un único campo."
    )
