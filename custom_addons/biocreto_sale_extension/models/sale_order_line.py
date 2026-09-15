from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Helper de formato UNICO del slump. Se importa (no se reimplementa) para
# que no pueda existir una segunda forma de imprimir un slump en el sistema.
from .biocreto_slump_format import biocreto_format_slump

# Los tres nombres de categoría vendible, en un solo sitio.
from .product_category import BIOCRETO_CATEGORIAS_VENTA


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ─────────────────────────────────────────────────────────────────
    # Campo puente: lee la categoría del producto automáticamente
    # Invisible en UI. Sirve solo para condiciones de visibilidad.
    # ─────────────────────────────────────────────────────────────────
    biocreto_product_categ = fields.Char(
        related='product_id.categ_id.name',
        string="Categoría del producto",
        store=False,
    )

    # ─────────────────────────────────────────────────────────────────
    # Filtro del producto de la línea: solo las tres categorías que
    # BIOCRETO vende (Concreto, Bombeo, Servicios adicionales).
    #
    # POR QUÉ AQUÍ Y NO EN LA VISTA
    # -----------------------------
    # `sale` deja el punto de extensión abierto: el campo nativo se
    # declara con `domain=lambda self: self._domain_product_id()`
    # (odoo/addons/sale/models/sale_order_line.py:83-88) y el método
    # devuelve `[('sale_ok', '=', True)]` (:360-361). Extenderlo con
    # `super()` es aditivo y respeta a quien ya lo hubiera extendido
    # antes — `sale_renting` lo hace (:46-49).
    #
    # Viviendo en el campo, el filtro cubre TODAS las vistas de
    # sale.order.line (la lista de la orden, la vista de variante, la
    # tarjeta móvil) sin repetir el dominio en cada xpath. En la vista
    # nativa el campo NO trae `domain` propio, solo `context`
    # (odoo/addons/sale/views/sale_order_views.xml:522-528).
    #
    # POR QUÉ NO EL PATRÓN `fields.Binary` DE `biocreto_vehiculo_domain`
    # -----------------------------------------------------------------
    # Aquel dominio depende de un dato de CADA línea — la categoría de
    # flota configurada en SU compañía — y por eso necesita un compute
    # (`_compute_biocreto_vehiculo_domain`, más abajo en este archivo).
    # Este es una lista fija de tres nombres, idéntica para todas las
    # líneas: un compute solo añadiría trabajo por línea y un campo más
    # al modelo, sin ganar nada.
    #
    # ALCANCE: `sale.order.line` y nada más. `purchase.order.line` es
    # otro modelo, no hereda de éste y no tiene este método.
    #
    # Las líneas YA GUARDADAS con un producto de otra categoría no se
    # rompen: un `domain` solo restringe el desplegable del cliente web,
    # no valida lo que hay escrito.
    # ─────────────────────────────────────────────────────────────────
    def _domain_product_id(self):
        dominio = super()._domain_product_id()
        hoja = ('categ_id.name', 'in', list(BIOCRETO_CATEGORIAS_VENTA))
        if isinstance(dominio, str):
            # `sale_renting` devuelve el dominio como CADENA porque el
            # suyo referencia un campo del registro (:46-49). Hoy está
            # desinstalado, pero si se instalara, concatenar listas
            # reventaría. Se reconstruye en notación prefija quitando
            # los corchetes exteriores de la cadena de super().
            return "['&', %r, %s]" % (hoja, dominio.strip()[1:-1])
        return dominio + [hoja]

    # ─────────────────────────────────────────────────────────────────
    # Campos de CONCRETO — Many2one a los catálogos maestros.
    # v19.0.1.12.0: los tres maestros pasaron a ser GLOBALES y perdieron
    # su `company_id`. Con ello se cae aquí `check_company=True` y el
    # `domain` por compañía. No es una relajación opcional: es obligado.
    #
    # POR QUÉ `check_company` YA NO PUEDE QUEDARSE
    # -------------------------------------------
    # El ORM arma la comprobación con `_check_company_domain` del
    # comodelo (odoo/orm/models.py):
    #
    #     return Domain('company_id', 'in', to_record_ids(companies) + [False])
    #
    # es decir, siempre consulta `company_id` EN EL COMODELO. Contra un
    # modelo que ya no tiene ese campo, la evaluación revienta. Verificado
    # en shell contra dos comodelos sin `company_id`:
    #
    #     uom.uom      -> ValueError: Invalid field uom.uom.company_id
    #     res.country  -> ValueError: Invalid field res.country.company_id
    #
    # (El `+ [False]` de esa misma línea es lo que hace que un registro
    # con `company_id = False` pase siempre la validación; por eso la
    # comprobación es inofensiva mientras el campo EXISTE, y letal cuando
    # no existe.)
    #
    # El `domain` se va por lo mismo: `[('company_id', '=', company_id)]`
    # se evalúa contra el comodelo y dejaría el desplegable vacío o en
    # error. Sin él, los tres desplegables muestran la lista completa,
    # que es justo lo que se busca.
    #
    # Lo que NO cambia: la obligatoriedad condicional de la vista
    # (`biocreto_product_categ == 'Concreto'`) ni la validación de
    # `_biocreto_validate_before_confirm`. Los tres siguen siendo
    # obligatorios para confirmar una línea de Concreto.
    # ─────────────────────────────────────────────────────────────────
    biocreto_estructura = fields.Many2one(
        comodel_name='biocreto.estructura',
        string="Estructura",
    )
    biocreto_tipo_cemento = fields.Many2one(
        comodel_name='biocreto.tipo.cemento',
        string="Tipo de cemento",
    )
    biocreto_huso_tmn = fields.Many2one(
        comodel_name='biocreto.huso.tmn',
        string="Huso TMN",
    )
    # ─────────────────────────────────────────────────────────────────
    # v19.0.1.8.0: el slump del CONCRETO pasa de valor único a RANGO.
    #
    # Reemplaza al antiguo `biocreto_slump` (Float). La migración de
    # 19.0.1.8.0 vuelca cada valor viejo a min == max, de modo que el
    # computado imprime exactamente lo mismo que antes ("6\"", no
    # "6\" - 6\"") y ningún documento ya emitido cambia de aspecto.
    #
    # Dos Float tecleados y no un catálogo: el rango de concreto lo
    # negocia el vendedor obra por obra. La orden 2026-ECO-TI-0009 tiene
    # tres líneas del MISMO producto con slumps distintos, ya facturadas;
    # cerrar esto a un desplegable rompería ese caso real.
    # ─────────────────────────────────────────────────────────────────
    biocreto_slump_min = fields.Float(
        string="Slump mín. (pulg.)",
        digits=(16, 2),
    )
    biocreto_slump_max = fields.Float(
        string="Slump máx. (pulg.)",
        digits=(16, 2),
    )
    # store=True es obligatorio, no cosmético: es lo que habilita agrupar
    # y filtrar por rango en vistas lista, búsqueda y tablas dinámicas.
    # Un compute sin almacenar nunca llega al `read_group` del cliente.
    biocreto_slump_rango = fields.Char(
        string="Slump",
        compute='_compute_biocreto_slump_rango',
        store=True,
        help="Etiqueta imprimible del rango de slump. Se calcula sola desde "
             "el mínimo y el máximo; es el ÚNICO valor que se imprime en "
             "reportes.",
    )

    @api.depends('biocreto_slump_min', 'biocreto_slump_max')
    def _compute_biocreto_slump_rango(self):
        for line in self:
            line.biocreto_slump_rango = biocreto_format_slump(
                line.biocreto_slump_min, line.biocreto_slump_max,
            )

    @api.constrains('biocreto_slump_min', 'biocreto_slump_max')
    def _check_biocreto_slump_rango(self):
        """Coherencia del rango. Solo cuando los DOS extremos tienen valor.

        Con uno solo relleno no hay rango que validar: es una captura a
        medias, y bloquearla impediría guardar la cotización en borrador
        mientras se teclea. La obligatoriedad de ambos se exige al
        CONFIRMAR, en `_biocreto_validate_before_confirm`.
        """
        for line in self:
            minimo = line.biocreto_slump_min
            maximo = line.biocreto_slump_max
            if minimo and maximo and maximo < minimo:
                raise ValidationError(_(
                    "En la línea «%(prod)s» el slump máximo (%(max)g\") es "
                    "menor que el mínimo (%(min)g\"). Revise el rango.",
                    prod=line.product_id.display_name or _("(sin producto)"),
                    max=maximo, min=minimo,
                ))

    # ─────────────────────────────────────────────────────────────────
    # Campos de BOMBEO
    # ─────────────────────────────────────────────────────────────────
    biocreto_vehiculo_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string="Vehículo Asignado",
        help="Vehículo de la flota asignado al servicio de bombeo.",
    )
    biocreto_tuberia_adicional = fields.Integer(
        string="Tuberías adicionales (m)",
        default=0,
    )
    # ═════════════════════════════════════════════════════════════════
    # v19.0.1.9.0: el slump de BOMBEO apunta a la LÍNEA DE CONCRETO de
    # la propia cotización, no a un catálogo.
    #
    # Por qué no un catálogo (se probó en v19.0.1.8.0 y se descartó): un
    # registro de catálogo es COMPARTIDO. Editarlo cambia retroactivamente
    # todas las líneas que lo referencian, facturas incluidas. Con una
    # referencia a la línea de concreto, el bombeo dice exactamente el
    # slump del concreto que se está bombeando, por definición, y no hay
    # dato que mantener sincronizado a mano.
    #
    # ondelete='set null': si se borra la línea de concreto referenciada,
    # el bombeo queda sin referencia en lugar de bloquear el borrado.
    # Editar una cotización nunca debe quedar bloqueado por esto.
    # ═════════════════════════════════════════════════════════════════
    biocreto_slump_bombeable_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string="Slump bombeable",
        ondelete='set null',
        domain="[('id', 'in', biocreto_slump_bombeable_domain)]",
        help="Línea de concreto de esta misma cotización cuyo slump se "
             "bombea. El rango se toma de ella; no se teclea aparte.",
    )

    # v19.0.1.9.2: NO existe un campo `related` acompañante. UN SOLO campo
    # de bombeable en el modelo y uno solo en el formulario. El rango se
    # lee siempre a través de la relación:
    #     line.biocreto_slump_bombeable_line_id.biocreto_slump_rango
    # Consecuencia asumida: el bombeable no se puede agrupar por rango en
    # tablas dinámicas (agruparía por línea). El concreto sí conserva esa
    # capacidad, que es donde tiene valor.

    # Dominio COMPUTADO, no estático. Un dominio estático con `parent.id`
    # no resuelve en una orden todavía sin guardar (id NewId), que es
    # justo cuando el vendedor teclea las líneas. Mismo patrón que
    # `_compute_biocreto_bom_domain`, ya usado en este archivo.
    biocreto_slump_bombeable_domain = fields.Binary(
        string="Dominio slump bombeable",
        compute='_compute_biocreto_slump_bombeable_domain',
        store=False,
    )

    @api.depends('order_id.order_line.biocreto_slump_rango',
                 'order_id.order_line.product_id')
    def _compute_biocreto_slump_bombeable_domain(self):
        """IDs de las líneas de concreto de ESTA orden que tienen slump.

        Se depende de `order_id.order_line.*` para que el dominio se
        reevalúe al añadir, quitar o editar líneas sin guardar la orden.

        Sobre órdenes SIN GUARDAR, y qué se puede esperar de verdad:

          · Orden ya guardada y abierta en el formulario: sus líneas son
            NewId CON origen, y `.ids` devuelve los ids reales
            (`OriginIds`, odoo/orm/models.py:5903-5907). El dominio
            funciona. Es el caso de uso habitual.

          · Línea de concreto que NUNCA se ha guardado: no tiene id en
            base, así que `.ids` la omite y no aparece en el desplegable.
            No es una carencia de este código: NINGÚN Many2one de Odoo
            puede apuntar a un registro que aún no existe en base — el
            desplegable resuelve contra el servidor por id. Hay que
            guardar la cotización antes de asignar el slump del bombeo.
        """
        for line in self:
            candidatas = line.order_id.order_line.filtered(
                lambda l, actual=line: (
                    l != actual
                    and l.biocreto_product_categ == 'Concreto'
                    and l.biocreto_slump_rango
                )
            )
            line.biocreto_slump_bombeable_domain = candidatas.ids

    # ═════════════════════════════════════════════════════════════════
    # Etiqueta del desplegable de bombeo. CONDICIONAL:
    #
    #   · 1 sola línea de concreto candidata en la orden -> `6"`
    #     Sin prefijo: no hay nada que desambiguar y el prefijo solo
    #     sería ruido.
    #   · 2 o más candidatas -> `L1 · 6"`
    #     El prefijo es imprescindible porque dos líneas distintas pueden
    #     tener el MISMO rango y quedarían indistinguibles.
    #
    # El recuento se hace sobre las líneas de LA MISMA orden que cumplen
    # el dominio del campo, es decir, las que el usuario ve realmente en
    # el desplegable.
    #
    # Se activa SOLO bajo la clave de contexto
    # `biocreto_slump_line_label`, que la vista inyecta en ese único
    # campo. Sin ella, el display_name de sale.order.line no cambia en
    # ninguna otra parte del sistema.
    #
    # El contexto llega tanto al desplegable (name_search) como al valor
    # ya seleccionado: `web_read` aplica el `context` de la especificación
    # del campo antes de leer el display_name de los co_records
    # (odoo/addons/web/models/models.py:137-138 y :148-150).
    #
    # El prefijo es EXCLUSIVO de la pantalla. Los reportes imprimen solo
    # el rango, leído por la relación — nunca el display_name.
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_lineas_concreto_con_slump(self):
        """Líneas de CONCRETO con slump de esta orden. Fuente única.

        La consumen dos sitios y por eso vive aparte:
          · el dominio del campo (quitándole la propia línea de bombeo);
          · el recuento que decide si la etiqueta lleva prefijo.

        Devuelve el recordset, no los ids: para contar y numerar hacen
        falta los registros, y en una orden sin guardar los ids todavía
        no existen.

        Una línea de BOMBEO nunca pertenece a este conjunto, así que el
        recuento visto desde una línea de concreto coincide exactamente
        con lo que ve la línea de bombeo en su desplegable.
        """
        self.ensure_one()
        return self.order_id.order_line.filtered(
            lambda l: l.biocreto_product_categ == 'Concreto'
            and l.biocreto_slump_rango
        )

    def _biocreto_numero_linea(self):
        """Posición VISIBLE de la línea en la cotización (1-based).

        Se numera sobre las líneas de producto de la orden en el mismo
        orden en que las pinta el formulario (sequence, id), saltando
        secciones y notas — que no son líneas para el usuario.
        Deliberadamente NO se usa el id de base de datos.
        """
        self.ensure_one()
        reales = self.order_id.order_line.filtered(lambda l: not l.display_type)
        reales = reales.sorted(key=lambda l: (l.sequence, l.id))
        for indice, linea in enumerate(reales, start=1):
            if linea == self:
                return indice
        return 0

    @api.depends_context('biocreto_slump_line_label')
    def _compute_display_name(self):
        if not self.env.context.get('biocreto_slump_line_label'):
            return super()._compute_display_name()
        for line in self:
            rango = line.biocreto_slump_rango or ''
            if not rango:
                # Sin rango no hay nada que etiquetar: se deja el
                # display_name normal para no mostrar una fila muda.
                super(SaleOrderLine, line)._compute_display_name()
                continue
            # ¿Hace falta desambiguar? Solo si hay 2+ candidatas.
            candidatas = line._biocreto_lineas_concreto_con_slump()
            if len(candidatas) < 2:
                line.display_name = rango
                continue
            numero = line._biocreto_numero_linea()
            if not numero:
                line.display_name = rango
                continue
            line.display_name = "L%s · %s" % (numero, rango)

    # ─────────────────────────────────────────────────────────────────
    # Volumen operativo y costo compensado (sólo Concreto).
    # Fase 1: costo compensado se calcula con el VOLUMEN OPERATIVO
    # PLANEADO. La fase 2 (producido real) la añade biocreto_fabricacion
    # extendiendo este @api.depends y la lógica del compute.
    # ─────────────────────────────────────────────────────────────────
    biocreto_volumen_operativo = fields.Float(
        string="Volumen operativo",
        digits='Product Unit of Measure',
        help="Volumen real de producción (m³). Base del costo compensado.",
    )
    biocreto_costo_compensado = fields.Float(
        string="Costo compensado",
        compute='_compute_biocreto_costo_compensado',
        store=True,
        digits='Product Price',
        help="Precio efectivo por m³ entregado. "
             "Fase 1: usa el volumen operativo planeado. "
             "biocreto_fabricacion extenderá este compute para usar el "
             "producido real cuando la OF esté terminada.",
    )

    @api.depends('price_unit', 'product_uom_qty', 'biocreto_volumen_operativo')
    def _compute_biocreto_costo_compensado(self):
        for line in self:
            divisor = line.biocreto_volumen_operativo
            line.biocreto_costo_compensado = (
                (line.price_unit * line.product_uom_qty) / divisor
            ) if divisor else 0.0

    # ─────────────────────────────────────────────────────────────────
    # Boom (Lista de materiales nativa de mrp). Se asigna desde Laboratorio.
    # El domain por producto se aplica en la vista (reacciona a product_id).
    # ─────────────────────────────────────────────────────────────────
    bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        string="Diseño de mezcla",
        help="Diseño de mezcla (lista de materiales nativa). "
             "Se asigna en Laboratorio cuando la orden pasa al estado Programado.",
    )

    # ─────────────────────────────────────────────────────────────────
    # Tipo de colocación (sólo Concreto). Sección "Especificaciones de envío".
    # ─────────────────────────────────────────────────────────────────
    biocreto_tipo_colocacion = fields.Selection(
        selection=[
            ('directo', 'Directo'),
            ('pluma', 'Pluma'),
        ],
        string="Tipo de colocación",
    )

    # ─────────────────────────────────────────────────────────────────
    # Dominios dinámicos para Vehículo y Boom.
    #
    # Patrón canónico Odoo 19 para domains que dependen de otros campos:
    # un Binary computed sirve como contenedor del domain y la vista
    # lo referencia por nombre (domain="<field_name>"). Verificado en
    # account/models/account_tax.py:4952 (tag_ids_domain) y
    # account_intrastat/views (intrastat_code_domain).
    #
    # ¿Por qué Binary y no Char/escribir el domain como lista?
    # El widget many2one lee el campo como list-of-tuples directamente,
    # sin pasar por safe_eval del string XML. Esto permite:
    #   - usar identificadores Python normales (no hay que serializar)
    #   - retornar [] cuando no hay filtro (= mostrar todos)
    #   - retornar [('id','in',[])] para "ninguno" si fuera necesario
    # ─────────────────────────────────────────────────────────────────
    biocreto_vehiculo_domain = fields.Binary(
        compute='_compute_biocreto_vehiculo_domain',
        help="Domain dinámico para biocreto_vehiculo_id: filtra por la "
             "categoría de Bomba parametrizada en la Compañía. Si la Compañía "
             "no tiene categoría configurada, retorna [] (muestra todos).",
    )
    biocreto_bom_domain = fields.Binary(
        compute='_compute_biocreto_bom_domain',
        help="Domain dinámico para bom_id: BoMs del producto de la línea. "
             "Si no hay producto seleccionado, retorna [] (muestra todas).",
    )

    @api.depends('company_id', 'company_id.biocreto_bomba_categ_id')
    def _compute_biocreto_vehiculo_domain(self):
        for line in self:
            categ = line.company_id.biocreto_bomba_categ_id
            line.biocreto_vehiculo_domain = (
                [('category_id', '=', categ.id)] if categ else []
            )

    @api.depends('product_id', 'product_id.product_tmpl_id')
    def _compute_biocreto_bom_domain(self):
        for line in self:
            tmpl = line.product_id.product_tmpl_id
            line.biocreto_bom_domain = (
                [('product_tmpl_id', '=', tmpl.id)] if tmpl else []
            )

    # ─────────────────────────────────────────────────────────────────
    # Acceso al detalle de la línea como dialog modal
    # ─────────────────────────────────────────────────────────────────
    def action_open_biocreto_line_form(self):
        """Abre el form standalone con los grupos BIOCRETO en dialog modal.

        Al ser type="object" en una list editable, Odoo persiste la cotización
        (y la línea) ANTES de invocar el método. Esto NO genera bucle porque
        la validación dura de campos técnicos vive en action_confirm
        (sale_order.py), no en @api.constrains: guardar un borrador con
        campos técnicos vacíos no falla.
        """
        self.ensure_one()
        view = self.env.ref(
            'biocreto_sale_extension.sale_order_line_view_form_biocreto'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Detalle de línea"),
            'res_model': 'sale.order.line',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
        }
