"""Migración v19.0.1.2.3 → v19.0.1.3.0 — los pedidos en 'sent' vuelven a Cotización.

Desde esta versión el estado nativo 'sent' se muestra como "Preprogramado"
y solo se llega a él con el botón Preprogramar. Los pedidos que hoy están
en 'sent' llegaron por el envío por correo (`mark_so_as_sent`), no porque
tengan fecha reservada: se devuelven a Cotización con `action_draft()`,
que deja el cambio de estado en el chatter.

Salvaguarda: `action_draft` borra la firma de cotización (nativo,
sale/models/sale_order.py:1044-1051) y las firmas de contrato y jefe de
obra (override de este módulo). Un pedido que tenga alguna firma o una
transacción de pago NO se toca: se deja en 'sent' y se avisa en el log
para revisarlo a mano.

Idempotente: si no hay pedidos en 'sent', no hace nada.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _biocreto_bloqueos(order):
    """Lo que action_draft borraría o rompería en este pedido."""
    motivos = []
    if order.signature or order.signed_by or order.signed_on:
        motivos.append("firma de cotización")
    if order.biocreto_firma_contrato or order.biocreto_firma_contrato_por:
        motivos.append("firma de contrato")
    if order.biocreto_firma_jefe_obra or order.biocreto_firma_jefe_obra_por:
        motivos.append("firma de jefe de obra")
    if order.transaction_ids:
        motivos.append("transacciones de pago %s" % order.transaction_ids.mapped('reference'))
    return motivos


def migrate(cr, version):
    if not version:
        return

    # Idioma del administrador: el seguimiento del campo `state` guarda
    # las etiquetas en el idioma del entorno; sin él quedarían en inglés
    # ("Quotation") en el chatter.
    lang = api.Environment(cr, SUPERUSER_ID, {}).ref('base.user_admin').lang or 'en_US'
    env = api.Environment(cr, SUPERUSER_ID, {'lang': lang})
    # Todas las compañías: el superusuario sin allowed_company_ids no
    # filtra por compañía en search().
    pedidos = env['sale.order'].search([('state', '=', 'sent')])
    if not pedidos:
        _logger.info("BIOCRETO preprogramado: no hay pedidos en 'sent'; nada que migrar.")
        return

    bloqueados = env['sale.order']
    for order in pedidos:
        motivos = _biocreto_bloqueos(order)
        if motivos:
            bloqueados |= order
            _logger.warning(
                "BIOCRETO preprogramado: %s (compañía %s) NO se devuelve a "
                "Cotización porque tiene %s. Revisar a mano.",
                order.name, order.company_id.name, ", ".join(motivos),
            )

    a_migrar = pedidos - bloqueados
    if a_migrar:
        a_migrar.action_draft()
    _logger.info(
        "BIOCRETO preprogramado: %d pedido(s) devueltos de 'sent' a Cotización: %s. "
        "%d se dejaron en 'sent' por tener firma o pago.",
        len(a_migrar), a_migrar.mapped('name'), len(bloqueados),
    )
