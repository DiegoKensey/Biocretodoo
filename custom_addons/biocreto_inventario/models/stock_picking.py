from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ─────────────────────────────────────────────────────────────────
    # Documentos de sustento.
    #
    # Se pueden agregar líneas a una recepción YA VALIDADA: la factura
    # del proveedor llega semanas después. Comprobado que nada lo impide —
    # `stock.picking.write()` (stock/models/stock_picking.py:1133-1135)
    # solo bloquea `picking_type_id` en estado done/cancel; el resto de
    # los `readonly` de la vista nativa son campo a campo. Por eso NINGÚN
    # campo de este módulo declara `readonly` por estado: hacerlo sería
    # romper el caso de la factura tardía.
    # ─────────────────────────────────────────────────────────────────
    biocreto_documento_ids = fields.One2many(
        comodel_name='biocreto.recepcion.documento',
        inverse_name='picking_id',
        string="Documentos de sustento",
        copy=False,
    )

    # ─────────────────────────────────────────────────────────────────
    # Ingreso.
    #
    # `biocreto_fecha_ingreso` NO es `date_done`. `date_done`
    # (stock_picking.py:606) es «Date of Transfer», la fecha en que se
    # pulsó Validar, y la escribe el sistema en `_action_done` (:1268);
    # la lista nativa la muestra como «Effective Date». Esta otra es
    # cuándo entró físicamente el camión, que puede ser días antes.
    # La etiqueta evita a propósito la palabra «recepción» para que nadie
    # las confunda.
    # ─────────────────────────────────────────────────────────────────
    biocreto_nro_control_ingreso = fields.Char(
        string="N° de control de ingreso",
        copy=False,
    )
    biocreto_evidencia_ingreso = fields.Binary(
        string="Evidencia de ingreso",
        attachment=True,
        copy=False,
    )
    biocreto_evidencia_ingreso_filename = fields.Char(copy=False)
    biocreto_fecha_ingreso = fields.Datetime(
        string="Ingreso a planta",
        default=fields.Datetime.now,
        copy=False,
        index=True,
        help="Fecha y hora en que el material entró físicamente a planta. "
             "Es editable siempre y no tiene relación con la fecha en que "
             "se validó la transferencia en el sistema.",
    )

    # ─────────────────────────────────────────────────────────────────
    # Transporte.
    # ─────────────────────────────────────────────────────────────────
    biocreto_placa = fields.Char(string="Placa", copy=False)
    biocreto_conductor_id = fields.Many2one(
        comodel_name='res.partner',
        string="Conductor",
        copy=False,
        # SIN `check_company`: `res.partner.company_id` no es required y
        # los contactos se comparten entre compañías. Un check_company
        # rechazaría los contactos sin compañía, que son la norma.
    )
    biocreto_cantera = fields.Char(string="Cantera", copy=False)

    # `stock.picking` NO tiene `currency_id` — comprobado contra el
    # registro. Un `Monetary` sin `currency_field` rompe la vista al
    # construirla, así que el campo de moneda se declara aquí, colgando
    # de la compañía del picking.
    biocreto_currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        string="Moneda",
        readonly=True,
    )
    biocreto_flete = fields.Monetary(
        string="Flete",
        currency_field='biocreto_currency_id',
        copy=False,
        help="Importe del flete. Es informativo: NO se suma al costo del "
             "material ni genera un landed cost.",
    )
    biocreto_flete_responsable = fields.Char(
        string="Responsable del flete",
        copy=False,
    )

    # Sin `default`: se marca a mano, cada vez. Marcarlo por defecto
    # convertiría la excepción en la norma.
    biocreto_sin_comprobante = fields.Boolean(
        string="Sin comprobante",
        copy=False,
        help="El proveedor entregó el material sin comprobante de pago.",
    )

    @api.onchange('partner_id')
    def _onchange_biocreto_partner_conductor(self):
        """Limpia el conductor SOLO si dejó de pertenecer al proveedor.

        El `domain` de la vista filtra el desplegable pero no valida lo ya
        guardado: cambiando el proveedor, el conductor anterior se
        quedaría apuntando a un contacto de otra empresa sin que nadie
        avise. Si el conductor sí cuelga del proveedor nuevo, se respeta.
        """
        for picking in self:
            conductor = picking.biocreto_conductor_id
            if not conductor:
                continue
            if conductor.parent_id != picking.partner_id:
                picking.biocreto_conductor_id = False
