from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BiocretoRequerimientoEntrega(models.Model):
    _name = 'biocreto.requerimiento.entrega'
    _description = 'Entrega de materiales'
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    # ─────────────────────────────────────────────────────────────────
    # Modelo PERSISTENTE, no TransientModel: la entrega ES el documento
    # (lleva firma, correlativo y constancia PDF). Se abre en modal
    # (`target='new'`) sin `res_id`: el registro nace al pulsar
    # "Confirmar entrega", porque un boton type="object" guarda el
    # formulario antes de invocar el metodo. Si el usuario descarta, no
    # queda ningun borrador huerfano.
    # ─────────────────────────────────────────────────────────────────
    name = fields.Char(string="N.º de entrega", readonly=True, copy=False, index=True)
    requerimiento_id = fields.Many2one(
        'biocreto.requerimiento', string="Requerimiento",
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        string="Compañía", related='requerimiento_id.company_id',
        store=True, readonly=True, index=True)
    fecha = fields.Datetime(string="Fecha", default=fields.Datetime.now, required=True)

    employee_id = fields.Many2one(
        'hr.employee', string="Recibido por", required=True, check_company=True,
        help="Empleado que recibe el material. Su departamento determina la "
             "ubicación de destino.")
    # Copia HISTORICA. Es `related` pero con store=True a proposito: si
    # manana el empleado cambia de area, la entrega ya emitida debe
    # seguir diciendo a que area fue el material. Un related no
    # almacenado reescribiria el pasado.
    department_id = fields.Many2one(
        'hr.department', string="Área", related='employee_id.department_id',
        store=True, readonly=True)
    entregado_por_id = fields.Many2one(
        'res.users', string="Entregado por", readonly=True,
        default=lambda self: self.env.user, copy=False)

    firma_receptor = fields.Binary(
        string="Firma del receptor", attachment=True, copy=False)
    firma_receptor_nombre = fields.Char(
        string="Nombre del firmante",
        compute='_compute_firma_receptor_nombre', store=True, readonly=False)

    # compute + precompute + readonly=False + store: patron canonico v19
    # de precarga de lineas en un modal, identico a
    # stock/wizard/stock_picking_return.py:103 (product_return_moves).
    # NO se usa default_get.
    linea_ids = fields.One2many(
        'biocreto.requerimiento.entrega.linea', 'entrega_id', string="Líneas",
        compute='_compute_linea_ids', store=True, readonly=False, precompute=True)

    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('confirmado', 'Confirmado'),
    ], string="Estado", default='borrador', required=True, copy=False)

    @api.depends('employee_id')
    def _compute_firma_receptor_nombre(self):
        """Autollena con el nombre del empleado pero deja sobrescribir.

        Mismo criterio que `_compute_descripcion` de la linea de
        requerimiento (biocreto_requerimiento_linea.py:119-127): si no
        hay de donde copiar, se conserva lo que ya hubiera escrito el
        usuario en vez de borrarlo.
        """
        for entrega in self:
            if entrega.employee_id:
                entrega.firma_receptor_nombre = entrega.employee_id.name
            else:
                entrega.firma_receptor_nombre = entrega.firma_receptor_nombre or False

    @api.depends('requerimiento_id')
    def _compute_linea_ids(self):
        """Precarga una linea por cada linea de requerimiento entregable.

        Quedan fuera las canceladas y las que ya no tienen pendiente. Las
        lineas SIN producto SI entran: aparecen bloqueadas con su motivo,
        para que el encargado vea que falta darlas de alta en vez de que
        desaparezcan sin explicacion.

        El comando (0, 0, ...) lleva SOLO `requerimiento_linea_id`. Todo lo
        demas (pedido, ya entregado, producto, unidad) se deriva de ahi por
        compute: asi el registro sale igual tanto si lo crea este compute
        como si lo crea el cliente web, que solo devuelve la clave ajena y
        los dos campos editables. Ver la nota de `cantidad_pedida`.
        """
        for entrega in self:
            requerimiento = entrega.requerimiento_id
            if not requerimiento:
                entrega.linea_ids = [(5, 0, 0)]
                continue
            candidatas = requerimiento.linea_ids.filtered(
                lambda linea: linea.estado != 'cancelado'
                and linea.cantidad_pendiente > 0)
            entrega.linea_ids = [(5, 0, 0)] + [
                (0, 0, {'requerimiento_linea_id': linea.id})
                for linea in candidatas
            ]

    # ─────────────────────────────────────────────────────────────────
    # Numeracion {REQUERIMIENTO}-{n}
    #
    # Se cuentan hermanos con search_count, patron de
    # biocreto_fabricacion/models/biocreto_carga.py:88-96. NO se usa
    # ir.sequence: las secuencias de este proyecto se crean con
    # implementation='standard' (biocreto_requerimiento.py:170), que es
    # una secuencia nativa de PostgreSQL -- `nextval` NO es transaccional
    # y sobrevive a un ROLLBACK, quemando correlativos en cada intento
    # fallido.
    # ─────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """El correlativo se pone DESPUES de crear, no antes.

        Antes se leia `vals['requerimiento_id']`, y desde el cliente web
        esa clave NO viene: el campo va `readonly="1"` en el formulario
        del asistente, asi que el cliente no lo devuelve; quien lo rellena
        es el `default_requerimiento_id` del contexto, y eso ocurre DENTRO
        de super().create(), cuando el nombre ya estaba compuesto. El
        resultado era el literal «False-1» en toda entrega creada desde la
        interfaz.

        Hecho de la misma familia que el fallo de `requerimiento_linea_id`:
        un campo readonly en la vista no viaja de vuelta al servidor.
        Componiendo el nombre despues, da igual si el valor llego en vals
        o lo puso el default del contexto.
        """
        entregas = super().create(vals_list)
        for entrega in entregas:
            if entrega.name:
                continue
            entrega.name = entrega._biocreto_build_name()
        return entregas

    def _biocreto_build_name(self):
        """{REQUERIMIENTO}-E{n}. Nunca devuelve un nombre con `False` dentro.

        v19.0.1.7.0: se antepone la «E» al correlativo. Sigue contando
        hermanos con search_count, NO con ir.sequence: una secuencia
        `implementation='standard'` no es transaccional y quemaria un
        correlativo en cada rollback.

        El requerimiento es `required=True`, asi que llegar aqui sin el
        deberia ser imposible; el UserError esta para que, si alguna via
        futura lo esquiva, el fallo se vea en el acto en vez de grabarse
        como el literal «False-1» y aparecer luego en la constancia.
        """
        self.ensure_one()
        requerimiento = self.requerimiento_id
        if not requerimiento:
            raise UserError(_(
                "No se puede numerar la entrega: no está asociada a ningún "
                "requerimiento.\n\n"
                "Ábrala desde el requerimiento, con el botón «Registrar "
                "entrega»."))
        if not requerimiento.name:
            raise UserError(_(
                "El requerimiento %s todavía no tiene número, así que la "
                "entrega no se puede numerar.",
                requerimiento.display_name))
        # `id != self` para no contarse a si misma: search() vacia el
        # buffer de escritura antes de consultar, asi que la entrega
        # recien creada ya esta en la tabla.
        existentes = self.search_count([
            ('requerimiento_id', '=', requerimiento.id),
            ('id', '!=', self.id),
        ])
        return '%s-E%s' % (requerimiento.name, existentes + 1)

    # ────────────────────────────────────────────────────────────────
    # Reapertura de un borrador
    #
    # v19.0.1.4.0: la firma vuelve a capturarse EN LINEA, dentro del
    # asistente (widget="signature"), y desaparece el segundo dialogo.
    # Con eso el asistente ya no se guarda a mitad de camino: el unico
    # boton que persiste el registro es "Confirmar entrega", asi que
    # cerrar con la X no deja nada en base.
    #
    # Se conserva `action_continuar` porque los borradores que dejo la
    # etapa anterior siguen ahi y no habria otra forma de terminarlos.
    # ────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_accion_asistente(self):
        """La accion que reabre el asistente de entrega sobre este registro.

        La vista va por xmlid explicito y NO como [[False, 'form']]: el
        modelo tiene DOS vistas formulario (el asistente y el dialogo de
        firma), asi que dejar que Odoo elija por prioridad es apostar a
        que nadie toque esas prioridades.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Registrar entrega"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[self.env.ref(
                'biocreto_requerimientos.'
                'biocreto_requerimiento_entrega_view_form').id, 'form']],
            'target': 'new',
        }

    def action_continuar(self):
        """Reabre un borrador en el asistente, desde la lista de entregas.

        Sin esto, un borrador es un callejon sin salida: el asistente solo
        se abre como DIALOGO desde el requerimiento, y esa via crea uno
        nuevo (pasa `default_requerimiento_id`, no `res_id`). Abrir el
        registro desde el listado tampoco vale, porque el <footer> se
        saca del arch (form_controller.js:241-250) y solo se pinta
        `t-if="env.inDialog"` (form_controller.xml:13): en pagina completa
        no habria ningun boton que pulsar.
        """
        self.ensure_one()
        if self.state == 'confirmado':
            raise UserError(_(
                "Esta entrega ya está confirmada: no hay nada que continuar."))
        return self._biocreto_accion_asistente()


    # ─────────────────────────────────────────────────────────────────
    # Confirmacion
    # ─────────────────────────────────────────────────────────────────
    def action_confirmar(self):
        """Valida, mueve stock, cierra estados y adjunta la constancia.

        Todas las validaciones viven AQUI y no en @api.constrains: un
        constrains se dispararia tambien al guardar el borrador desde
        cualquier otra via y bloquearia el flujo a medias.

        Atomicidad: cualquier UserError revierte la transaccion entera,
        asi que no puede quedar media entrega con unos movimientos
        hechos y otros no.
        """
        self.ensure_one()
        if self.state == 'confirmado':
            raise UserError(_("Esta entrega ya está confirmada."))

        seleccionadas = self._biocreto_validar()
        self._biocreto_generar_movimientos(seleccionadas)

        self.state = 'confirmado'
        # El compute almacenado de la linea de requerimiento depende del
        # state de la entrega; hay que vaciar el buffer para que se
        # recalcule ANTES de leerlo al fijar los estados.
        self.env.flush_all()

        self.requerimiento_id._biocreto_cerrar_desde_entregas(
            seleccionadas.requerimiento_linea_id)
        self._biocreto_publicar_constancia()
        return {'type': 'ir.actions.act_window_close'}

    def _biocreto_validar(self):
        """Devuelve las lineas a entregar o lanza UserError."""
        self.ensure_one()

        if not self.employee_id:
            raise UserError(_(
                "Indique quién recibe el material antes de confirmar la entrega."))

        if not self.department_id:
            raise UserError(_(
                "El empleado «%(empleado)s» no tiene departamento asignado, y el "
                "departamento es lo que determina a qué ubicación va el material.\n\n"
                "Complete el campo «Departamento» en la ficha del empleado "
                "(Empleados → %(empleado)s) y vuelva a intentarlo.\n\n"
                "Si usted no puede editar empleados, solicíteselo al "
                "administrador de Recursos Humanos.",
                empleado=self.employee_id.name))

        if not self.firma_receptor:
            raise UserError(_(
                "Falta la firma del receptor. Pulse sobre el recuadro de firma "
                "y pida a %(empleado)s que firme antes de confirmar.",
                empleado=self.employee_id.name))

        seleccionadas = self.linea_ids.filtered(
            lambda linea: linea.seleccionada and linea.cantidad_entregar > 0)
        if not seleccionadas:
            raise UserError(_(
                "No ha marcado ninguna línea con cantidad a entregar."))

        for linea in seleccionadas:
            etiqueta = linea.descripcion or linea.product_id.display_name or ''
            if linea.cantidad_entregar > linea.cantidad_pendiente:
                raise UserError(_(
                    "«%(producto)s»: intenta entregar %(pide)s pero solo quedan "
                    "%(pendiente)s pendientes.",
                    producto=etiqueta,
                    pide=linea.cantidad_entregar,
                    pendiente=linea.cantidad_pendiente))
            if linea.afecta_inventario and linea.cantidad_entregar > linea.stock_disponible:
                raise UserError(_(
                    "«%(producto)s»: intenta entregar %(pide)s pero solo hay "
                    "%(stock)s en stock.\n\n"
                    "Odoo no impide dejar el inventario en negativo, así que este "
                    "bloqueo es del módulo, no del sistema.",
                    producto=etiqueta,
                    pide=linea.cantidad_entregar,
                    stock=linea.stock_disponible))

        # Ubicacion destino: se valida POR LINEA, no una sola vez.
        # Una misma entrega puede llevar consumibles y activos, y puede
        # fallar solo por uno de los dos tipos.
        for linea in seleccionadas.filtered('afecta_inventario'):
            destino, etiqueta_campo = self._biocreto_destino_de(linea)
            if not destino:
                raise UserError(_(
                    "El área «%(area)s» no tiene configurada la «%(campo)s», y la "
                    "línea «%(producto)s» la necesita.\n\n"
                    "Vaya a Empleados → Departamentos → %(area)s y rellene ese "
                    "campo en el apartado «BIOCRETO — Entregas de materiales».",
                    area=self.department_id.name,
                    campo=etiqueta_campo,
                    producto=linea.descripcion or linea.product_id.display_name))
            if destino.usage == 'view':
                raise UserError(_(
                    "La «%(campo)s» del área «%(area)s» apunta a «%(ubicacion)s», "
                    "que es una ubicación de tipo «Vista».\n\n"
                    "Odoo prohíbe mover existencias hacia una ubicación de vista: "
                    "solo sirven para agrupar en el árbol. Cambie su tipo (por "
                    "ejemplo a «Ubicación de cliente») o apunte el campo a una "
                    "ubicación que no sea de vista.",
                    campo=etiqueta_campo,
                    area=self.department_id.name,
                    ubicacion=destino.complete_name))
        return seleccionadas

    def _biocreto_destino_de(self, linea):
        """(ubicacion, etiqueta) segun el producto sea activo o consumible.

        v19.0.1.6.0: la fuente de verdad ya NO es la categoria sino el
        propio producto (product.template.biocreto_es_activo). Una misma
        categoria mezcla las dos naturalezas, asi que preguntarle a la
        categoria daba el destino equivocado para la mitad de sus
        productos.

        Es el UNICO sitio del modulo que decide activo vs. consumible: lo
        llaman tanto la validacion previa de las lineas como
        `_biocreto_generar_movimientos`, de modo que el destino que se
        valida y el que se escribe en el stock.move no pueden divergir.

        Boolean sin default -> False -> consumible. Un producto que nadie
        haya marcado cae en consumo, que es lo prudente y lo que ya hacian
        todos los que no estaban en una categoria marcada.
        """
        self.ensure_one()
        if linea.product_id.biocreto_es_activo:
            return (self.department_id.biocreto_ubicacion_activos,
                    _("Ubicación de activos"))
        return (self.department_id.biocreto_ubicacion_consumo,
                _("Ubicación de consumo"))

    def _biocreto_generar_movimientos(self, seleccionadas):
        """Un stock.move validado por linea que afecte inventario.

        Movimientos SIN picking y SIN picking_type_id, patron de
        stock.scrap (odoo/addons/stock/models/stock_scrap.py:125-163).
        Ademas de ser mas simple, evita contaminar el search_count de
        correlativos de biocreto_fabricacion, que cuenta pickings cuyo
        name casa 'RAIZ-%' (biocreto_carga.py:222-223).

        Hechos verificados empiricamente que NO se pueden reinterpretar:
          · stock.move NO tiene campo `name` en v19.
          · `quantity_done` no existe; el campo es `quantity` (compute
            almacenado con inverse `_set_quantity`).
          · sin `picked = True` el movimiento se CANCELA en silencio
            dentro de _action_done (stock_move.py:2085-2093).
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        almacen = self.env['stock.warehouse'].search(
            [('company_id', '=', company.id)], limit=1)
        if not almacen:
            raise UserError(_(
                "La compañía «%(compania)s» no tiene ningún almacén configurado.",
                compania=company.name))
        origen = almacen.lot_stock_id

        Move = self.env['stock.move']
        for linea in seleccionadas.filtered('afecta_inventario'):
            destino, _etiqueta = self._biocreto_destino_de(linea)
            movimiento = Move.create({
                'product_id': linea.product_id.id,
                'product_uom': linea.product_uom_id.id,
                'product_uom_qty': linea.cantidad_entregar,
                'location_id': origen.id,
                'location_dest_id': destino.id,
                'company_id': company.id,
                'origin': self.name,
                'state': 'draft',
            })
            movimiento._action_confirm()
            movimiento._action_assign()
            movimiento.quantity = linea.cantidad_entregar
            movimiento.picked = True
            movimiento._action_done()
            if movimiento.state != 'done':
                raise UserError(_(
                    "El movimiento de stock de «%(producto)s» quedó en estado "
                    "«%(estado)s» en vez de «done». No se ha registrado nada: "
                    "revise el stock y la ubicación de destino.",
                    producto=linea.product_id.display_name,
                    estado=movimiento.state))
            linea.stock_move_id = movimiento.id

    def _biocreto_publicar_constancia(self):
        """Renderiza la constancia y la deja SOLO en el mensaje del chatter.

        Patron de biocreto_sale_portal/controllers/portal.py:269-285:
        `_render_qweb_pdf(...)[0]` + `message_post(attachments=[...])`.
        PlutoPrint se activa solo, por report_name.

        Los dos mecanismos de message_post acaban igual de ligados al
        REGISTRO: `_process_attachments_for_post` crea el ir.attachment con
        `'res_model': model, 'res_id': res_id` (mail_thread.py:2455-2461),
        exactamente los mismos valores a los que reescribe los que llegan
        por `attachment_ids` (:2412). Con cualquiera de los dos, la
        constancia aparecia en los adjuntos del requerimiento y sumaba en
        `attachment_number` -- que es el contador de "documentos que
        adjunto el solicitante" y alimenta la validacion de
        `requirer_document` (biocreto_requerimiento.py:291).

        Por eso, despues de publicar, se reapunta el adjunto al mensaje.
        No es un apano: es el convenio que el propio nucleo reconoce, y
        ademas cierra la limpieza. mail.message.unlink borra en cascada
        justo los adjuntos con esta forma:

            self.mapped('attachment_ids').filtered(
                lambda attach: attach.res_model == self._name
                and (attach.res_id in self.ids or attach.res_id == 0)
            ).unlink()
                (mail_message.py:809-811)

        El PDF sigue viendose y descargandose desde la burbuja del
        chatter: el enlace sale del m2m message.attachment_ids, que no se
        toca, y el control de acceso pasa a evaluarse contra la
        mail.message (ir_attachment.py:497-544), legible por quien pueda
        leer el mensaje.
        """
        self.ensure_one()
        pdf, _ext = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'biocreto_requerimientos.report_constancia_entrega', [self.id])
        nombre_fichero = '%s_ENTREGA.pdf' % (
            (self.name or str(self.id)).replace('/', '_'))
        mensaje = self.requerimiento_id.message_post(
            body=_("Entrega registrada para %(nombre)s",
                   nombre=self.firma_receptor_nombre or self.employee_id.name),
            attachments=[(nombre_fichero, pdf)],
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        mensaje.attachment_ids.sudo().write({
            'res_model': mensaje._name,
            'res_id': mensaje.id,
        })
        return mensaje

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmada(self):
        if any(entrega.state == 'confirmado' for entrega in self):
            raise UserError(_(
                "No se puede eliminar una entrega confirmada: ya movió "
                "inventario y tiene constancia emitida."))


class BiocretoRequerimientoEntregaLinea(models.Model):
    _name = 'biocreto.requerimiento.entrega.linea'
    _description = 'Línea de entrega de materiales'
    _check_company_auto = True

    entrega_id = fields.Many2one(
        'biocreto.requerimiento.entrega', string="Entrega",
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        string="Compañía", related='entrega_id.company_id', store=True, index=True)
    requerimiento_linea_id = fields.Many2one(
        'biocreto.requerimiento.linea', string="Línea de requerimiento",
        required=True, index=True, ondelete='cascade')

    product_id = fields.Many2one(
        related='requerimiento_linea_id.product_id', string="Producto", store=True)
    descripcion = fields.Char(
        related='requerimiento_linea_id.descripcion', string="Descripción")
    product_uom_id = fields.Many2one(
        related='requerimiento_linea_id.product_uom_id', string="Unidad")

    seleccionada = fields.Boolean(string="Entregar")

    # ─────────────────────────────────────────────────────────────────
    # FOTO del momento en que se abre el modal, NO campos relacionados.
    #
    # Van como compute almacenado con precompute y dependiendo SOLO de
    # `requerimiento_linea_id`, que nunca cambia. Dos razones:
    #
    #  1. El cliente web no los envia de vuelta al guardar (son readonly
    #     en la vista y no editables), asi que si fueran campos planos se
    #     grabarian a 0 y `cantidad_pendiente` saldria 0 -> la entrega se
    #     rechazaria con "solo quedan 0 pendientes". Como compute, el
    #     servidor los rellena siempre, envie el cliente lo que envie.
    #  2. Si fueran `related` vivos a la linea de requerimiento,
    #     `cantidad_ya_entregada` cambiaria al confirmar (esta entrega
    #     pasa a contar) y la columna "Pendiente" de la constancia
    #     restaria dos veces. Dependiendo solo de la clave ajena, el
    #     valor queda congelado.
    # ─────────────────────────────────────────────────────────────────
    cantidad_pedida = fields.Float(
        string="Pedido", digits='Product Unit',
        compute='_compute_cantidades_origen', store=True, precompute=True)
    cantidad_ya_entregada = fields.Float(
        string="Ya entregado", digits='Product Unit',
        compute='_compute_cantidades_origen', store=True, precompute=True)
    cantidad_pendiente = fields.Float(
        string="Pendiente", digits='Product Unit',
        compute='_compute_cantidad_pendiente')

    # store=True + readonly=False: se autollena al marcar la casilla pero
    # el encargado puede bajarlo a mano para una entrega parcial. El
    # @api.depends es SOLO sobre `seleccionada` a proposito: asi una
    # cantidad editada a mano sobrevive (el compute no se vuelve a
    # disparar mientras la casilla no cambie).
    cantidad_entregar = fields.Float(
        string="A entregar", digits='Product Unit',
        compute='_compute_cantidad_entregar', store=True, readonly=False)

    stock_disponible = fields.Float(
        string="Stock disponible", digits='Product Unit',
        compute='_compute_stock_disponible')
    afecta_inventario = fields.Boolean(
        string="Afecta inventario", compute='_compute_afecta_inventario')
    bloqueada = fields.Boolean(string="Bloqueada", compute='_compute_bloqueada')
    motivo_bloqueo = fields.Char(string="Observación", compute='_compute_bloqueada')

    stock_move_id = fields.Many2one(
        'stock.move', string="Movimiento de stock", readonly=True, copy=False)

    @api.depends('requerimiento_linea_id')
    def _compute_cantidades_origen(self):
        for linea in self:
            origen = linea.requerimiento_linea_id
            linea.cantidad_pedida = origen.cantidad
            linea.cantidad_ya_entregada = origen.cantidad_entregada_requerimiento

    @api.depends('cantidad_pedida', 'cantidad_ya_entregada')
    def _compute_cantidad_pendiente(self):
        for linea in self:
            linea.cantidad_pendiente = max(
                0.0, linea.cantidad_pedida - linea.cantidad_ya_entregada)

    @api.depends('product_id')
    def _compute_afecta_inventario(self):
        for linea in self:
            linea.afecta_inventario = bool(
                linea.product_id and linea.product_id.is_storable)

    @api.depends('requerimiento_linea_id.stock_disponible')
    def _compute_stock_disponible(self):
        for linea in self:
            linea.stock_disponible = linea.requerimiento_linea_id.stock_disponible

    @api.depends('seleccionada')
    def _compute_cantidad_entregar(self):
        for linea in self:
            if not linea.seleccionada:
                linea.cantidad_entregar = 0.0
                continue
            pendiente = linea.cantidad_pendiente
            if linea.afecta_inventario:
                linea.cantidad_entregar = max(
                    0.0, min(pendiente, linea.stock_disponible))
            else:
                linea.cantidad_entregar = max(0.0, pendiente)

    @api.depends('product_id', 'afecta_inventario', 'stock_disponible')
    def _compute_bloqueada(self):
        """Reglas del Paso 7. Bloquear una linea NO impide entregar las demas."""
        for linea in self:
            if not linea.product_id:
                linea.bloqueada = True
                linea.motivo_bloqueo = _(
                    "Falta crear el producto. Usa el botón Crear producto.")
            elif not linea.afecta_inventario:
                linea.bloqueada = False
                linea.motivo_bloqueo = _("No afecta inventario")
            elif linea.stock_disponible <= 0:
                linea.bloqueada = True
                linea.motivo_bloqueo = _("Sin stock disponible")
            else:
                linea.bloqueada = False
                linea.motivo_bloqueo = False
