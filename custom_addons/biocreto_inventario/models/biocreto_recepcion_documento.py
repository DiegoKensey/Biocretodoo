import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.biocreto_base.models.biocreto_identificador import (
    biocreto_identificador_partner,
)

# ──────────────────────────────────────────────────────────────────────
# Abreviaturas que entran en el NOMBRE DEL ARCHIVO.
#
# Se mantienen aparte del `selection` a propósito: la etiqueta del
# desplegable es para el usuario y puede traducirse o reescribirse; la
# abreviatura forma parte del nombre de un archivo ya guardado y no debe
# moverse sin pensarlo. Si algún día cambia una, los archivos anteriores
# conservan la vieja hasta que alguien toque su línea.
# ──────────────────────────────────────────────────────────────────────
BIOCRETO_TIPOS_DOCUMENTO = [
    ('guia', "Guía de remisión"),
    ('factura', "Factura"),
    ('boleta', "Boleta"),
    ('ticket', "Ticket de recojo"),
    ('recibo', "Recibo de egreso"),
    ('guia_propia', "Guía de remisión propia"),
    ('otro', "Otro"),
]

BIOCRETO_ABREVIATURAS = {
    'guia': 'GUIA',
    'factura': 'FACTURA',
    'boleta': 'BOLETA',
    'ticket': 'TICKET',
    'recibo': 'RECIBO',
    'guia_propia': 'GUIA-PROPIA',
    'otro': 'OTRO',
}


