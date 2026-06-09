from odoo import api, fields, models


class BiocretoDocumentoControl(models.Model):
    _name = 'biocreto.documento.control'
    _description = 'Documento de Control SIG'
    _inherit = ['mail.thread']
    _order = 'codigo'

    name = fields.Char(
        string="Nombre del documento",
        required=True,
        tracking=True,
    )
    codigo = fields.Char(
        string="Codigo",
        required=True,
        tracking=True,
        help="Ej.: BC-GC-FR-09",
    )
    codigo_documento = fields.Char(
        string="Codigo identificador (tecnico)",
        required=True,
        help="Identificador que los reportes QWeb consultan. Ej.: cotizacion_menor, contrato.",
    )
    version = fields.Char(
        string="Version",
        required=True,
        default="01",
        tracking=True,
        help="Ej.: 01",
    )
    fecha_version = fields.Date(
        string="Fecha de version",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    descripcion = fields.Text(string="Descripcion")
    pdf_oficial = fields.Binary(string="PDF oficial (formato vigente)", attachment=True)
    pdf_oficial_filename = fields.Char(string="Nombre del archivo")
    version_ids = fields.One2many(
        'biocreto.documento.control.version',
        'documento_id',
        string="Historial de versiones",
    )
    active = fields.Boolean(default=True)

    _codigo_documento_uniq = models.Constraint(
        'UNIQUE(codigo_documento)',
        'El codigo identificador (tecnico) debe ser unico.',
    )

    def write(self, vals):
        # Solo archivamos cuando cambia la VERSION (subida de version).
        # Tomamos snapshot de los valores ANTERIORES antes de llamar super.
        snapshots = {}
        if 'version' in vals:
            for doc in self:
                snapshots[doc.id] = {
                    'documento_id': doc.id,
                    'codigo': doc.codigo,
                    'version': doc.version,
                    'fecha_version': doc.fecha_version,
                    'pdf_oficial': doc.pdf_oficial,
                    'pdf_oficial_filename': doc.pdf_oficial_filename,
                }
        res = super().write(vals)
        if snapshots:
            self.env['biocreto.documento.control.version'].create(
                list(snapshots.values())
            )
        return res

    @api.model
    def get_control_for_qweb(self, codigo_documento):
        """Helper invocable desde QWeb para obtener codigo/version/fecha vigentes.

        Uso en plantilla QWeb:
            <t t-set="ctrl" t-value="env['biocreto.documento.control'].get_control_for_qweb('contrato')"/>
        """
        doc = self.search([('codigo_documento', '=', codigo_documento)], limit=1)
        if not doc:
            return {}
        return {
            'codigo': doc.codigo,
            'version': doc.version,
            'fecha_version': doc.fecha_version,
        }
