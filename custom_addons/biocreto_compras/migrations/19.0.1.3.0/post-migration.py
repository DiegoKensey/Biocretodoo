"""Migration 19.0.1.3.0 — sincronizar el JSONB `es_PE` de las traducciones del
Selection `purchase.order.state` con los labels Python definidos en
biocreto_compras.

Contexto (diagnostico 2026-07-01):
    En v19 las traducciones de Selection labels viven en el JSONB del campo
    `name` de `ir.model.fields.selection`. Cuando redefinimos state con
    selection=[('sent','Cotización enviada'),...] en biocreto_compras, Odoo
    actualiza el `en_US` del JSONB al valor Python pero NO toca las demas
    entradas del JSONB (incluida `es_PE`). Por eso el JSONB del registro `sent`
    quedaba `{'en_US':'Cotización enviada', 'es_PE':'Solicitud de cotización enviada'}`
    — el es_PE se hereda del `purchase/i18n/es_PE.po` original que traducia
    el label EN nativo (`RFQ Sent` → `Solicitud de cotización enviada`).

Solucion:
    UPDATE directo del JSONB por `value` del selection, forzando que la clave
    `es_PE` coincida con el label Python. Se hace en post-migration para que
    corra en cada `-u` (a diferencia del post_init_hook que solo corre al
    install fresco).

Idempotente: correr varias veces produce el mismo estado final.
"""

# Mapping: value en el selection → label Python actual (biocreto_compras/models/purchase_order.py:29-44)
_LABELS_ES_PE = {
    'draft':      'Solicitud de cotización',
    'sent':       'Cotización enviada',
    'registro':   'Registro',
    'to approve': 'Por aprobar',
    'purchase':   'Orden de Compra',
    'cancel':     'Cancelado',
}


def migrate(cr, version):
    """Sincroniza el JSONB `es_PE` del selection state a los labels Python."""
    for value, label in _LABELS_ES_PE.items():
        cr.execute(
            """
            UPDATE ir_model_fields_selection
               SET name = jsonb_set(name, '{es_PE}', to_jsonb(%s::text))
             WHERE value = %s
               AND field_id IN (
                     SELECT id FROM ir_model_fields
                      WHERE model = 'purchase.order' AND name = 'state'
                   )
            """,
            (label, value),
        )
