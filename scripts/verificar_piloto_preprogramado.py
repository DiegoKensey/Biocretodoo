# -*- coding: utf-8 -*-
"""Verificación PREVIA al despliegue de "Preprogramado" en BIOCRETO_PILOTO.

SOLO LECTURA. No escribe nada y termina con env.cr.rollback().
Se ejecuta dentro de `odoo shell`, que ya define `env`:

    cd /tmp
    sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d BIOCRETO_PILOTO \
        --no-http < /tmp/verificar_piloto_preprogramado.py

Imprime lo que hay que revisar antes de actualizar
biocreto_sale_contract_state (v19.0.1.3.0) y biocreto_sale_portal (v19.0.2.2.0).
"""
from datetime import timedelta

from odoo import fields

try:
    SO = env['sale.order'].sudo().with_context(active_test=False)  # noqa: F821 (env lo da odoo shell)
    hace_3_meses = fields.Datetime.now() - timedelta(days=90)

    print("\n=== 1. CORREO SALIENTE ===")
    servidores = env['ir.mail_server'].sudo().search([])  # noqa: F821
    print("  servidores ir.mail_server: %s" % [(s.name, s.smtp_host, s.active) for s in servidores] or 'NINGUNO')
    env.cr.execute("""
        SELECT mm.state, count(*)
          FROM mail_mail mm
          JOIN mail_message m ON m.id = mm.mail_message_id
         WHERE m.model = 'sale.order' AND mm.create_date >= %s
         GROUP BY mm.state ORDER BY 1""", [hace_3_meses])  # noqa: F821
    print("  mail.mail de sale.order (últimos 3 meses) por estado: %s" % env.cr.fetchall())  # noqa: F821

    print("\n=== 2. PEDIDOS POR ESTADO Y COMPAÑÍA ===")
    env.cr.execute("""
        SELECT c.name, so.state, count(*)
          FROM sale_order so JOIN res_company c ON c.id = so.company_id
         GROUP BY 1, 2 ORDER BY 1, 2""")  # noqa: F821
    for fila in env.cr.fetchall():  # noqa: F821
        print("  %-30s %-12s %s" % fila)

    print("\n=== 3. PEDIDOS EN 'sent' (la migración los devolverá a Cotización) ===")
    enviados = SO.search([('state', '=', 'sent')])
    if not enviados:
        print("  ninguno")
    for o in enviados:
        adjuntos = env['ir.attachment'].sudo().search_count(  # noqa: F821
            [('res_model', '=', 'sale.order'), ('res_id', '=', o.id)])
        bloquea = bool(o.signature or o.signed_by or o.signed_on or o.transaction_ids
                       or o.biocreto_firma_contrato or o.biocreto_firma_contrato_por
                       or o.biocreto_firma_jefe_obra or o.biocreto_firma_jefe_obra_por)
        print("  %s | cliente=%s | creado=%s | compañía=%s" % (o.name, o.partner_id.name, o.create_date, o.company_id.name))
        print("      firma cotización=%s (%s)  firma contrato=%s  firma JO=%s" % (
            bool(o.signature), o.signed_by or '-', bool(o.biocreto_firma_contrato), bool(o.biocreto_firma_jefe_obra)))
        print("      transacciones=%s  actividades=%s  adjuntos=%s  require_signature=%s  require_payment=%s" % (
            [(t.reference, t.state) for t in o.transaction_ids], len(o.activity_ids), adjuntos,
            o.require_signature, o.require_payment))
        print("      -> %s" % ("LA MIGRACIÓN LO DEJARÁ EN 'sent' (tiene firma o pago): revisar a mano"
                                if bloquea else "se devolverá a Cotización"))

    print("\n=== 4. USUARIOS DE VENTAS ===")
    for xid in ('sales_team.group_sale_salesman', 'sales_team.group_sale_manager'):
        g = env.ref(xid)  # noqa: F821
        internos = g.all_user_ids.filtered(lambda u: not u.share)
        print("  %s (%s): %s" % (g.full_name, len(internos), internos.mapped('login')))

    print("\n=== 5. VISTA DE STUDIO SOBRE LA FECHA DE VACEO ===")
    env.cr.execute("""
        SELECT v.id, v.name, v.active, v.arch_db->>'en_US'
          FROM ir_ui_view v
          JOIN ir_model_data imd ON imd.model = 'ir.ui.view' AND imd.res_id = v.id
         WHERE imd.module = 'studio_customization' AND v.model = 'sale.order'
           AND v.arch_db->>'en_US' LIKE '%%biocreto_fecha_vaceo%%'""")  # noqa: F821
    filas = env.cr.fetchall()  # noqa: F821
    if not filas:
        print("  ninguna")
    for vid, nombre, activa, arch in filas:
        print("  id=%s activa=%s nombre=%s\n%s" % (vid, activa, nombre, arch))

    print("\n=== 6. PAGOS ONLINE ===")
    prov = env['payment.provider'].sudo().search([('state', '!=', 'disabled')])  # noqa: F821
    print("  proveedores activos: %s" % ([(p.name, p.code, p.state) for p in prov] or 'NINGUNO'))
    print("  pedidos abiertos (draft/sent) con require_payment: %s" % SO.search_count(
        [('state', 'in', ('draft', 'sent')), ('require_payment', '=', True)]))

    print("\n=== 7. ACCIONES DEL MENÚ ACCIÓN ===")
    for xid in ('sale.model_sale_order_action_quotation_sent', 'sale.model_sale_order_send_mail'):
        a = env.ref(xid, raise_if_not_found=False)  # noqa: F821
        print("  %s: %s" % (xid, ("group_ids=%s" % a.group_ids.mapped('full_name')) if a else 'NO EXISTE'))

    print("\n=== 8. VERSIONES ===")
    for m in env['ir.module.module'].sudo().search([  # noqa: F821
            ('name', 'in', ['sale', 'biocreto_sale_contract_state', 'biocreto_sale_portal'])]):
        # latest_version = versión instalada en la BD; installed_version = la del
        # manifiesto en disco (nombres del ORM, al revés de lo intuitivo).
        print("  %-30s estado=%-10s en BD=%-12s en disco=%s" % (
            m.name, m.state, m.latest_version, m.installed_version))
finally:
    env.cr.rollback()  # noqa: F821
    print("\nROLLBACK OK — no se escribió nada.")
