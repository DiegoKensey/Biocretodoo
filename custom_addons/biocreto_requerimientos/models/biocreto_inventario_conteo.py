# ═══════════════════════════════════════════════════════════════════════
#  INVENTARIO DE ACTIVOS POR AREA  —  formato BC-GL-FR-15
#
#  Un documento por area y por recuento, con flujo
#  borrador -> enviado -> validado, y rechazado como vuelta atras.
#
#  POR QUE AHORA HAY ESTADOS (antes NO los habia)
#  ----------------------------------------------
#  Hasta v19.0.2.0.0 este archivo decia, y con razones: "SIN estados: se
#  edita libremente mientras el area termina de contar". Eso valia
#  mientras el conteo era solo una hoja que se imprimia. Dejo de valer
#  cuando el conteo pasa a hacer DOS cosas nuevas:
#
#    1. Es la FOTO DE UN PERIODO. El conteo de enero tiene que seguir
#       diciendo en marzo lo que se conto en enero. Un documento que se
#       recalcula solo no es una foto, y el PDF ya firmado dejaria de
#       cuadrar con lo que el sistema enseña.
#    2. MUEVE INVENTARIO. Al validarse, las unidades en Malogrado se
#       desechan de verdad con `stock.scrap`. Una baja de inventario es
#       irreversible; no puede dispararla un documento que cualquiera
#       reabre y reedita.
#
#  Por eso el documento ahora se cierra. `borrador` y `rechazado` se
#  editan y recargan; `enviado` y `validado` no se tocan.
#
#  POR QUE LAS LINEAS YA NO TIENEN BOTON DE CARGA
#  ----------------------------------------------
#  `linea_ids` es compute + store + readonly=False + precompute, el
#  patron canonico de v19 (mismo que
#  `biocreto_requerimiento_entrega.linea_ids`:50-55). Las lineas
#  aparecen al elegir el area, se editan y se guardan como registros
#  reales. NO se uso un One2many computado SIN almacenar: devuelve
#  `NewId` en cada lectura y se lleva por delante lo tecleado en cada
#  recomputacion (odoo/orm/fields.py:453 lo deja ademas readonly si no
#  hay `inverse`).
#
#  POR QUE NO HAY `@api.constrains` EN TODO EL ARCHIVO
#  ---------------------------------------------------
#  Es la regla del proyecto, y aqui ademas es la unica opcion viable: un
#  conteo a medio llenar es el ESTADO NORMAL del documento durante el
#  recuento fisico. Un constrains sobre la suma saltaria en cada guardado
#  automatico del formulario y haria el modulo inusable. Las validaciones
#  viven en `action_enviar` y `action_imprimir`.
#
#  LO QUE SE QUITO EN v19.0.3.0.0 Y POR QUE
#  ----------------------------------------
#  · `action_cargar_activos` y su boton: los sustituye el compute.
#  · `action_verificar` y su boton: sus tres validaciones siguen vivas
#    en `_biocreto_validar`, ahora llamadas desde Enviar e Imprimir.
#  · `_biocreto_arrastrar` y `_biocreto_conteo_anterior`: el arrastre de
#    estados del conteo anterior DESAPARECE. Ver la nota de
#    `_compute_linea_ids`. Quedan en el historial de git si hicieran
#    falta.
# ═══════════════════════════════════════════════════════════════════════
from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import float_compare


def _biocreto_num(valor):
    """`8` en vez de `8.0`; `8.5` en vez de `8.50`. Para los mensajes."""
    if float(valor) == int(valor):
        return '%d' % int(valor)
    return ('%.2f' % valor).rstrip('0').rstrip('.')


# Estados en los que el documento esta CERRADO: ni se recargan las
# lineas ni se edita nada. Una sola definicion para que la guarda del
# compute y la de las acciones no puedan divergir.
BIOCRETO_ESTADOS_CERRADOS = ('enviado', 'validado')


