from urllib.parse import quote_plus

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
    # Devuelve el .name del l10n_latam_identification_type_id (RUC, DNI,
    # Pasaporte, etc.). Si no hay tipo configurado cae al literal
    # 'RUC / DNI' para no romper el reporte.
    # -----------------------------------------------------------------
    def biocreto_cot_doc_tipo(self):
        self.ensure_one()
        return self.partner_id.l10n_latam_identification_type_id.name or 'RUC / DNI'

    # -----------------------------------------------------------------
    # String formateado para 'Fecha vaciado'.
    #   Mismo dia: 'dd/MM/yyyy HH:mm -> HH:mm'
    #   Dias distintos: 'dd/MM/yyyy HH:mm -> dd/MM/yyyy HH:mm'
    # Devuelve '' si falta inicio o fin (el QWeb lo imprime vacio).
    # -----------------------------------------------------------------
    def biocreto_cot_fecha_vaceo_label(self):
        self.ensure_one()
        ini = self.biocreto_fecha_vaceo_inicio
        fin = self.biocreto_fecha_vaceo_fin
        if not ini or not fin:
            return ''
        flecha = '→'  # caracter "→" U+2192 RIGHTWARDS ARROW
        if ini.date() == fin.date():
            return '%s  %s  %s' % (
                ini.strftime('%d/%m/%Y %H:%M'),
                flecha,
                fin.strftime('%H:%M'),
            )
        return '%s  %s  %s' % (
            ini.strftime('%d/%m/%Y %H:%M'),
            flecha,
            fin.strftime('%d/%m/%Y %H:%M'),
        )

    # -----------------------------------------------------------------
    # Formato de monto: separador de miles + 2 decimales.
    # Usado en QWeb porque el operador % de Python no acepta el flag ','
    # (solo .format() / f-strings lo soportan).
    # -----------------------------------------------------------------
    def biocreto_cot_money(self, amount):
        return '{:,.2f}'.format(amount or 0.0)
