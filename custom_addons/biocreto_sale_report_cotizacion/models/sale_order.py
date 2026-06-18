from urllib.parse import quote_plus

import pytz

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -----------------------------------------------------------------
    # Filtros de lineas por categoria (Concreto / Bombeo).
    # Replican el patron exacto que ya usa biocreto_sale_extension en
    # sale_order.py:150 y :320 (filter by product_id.categ_id.name).
    # Se centralizan aqui para que el QWeb no tenga logica.
    # -----------------------------------------------------------------
    def biocreto_cot_lineas_concreto(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and l.biocreto_product_categ == 'Concreto'
        )

    def biocreto_cot_lineas_bombeo(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and l.biocreto_product_categ == 'Bombeo'
        )

    # -----------------------------------------------------------------
    # Subtotales por seccion (A. Concreto / B. Bombeo) + Gran total.
    # price_subtotal y price_tax son campos nativos de sale.order.line
    # mantenidos por sale; no hace falta recomputar IGV manualmente.
    # -----------------------------------------------------------------
    def biocreto_cot_totales(self):
        self.ensure_one()
        conc = self.biocreto_cot_lineas_concreto()
        bomb = self.biocreto_cot_lineas_bombeo()
        conc_subtotal = sum(conc.mapped('price_subtotal'))
        conc_igv = sum(conc.mapped('price_tax'))
        bomb_subtotal = sum(bomb.mapped('price_subtotal'))
        bomb_igv = sum(bomb.mapped('price_tax'))
        conc_total = conc_subtotal + conc_igv
        bomb_total = bomb_subtotal + bomb_igv
        return {
            'conc_subtotal': conc_subtotal,
            'conc_igv': conc_igv,
            'conc_total': conc_total,
            'bomb_subtotal': bomb_subtotal,
            'bomb_igv': bomb_igv,
            'bomb_total': bomb_total,
            'gran_total': conc_total + bomb_total,
        }

    # -----------------------------------------------------------------
    # Vigencia en dias calendario: validity_date - date_order.
    # validity_date es Date (nativo sale), date_order es Datetime.
    # -----------------------------------------------------------------
    def biocreto_cot_vigencia_dias(self):
        self.ensure_one()
        if self.validity_date and self.date_order:
            return (self.validity_date - self.date_order.date()).days
        return 0

    # -----------------------------------------------------------------
    # URL del portal con access_token, ya url-encoded para inyectar en
    # el src del endpoint /report/barcode/QR/<value>.
    # -----------------------------------------------------------------
    def biocreto_cot_qr_url(self):
        self.ensure_one()
        return quote_plus(self.get_base_url() + self.get_portal_url())

    # -----------------------------------------------------------------
    # Contacto-persona para empresas. Si is_company=True devuelve el
    # primer child_id de tipo 'contact'; si es persona devuelve el
    # propio partner. Si la empresa no tiene contactos, devuelve un
    # recordset vacio (el QWeb usa t-if para evitar imprimir vacios).
    # -----------------------------------------------------------------
    def biocreto_cot_contacto_persona(self):
        self.ensure_one()
        partner = self.partner_id
        if partner.is_company:
            contacts = partner.child_ids.filtered(lambda c: c.type == 'contact')
            return contacts[:1]
        return partner

    # -----------------------------------------------------------------
    # Etiqueta dinamica del tipo de documento del cliente.
    # v19.0.2.0.0: lee el tipo de doc desde el commercial_partner_id
    # (la EMPRESA, no la persona contacto). Si la cotizacion es a una
    # persona suelta, commercial_partner_id == partner_id, asi que
    # sigue funcionando. Si es a una empresa via su contacto, leemos
    # el tipo de doc de la empresa (que es donde tiene sentido cargar
    # RUC, no en cada contacto).
    # -----------------------------------------------------------------
    def biocreto_cot_doc_tipo(self):
        self.ensure_one()
        cp = self.partner_id.commercial_partner_id
        return cp.l10n_latam_identification_type_id.name or 'RUC / DNI'

    # -----------------------------------------------------------------
    # Conversion UTC -> America/Lima.
    # v19.0.2.0.0: los Datetime de Odoo se guardan en UTC. Para que
    # las horas en el reporte salgan en hora Peru (UTC-5), aplicamos
    # tz manualmente. Compatible con datetimes naive (tipico cuando
    # vienen del ORM via fields.Datetime) y aware (defensivo).
    # -----------------------------------------------------------------
    def _biocreto_to_lima(self, dt):
        if not dt:
            return dt
        tz = pytz.timezone('America/Lima')
        if dt.tzinfo is None:
            return pytz.utc.localize(dt).astimezone(tz)
        return dt.astimezone(tz)

    # -----------------------------------------------------------------
    # Fechas de vaciado separadas (v19.0.2.0.0).
    # La spec pide intercalar un <i class="fa fa-long-arrow-right"/>
    # entre inicio y fin desde el QWeb. Por eso retornamos las dos
    # piezas como strings independientes (NO un solo string con la
    # flecha). El fin omite la fecha si es el mismo dia que el inicio.
    # Ambos formatos ya en hora Peru.
    # -----------------------------------------------------------------
    def biocreto_cot_fecha_vaceo_ini(self):
        self.ensure_one()
        ini = self._biocreto_to_lima(self.biocreto_fecha_vaceo_inicio)
        return ini.strftime('%d/%m/%Y %H:%M') if ini else ''

    def biocreto_cot_fecha_vaceo_fin(self):
        self.ensure_one()
        ini = self.biocreto_fecha_vaceo_inicio
        fin = self.biocreto_fecha_vaceo_fin
        if not fin:
            return ''
        fin_local = self._biocreto_to_lima(fin)
        ini_local = self._biocreto_to_lima(ini) if ini else None
        if ini_local and ini_local.date() == fin_local.date():
            return fin_local.strftime('%H:%M')
        return fin_local.strftime('%d/%m/%Y %H:%M')

    # -----------------------------------------------------------------
    # Formato de monto: separador de miles + 2 decimales.
    # Usado en QWeb porque el operador % de Python no acepta el flag ','
    # (solo .format() / f-strings lo soportan).
    # -----------------------------------------------------------------
    def biocreto_cot_money(self, amount):
        return '{:,.2f}'.format(amount or 0.0)

    # -----------------------------------------------------------------
    # Rotulo dinamico para el tag vertical (v19.0.2.0.0).
    # Estados verificados:
    #   - 'draft','sent' (nativos sale)
    #   - 'contract','programado' (biocreto_sale_contract_state via
    #      selection_add en sale.order, custom_addons/biocreto_sale_
    #      contract_state/models/sale_order.py:19-29)
    #   - 'sale','done' (nativos sale)
    #   - 'cancel' (nativo) -> tratado como Cotizacion
    #
    # Regla de negocio:
    #   Orden       si state in ('sale','done')
    #   Cotizacion  para todo lo demas
    # El CSS .cot-vertical-tag-inline aplica text-transform: uppercase
    # asi que retornamos capitalizado.
    # -----------------------------------------------------------------
    def biocreto_cot_rotulo(self):
        self.ensure_one()
        if self.state in ('sale', 'done'):
            return 'Orden'
        return 'Cotización'