class BiocretoInventarioConteo(models.Model):
    _name = 'biocreto.inventario.conteo'
    _description = 'Inventario de activos por área'
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
    _order = 'fecha desc, id desc'

    name = fields.Char(
        string="Número", readonly=True, copy=False, default="/", index=True)

    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado'),
        ('validado', 'Validado'),
        ('rechazado', 'Rechazado'),
    ], string="Estado", default='borrador', required=True,
        store=True, index=True, tracking=True, copy=False, group_expand=True)

    department_id = fields.Many2one(
        'hr.department', string="Área", required=True,
        check_company=True, ondelete='restrict', tracking=True,
        help="El área que se inventaría. Su «Ubicación de activos» es la que "
             "se lee para cargar las existencias.")

    # Related ALMACENADO. Dos motivos:
    #   - el reporte y el dialogo de impresion filtran y agrupan por el, y
    #     un related no almacenado no se puede usar en un `search`;
    #   - congela la ubicacion que se uso: si manana alguien reconfigura
    #     el departamento, los conteos ya impresos siguen diciendo donde
    #     se conto. `readonly` implicito por ser related sin inverse.
    ubicacion_id = fields.Many2one(
        'stock.location', string="Ubicación",
        related='department_id.biocreto_ubicacion_activos',
        store=True, readonly=True)

    fecha = fields.Date(
        string="Fecha", required=True, default=fields.Date.context_today,
        index=True, tracking=True)

    tipo = fields.Selection(
        [('selectivo', "Selectivo"), ('general', "General")],
        string="Tipo", default='selectivo', required=True)

    responsable_id = fields.Many2one(
        'hr.employee', string="Responsable", required=True,
        check_company=True, ondelete='restrict', tracking=True)
    responsable2_id = fields.Many2one(
        'hr.employee', string="Segundo responsable",
        check_company=True, ondelete='restrict')

    # ─────────────────────────────────────────────────────────────────
    # LAS LINEAS SE CARGAN SOLAS
    #
    # compute + store + readonly=False + precompute: el patron canonico
    # de v19 para precargar lineas editables, identico al de
    # `biocreto_requerimiento_entrega.linea_ids` (:50-55) y al del
    # nativo `stock/wizard/stock_picking_return.py` (product_return_moves).
    #
    # `store=True` es lo que hace que el conteo sea una FOTO: las lineas
    # son registros reales, no una lectura en vivo de `stock.quant`.
    # ─────────────────────────────────────────────────────────────────
    linea_ids = fields.One2many(
        'biocreto.inventario.conteo.linea', 'conteo_id', string="Líneas",
        compute='_compute_linea_ids', store=True, readonly=False,
        precompute=True)

    company_id = fields.Many2one(
        'res.company', string="Compañía", required=True, index=True,
        default=lambda self: self.env.company)

    biocreto_motivo_rechazo = fields.Text(
        string="Motivo del rechazo", readonly=True, copy=False,
        help="Lo escribe el validador al rechazar. Se sobrescribe en cada "
             "rechazo; el historial completo queda en el chatter.")

    # ── Resumen, para la cabecera del formulario y la barra del PDF ──
    # NO almacenados: son una suma de las lineas, y el documento se edita
    # continuamente. Almacenarlos solo anadiria invalidaciones.
    biocreto_total_productos = fields.Integer(
        string="Productos", compute='_compute_biocreto_resumen')
    biocreto_total_unidades = fields.Float(
        string="Unidades", compute='_compute_biocreto_resumen')
    biocreto_fuera_productos = fields.Integer(
        string="Productos fuera de Bueno", compute='_compute_biocreto_resumen')
    biocreto_fuera_unidades = fields.Float(
        string="Unidades fuera de Bueno", compute='_compute_biocreto_resumen')
    # Solo MALOGRADO, que es lo unico que se da de baja. `fuera` incluye
    # tambien Regular, y un activo regular sigue en uso.
    #
    # NO almacenados, como el resto del resumen, y ademas por un motivo
    # propio: un compute almacenado se escribe por la via interna del
    # ORM, que NO pasa por `write()`, asi que el candado de edicion de
    # mas abajo no lo veria... pero cualquier variante futura que si
    # pasara chocaria con el. Para el filtro de "Bajas por validar" no
    # hacen falta almacenados: el dominio mira `linea_ids.cant_malogrado`
    # directamente.
    biocreto_baja_productos = fields.Integer(
        string="Productos a dar de baja", compute='_compute_biocreto_resumen')
    biocreto_baja_unidades = fields.Float(
        string="Unidades a dar de baja", compute='_compute_biocreto_resumen')

    biocreto_scrap_count = fields.Integer(
        string="Desechos", compute='_compute_biocreto_scrap_count')

    @api.depends('linea_ids.total', 'linea_ids.cant_regular',
                 'linea_ids.cant_malogrado')
    def _compute_biocreto_resumen(self):
        for conteo in self:
            fuera = conteo.linea_ids.filtered(
                lambda linea: (linea.cant_regular + linea.cant_malogrado) > 0)
            bajas = conteo.linea_ids.filtered(
                lambda linea: linea.cant_malogrado > 0)
            conteo.biocreto_total_productos = len(conteo.linea_ids)
            conteo.biocreto_total_unidades = sum(conteo.linea_ids.mapped('total'))
            conteo.biocreto_fuera_productos = len(fuera)
            conteo.biocreto_fuera_unidades = (
                sum(fuera.mapped('cant_regular'))
                + sum(fuera.mapped('cant_malogrado')))
            conteo.biocreto_baja_productos = len(bajas)
            conteo.biocreto_baja_unidades = sum(bajas.mapped('cant_malogrado'))

    @api.depends('linea_ids.biocreto_scrap_ids')
    def _compute_biocreto_scrap_count(self):
        for conteo in self:
            conteo.biocreto_scrap_count = len(conteo._biocreto_scraps())

    def _biocreto_scraps(self):
        """Los `stock.scrap` generados por este conteo.

        Se navegan por la LINEA, que es donde vive la clave ajena
        (`stock.scrap.biocreto_conteo_linea_id`). Ver la nota de ese
        campo en `stock_scrap.py` de este modulo.
        """
        self.ensure_one()
        return self.linea_ids.biocreto_scrap_ids

    # ═════════════════════════════════════════════════════════════════
    # CORRELATIVO
    # ═════════════════════════════════════════════════════════════════
    # `ir.sequence` SI sirve aqui, a diferencia del codigo de producto de
    # `biocreto_producto_codigo`: alli habia que rellenar huecos dejados
    # por productos borrados, cosa que una secuencia no sabe hacer. Un
    # conteo de inventario es estrictamente cronologico y nadie espera
    # que el numero 18 reaparezca si se borra ese documento.
    #
    # Patron calcado de `biocreto_requerimiento._biocreto_ensure_sequence_
    # requerimiento`: una secuencia POR COMPANIA, creada en lazy, prefijo
    # vacio, padding 4 y `use_date_range=True` para el reinicio anual. El
    # prefijo se compone aqui y no en la secuencia porque incluye el
    # `plant_code` de la compania, que puede cambiar.
    @api.model
    def _biocreto_ensure_sequence(self, company_id):
        Sequence = self.env['ir.sequence'].sudo()
        codigo = 'biocreto.inventario.conteo.%s' % company_id
        secuencia = Sequence.search(
            [('code', '=', codigo), ('company_id', '=', company_id)], limit=1)
        if not secuencia:
            company = self.env['res.company'].browse(company_id)
            secuencia = Sequence.create({
                'name': 'BIOCRETO Inventario de activos - %s' % company.name,
                'code': codigo,
                'company_id': company_id,
                'padding': 4,
                'number_increment': 1,
                'implementation': 'standard',
                'use_date_range': True,
                'prefix': '',
            })
        return secuencia

    def _biocreto_numero(self, company_id):
        """INV-{PLANTA}-{AÑO}-{0001}, o INV-{AÑO}-{0001} sin plant_code."""
        company = self.env['res.company'].browse(company_id)
        secuencia = self._biocreto_ensure_sequence(company_id)
        correlativo = secuencia.with_company(company_id).next_by_id()
        anio = str(fields.Date.context_today(self).year)
        planta = (company.plant_code or '').upper()
        if planta:
            return "INV-%s-%s-%s" % (planta, anio, correlativo)
        return "INV-%s-%s" % (anio, correlativo)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = self._biocreto_numero(company_id)
        conteos = super().create(vals_list)
        # El candado del area va AQUI y no en un @api.constrains: un
        # constrains saltaria tambien al escribir cualquier otro campo de
        # un conteo ya existente, y el area de un conteo abierto es
        # legitima -- es EL conteo abierto de esa area. Aqui se comprueba
        # en el unico instante en que aparece un segundo documento.
        conteos._biocreto_exigir_area_libre()
        return conteos

    def copy_data(self, default=None):
        # Un duplicado nace en borrador, con numero nuevo y SIN lineas ni
        # motivo de rechazo: duplicar un conteo es empezar el del mes
        # siguiente, no clonar el recuento. Las lineas las trae el
        # compute en cuanto el duplicado tiene departamento.
        default = dict(default or {}, name='/', linea_ids=False,
                       state='borrador', biocreto_motivo_rechazo=False)
        return super().copy_data(default=default)

    # ═════════════════════════════════════════════════════════════════
    # LA CARGA AUTOMATICA
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_stock_por_producto(self):
        """{product.product: cantidad} de los ACTIVOS de la ubicación.

        Se lee `stock.quant` y no `product.qty_available` porque hace
        falta el detalle por ubicación, y `qty_available` obliga a pasar
        por el contexto `location` para acabar leyendo los mismos quants.

        `child_of`: la ubicación del área puede tener sublocalizaciones
        (estantes) y un activo guardado en una de ellas sigue siendo del
        área.

        `sudo()` + FILTRO DE COMPAÑIA EXPLICITO. Las dos cosas, y no una:
        el `sudo()` hace falta porque el ACL de `stock.quant` exige el
        grupo Inventario/Usuario y un Encargado de requerimientos no lo
        tiene — sin él, cargar el conteo revienta con AccessError. Pero
        `sudo()` anula también las reglas de registro multicompañía, así
        que el `('company_id', '=', ...)` del dominio deja de ser una
        redundancia y pasa a ser la ÚNICA barrera entre plantas.
        """
        self.ensure_one()
        if not self.ubicacion_id:
            return {}
        quants = self.env['stock.quant'].sudo().search([
            ('location_id', 'child_of', self.ubicacion_id.id),
            ('company_id', '=', self.company_id.id),
            ('product_id.biocreto_es_activo', '=', True),
        ])
        por_producto = {}
        for quant in quants:
            producto = quant.product_id
            por_producto[producto] = por_producto.get(producto, 0.0) + quant.quantity
        # Un producto con saldo 0 o negativo en el area no se cuenta: no
        # esta ahi. El negativo existe de verdad en esta base (un quant a
        # -4 por un ajuste), y meterlo en el conteo obligaria al usuario
        # a repartir una cantidad imposible entre tres estados.
        return {p: c for p, c in por_producto.items() if c > 0}

    @api.depends('department_id')
    def _compute_linea_ids(self):
        """Sincroniza las líneas con los activos que hay HOY en el área.

        AGREGA lo que falta, QUITA lo que ya no está Y no tiene datos, y
        NO TOCA nada que alguien haya escrito. Nunca reemplaza la tabla
        entera: el botón «Cargar activos» hacía eso y por eso tenía que
        ser un botón con confirmación.

        LA GUARDA POR ESTADO VA AQUI, NO EN LA VISTA
        --------------------------------------------
        Un `readonly` de vista no detiene un `write` por código, ni una
        importación CSV, ni una llamada por API. Si alguien cambia el
        departamento de un conteo ya enviado o validado, las líneas NO se
        recalculan: son la foto de lo que se contó ese día y el documento
        puede estar ya impreso y firmado.

        EL ARRASTRE DEL CONTEO ANTERIOR DESAPARECE
        ------------------------------------------
        `action_cargar_activos` heredaba los estados del conteo previo
        del área. Aquí NO, por tres motivos que apuntan al mismo sitio:

          · El encargo lo prohíbe expresamente: «NO copiar las líneas de
            un conteo anterior. Cada conteo parte del stock real».
          · Con la validación de bajas, heredar sería ADEMAS incorrecto:
            las unidades que el conteo anterior marcó como Malogrado ya
            se desecharon al validarlo, así que ya no están en el stock.
            Arrastrarlas resucitaría unidades que no existen.
          · Un conteo es un recuento FISICO. Precargar el resultado del
            mes pasado invita a confirmarlo sin mirar, que es justo lo
            que un inventario tiene que evitar.

        Las líneas nuevas nacen con los tres estados a cero. Quien cuenta
        reparte el total; el sistema no se lo adivina.
        """
        for conteo in self:
            conteo._biocreto_sincronizar_lineas()

    def _biocreto_sincronizar_lineas(self):
        """El trabajo real del compute. Idempotente: si no hay nada que
        cambiar NO escribe, y por eso se puede llamar también al abrir el
        formulario sin ensuciar el `write_date` de cada visita."""
        for conteo in self:
            if conteo.state in BIOCRETO_ESTADOS_CERRADOS:
                continue
            if not conteo.department_id or not conteo.ubicacion_id:
                # Sin área o sin ubicación configurada no hay de dónde
                # leer. NO se vacían las líneas que hubiera: el aviso lo
                # da `action_enviar` con un UserError que explica dónde
                # se configura.
                continue

            stock = conteo._biocreto_stock_por_producto()
            comandos = []
            ya_estan = conteo.env['product.product']

            for linea in conteo.linea_ids:
                producto = linea.producto_id
                if producto and producto in stock:
                    ya_estan |= producto
                    # El total se refresca SOLO si nadie ha escrito en la
                    # línea. Con datos, ni las cantidades ni el motivo se
                    # tocan: son el recuento de una persona.
                    if not linea.biocreto_tiene_datos:
                        cantidad = stock[producto]
                        if float_compare(linea.total, cantidad,
                                         precision_digits=2) != 0:
                            comandos.append((1, linea.id, {'total': cantidad}))
                elif not linea.biocreto_tiene_datos:
                    # Ya no está en el área y nadie la tocó: sobra.
                    comandos.append((2, linea.id))
                elif producto:
                    # Ya no está PERO tiene datos: se queda. Alguien contó
                    # algo ahí y borrarlo perdería su trabajo sin avisar.
                    ya_estan |= producto

            for producto, cantidad in sorted(
                    stock.items(), key=lambda kv: kv[0].display_name or ''):
                if producto in ya_estan:
                    continue
                comandos.append((0, 0, {
                    'producto_id': producto.id,
                    'total': cantidad,
                    # La marca de origen. Ver la nota del campo.
                    'biocreto_manual': False,
                    'cant_bueno': 0.0,
                    'cant_regular': 0.0,
                    'cant_malogrado': 0.0,
                    'motivo': False,
                }))

            if comandos:
                conteo.linea_ids = comandos

    # ═════════════════════════════════════════════════════════════════
    # VALIDACIONES  (en métodos de acción, NUNCA en @api.constrains)
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_exigir_area_libre(self, accion='crear'):
        """Un área no puede tener dos conteos abiertos a la vez.

        Abierto = `borrador` o `enviado`. Dos documentos vivos de la
        misma área compiten por el mismo stock y el segundo en validarse
        desecharía unidades que el primero ya dio de baja.

        v19.0.3.1.0 — `RedirectWarning` en vez de `UserError`: el aviso
        lleva un botón «Ir al conteo abierto» que abre ESE registro. Antes
        el usuario leía el número y tenía que salir a buscarlo a la lista.

        v19 acepta un DICCIONARIO de acción, no solo un id:
          · `odoo/exceptions.py:35` — `__init__(self, message, action,
            button_text, additional_context=None)`;
          · `web/static/src/core/errors/error_dialogs.js:195` — el botón
            hace `actionService.doAction(this.actionId, …)`, y `doAction`
            acepta el diccionario tal cual (`:192` incluso prevé un `help`
            dentro de él);
          · precedente nativo: `account/models/account_move_line.py:3064`.

        `accion` solo cambia el final del mensaje. La regla es la misma
        venga de donde venga: `create`, `write` al cambiar de área, o
        `action_enviar`.

        Si hay MÁS de un conteo abierto de la misma área —datos anteriores
        a esta regla—, se enlaza el más reciente y se dice cuántos hay.
        """
        estados = dict(self._fields['state'].selection)
        for conteo in self:
            if conteo.state in ('validado', 'rechazado'):
                continue
            abiertos = self.search([
                ('id', '!=', conteo.id),
                ('department_id', '=', conteo.department_id.id),
                ('company_id', '=', conteo.company_id.id),
                ('state', 'in', ('borrador', 'enviado')),
            ], order='fecha desc, id desc')
            if not abiertos:
                continue
            otro = abiertos[0]
            if accion == 'enviar':
                cierre = _("Termínelo o envíelo antes de enviar este.")
            else:
                cierre = _("Termínelo o envíelo antes de crear otro.")
            mensaje = _(
                "El área %(area)s ya tiene un conteo abierto: %(otro)s "
                "(%(estado)s). %(cierre)s",
                area=conteo.department_id.name, otro=otro.name,
                estado=estados[otro.state], cierre=cierre)
            if len(abiertos) > 1:
                mensaje += "\n\n" + _(
                    "Hay %(n)s conteos abiertos de esta área; el botón abre "
                    "el más reciente.", n=len(abiertos))
            raise RedirectWarning(mensaje, {
                'type': 'ir.actions.act_window',
                'name': otro.name,
                'res_model': self._name,
                'res_id': otro.id,
                'view_mode': 'form',
                # La MISMA vista de formulario que fijan las dos acciones
                # del menú, no la que Odoo elija por defecto.
                'views': [[self.env.ref(
                    'biocreto_requerimientos.'
                    'biocreto_inventario_conteo_view_form').id, 'form']],
                'target': 'current',
            }, _("Ir al conteo abierto"))

    def _biocreto_exigir_ubicacion(self):
        """El área tiene que tener su ubicación de activos configurada.

        Sin ella no hay de dónde leer el stock, y el error tiene que
        decir dónde se arregla: quien inventaría un área no suele saber
        que eso vive en la ficha del departamento.
        """
        self.ensure_one()
        if not self.department_id:
            raise UserError(_("Elija primero el área que se va a inventariar."))
        if not self.ubicacion_id:
            raise UserError(_(
                "El área «%(area)s» no tiene configurada su «Ubicación de "
                "activos», así que no hay de dónde leer las existencias.\n\n"
                "Se configura en Empleados → Configuración → Departamentos → "
                "%(area)s, campo «Ubicación de activos».",
                area=self.department_id.name))

    def _biocreto_validar(self):
        """Las tres validaciones, todas a la vez.

        Se acumulan y se lanzan en UN solo UserError en vez de reventar
        en la primera. Un conteo de 40 líneas con 6 descuadres son 6
        viajes de ida y vuelta si se avisa de uno en uno.
        """
        self.ensure_one()
        problemas = []
        stock = self._biocreto_stock_por_producto()

        for linea in self.linea_ids:
            nombre = linea.producto_id.display_name or _("(sin producto)")
            suma = linea.cant_bueno + linea.cant_regular + linea.cant_malogrado

            # 1) La suma de los tres estados tiene que dar el total.
            if float_compare(suma, linea.total, precision_digits=2) != 0:
                problemas.append(_(
                    "· %(prod)s: los estados suman %(suma)s y el total es "
                    "%(total)s (diferencia de %(dif)s).",
                    prod=nombre,
                    suma=_biocreto_num(suma),
                    total=_biocreto_num(linea.total),
                    dif=_biocreto_num(suma - linea.total)))

            # 2) Unidades fuera de Bueno exigen motivo.
            if (linea.cant_regular + linea.cant_malogrado) > 0 \
                    and not (linea.motivo or '').strip():
                problemas.append(_(
                    "· %(prod)s: tiene %(fuera)s unidades en Regular o "
                    "Malogrado y no indica el motivo.",
                    prod=nombre,
                    fuera=_biocreto_num(
                        linea.cant_regular + linea.cant_malogrado)))

            # 3) El total no puede pasarse del stock real de la ubicacion.
            #    EXCEPCION: las lineas agregadas a mano. Existen justo
            #    para registrar lo que el sistema no sabe que esta ahi,
            #    asi que compararlas con el stock las haria inutiles.
            if not linea.biocreto_manual:
                real = stock.get(linea.producto_id, 0.0)
                if float_compare(linea.total, real, precision_digits=2) > 0:
                    problemas.append(_(
                        "· %(prod)s: el total registrado (%(total)s) supera el "
                        "stock de la ubicación (%(real)s).",
                        prod=nombre,
                        total=_biocreto_num(linea.total),
                        real=_biocreto_num(real)))

        if problemas:
            raise UserError(_(
                "El conteo %(nombre)s no cuadra:\n\n%(detalle)s",
                nombre=self.name, detalle="\n".join(problemas)))
        return True

    def _biocreto_exigir_validador(self):
        """Solo el grupo validador valida o rechaza.

        Se pregunta SOLO por `group_inventario_validador`. Hoy ese grupo
        lo implica `group_requerimiento_manager`, asi que validan los
        administradores; el dia que exista la figura del jefe de area
        basta con meter gente en el grupo nuevo y ESTE CODIGO NO CAMBIA.
        """
        if not self.env.user.has_group(
                'biocreto_requerimientos.group_inventario_validador'):
            raise UserError(_(
                "No tiene permiso para validar ni rechazar conteos de "
                "activos.\n\nHace falta el perfil «Validador de inventario "
                "de activos»."))

    # ═════════════════════════════════════════════════════════════════
    # LAS ACCIONES DEL FLUJO
    # ═════════════════════════════════════════════════════════════════
    def action_enviar(self):
        """Cierra el conteo y lo manda a validar."""
        self.ensure_one()
        if self.state in BIOCRETO_ESTADOS_CERRADOS:
            raise UserError(_(
                "El conteo %(nombre)s ya está en estado «%(estado)s».",
                nombre=self.name,
                estado=dict(self._fields['state'].selection)[self.state]))
        self._biocreto_exigir_ubicacion()
        self._biocreto_exigir_area_libre(accion='enviar')
        if not self.linea_ids:
            raise UserError(_(
                "El conteo %s no tiene ninguna línea que enviar.", self.name))
        self._biocreto_validar()
        self.state = 'enviado'
        self.message_post(body=_(
            "Conteo enviado a validación. %(prod)s productos, "
            "%(uds)s unidades a dar de baja.",
            prod=self.biocreto_baja_productos,
            uds=_biocreto_num(self.biocreto_baja_unidades)))
        return True

    def action_validar(self):
        """Aprueba el conteo y ejecuta las bajas. TODO O NADA.

        No hay validación por línea ni parcial: el documento se aprueba
        entero o no se aprueba. Y las bajas se ejecutan AQUI, nunca al
        enviar: si se crearan al enviar, un conteo rechazado dejaría
        desechos hechos sobre stock real que habría que revertir a mano,
        y una baja validada no se revierte —se corrige con un ajuste.
        """
        self.ensure_one()
        self._biocreto_exigir_validador()
        if self.state != 'enviado':
            raise UserError(_(
                "Solo se valida un conteo enviado. %(nombre)s está en "
                "«%(estado)s».", nombre=self.name,
                estado=dict(self._fields['state'].selection)[self.state]))

        scraps = self._biocreto_generar_desechos()
        self.state = 'validado'
        self.biocreto_motivo_rechazo = False
        if scraps:
            self.message_post(body=_(
                "Conteo validado. %(n)s desecho(s) generado(s): %(refs)s",
                n=len(scraps), refs=", ".join(scraps.mapped('name'))))
        else:
            self.message_post(body=_(
                "Conteo validado. No había unidades en Malogrado, así que no "
                "se generó ningún desecho."))
        return True

    def action_rechazar(self):
        """Abre el diálogo que pide el motivo. El rechazo lo hace él."""
        self.ensure_one()
        self._biocreto_exigir_validador()
        if self.state != 'enviado':
            raise UserError(_(
                "Solo se rechaza un conteo enviado. %(nombre)s está en "
                "«%(estado)s».", nombre=self.name,
                estado=dict(self._fields['state'].selection)[self.state]))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Rechazar el conteo %s", self.name),
            'res_model': 'biocreto.inventario.rechazo.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {'default_conteo_id': self.id},
        }

    def _biocreto_rechazar(self, motivo):
        """El rechazo de verdad. Lo llama el diálogo, nunca la vista."""
        self.ensure_one()
        self._biocreto_exigir_validador()
        motivo = (motivo or '').strip()
        if not motivo:
            raise UserError(_("Escriba el motivo del rechazo."))
        self.state = 'rechazado'
        self.biocreto_motivo_rechazo = motivo
        # El campo se sobrescribe en el siguiente rechazo; el chatter no.
        # Por eso van los dos: el campo para verlo arriba del formulario,
        # el mensaje para que quede el historial con autor y fecha.
        self.message_post(body=_(
            "<b>Conteo rechazado.</b><br/>Motivo: %s", motivo))
        return True

    def action_imprimir(self):
        """Imprime ESTE conteo.

        En `borrador` NO valida: la hoja se imprime precisamente para
        salir a contar con ella en la mano, antes de que los números
        estén puestos, y sale rotulada «BORRADOR». En cualquier otro
        estado sí se validan las tres reglas antes de imprimir.
        """
        self.ensure_one()
        if self.state != 'borrador':
            self._biocreto_validar()
        return self.env.ref(
            'biocreto_requerimientos.action_report_inventario_activos'
        ).report_action(self, data={'estado': 'todos'})

    def action_ver_desechos(self):
        """Botón inteligente: los `stock.scrap` que generó este conteo."""
        self.ensure_one()
        scraps = self._biocreto_scraps()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Desechos de %s", self.name),
            'res_model': 'stock.scrap',
            'view_mode': 'list,form',
            'domain': [('id', 'in', scraps.ids)],
            'context': {'create': False},
        }

    # ═════════════════════════════════════════════════════════════════
    # LAS BAJAS
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_ubicacion_desecho(self):
        """La ubicación de desecho de la compañía. Obligatoria.

        NO se cae al defecto de Odoo. `stock.scrap._compute_scrap_location_id`
        (stock_scrap.py:87-98) elige la ubicación `inventory` de MENOR ID
        de la compañía, que en esta base es «Inventory adjustment» (id
        11) — la contrapartida de los ajustes de inventario. Dejar que
        las bajas caigan ahí las mezclaría con las correcciones de stock
        y haría ilegible el histórico de ajustes.
        """
        self.ensure_one()
        ubicacion = self.company_id.biocreto_ubicacion_desecho
        if not ubicacion:
            raise UserError(_(
                "La compañía «%(compania)s» no tiene configurada su "
                "«Ubicación de desecho», y sin ella no se pueden dar de baja "
                "los activos malogrados.\n\n"
                "Se configura en Ajustes → Usuarios y compañías → Compañías "
                "→ %(compania)s, apartado BIOCRETO.",
                compania=self.company_id.name))
        return ubicacion

    def _biocreto_generar_desechos(self):
        """Un `stock.scrap` validado por cada línea con Malogrado.

        EL ORIGEN ES EL AREA, no `WH/Existencias`. El activo malogrado
        está físicamente en el área: descontarlo del almacén lo dejaría
        en negativo allí y las unidades seguirían apareciendo en el área.
        `stock.scrap.location_id` solo exige `usage='internal'`
        (stock_scrap.py:39-42), y las ubicaciones de área lo son, así que
        que no pertenezcan a ningún almacén es indiferente.

        Se valida en el momento con `do_scrap()`, que crea el movimiento,
        lo pasa a `done` y deja el scrap en `done` (stock_scrap.py:152-162).
        """
        self.ensure_one()
        lineas = self.linea_ids.filtered(
            lambda linea: linea.cant_malogrado > 0 and linea.producto_id)
        if not lineas:
            return self.env['stock.scrap']

        origen = self.ubicacion_id
        if not origen:
            self._biocreto_exigir_ubicacion()
        destino = self._biocreto_ubicacion_desecho()

        Scrap = self.env['stock.scrap']
        creados = Scrap
        for linea in lineas:
            scrap = Scrap.create({
                'product_id': linea.producto_id.id,
                'product_uom_id': linea.producto_id.uom_id.id,
                'scrap_qty': linea.cant_malogrado,
                'location_id': origen.id,
                'scrap_location_id': destino.id,
                'company_id': self.company_id.id,
                'origin': self.name,
                'biocreto_conteo_linea_id': linea.id,
            })
            scrap.do_scrap()
            if scrap.state != 'done':
                raise UserError(_(
                    "El desecho de «%(prod)s» quedó en estado «%(estado)s» en "
                    "vez de «done». No se ha validado nada: revise el stock "
                    "del área.",
                    prod=linea.producto_id.display_name, estado=scrap.state))
            # Las especificaciones de baja van al CHATTER del scrap, que
            # hereda mail.thread (stock_scrap.py:11). NO se crean
            # etiquetas al vuelo con este texto: `stock.scrap.reason.tag`
            # tiene UNIQUE(name) (:242-245) y acabarían cientos de
            # etiquetas de un solo uso.
            if (linea.motivo or '').strip():
                scrap.message_post(body=_(
                    "<b>Baja del conteo %(conteo)s</b> (área %(area)s).<br/>"
                    "Especificaciones: %(motivo)s",
                    conteo=self.name, area=self.department_id.name,
                    motivo=linea.motivo.strip()))
            creados |= scrap
        return creados

    # ═════════════════════════════════════════════════════════════════
    # LA SINCRONIZACION AL ABRIR EL FORMULARIO
    # ═════════════════════════════════════════════════════════════════
    def web_read(self, specification):
        """Pone las líneas al día al abrir un borrador en el formulario.

        POR QUE HACE FALTA ESTE GANCHO
        ------------------------------
        `_compute_linea_ids` depende de `department_id`, así que dispara
        al crear el conteo y al cambiar de área — pero NO al volver a
        abrir un borrador que ya existía. Y ese es justo el caso que
        importa: se entrega un activo nuevo al área el martes y el jueves
        alguien reabre el conteo que dejó a medias. Sin este gancho, el
        activo nuevo no aparecería nunca y haría falta el botón «Cargar
        activos» que este cambio vino a quitar.

        Un `@api.depends` no puede resolverlo: el conteo no depende de
        `stock.quant` por ninguna relación que el ORM pueda seguir.

        POR QUE AQUI Y CON ESTAS TRES CONDICIONES
        -----------------------------------------
        `web_read` es el punto por el que el cliente web lee un registro,
        y sincronizar ESCRIBE. Escribir durante una lectura es algo que
        hay que acotar, y se acota en tres ejes:

          · UN SOLO registro (`len(self) == 1`): descarta la vista de
            lista, que lee decenas de conteos de golpe;
          · la especificación tiene que pedir `linea_ids`: solo el
            FORMULARIO lo pide, la lista no;
          · solo `borrador` y `rechazado`: los cerrados ni se miran, y
            esa guarda vive además dentro de `_biocreto_sincronizar_lineas`.

        Y la sincronización es IDEMPOTENTE: si no hay nada que agregar ni
        que quitar no ejecuta ningún `write`, así que abrir el mismo
        conteo diez veces no toca la base diez veces.
        """
        if (len(self) == 1
                and isinstance(specification, dict)
                and 'linea_ids' in specification
                and self.state in ('borrador', 'rechazado')):
            self._biocreto_sincronizar_lineas()
        return super().web_read(specification)

    # ═════════════════════════════════════════════════════════════════
    # CANDADO DE EDICION
    # ═════════════════════════════════════════════════════════════════
    # Los estados cerrados no se editan. El `readonly` de la vista ya lo
    # impide desde la interfaz, pero no detiene un `write` por codigo ni
    # una importacion, que es justo como se estropeo la linea de
    # movimiento de la silla en septiembre.
    #
    # `state` y los campos del propio flujo quedan fuera: son los que
    # mueven el documento.
    BIOCRETO_CAMPOS_LIBRES = {
        'state', 'biocreto_motivo_rechazo', 'message_ids', 'message_follower_ids',
        'message_main_attachment_id', 'activity_ids', 'message_attachment_count',
        'access_token',
    }

    def write(self, vals):
        tocados = set(vals) - self.BIOCRETO_CAMPOS_LIBRES
        if tocados:
            cerrados = self.filtered(
                lambda c: c.state in BIOCRETO_ESTADOS_CERRADOS)
            if cerrados:
                raise UserError(_(
                    "El conteo %(nombre)s está en estado «%(estado)s» y ya no "
                    "se edita.\n\nUn conteo enviado está esperando validación, "
                    "y uno validado ya dio de baja sus activos: es la foto de "
                    "un período cerrado.",
                    nombre=cerrados[0].name,
                    estado=dict(self._fields['state'].selection)[
                        cerrados[0].state]))

        # v19.0.3.1.0 — la regla del área también al CAMBIAR de área.
        # Solo los registros cuyo valor cambia DE VERDAD: reescribir el
        # mismo departamento (el cliente web lo reenvía a menudo junto con
        # otros campos) no debe disparar el aviso. Se calcula ANTES del
        # `super()`, que es cuando todavía se ve el valor viejo.
        cambian_area = self.browse()
        if 'department_id' in vals:
            cambian_area = self.filtered(
                lambda c: c.department_id.id != vals['department_id'])
        resultado = super().write(vals)
        # Y se comprueba DESPUÉS, con el área nueva ya escrita: la regla
        # mira `conteo.department_id`. Si salta, la transacción entera se
        # deshace, incluidas las líneas que el compute recargó para el
        # área nueva.
        if cambian_area:
            cambian_area._biocreto_exigir_area_libre()
        return resultado

    # ═════════════════════════════════════════════════════════════════
    # HELPER DE LA PLANTILLA
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_fmt(self, valor):
        """Numero sin decimales cuando es entero, para el PDF.

        Vive en el MODELO y no en el QWeb porque una tabla de 14 columnas
        con 40 filas lo llama seis veces por fila: repetir la expresion
        en la plantilla la volveria ilegible. Es el mismo criterio de
        `_biocreto_usuarios_texto` del consolidado.
        """
        return _biocreto_num(valor or 0.0)


