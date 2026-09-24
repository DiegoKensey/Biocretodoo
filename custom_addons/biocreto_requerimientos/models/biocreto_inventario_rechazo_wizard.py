# ═══════════════════════════════════════════════════════════════════════
#  Dialogo de rechazo de un conteo de activos
#
#  TransientModel, siguiendo el patron de
#  `biocreto.requerimiento.cotizacion.wizard` (models/consolidado.py:629):
#  los campos viven en el propio dialogo, un solo `action_*` hace el
#  trabajo y devuelve, y el `required=True` va EN EL MODELO y no solo en
#  la vista, para que el motivo no pueda llegar vacio por API.
# ═══════════════════════════════════════════════════════════════════════
from odoo import _, fields, models
from odoo.exceptions import UserError


class BiocretoInventarioRechazoWizard(models.TransientModel):
    _name = 'biocreto.inventario.rechazo.wizard'
    _description = 'Rechazar un conteo de activos'

    conteo_id = fields.Many2one(
        'biocreto.inventario.conteo', string="Conteo",
        required=True, ondelete='cascade')
    motivo = fields.Text(
        string="Motivo del rechazo", required=True,
        help="Lo verá el jefe de área en la parte alta de su conteo, y queda "
             "además en el historial del documento con su autor y su fecha.")

    def action_rechazar(self):
        self.ensure_one()
        # El `required=True` del campo ya impide guardar vacio desde el
        # cliente, pero no cubre un motivo de puros espacios ni una
        # llamada por codigo. El rechazo sin motivo es justo el caso que
        # deja al jefe de area sin saber que corregir.
        if not (self.motivo or '').strip():
            raise UserError(_("Escriba el motivo del rechazo."))
        self.conteo_id._biocreto_rechazar(self.motivo)
        return {'type': 'ir.actions.act_window_close'}
