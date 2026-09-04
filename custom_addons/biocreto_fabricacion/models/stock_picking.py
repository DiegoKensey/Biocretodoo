from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    biocreto_carga_ids = fields.One2many(
        'biocreto.carga', 'picking_id', string="Cargas")
    biocreto_codigo_presinto = fields.Char(
        string="Código presinto", copy=False)
    biocreto_datos_guia = fields.Text(
        string="Datos de guía",
        compute='_compute_biocreto_datos_guia',
        store=True,
    )
    biocreto_guia_electronica = fields.Binary(
        string="Guía electrónica", attachment=True, copy=False)
    biocreto_guia_electronica_filename = fields.Char(copy=False)

    @api.depends(
        'biocreto_codigo_presinto',
        'biocreto_carga_ids',
        'biocreto_carga_ids.vehiculo_id.license_plate',
        'biocreto_carga_ids.hora_fin',
        'biocreto_carga_ids.sale_line_id.product_id.biocreto_fc_resistencia',
        'biocreto_carga_ids.sale_line_id.biocreto_huso_tmn',
        'biocreto_carga_ids.sale_line_id.biocreto_slump_rango',
        'move_ids.product_uom_qty',
        'move_ids.product_id',
    )
    def _compute_biocreto_datos_guia(self):
        """Texto plano de 7 lineas para la guia de remision fisica.

        Fuentes: la carga vinculada (placa del mixer, hora de salida), la linea
        de venta de esa carga (huso, slump), el producto de la linea (fc de
        resistencia — atributo maestro en product.template de biocreto_base)
        y los moves de esta entrega (cantidad). Dato ausente => linea con
        valor vacio, nunca romper.
        """
        for pick in self:
            carga = pick.biocreto_carga_ids[:1]
            line = carga.sale_line_id
            placa = carga.vehiculo_id.license_plate or ''
            fc = line.product_id.biocreto_fc_resistencia
            resistencia = str(fc) if fc else ''
            huso = line.biocreto_huso_tmn.display_name or ''
            # v19.0.1.8.0: el slump es un rango. Se toma el computado tal
            # cual (ya viene formateado como '6"' o '7" - 8"'); NO se
            # reconstruye el formato aqui.
            slump = line.biocreto_slump_rango or ''
            cantidad = ''
            if line:
                moves = pick.move_ids.filtered(
                    lambda m: m.product_id == line.product_id and m.state != 'cancel')
                if moves:
                    cantidad = f'{sum(moves.mapped("product_uom_qty")):g}'
            hora = ''
            if carga.hora_fin:
                hora = fields.Datetime.context_timestamp(
                    pick, carga.hora_fin).strftime('%d/%m/%Y %H:%M')
            pick.biocreto_datos_guia = (
                f"Placa: {placa}\n"
                f"Resistencia: {resistencia}\n"
                f"Huso: {huso}\n"
                f"Slump: {slump}\n"
                f"Cantidad: {cantidad}\n"
                f"Cod presinto: {pick.biocreto_codigo_presinto or ''}\n"
                f"Hora de salida: {hora}"
            )

    def write(self, vals):
        res = super().write(vals)
        # Sincronizacion picking -> carga del presinto. El flag de contexto
        # corta el rebote carga -> picking -> carga.
        if 'biocreto_codigo_presinto' in vals and not self.env.context.get('biocreto_sync_presinto'):
            cargas = self.biocreto_carga_ids.filtered(
                lambda c: c.codigo_presinto != vals['biocreto_codigo_presinto'])
            if cargas:
                cargas.with_context(biocreto_sync_presinto=True).write(
                    {'codigo_presinto': vals['biocreto_codigo_presinto']})
        return res