class BiocretoInventarioConteoLinea(models.Model):
    _name = 'biocreto.inventario.conteo.linea'
    _description = 'Línea del inventario de activos'
    _order = 'conteo_id, id'

    conteo_id = fields.Many2one(
        'biocreto.inventario.conteo', string="Conteo",
        required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string="Compañía",
        related='conteo_id.company_id', store=True, index=True)
    state = fields.Selection(
        related='conteo_id.state', string="Estado del conteo", store=True)

    producto_id = fields.Many2one(
        'product.product', string="Material", required=True,
        check_company=True, ondelete='restrict',
        domain="[('biocreto_es_activo', '=', True)]")

    # ─────────────────────────────────────────────────────────────────
    # AUTOMATICA vs. AGREGADA A MANO
    #
    # No hay forma de deducirlo del contenido de la linea: un producto
    # que tambien existe en el stock puede haberse tecleado a mano, y uno
    # cargado puede haber quedado con el total editado. Asi que se marca
    # en el momento de nacer, que es el unico instante en que se sabe.
    #
    # El default es True — MANUAL — y no False, y esto es deliberado:
    # `_compute_linea_ids` pone explicitamente False en cada linea que
    # crea, mientras que una linea tecleada en la lista del formulario
    # nace con el default. Poniendo el default en True, cualquier via de
    # creacion que no sea el compute queda marcada como manual sin tener
    # que enumerarlas (importacion CSV, creacion por API, duplicado de
    # linea con el boton de la lista). El criterio prudente es el
    # contrario al que parece: una linea mal marcada como manual solo se
    # salta la validacion de stock; una mal marcada como automatica
    # bloquearia un conteo legitimo.
    # ─────────────────────────────────────────────────────────────────
    biocreto_manual = fields.Boolean(
        string="Agregada a mano", default=True, copy=True,
        help="Marcada: la línea la escribió una persona y no se compara con "
             "el stock del sistema. Desmarcada: vino de la carga automática.")

    total = fields.Float(string="Total", digits='Product Unit of Measure')
    cant_bueno = fields.Float(
        string="Bueno", digits='Product Unit of Measure')
    cant_regular = fields.Float(
        string="Regular", digits='Product Unit of Measure')
    cant_malogrado = fields.Float(
        string="Malogrado", digits='Product Unit of Measure')
    motivo = fields.Text(string="Especificaciones de baja")

    # ─────────────────────────────────────────────────────────────────
    # "LINEA CON DATOS": lo que la carga automatica NO puede tocar.
    #
    # Almacenado porque `_compute_linea_ids` lo consulta linea a linea en
    # cada recarga; sin `store` seria un compute por fila en cada pasada.
    #
    # Cuenta como dato CUALQUIERA de estas tres cosas:
    #
    #   · una cantidad de estado distinta de cero — las tres nacen a 0 y
    #     el sistema nunca las escribe, asi que un valor ahi solo puede
    #     haberlo puesto una persona;
    #   · un motivo escrito — es texto libre, no lo genera nada;
    #   · la marca de linea agregada a mano — la linea entera es obra de
    #     una persona, aunque todavia no le haya puesto numeros.
    #
    # `total` NO cuenta, y es la decision que importa: lo escribe la
    # carga automatica en cada pasada, asi que tomarlo como dato del
    # usuario congelaria TODAS las lineas desde la primera carga y la
    # sincronizacion no volveria a funcionar nunca.
    # ─────────────────────────────────────────────────────────────────
    biocreto_tiene_datos = fields.Boolean(
        string="Tiene datos registrados", compute='_compute_biocreto_tiene_datos',
        store=True,
        help="Marcada cuando alguien ya registró algo en esta línea. Las "
             "líneas con datos no se modifican al recargar los activos del "
             "área.")

    @api.depends('cant_bueno', 'cant_regular', 'cant_malogrado', 'motivo',
                 'biocreto_manual')
    def _compute_biocreto_tiene_datos(self):
        for linea in self:
            linea.biocreto_tiene_datos = bool(
                linea.cant_bueno or linea.cant_regular or linea.cant_malogrado
                or (linea.motivo or '').strip()
                or linea.biocreto_manual)

    # ─────────────────────────────────────────────────────────────────
    # EL ENLACE CON LAS BAJAS
    #
    # La clave ajena vive en `stock.scrap` y apunta a ESTA LINEA, no al
    # conteo. Una sola clave resuelve las dos direcciones: desde la linea
    # se llega por este One2many, y desde el desecho por el Many2one. Un
    # Many2one aqui habria obligado a un segundo campo en stock.scrap
    # para poder volver, y dos claves para una relacion acaban
    # divergiendo.
    #
    # Apunta a la LINEA y no al conteo porque una baja nace de un
    # producto concreto: desde el desecho se quiere saber de que material
    # y con que especificaciones, no solo de que documento.
    # ─────────────────────────────────────────────────────────────────
    biocreto_scrap_ids = fields.One2many(
        'stock.scrap', 'biocreto_conteo_linea_id', string="Desechos",
        readonly=True)

    # ── De la ficha del producto, solo lectura ──
    # `related` y no copia del valor: si alguien corrige la marca en la
    # ficha, los conteos se corrigen solos. El dato de negocio del conteo
    # son las cantidades, no las caracteristicas.
    codigo = fields.Char(
        string="Código", related='producto_id.default_code', readonly=True)
    uom_name = fields.Char(
        string="Und.", related='producto_id.uom_id.name', readonly=True)
    marca = fields.Char(
        string="Marca", related='producto_id.biocreto_marca', readonly=True)
    modelo = fields.Char(
        string="Modelo", related='producto_id.biocreto_modelo', readonly=True)
    serie = fields.Char(
        string="N° de serie", related='producto_id.biocreto_serie',
        readonly=True)
    color = fields.Char(
        string="Color", related='producto_id.biocreto_color', readonly=True)
    dimensiones = fields.Char(
        string="Dimensiones", related='producto_id.biocreto_dimensiones',
        readonly=True)
