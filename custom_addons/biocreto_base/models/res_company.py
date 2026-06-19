from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    plant_code = fields.Char(
        string="Código de Planta",
        size=8,
        index=True,
        help="Código corto de la planta (ej: CONC, COMU, CAJ). "
             "Útil para reportes y referencias técnicas.",
    )
    manager_id = fields.Many2one(
        'res.users',
        string="Gerente de Sede",
        domain="[('company_ids', 'in', id)]",
        help="Usuario responsable operativo de la planta.",
    )

    @api.constrains('plant_code')
    def _biocreto_check_plant_code_unique(self):
        """Unicidad case-insensitive de plant_code entre compañías."""
        for company in self:
            code = (company.plant_code or '').strip()
            if not code:
                continue
            duplicate = self.sudo().search([
                ('id', '!=', company.id),
                ('plant_code', '=ilike', code),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "El código de planta '%(code)s' ya está asignado a la "
                    "compañía '%(company)s'.",
                    code=code,
                    company=duplicate.name,
                ))
