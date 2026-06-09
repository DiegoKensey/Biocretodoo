from odoo import fields, models


class BiocretoDocumentoControlVersion(models.Model):
    _name = 'biocreto.documento.control.version'
    _description = 'Historial de Version de Documento SIG'
    _order = 'fecha_version desc, id desc'

    documento_id = fields.Many2one(
        'biocreto.documento.control',
        string="Documento",
        required=True,
        ondelete='cascade',
        index=True,
    )
    codigo = fields.Char(string="Codigo")
    version = fields.Char(string="Version")
    fecha_version = fields.Date(string="Fecha de version")
    pdf_oficial = fields.Binary(string="PDF de esta version", attachment=True)
    pdf_oficial_filename = fields.Char(string="Nombre del archivo")
