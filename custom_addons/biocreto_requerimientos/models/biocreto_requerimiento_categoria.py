from odoo import _, api, fields, models

# Copiada de approvals/models/approval_category.py:9-12, con etiquetas en es_PE.
CATEGORY_SELECTION = [
    ('required', 'Obligatorio'),
    ('optional', 'Opcional'),
    ('no', 'Ninguno')]


class BiocretoRequerimientoCategoria(models.Model):
    _name = 'biocreto.requerimiento.categoria'
    _description = 'Categoría de Requerimiento'
    _order = 'sequence, id'

    _check_company_auto = True

    name = fields.Char(string="Nombre", translate=True, required=True)
    description = fields.Char(string="Descripción", translate=True)
    # Sin default: las imagenes se proveeran despues.
    image = fields.Binary(string="Imagen")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="Secuencia")
    # NO required y sin default: la categoria es compartida entre plantas.
    # La regla multiempresa la deja visible con company_id = False.
    company_id = fields.Many2one(
        'res.company', string="Compañía", copy=False, index=True,
        help="Dejar vacío para compartir la categoría entre todas las plantas.")

    has_date = fields.Selection(CATEGORY_SELECTION, string="Tiene Fecha", default='no', required=True)
    has_period = fields.Selection(CATEGORY_SELECTION, string="Tiene Periodo", default='no', required=True)
    has_quantity = fields.Selection(CATEGORY_SELECTION, string="Tiene Cantidad", default='no', required=True)
    has_amount = fields.Selection(CATEGORY_SELECTION, string="Tiene Importe", default='no', required=True)
    has_reference = fields.Selection(
        CATEGORY_SELECTION, string="Tiene Referencia", default='no', required=True,
        help="Una referencia adicional que se indica en la solicitud.")
    has_partner = fields.Selection(CATEGORY_SELECTION, string="Tiene Contacto", default='no', required=True)
    has_location = fields.Selection(CATEGORY_SELECTION, string="Tiene Ubicación", default='no', required=True)
    has_product = fields.Selection(
        CATEGORY_SELECTION, string="Tiene Producto", default='no', required=True,
        help="Productos adicionales que se detallan en la solicitud.")
    # Usa la MISMA constante que los nueve has_*: las etiquetas coinciden
    # exactamente ('Obligatorio' / 'Opcional' / 'Ninguno'), asi que declarar
    # una lista suelta solo duplicaria texto a traducir.
    #
    # El tercer valor 'no' es una extension propia: el nativo de Aprobaciones
    # (approvals/models/approval_category.py:59-61) solo contempla
    # required/optional porque alli el adjunto no se puede desactivar. Con
    # 'no' el formulario de solicitud esconde los dos widgets attach_document.
    #
    # El default sigue siendo 'optional' para no alterar las categorias
    # existentes, y el registro de datos lleva noupdate="1"
    # (data/biocreto_requerimiento_categoria_data.xml:3), asi que una
    # actualizacion del modulo tampoco pisa el valor que elija el usuario.
    requirer_document = fields.Selection(
        CATEGORY_SELECTION, string="Documentos", default='optional',
        required=True)

    automated_sequence = fields.Boolean(
        string="¿Numeración automática?",
        help="Si está marcado, las solicitudes reciben un código generado "
             "automáticamente a partir del código indicado.")
    sequence_code = fields.Char(string="Código")

    solicitud_count = fields.Integer(
        string="Solicitudes por revisar", compute='_compute_solicitud_count')

    def _compute_solicitud_count(self):
        """Un solo _read_group para todas las tarjetas del tablero.
        Patron anti-N+1 copiado de approvals/models/approval_category.py:72-77.
        """
        domain = [('state', '=', 'enviado')]
        data = self.env['biocreto.requerimiento']._read_group(
            domain, ['categoria_id'], ['__count'])
        mapped = {categoria.id: count for categoria, count in data}
        for categoria in self:
            categoria.solicitud_count = mapped.get(categoria.id, 0)

    def create_solicitud(self):
        """Boton "Nueva solicitud" del tablero.

        No crea nada en BD: devuelve una accion que abre el formulario vacio
        con los defaults por contexto. Copiado de
        approvals/models/approval_category.py:148-162.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "biocreto.requerimiento",
            "views": [[False, "form"]],
            "context": {
                'default_name': _('Nuevo') if self.automated_sequence else self.name,
                'default_categoria_id': self.id,
                'default_solicitante_id': self.env.user.id,
                'default_state': 'borrador',
            },
        }
