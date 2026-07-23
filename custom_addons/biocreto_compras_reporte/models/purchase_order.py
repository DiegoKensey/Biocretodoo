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
    # Lineas a imprimir. v19.0.1.4.0 CORRECCION 6: incluye TODAS las
    # lineas (productos + secciones + subsecciones + notas) preservando
    # el orden de captura y con el correlativo YA calculado.
    #
    # Retorna list[dict]:
    #   {'num': int|False, 'line': record, 'tipo': str}
    # - 'num' solo se asigna a lineas de producto (display_type falsy).
    #   Secciones y notas llevan False y NO consumen numero.
    # - 'tipo' in ('producto', 'line_section', 'line_subsection', 'line_note').
    #
    # Orden: self.order_line respeta `_order = order_id, sequence, id`
    # (verificado en runtime: purchase.order.line._order). No hace falta
    # .sorted('sequence') explicito.
    #
    # Decision: NO excluir product_qty == 0. En una SC una cantidad 0 es
    # error de captura que conviene visibilizar. El nativo filtra con
    # `l.display_type or l.product_qty != 0`; aca no.
    # -----------------------------------------------------------------
    def biocreto_sc_lineas(self):
        self.ensure_one()
        res = []
        contador = 0
        for line in self.order_line:
            if line.display_type:
                res.append({'num': False, 'line': line, 'tipo': line.display_type})
            else:
                contador += 1
                res.append({'num': contador, 'line': line, 'tipo': 'producto'})
        return res

    # -----------------------------------------------------------------
    # v19.0.1.4.0 CORRECCION 6: descripcion de compra SIN el nombre.
    # line.name es armado por _get_product_purchase_description en
    # purchase/models/purchase_order_line.py:568-574 como:
    #   name = product.display_name
    #   if product.description_purchase:
    #       name += '\n' + description_purchase
    # Partimos por el PRIMER salto de linea: lo anterior es el nombre
    # (ya impreso en negrita en la celda), lo posterior es la descripcion.
    # Retorna '' si no hay descripcion -> la celda queda solo con el nombre.
    # -----------------------------------------------------------------
    def biocreto_sc_desc_extra(self, line):
        self.ensure_one()
        if not line or not line.name:
            return ''
        partes = line.name.split('\n', 1)
        return partes[1].strip() if len(partes) > 1 else ''

    # -----------------------------------------------------------------
    # Firmante: create_uid del registro (NO env.user - la firma es del
    # que EMITIO la SC, no del que la imprime).
    #   nombre : upper() del create_uid.name
    #   cargo  : create_uid.partner_id.function (Char nativo)
    #   firma  : create_uid.biocreto_firma (Binary attachment=True,
    #            biocreto_base/models/res_users.py). False si vacia
    #            para que el t-if del QWeb no dibuje img rota.
    #
    # v19.0.1.3.0 CORRECCION 5: se agrega 'firma'. Mismo mecanismo que
    # venta (biocreto_sale_report_cotizacion), cambiando el origen:
    #   venta   -> o.user_id.biocreto_firma
    #   compras -> o.create_uid.biocreto_firma
    # Sin sudo(): venta NO lo usa (probado en produccion). El binario
    # atado a res.users vive en ir.attachment pero es legible por
    # cualquier usuario que pueda leer el res.users (SELF_READABLE_FIELDS
    # de biocreto_base incluye biocreto_firma para el propio user, y el
    # ACL de res.users permite lectura general). Ver criterio 21 del
    # checklist para prueba end-to-end.
    # -----------------------------------------------------------------
    def biocreto_sc_firmante(self):
        self.ensure_one()
        creador = self.create_uid
        return {
            'nombre': (creador.name or '').upper(),
            'cargo': creador.partner_id.function or '',
            'firma': creador.biocreto_firma or False,
        }

    # =================================================================
    # v19.0.2.0.0 — helpers exclusivos del body_oc.
    # =================================================================

    def biocreto_sc_moneda_simbolo(self):
        """Simbolo corto de la moneda para renglones de importe."""
        self.ensure_one()
        cur = self.currency_id
        if not cur:
            return ''
        if cur.name == 'PEN':
            return 'S/'
        if cur.name == 'USD':
            return '$'
        return cur.symbol or cur.name or ''

    def biocreto_oc_monto_palabras(self, amount):
        """Monto a texto en formato bancario peruano: '<Palabras> con XX/100 <moneda>'.

        Clon 1:1 de biocreto_sale_extension.sale_order.biocreto_contrato_monto_palabras
        (sale_order.py:459-511), con UNA parametrizacion adicional: el sufijo
        final ('soles' / 'dolares' / '<curr_name>') depende de self.currency_id
        en vez de hardcodearse a 'soles'. El .upper() se aplica en el QWeb.
        """
        self.ensure_one()
        try:
            amount = float(amount or 0.0)
        except (TypeError, ValueError):
            return ''
        integer_part = int(amount)
        centimos = int(round((amount - integer_part) * 100))
        if centimos == 100:
            integer_part += 1
            centimos = 0
        raw = self.currency_id.amount_to_text(integer_part) or ''
        unit = (self.currency_id.currency_unit_label or '').strip()
        if unit and raw.endswith(' ' + unit):
            palabras = raw[:-(len(unit) + 1)]
        elif ' ' in raw:
            palabras = raw.rsplit(' ', 1)[0]
        else:
            palabras = raw
        palabras = palabras.strip().lower().capitalize()
        cname = (self.currency_id.name or '').upper()
        if cname == 'PEN':
            sufijo = 'soles'
        elif cname == 'USD':
            sufijo = 'dólares'
        else:
            sufijo = (self.currency_id.currency_unit_label or cname or '').lower()
            if sufijo and not sufijo.endswith('s'):
                sufijo += 's'
        return f'{palabras} con {centimos:02d}/100 {sufijo}'

    def biocreto_oc_descuento_total(self):
        """Suma de descuentos de linea. Devuelve 0.0 si no hay ninguno.
        El grupo product.group_discount_per_so_line NO aplica a compras
        (es de sale y ni siquiera existe en esta BD) — leemos line.discount directo."""
        self.ensure_one()
        return sum(
            (l.price_unit or 0.0) * (l.product_qty or 0.0) * ((l.discount or 0.0) / 100.0)
            for l in self.order_line if not l.display_type
        )

    def biocreto_oc_condiciones(self):
        """Valores de las condiciones pactadas para la OC. Cadena vacia => el
        QWeb pinta la linea punteada en blanco (mismo criterio para los 7)."""
        self.ensure_one()
        fecha = ''
        if self.date_planned:
            dt = self._biocreto_to_lima(self.date_planned)
            fecha = dt.strftime('%d/%m/%Y') if dt else ''

        garantia = ''
        meses = self.biocreto_garantia_meses or 0
        if meses > 0:
            garantia = '%s %s' % (meses, 'mes' if meses == 1 else 'meses')

        cta = self.biocreto_cuenta_deposito_id
        return {
            'fecha_entrega': fecha,
            'forma_pago': self.payment_term_id.name or '',
            'medio_pago': self.biocreto_medio_pago_id.name or '',
            'garantia': garantia,
            'banco': (cta.bank_id.name or cta.bank_name or '') if cta else '',
            'cuenta': (cta.acc_number or '') if cta else '',
            'cci': (cta.biocreto_cci or '') if cta else '',
        }

    def biocreto_oc_firmantes(self):
        """Firmas de la OC: creador (izquierda) + gerente de sede (derecha).
        Si manager_id esta vacio, devuelve lista de 1 sola firma — el QWeb
        centra la unica columna, igual criterio que la SC.
        Sin sudo (mismo criterio que biocreto_sc_firmante, ver docstring alli).
        Formato: nombre en mayusculas + function, SIN prefijo tipo 'Solicitado por'."""
        self.ensure_one()
        creador = self.create_uid
        gerente = self.company_id.manager_id
        firmantes = [{
            'nombre': (creador.name or '').upper(),
            'cargo': creador.partner_id.function or '',
            'firma': creador.biocreto_firma or False,
        }]
        if gerente and gerente != creador:
            firmantes.append({
                'nombre': (gerente.name or '').upper(),
                'cargo': gerente.partner_id.function or '',
                'firma': gerente.biocreto_firma or False,
            })
        return firmantes
