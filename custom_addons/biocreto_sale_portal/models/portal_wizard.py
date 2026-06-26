from odoo import _, api, fields, models
from odoo.exceptions import UserError


# Dominio sintetico para los logins de portal sin correo real. El buzon
# nunca recibe nada (suprimimos el envio), solo da forma de email valida
# para el login de Odoo.
EMAIL_DOMAIN = '@biocreto.com.pe'


def _biocreto_clean_vat(vat):
    """Deja solo alfanumericos (DNI/RUC peruanos vienen siempre asi, pero
    algunos usuarios escriben con guiones/espacios)."""
    return ''.join(ch for ch in (vat or '') if ch.isalnum())


class PortalWizard(models.TransientModel):
    _inherit = 'portal.wizard'

    @api.depends('partner_ids')
    def _compute_user_ids(self):
        """Pre-llena el `email` de cada wizard line con el sintetico
        `<vat>@biocreto.com.pe` del commercial_partner, sobreescribiendo
        el `partner.email` nativo (que tipicamente esta vacio para
        clientes BIOCRETO).

        Sin esto, el flujo nativo dejaria `email=''` -> `email_state='ko'`
        -> boton "Grant Access" invisible en la vista.

        Reusa la logica de target/identificador definida en la linea
        (`portal.wizard.user`) para mantener una sola fuente de verdad.
        """
        super()._compute_user_ids()
        for wizard in self:
            for line in wizard.user_ids:
                target = line._biocreto_target_partner()
                vat = _biocreto_clean_vat(target.vat)
                if vat:
                    line.email = vat + EMAIL_DOMAIN


class PortalWizardUser(models.TransientModel):
    _inherit = 'portal.wizard.user'

    # =================================================================
    # Helpers de target/identificador — una sola fuente de verdad.
    # =================================================================
    def _biocreto_target_partner(self):
        """Devuelve el partner sobre el que vive el usuario portal:
        - Contacto de empresa  -> commercial_partner (la empresa).
        - Persona natural      -> el propio partner (commercial == self).
        """
        self.ensure_one()
        return self.partner_id.commercial_partner_id or self.partner_id

    def _biocreto_identificador(self, partner):
        """Devuelve el vat saneado (DNI/RUC). Lanza UserError si falta.
        Bloqueante por diseno: sin DNI/RUC no hay como construir login
        ni password fijos."""
        vat = _biocreto_clean_vat(partner.vat)
        if not vat:
            raise UserError(_(
                "El contacto/empresa «%(name)s» no tiene DNI/RUC "
                "registrado. Es obligatorio para generar el acceso al "
                "portal (se usa como login y contraseña).",
                name=partner.display_name,
            ))
        return vat

    def _biocreto_synthetic_email(self, partner):
        """Login sintetico — no necesita ser un buzon real."""
        return self._biocreto_identificador(partner) + EMAIL_DOMAIN

    # =================================================================
    # Override de computes nativos — apuntar al target (commercial_partner)
    # en vez del contacto seleccionado en el wizard.
    # =================================================================
    @api.depends('partner_id')
    def _compute_user_id(self):
        """El user portal vive sobre el commercial_partner. Asi la vista
        muestra correctamente `is_portal=True` cuando la empresa ya tiene
        su user (aunque hayas seleccionado un contacto distinto), y
        ofrece "Revoke" en lugar de "Grant Access"."""
        for line in self:
            target = line._biocreto_target_partner()
            user = target.with_context(active_test=False).user_ids
            line.user_id = user[:1] if user else False

    @api.depends('email', 'partner_id')
    def _compute_email_state(self):
        """Forzar 'ok' cuando el email del wizard coincide con el
        sintetico esperado del target. Sin esto:
        - 'exist': el nativo marca asi si ya hay otro user con ese login
          -> bloquea reuso del user de la empresa.
        - 'ko':    si el partner no tiene email natural -> bloquea el
          boton Grant Access.
        """
        super()._compute_email_state()
        for line in self:
            target = line._biocreto_target_partner()
            vat = _biocreto_clean_vat(target.vat)
            if not vat:
                continue
            expected = (vat + EMAIL_DOMAIN).lower()
            if (line.email or '').lower() == expected:
                line.email_state = 'ok'

    # =================================================================
    # Reescritura del flujo de concesion.
    # =================================================================
    # No llamamos super() porque el nativo:
    #   1. valida email_state == 'ok' con assert de unicidad (queremos
    #      permitir reuso del user de la empresa);
    #   2. opera sobre self.partner_id (queremos commercial_partner);
    #   3. hace signup_prepare + _send_email (queremos password directa
    #      sin correo);
    # Reescribir las ~30 lineas es mas claro y robusto que parchear cada
    # hook intermedio.
    # =================================================================
    def action_grant_access(self):
        self.ensure_one()
        target = self._biocreto_target_partner()
        identificador = self._biocreto_identificador(target)  # bloquea sin vat
        synth_email = identificador + EMAIL_DOMAIN

        group_portal = self.env.ref('base.group_portal')
        group_public = self.env.ref('base.group_public')

        # Buscar user existente sobre EL TARGET (no sobre self.partner_id).
        # active_test=False para encontrar archivados por revoke previo.
        user_sudo = target.with_context(active_test=False).sudo().user_ids[:1]

        if user_sudo and user_sudo._is_internal():
            raise UserError(_(
                "El usuario asociado a «%(name)s» es interno; no se "
                "puede otorgar acceso al portal sobre el mismo.",
                name=target.display_name,
            ))

        if user_sudo:
            # Reuso/reactivacion. write idempotente:
            #   - active=True (si estaba archivado, lo desarchiva)
            #   - group_portal IN, group_public OUT
            #   - login=synth_email (asegura consistencia si el user
            #     existente tenia otro login)
            user_sudo.write({
                'active': True,
                'login': synth_email,
                'group_ids': [(4, group_portal.id), (3, group_public.id)],
            })
        else:
            # Creacion sobre el commercial_partner (no sobre el contacto).
            company = target.company_id or self.env.company
            user_sudo = self.env['res.users'].with_context(
                no_reset_password=True,
            ).sudo().with_company(company.id)._create_user_from_template({
                'email': synth_email,
                'login': synth_email,
                'partner_id': target.id,
                'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'group_ids': [(6, 0, [group_portal.id])],
            })

        # Password fija = identificador. El setter de res.users.password
        # hashea automaticamente (verificado en base/models/res_users.py).
        # sudo() necesario porque el wizard puede correr como usuario sin
        # permisos directos para escribir password ajenos.
        user_sudo.sudo().password = identificador

        # NO signup_prepare (no hay flujo de set-password).
        # NO _send_email (suprimido — el buzon no existe).

        return self.action_refresh_modal()

    # =================================================================
    # Suprimir envio de correo de invitacion.
    # =================================================================
    # action_grant_access reescrito no llama a _send_email, pero
    # action_invite_again (boton "Re-Invite" del wizard) si lo llama.
    # Sin override, harian un envio fallido al buzon ficticio.
    # =================================================================
    def _send_email(self):
        """Suprimido por diseno BIOCRETO: las credenciales son fijas
        (RUC/DNI) y el buzon sintetico no recibe correo."""
        return True
