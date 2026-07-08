from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # ─────────────────────────────────────────────────────────────────
    # v19.0.2.0.0 (Lote 2): main attachment.
    #
    # No podemos heredar 'mail.thread.main.attachment' desde una extension
    # in-place de purchase.order (que ya hereda 'mail.thread') porque el MRO
    # queda inconsistente:
    #   Cannot create a consistent method resolution order (MRO) for bases
    #   BaseModel, base, mail.thread, mail.activity.mixin,
    #   account.document.import.mixin, mail.thread.main.attachment
    # (mail.thread.main.attachment tambien hereda mail.thread → doble camino).
    #
    # Solucion: portar los artefactos criticos del mixin
    # (mail/models/mail_thread_main_attachment.py) DIRECTAMENTE:
    #   1. Field `message_main_attachment_id` — el AttachmentView JS
    #      (mail/static/src/core/common/attachment_view.js) lo lee para
    #      decidir cual PDF/imagen renderizar en el preview lateral.
    #   2. `_message_set_main_attachment_id` — llamado desde subir_cotizacion.
    #   3. `_thread_to_store` override — CRITICO: expone el campo al store
    #      del mail. Sin esto, el JS no recibe el main attachment aunque
    #      el registro lo tenga.
    #
    # NO portamos `_message_post_after_hook` porque el flujo BIOCRETO no
    # necesita fijar el main desde message_post — subir_cotizacion es el
    # unico punto de entrada.
    # ─────────────────────────────────────────────────────────────────
    message_main_attachment_id = fields.Many2one(
        string="Main Attachment",
        comodel_name='ir.attachment',
        copy=False,
        index='btree_not_null',
    )

    def _message_set_main_attachment_id(self, attachments, force=False, filter_xml=True):
        """Portado 1:1 de mail_thread_main_attachment.py:27-50."""
        if attachments and (force or not self.message_main_attachment_id):
            if filter_xml:
                attachments = attachments.filtered(
                    lambda r: not r.mimetype.endswith('xml')
                    and not r.mimetype.endswith('application/octet-stream')
                )
            if attachments:
                self.with_context(tracking_disable=True).message_main_attachment_id = max(
                    attachments,
                    key=lambda r: (r.mimetype.endswith('pdf'), r.mimetype.startswith('image')),
                ).id

    def _thread_to_store(self, store, fields, *, request_list=None):
        """Portado de mail_thread_main_attachment.py:52-59: expone el campo al
        store JS. Sin este override el AttachmentView no sabe que hay un main."""
        super()._thread_to_store(store, fields, request_list=request_list)
        if request_list and "attachments" in request_list:
            from odoo.addons.mail.tools.discuss import Store
            store.add(
                self,
                Store.One("message_main_attachment_id", []),
                as_thread=True,
            )

    # ─────────────────────────────────────────────────────────────────
    # v19.0.1.1.0: redefinicion COMPLETA de la lista `selection` (no
    # selection_add) por dos motivos:
    #   1. El statusbar renderiza los estados en el orden de la lista;
    #      selection_add SIEMPRE agrega al final → 'registro' aparecia
    #      despues de 'Orden de Compra'. La unica forma de reordenar
    #      es redefinir la lista entera.
    #   2. Traduccion al espanol de las etiquetas de los 6 estados.
    #
    # Kwargs nativos preservados verbatim (purchase/models/purchase_order.py:105-111):
    #   string='Status', readonly=True, index=True, copy=False,
    #   default='draft', tracking=True.
    #
    # Sin ondelete: al redefinir con selection= (no selection_add), el
    # parametro ondelete no aplica. Trade-off aceptable: si algun dia se
    # desinstala biocreto_compras, registros con state='registro' quedan
    # fuera de la definicion nativa. En la practica, este modulo no se
    # desinstala una vez desplegado.
    #
    # Grep verificado (2026-07-01): ningun otro modulo enterprise o custom
    # hace selection_add sobre purchase.order.state → redefinicion segura.
    # ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Solicitud de cotización'),
            ('sent', 'Cotización enviada'),
            ('registro', 'Registro'),
            ('to approve', 'Por aprobar'),
            ('purchase', 'Orden de Compra'),
            ('cancel', 'Cancelado'),
        ],
        string='Status',
        readonly=True,
        index=True,
        copy=False,
        default='draft',
        tracking=True,
    )

    # ─────────────────────────────────────────────────────────────────
    # Redefinicion del dominio de alternative_po_ids (viene de purchase_requisition,
    # models/purchase.py:30-34). Solo cambia el domain: se mantiene el related
    # sobre purchase_group_id.order_ids, el string, check_company y help.
    # Se AGREGA 'registro' y se QUITA 'to approve': la comparacion de alternativas
    # ahora vive en la fase de trabajo (registro), no en la aprobacion.
    # ─────────────────────────────────────────────────────────────────
    alternative_po_ids = fields.One2many(
        'purchase.order', related='purchase_group_id.order_ids', readonly=False,
        domain="[('id', '!=', id), ('state', 'in', ['draft', 'sent', 'registro'])]",
        string="Alternative POs", check_company=True,
        help="Other potential purchase orders for purchasing products",
    )

    # ─────────────────────────────────────────────────────────────────
    # Numeracion BIOCRETO: CP-AAAA-PLANTA-NNNN
    # Patron replicado 1:1 de biocreto_sale_extension (ir.sequence por compania
    # con use_date_range=True para reset anual). Diferencia con sale: NO se
    # incluyen las iniciales del vendedor, se antepone el prefijo literal 'CP-'.
    # Si la compania no tiene plant_code, se deja que Odoo asigne el name nativo
    # (defensivo, mismo criterio que sale_extension).
    # ─────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New') or not vals.get('name'):
                company_id = vals.get('company_id') or self.env.company.id
                custom_name = self._biocreto_build_name_compras(company_id)
                if custom_name:
                    vals['name'] = custom_name
        return super().create(vals_list)

    @api.model
    def _biocreto_build_name_compras(self, company_id):
        """Construye CP-AAAA-PLANTA-NNNN. Retorna None si la compania no tiene plant_code."""
        company = self.env['res.company'].browse(company_id)
        if not company.plant_code:
            return None
        plant = company.plant_code.upper()
        year = str(fields.Date.context_today(self).year)
        sequence = self._biocreto_ensure_sequence_compras(company_id)
        correlative = sequence.with_company(company_id).next_by_id()
        return f"CP-{year}-{plant}-{correlative}"

    @api.model
    def _biocreto_ensure_sequence_compras(self, company_id):
        """Garantiza la existencia de la secuencia por compania.
        Prefijo vacio, padding 4, use_date_range=True → reset anual automatico.
        Creacion lazy (no hay XML de seed): la primera OC en cada compania la
        materializa. Mismo patron que biocreto_sale_extension._biocreto_ensure_sequence.
        """
        Sequence = self.env['ir.sequence'].sudo()
        seq_code = f'biocreto.purchase.order.{company_id}'
        sequence = Sequence.search([
            ('code', '=', seq_code),
            ('company_id', '=', company_id),
        ], limit=1)
        if not sequence:
            company = self.env['res.company'].browse(company_id)
            sequence = Sequence.create({
                'name': f'BIOCRETO Compras - {company.name}',
                'code': seq_code,
                'company_id': company_id,
                'padding': 4,
                'number_increment': 1,
                'implementation': 'standard',
                'use_date_range': True,
                'prefix': '',
            })
        return sequence

    # ─────────────────────────────────────────────────────────────────
    # v19.0.3.1.0: Validacion BIOCRETO — no permitir avanzar de estado
    # si no hay al menos una linea NO-display (producto real) con
    # cantidad > 0.
    #
    # Por que aca y no en @api.constrains:
    #   Los @api.constrains disparan popups modales que interrumpen la
    #   UX de manera confusa (bug ya conocido en el proyecto — ver
    #   memoria/biocreto-pending-breakage). Validar en los metodos de
    #   accion, ANTES de mutar estado, da un UserError controlado con
    #   mensaje BIOCRETO en el flujo del usuario.
    #
    # Difiere de la nativa (_confirmation_error_message, purchase/models/
    # purchase_order.py:654-665): la nativa solo checa "linea sin
    # product_id" (permite qty=0). Nuestra regla es mas estricta:
    # exige AL MENOS 1 linea con product_id Y product_qty > 0. Cubre el
    # caso del flujo con contrato blanket, donde el _onchange_requisition_id
    # carga las lineas con product_qty=0 y el usuario DEBE editar la
    # cantidad antes de confirmar (purchase_requisition/models/purchase.py:87).
    #
    # Se ignoran las lineas display (secciones, notas, downpayments):
    # filtered por display_type. Coincide con el criterio nativo de
    # _confirmation_error_message.
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_validar_lineas(self):
        """Bloquea avanzar de estado si no hay al menos una linea con qty > 0."""
        for order in self:
            lineas_validas = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id and l.product_qty > 0
            )
            if not lineas_validas:
                raise UserError(_(
                    "No puede continuar: la orden %(orden)s debe tener al menos "
                    "un producto con cantidad mayor a cero.",
                    orden=order.name or _('nueva'),
                ))

    # ─────────────────────────────────────────────────────────────────
    # Orquestacion de confirmacion (dos hops):
    #   Hop 1 (sent → registro): capturado en button_confirm.
    #   Hop 2 (registro → to approve / purchase): button_confirm_registro.
    #
    # Diseño: en el Hop 2 movemos temporalmente state='sent' con tracking
    # silenciado + llamamos a super().button_confirm() con un context key
    # que hace que el mismo override caiga en la rama de bypass — asi el
    # super() nativo corre TAL CUAL (incluyendo el warning wizard de
    # alternativas que purchase_requisition inyecta) sin re-entrar al hop.
    #
    # v19.0.3.1.0: la validacion _biocreto_validar_lineas se dispara antes
    # de CUALQUIER transicion (excepto en el path bypass, donde ya fue
    # validado por button_confirm_registro que nos llamo). Cubre AMBOS
    # flujos:
    #   - Flujo normal: sent→registro y draft→sent/purchase (via super)
    #     → validacion en button_confirm.
    #   - Flujo con contrato: draft_confirm (boton XML) llama a
    #     button_confirm nativo → nuestro override lo intercepta → cae
    #     en la rama draft (to_native) → validacion antes del super.
    # ─────────────────────────────────────────────────────────────────
    def button_confirm(self):
        # Bypass reentrante: cuando button_confirm_registro nos llama con
        # este context, delegamos derecho al comportamiento nativo.
        # No re-validamos: ya lo hizo button_confirm_registro.
        if self.env.context.get('biocreto_bypass_registro_hop'):
            return super().button_confirm()

        # v19.0.3.1.0: validar producto+cantidad ANTES de la transicion.
        # Aplica a AMBOS flujos: sent→registro (normal) y draft→super
        # (con contrato via draft_confirm).
        self._biocreto_validar_lineas()

        # Hop 1: sent → registro (no confirmamos aun; escribimos el estado)
        to_registro = self.filtered(lambda o: o.state == 'sent')
        if to_registro:
            to_registro.write({'state': 'registro'})

        # draft → comportamiento nativo (no hop): mantiene el super() nativo
        # por si algun flujo alterno crea una PO directo en draft y confirma.
        # En el flujo con contrato (Lote 3.1), este es el path que dispara
        # draft_confirm → _approval_allowed → to approve/purchase.
        to_native = self.filtered(lambda o: o.state == 'draft')
        if to_native:
            super(PurchaseOrder, to_native).button_confirm()

        return True

    # ─────────────────────────────────────────────────────────────────
    # v19.0.2.0.0 (Lote 2): backend del widget nativo `attach_document`
    # (odoo/addons/web/static/src/views/widgets/attach_document/attach_document.js).
    # El widget XML declara `action="subir_cotizacion"` → JS hace
    # `orm.call('purchase.order', 'subir_cotizacion', [resId], {attachment_ids: [...]})`
    # despues de subir el archivo via `/web/binary/upload_attachment` (que ya
    # crea el ir.attachment con res_model='purchase.order' y res_id=<id> del PO).
    # Aqui solo fijamos el ultimo attachment como principal → aparece en el
    # preview lateral (AttachmentView lee thread.attachmentsInWebClientView[0]
    # o message_main_attachment_id).
    #
    # force=True permite el REEMPLAZO al re-subir en 'registro' (el hook nativo
    # sin force solo asigna si NO hay main previo, mail_thread_main_attachment.py:38).
    #
    # Patron identico a hr_expense.attach_document (hr_expense/models/hr_expense.py:1198-1200).
    # ─────────────────────────────────────────────────────────────────
    def subir_cotizacion(self, **kwargs):
        """Widget attach_document: fija el ultimo adjunto subido como principal."""
        self.ensure_one()
        self._message_set_main_attachment_id(
            self.env["ir.attachment"].browse(kwargs['attachment_ids'][-1:]),
            force=True,
        )

    def button_confirm_registro(self):
        """Boton 'Confirmar OC' multi-estado (usado en draft y en registro):
        - Desde draft: salto rapido a 'registro' (se saltea 'sent').
        - Desde registro: dispara aprobacion nativa via bypass reentrante
          (equivalente a Hop 2 del Lote 1).

        v19.0.1.2.0: se amplia la logica original (solo registro) para aceptar
        tambien draft, porque el mismo boton XML se reutiliza en ambos estados
        con condiciones `invisible` distintas.

        v19.0.3.1.0: validacion _biocreto_validar_lineas al inicio.

        Snapshots de los subconjuntos ANTES de mutar para evitar que los que
        acaban de saltar draft→registro se cuelen en la rama de aprobacion.
        """
        # v19.0.3.1.0: validar producto+cantidad ANTES de la transicion.
        # Cubre draft→registro (flujo normal Lote 1) y registro→to approve/purchase
        # (Hop 2 del Lote 1). El super() del bypass NO re-valida.
        self._biocreto_validar_lineas()

        from_draft = self.filtered(lambda o: o.state == 'draft')
        from_registro = self.filtered(lambda o: o.state == 'registro')

        if from_draft:
            from_draft.write({'state': 'registro'})

        if not from_registro:
            return True

        # Movemos a 'sent' con tracking_disable para evitar entrada doble
        # en el chatter (Registro → sent → to approve/purchase).
        from_registro.with_context(tracking_disable=True).write({'state': 'sent'})
        return from_registro.with_context(
            biocreto_bypass_registro_hop=True,
        ).button_confirm()
