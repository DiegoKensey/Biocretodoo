from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    biocreto_firma = fields.Binary(
        string="Firma digital",
        attachment=True,
        help="Firma del usuario para documentos (cotizaciones, contratos). "
             "Se puede generar automaticamente desde el nombre, dibujar a mano "
             "o cargar una imagen.",
    )

    # Permitir que el propio usuario lea/escriba su firma en sus Preferencias.
    # En Odoo 19 SELF_READABLE_FIELDS/SELF_WRITEABLE_FIELDS son @property que
    # retornan list. Para extender, redeclaramos el @property con el mismo
    # nombre y concatenamos a super(). Confirmado contra
    # odoo/addons/base/models/res_users.py:175-193.
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['biocreto_firma']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['biocreto_firma']
