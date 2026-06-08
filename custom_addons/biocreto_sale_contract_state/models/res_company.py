from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    biocreto_buffer_confirmacion_horas = fields.Integer(
        string="Confirmación horas a OV",
        default=1,
        help="Horas de anticipación con que el sistema confirma automáticamente "
             "una orden Programada hacia Orden de Venta, antes del inicio del vaceo. "
             "0 = sin anticipación (confirma a la hora del vaceo, en la siguiente "
             "corrida del cron).",
    )
    biocreto_candado_diseno = fields.Boolean(
        string="Exigir diseño antes de OV",
        default=True,
        help="Si está activado, no se puede pasar de Programado a Orden de Venta "
             "si alguna línea de Concreto no tiene Diseño de mezcla asignado. "
             "El cron siempre respeta esta exigencia; el botón manual puede saltarla "
             "solo si este candado está desactivado.",
    )