class BiocretoRecepcionDocumento(models.Model):
    _name = 'biocreto.recepcion.documento'
    _description = "Documento de sustento de recepción"
    _order = 'picking_id, id'

    picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string="Recepción",
        required=True,
        ondelete='cascade',
        index=True,
    )
    # Related almacenado: sin él las reglas de registro multicompañía no
    # alcanzan a este modelo. `stock.picking.company_id` es a su vez un
    # related de `picking_type_id.company_id`, almacenado e indexado.
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Compañía",
        related='picking_id.company_id',
        store=True,
        index=True,
    )
    tipo = fields.Selection(
        selection=BIOCRETO_TIPOS_DOCUMENTO,
        string="Tipo",
    )
    numero = fields.Char(string="Número")

    # ─────────────────────────────────────────────────────────────────
    # Many2one a ir.attachment, NO `Binary(attachment=True)`.
    #
    # Con `Binary(attachment=True)` el adjunto lo crea el ORM por debajo y
    # hay que ir a buscarlo por `res_model`/`res_field` para renombrarlo —
    # y ahí aparece el problema de releerlo en la misma transacción en que
    # se escribió. Con el Many2one el registro existe ANTES: renombrar es
    # un `write` sobre un Char, que es exactamente lo que hace
    # `biocreto_compras.subir_cotizacion` y lleva funcionando desde la
    # v19.0.4.0.0.
    #
    # `ondelete='set null'`: si alguien borra el adjunto desde Ajustes, la
    # línea sobrevive con su tipo y su número, que siguen siendo el dato
    # de negocio.
    # ─────────────────────────────────────────────────────────────────
    attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        # "Guardado como" y no "Archivo": el control de subida de abajo ya
        # se llama Archivo, y dos campos del mismo modelo con la misma
        # etiqueta confunden al usuario y al exportador.
        string="Guardado como",
        ondelete='set null',
        copy=False,
    )

    # ─────────────────────────────────────────────────────────────────
    # El CONTROL DE SUBIDA. No es almacenamiento.
    #
    # En v19 NO existe un widget `many2one_binary`: los widgets de archivo
    # registrados son `binary` / `list.binary` (para campos Binary) y
    # `many2many_binary` (para Many2many a ir.attachment). Comprobado en
    # el registro de campos de `web`. Un Many2one a ir.attachment, por
    # tanto, no tiene control de subida propio y el usuario tendría que
    # crear el adjunto por otra vía antes de poder elegirlo.
    #
    # La solución: este Binary NO ALMACENADO es solo el control de la
    # interfaz. Lee del adjunto y, al subir, crea o actualiza el
    # `ir.attachment` que cuelga de `attachment_id` — que sigue siendo el
    # almacenamiento real, con las ventajas por las que se eligió:
    # renombrar es un `write` sobre un Char y nunca hay que releer un
    # Binary recién escrito en la misma transacción.
    #
    # El `filename` sí se guarda, porque de él sale la EXTENSION con la
    # que se compone el nombre final.
    # ─────────────────────────────────────────────────────────────────
    biocreto_archivo = fields.Binary(
        string="Archivo",
        compute='_compute_biocreto_archivo',
        inverse='_inverse_biocreto_archivo',
        store=False,
    )
    biocreto_archivo_filename = fields.Char(
        string="Nombre original",
        copy=False,
    )

    @api.depends('attachment_id')
    def _compute_biocreto_archivo(self):
        for linea in self:
            linea.biocreto_archivo = linea.attachment_id.sudo().datas or False

    def _inverse_biocreto_archivo(self):
        """Crea o reemplaza el `ir.attachment` de la línea.

        Cuando el usuario sube un archivo sobre una línea que ya tenía
        uno, el anterior se BORRA: está reemplazando, no acumulando. El
        borrado del viejo lo hace `write` cuando cambia `attachment_id`;
        aquí solo se crea el nuevo y se apunta.
        """
        Adjunto = self.env['ir.attachment'].sudo()
        # La validacion va ANTES de crear nada: asi el UserError sale
        # limpio y no queda un ir.attachment a medio camino esperando a
        # que el rollback lo barra.
        self.filtered('biocreto_archivo')._biocreto_validar_numero_subida()
        for linea in self:
            if not linea.biocreto_archivo:
                # Vaciar el control borra el adjunto.
                if linea.attachment_id:
                    linea.attachment_id = False
                continue
            ext = linea._biocreto_extension(linea.biocreto_archivo_filename)
            nuevo = Adjunto.create({
                'name': linea._biocreto_nombre_archivo(ext),
                'datas': linea.biocreto_archivo,
                'res_model': linea._name,
                'res_id': linea.id,
            })
            linea.attachment_id = nuevo.id

    # ═════════════════════════════════════════════════════════════════
    # EL NOMBRE DEL ARCHIVO
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_nombre_archivo(self, extension):
        """{REFERENCIA}_{TIPO}_{RUC_O_DNI}_{NUMERO}.{ext}

        Ejemplo: WH-IN-00047_GUIA_20608552171_001-0004521.pdf

        - REFERENCIA: la del picking con las `/` cambiadas por `-`, porque
          una barra en un nombre de archivo se lee como separador de ruta
          en cuanto el archivo sale de Odoo.
        - TIPO: la abreviatura, no el texto del desplegable.
        - RUC_O_DNI: el helper compartido de `biocreto_base`, que nunca
          falla aunque el proveedor no tenga documento.
        - NUMERO: tal como lo escribió el usuario, saneado de lo que no
          puede ir en un nombre de archivo pero conservando el guion, que
          es parte de la numeración peruana (001-0004521).
        """
        self.ensure_one()
        referencia = (self.picking_id.name or 'SIN-REF').replace('/', '-')
        referencia = re.sub(r'[^A-Za-z0-9\-]+', '', referencia)

        tipo = BIOCRETO_ABREVIATURAS.get(self.tipo, 'OTRO')
        ident = biocreto_identificador_partner(self.picking_id.partner_id)

        numero = re.sub(r'[^A-Za-z0-9\-]+', '', (self.numero or '').strip())

        base = '_'.join([referencia, tipo, ident, numero])
        return f"{base}.{extension}" if extension else base

    @staticmethod
    def _biocreto_extension(nombre):
        """Extensión en minúsculas de un nombre de archivo, o cadena vacía."""
        nombre = nombre or ''
        return nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''

    def _biocreto_renombrar_adjunto(self):
        """Renombra el adjunto existente conservando su extensión.

        Se llama desde `write` cuando cambian `tipo` o `numero`: el usuario
        no tiene que volver a subir el archivo solo porque corrigió un
        dígito. Sin adjunto, no hace nada.
        """
        for linea in self:
            if not linea.attachment_id:
                continue
            ext = linea._biocreto_extension(linea.attachment_id.name)
            linea.attachment_id.sudo().name = linea._biocreto_nombre_archivo(ext)

    # ═════════════════════════════════════════════════════════════════
    # LA ÚNICA VALIDACIÓN DEL MÓDULO
    # ═════════════════════════════════════════════════════════════════
    def _biocreto_validar_numero_subida(self):
        """Sin número no se puede subir archivo.

        Va en un método de acción y NO en `@api.constrains` porque es el
        principio del proyecto y porque aquí además hace falta: un
        `constrains` saltaría también al guardar una línea a medio llenar
        sin archivo, que es un caso perfectamente válido —el usuario
        apunta el tipo y el número ahora y adjunta el PDF mañana.
        """
        for linea in self:
            if not (linea.numero or '').strip():
                raise UserError(_(
                    "Escriba el número del documento antes de adjuntar el "
                    "archivo: el número forma parte del nombre con el que se "
                    "guarda.\n\nTipo: %(tipo)s",
                    tipo=dict(BIOCRETO_TIPOS_DOCUMENTO).get(
                        linea.tipo, _("(sin tipo)")),
                ))

    # ═════════════════════════════════════════════════════════════════
    # CRUD
    # ═════════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        lineas = super().create(vals_list)
        lineas.filtered('attachment_id')._biocreto_validar_numero_subida()
        lineas.filtered('attachment_id')._biocreto_vincular_y_renombrar()
        return lineas

    def write(self, vals):
        # El adjunto ANTERIOR de cada línea, antes de que `super()` lo
        # pise: si llega uno nuevo, el viejo se borra (el usuario está
        # reemplazando, no acumulando).
        previos = {}
        if 'attachment_id' in vals:
            for linea in self:
                if linea.attachment_id and linea.attachment_id.id != vals['attachment_id']:
                    previos[linea.id] = linea.attachment_id

        resultado = super().write(vals)

        if 'attachment_id' in vals:
            self.filtered('attachment_id')._biocreto_validar_numero_subida()
            for linea in self:
                viejo = previos.get(linea.id)
                if viejo:
                    viejo.sudo().unlink()
            self.filtered('attachment_id')._biocreto_vincular_y_renombrar()
        elif {'tipo', 'numero'} & set(vals):
            # Cambió el tipo o el número con archivo ya subido: se renombra
            # el que hay. No hay que volver a subirlo.
            self._biocreto_renombrar_adjunto()

        return resultado

    def _biocreto_vincular_y_renombrar(self):
        """Ata el adjunto a su línea y le pone el nombre que le toca.

        `res_model`/`res_id` apuntando a la línea mantienen el archivo
        localizable desde Ajustes → Adjuntos y hacen que se borre con ella
        (el `ondelete='cascade'` del picking arrastra la línea, y el
        `ir.attachment` queda huérfano si no se ata aquí).
        """
        for linea in self:
            att = linea.attachment_id.sudo()
            ext = linea._biocreto_extension(att.name)
            att.write({
                'name': linea._biocreto_nombre_archivo(ext),
                'res_model': linea._name,
                'res_id': linea.id,
            })

    def unlink(self):
        adjuntos = self.attachment_id.sudo()
        resultado = super().unlink()
        adjuntos.unlink()
        return resultado
