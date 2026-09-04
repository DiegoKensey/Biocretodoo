from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ═════════════════════════════════════════════════════════════════
    # Cascada geografica estricta: Pais -> Departamento -> Provincia ->
    # Distrito.
    #
    # El diseno nativo va al REVES: el distrito escribe hacia arriba
    # (l10n_pe/models/res_partner.py:13-16 fija city_id; y ese city_id
    # dispara base_address_extended:47-56, que fija state_id). Por eso
    # ningun campo trae dominio y el desplegable de distrito ofrece los
    # 1874 del Peru. Con 255 distritos de nombre repetido (hay un Chilca
    # en Huancayo/Junin y otro en Canete/Lima) elegir a ciegas es la
    # norma, y el ubigeo del distrito viaja al XML de SUNAT
    # (l10n_pe_edi/models/account_edi_xml_ubl_pe.py:210).
    #
    # Aqui se anade el sentido descendente SIN quitar el ascendente: si
    # el usuario ya sabe el distrito, el nativo le sigue rellenando
    # provincia y departamento con el valor correcto.
    # ═════════════════════════════════════════════════════════════════

    @api.model
    def default_get(self, fields_list):
        """Peru como pais por defecto, editable.

        Se resuelve por `code` y no por xmlid ni por id: el registro es
        de `base`, pero el id es distinto en cada base de datos.

        Solo rellena si nadie lo puso antes: un `default_country_id` en
        el contexto sigue mandando, porque super() ya lo habria dejado
        en `valores`.
        """
        valores = super().default_get(fields_list)
        if 'country_id' in fields_list and not valores.get('country_id'):
            peru = self.env['res.country'].search([('code', '=', 'PE')], limit=1)
            if peru:
                valores['country_id'] = peru.id
        return valores

    @api.onchange('country_id')
    def _biocreto_onchange_country_id(self):
        """Limpiar los tres hijos que no correspondan al pais nuevo.

        Los nativos ya limpian state_id (base:581-584) y city_id
        (base_address_extended:58-62), pero NADIE limpia el distrito:
        sin esto se puede acabar con pais Chile y distrito El Tambo.
        """
        if self.state_id and self.state_id.country_id != self.country_id:
            self.state_id = False
        if self.city_id and self.city_id.country_id != self.country_id:
            self.city_id = False
        distrito = self.l10n_pe_district
        if distrito and distrito.city_id.country_id != self.country_id:
            self.l10n_pe_district = False

    @api.onchange('state_id')
    def _biocreto_onchange_state_id(self):
        """Limpiar provincia y distrito que no correspondan al departamento.

        Agujero nativo: `_onchange_state` (base:586-589) solo toca el
        pais, asi que cambiar el departamento dejaba provincia y
        distrito huerfanos, apuntando a otro departamento y sin ninguna
        senal visible.

        Limpia SOLO lo que no encaja, nunca incondicionalmente: mismo
        criterio que biocreto_sale_extension/models/sale_order.py:263-272.
        """
        if self.city_id and self.city_id.state_id != self.state_id:
            self.city_id = False
        distrito = self.l10n_pe_district
        if distrito and distrito.city_id.state_id != self.state_id:
            self.l10n_pe_district = False

    @api.onchange('city_id')
    def _onchange_city_id(self):
        """Impedir que vaciar la provincia borre el departamento.

        base_address_extended/models/res_partner.py:53-56 hace esto al
        quedarse city_id vacio:

            elif self._origin:
                self.city = False; self.zip = False; self.state_id = False

        Es la trampa de esta cascada. Cuando `_biocreto_onchange_state_id`
        limpia city_id, el motor de onchange encadena y ejecuta el nativo,
        que borra el departamento RECIEN elegido: el usuario se queda con
        los tres campos en blanco. Reproducido en v19: en un registro
        nuevo el departamento sobrevive (no hay `_origin`), en uno ya
        guardado no.

        Se conserva el borrado de `city` y `zip` -- son datos de la
        provincia que se fue -- y se restaura solo `state_id`. Un padre
        no puede morir porque se vacie su hijo.
        """
        departamento = self.state_id
        resultado = super()._onchange_city_id()
        if departamento and not self.city_id and not self.state_id:
            self.state_id = departamento
        return resultado

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
