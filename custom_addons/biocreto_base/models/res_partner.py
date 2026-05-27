from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.onchange('is_company', 'country_id')
    def _onchange_biocreto_set_default_id_type(self):
        """Autoseleccionar DNI o RUC según is_company cuando el país es Perú."""
        for partner in self:
            country_code = partner.country_id.code if partner.country_id else False
            if country_code and country_code != 'PE':
                continue
            xml_id = 'l10n_pe.it_RUC' if partner.is_company else 'l10n_pe.it_DNI'
            id_type = self.env.ref(xml_id, raise_if_not_found=False)
            if id_type:
                partner.l10n_latam_identification_type_id = id_type

    @api.constrains('vat', 'l10n_latam_identification_type_id')
    def _check_biocreto_id_length(self):
        """Validación ligera: RUC exige 11 dígitos numéricos, DNI exige 8."""
        ruc_type = self.env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
        dni_type = self.env.ref('l10n_pe.it_DNI', raise_if_not_found=False)
        for partner in self:
            if not partner.vat:
                continue
            id_type = partner.l10n_latam_identification_type_id
            if ruc_type and id_type == ruc_type:
                if len(partner.vat) != 11 or not partner.vat.isdigit():
                    raise ValidationError(_("El RUC debe tener 11 dígitos numéricos."))
            elif dni_type and id_type == dni_type:
                if len(partner.vat) != 8 or not partner.vat.isdigit():
                    raise ValidationError(_("El DNI debe tener 8 dígitos numéricos."))
