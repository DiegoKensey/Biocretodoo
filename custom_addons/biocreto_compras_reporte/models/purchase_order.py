import pytz

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # -----------------------------------------------------------------
    # Helpers t-out del reporte de Solicitud de Cotizacion (SC) y
    # Orden de Compra (OC). Prefijo biocreto_sc_* aun para OC porque
    # el layout y la mayoria de los datos son compartidos; el ruteo
    # SC/OC se hace en biocreto_sc_es_oc().
    # -----------------------------------------------------------------

    # UTC -> America/Lima. Portado 1:1 de biocreto_sale_report_cotizacion.
    def _biocreto_to_lima(self, dt):
        if not dt:
            return dt
        tz = pytz.timezone('America/Lima')
        if dt.tzinfo is None:
            return pytz.utc.localize(dt).astimezone(tz)
        return dt.astimezone(tz)

    # Separador de miles + 2 decimales. QWeb no soporta el flag ',' del %.
    def biocreto_sc_money(self, amount):
        return '{:,.2f}'.format(amount or 0.0)

    # -----------------------------------------------------------------
    # Ruteo SC / OC
    # -----------------------------------------------------------------
    # 'cancel' se imprime como SC por decision de negocio: un documento
    # cancelado nunca llego a ser Orden.
    def biocreto_sc_es_oc(self):
        self.ensure_one()
        return self.state == 'purchase'

    def biocreto_sc_rotulo(self):
        self.ensure_one()
        return 'Orden' if self.biocreto_sc_es_oc() else 'Cotización'

    # -----------------------------------------------------------------
    # Fecha de emision INMUTABLE: create_date.
    # Motivo: date_order (nativo 'Order Deadline') es editable por el
    # comprador. Para trazabilidad del documento se usa create_date.
    # -----------------------------------------------------------------
    def biocreto_sc_fecha_emision(self):
        self.ensure_one()
        dt = self._biocreto_to_lima(self.create_date)
        return dt.strftime('%d/%m/%Y') if dt else ''

    # -----------------------------------------------------------------
    # Moneda: "Soles (S/)" / "Dólares ($)" / "<code> (<symbol>)" default.
    # -----------------------------------------------------------------
    def biocreto_sc_moneda_label(self):
        self.ensure_one()
        cur = self.currency_id
        if not cur:
            return ''
        if cur.name == 'PEN':
            return 'Soles (S/)'
        if cur.name == 'USD':
            return 'Dólares ($)'
        return '%s (%s)' % (cur.name, cur.symbol or '')

    # -----------------------------------------------------------------
    # Direccion generica sobre res.partner. Usa campos nativos + el
    # l10n_pe_district agregado por l10n_pe (verificado en la BD).
    # Formato: "calle - distrito, provincia, departamento".
    # -----------------------------------------------------------------
    def biocreto_sc_direccion_partner(self, partner):
        self.ensure_one()
        if not partner:
            return ''
        partes = []
        if partner.l10n_pe_district:
            partes.append(partner.l10n_pe_district.name)
        if partner.city_id:
            partes.append(partner.city_id.name)
        elif partner.city:
            partes.append(partner.city)
        if partner.state_id:
            partes.append(partner.state_id.name)
        zona = ", ".join(partes)
        calle = partner.street or ''
        if calle and zona:
            return "%s - %s" % (calle, zona)
        return calle or zona or ''

    # -----------------------------------------------------------------
    # Etiqueta dinamica RUC / DNI desde commercial_partner_id.
    # biocreto_base garantiza que el vat cumpla 11/8 digitos y que el
    # tipo este seteado a l10n_pe.it_RUC / l10n_pe.it_DNI.
    # -----------------------------------------------------------------
    def biocreto_sc_doc_tipo(self, partner):
        self.ensure_one()
        if not partner:
            return 'RUC / DNI'
        cp = partner.commercial_partner_id
        return cp.l10n_latam_identification_type_id.name or 'RUC / DNI'

    # -----------------------------------------------------------------
    # Bloque SOLICITANTE (compania). Contacto/atencion salen del
    # create_uid (creador inmutable del registro), NO de env.user.
    # -----------------------------------------------------------------
    def biocreto_sc_solicitante(self):
        self.ensure_one()
        cpartner = self.company_id.partner_id
        creador = self.create_uid
        cp_creador = creador.partner_id
        return {
            'nombre': self.company_id.name or '',
            'doc_tipo': self.biocreto_sc_doc_tipo(cpartner),
            'doc_num': cpartner.vat or '—',
            'telefono': cp_creador.phone or '',
            'atencion': creador.name or '',
            'direccion': self.biocreto_sc_direccion_partner(cpartner),
        }

    # -----------------------------------------------------------------
    # Bloque PROVEEDOR - 3 casos:
    #   A) Empresa directa (partner.is_company y sin padre):
    #      Atencion = 'Área de Ventas'
    #   B) Contacto de una empresa (parent_id.is_company):
    #      nombre / RUC / direccion DE LA EMPRESA;
    #      Atencion = nombre del contacto;
    #      telefono = contacto.phone o empresa.phone
    #   C) Persona natural (sin parent, is_company=False):
    #      todo del propio partner; etiqueta doc = DNI
    # -----------------------------------------------------------------
    def biocreto_sc_proveedor(self):
        self.ensure_one()
        p = self.partner_id
        if not p:
            return {}
        cp = p.commercial_partner_id
        es_contacto_de_empresa = bool(cp and cp != p and cp.is_company)

        if es_contacto_de_empresa:
            base = cp
            atencion = p.name or ''
            telefono = p.phone or cp.phone or ''
        else:
            base = p
            atencion = 'Área de Ventas' if p.is_company else (p.name or '')
            telefono = p.phone or ''

        return {
            'nombre': base.name or '',
            'doc_tipo': self.biocreto_sc_doc_tipo(base),
            'doc_num': base.vat or '—',
            'telefono': telefono,
            'atencion': atencion,
            'direccion': self.biocreto_sc_direccion_partner(base),
        }

    # -----------------------------------------------------------------
    # Lineas a imprimir. Filtra display_type (sections/notes) igual que
    # los helpers de venta.
    # -----------------------------------------------------------------
    def biocreto_sc_lineas(self):
        self.ensure_one()
        return self.order_line.filtered(lambda l: not l.display_type)

    # -----------------------------------------------------------------
    # Firmante: create_uid del registro. Nombre en mayusculas, cargo
    # en `function` del partner del usuario. Ambos strings vacios si
    # no hay dato (dato del cliente, no bug del reporte).
    # -----------------------------------------------------------------
    def biocreto_sc_firmante(self):
        self.ensure_one()
        creador = self.create_uid
        return {
            'nombre': (creador.name or '').upper(),
            'cargo': creador.partner_id.function or '',
        }
