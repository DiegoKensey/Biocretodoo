import re

from odoo import api, fields, models
from odoo.exceptions import UserError


class BiocretoCarga(models.Model):
    _name = 'biocreto.carga'
    _description = 'Carga de mixer'
    _order = 'hora_inicio desc, id desc'

    name = fields.Char(readonly=True, copy=False)
    production_id = fields.Many2one(
        'mrp.production',
        string="Orden de Fabricacion",
        required=True,
        ondelete='cascade',
        index=True,
    )
    production_group_id = fields.Many2one(
        related='production_id.production_group_id',
        store=True,
        index=True,
        string="Cadena",
    )
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string="Linea de Venta",
        compute='_compute_sale_line_id',
        store=True,
        index=True,
    )
    sale_order_id = fields.Many2one(
        related='sale_line_id.order_id',
        store=True,
        index=True,
        string="Orden de Venta",
    )
    vehiculo_id = fields.Many2one('fleet.vehicle', string="Mixer")
    volumen_operativo = fields.Float(string="Volumen operativo", digits='Product Unit of Measure')
    volumen_facturado = fields.Float(string="Volumen facturado", digits='Product Unit of Measure')
    hora_inicio = fields.Datetime(default=fields.Datetime.now)
    hora_fin = fields.Datetime()
    estado = fields.Selection(
        [('en_curso', 'En curso'), ('terminada', 'Terminada')],
        default='en_curso',
        required=True,
    )
    linea_ids = fields.One2many('biocreto.carga.linea', 'carga_id', string="Dosificacion")
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    picking_id = fields.Many2one(
        'stock.picking', string="Entrega", readonly=True, copy=False, index=True)
    codigo_presinto = fields.Char(string="Código presinto")
    tipo_guia = fields.Selection(
        [('guia_e', 'Guía E.'), ('c_salida', 'C. Salida')],
        string="Tipo de guía",
        compute='_compute_tipo_guia',
    )
    guia_pdf_disponible = fields.Boolean(compute='_compute_guia_pdf_disponible')

    @api.depends('sale_line_id.tax_ids')
    def _compute_tipo_guia(self):
        # Linea con impuestos => venta facturable con guia electronica;
        # sin impuestos => constancia de salida (reporte nativo del picking).
        for rec in self:
            rec.tipo_guia = 'guia_e' if rec.sale_line_id.tax_ids else 'c_salida'

    @api.depends('picking_id')
    def _compute_guia_pdf_disponible(self):
        # bool(picking.biocreto_guia_electronica) obligaria a descargar el
        # binario entero por registro; consultar ir.attachment (res_field)
        # responde lo mismo sin traer contenido.
        atts = self.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'stock.picking'),
             ('res_id', 'in', self.picking_id.ids),
             ('res_field', '=', 'biocreto_guia_electronica')],
            ['res_id'],
        )
        con_guia = {a['res_id'] for a in atts}
        for rec in self:
            rec.guia_pdf_disponible = rec.picking_id.id in con_guia

    @api.depends('production_id.sale_line_id')
    def _compute_sale_line_id(self):
        for rec in self:
            rec.sale_line_id = rec.production_id.sale_line_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                prod = self.env['mrp.production'].browse(vals.get('production_id'))
                group = prod.production_group_id
                existing = self.search_count([('production_group_id', '=', group.id)])
                vals['name'] = f'C{existing + 1:02d}'
        return super().create(vals_list)

    def iniciar(self):
        """Marca la carga como en_curso y setea qty_producing en la OF.

        Tras el write, invoca _set_qty_producing() explicito porque los
        write() programaticos no disparan onchanges (_onchange_qty_producing
        es quien reescala move_raw_ids.quantity con unit_factor por raw en
        mrp/models/mrp_production.py:1356). Sin esta llamada, si el plantero
        no edita las raws en el cliente, TERMINAR consumiria 0 (state=done
        con quantity=0 en cada raw) y no descontaria inventario real.
        """
        for c in self:
            c.production_id.qty_producing = c.volumen_operativo
            # pick_manual_consumption_moves=False replica el _change_producing
            # nativo (mrp_production.py:916): escala qty pero NO marca picked.
            # Terminar() setea picked=True mas tarde.
            c.production_id._set_qty_producing(False)
            c.estado = 'en_curso'
            if not c.hora_inicio:
                c.hora_inicio = fields.Datetime.now()

    def terminar(self, raws_editados=None):
        """Cierra la carga y produce el parcial contra la OF.

        raws_editados: dict {move_raw_id: quantity_editada} — cantidades ajustadas
        por el plantero en la tabla de dosificacion. Solo esas se persisten.

        Flujo (recon B10):
          1) Snapshot de move_raw_ids a linea_ids.
          2) Escribir move_raw_ids.quantity + picked=True, qty_producing.
          3) button_mark_done con skip_backorder=True + mo_ids_to_backorder=[self.production_id.id]
             si queda saldo, [] si no.
          4) Devolver la nueva OF de la cadena (backorder) o False.
        """
        self.ensure_one()
        if self.estado == 'terminada':
            raise UserError("La carga ya esta terminada.")
        mo = self.production_id
        raws_editados = raws_editados or {}

        # 1) Snapshot de dosificacion (todas las raws, con la qty editada o la nativa)
        self.linea_ids.unlink()
        snapshot_vals = []
        for raw in mo.move_raw_ids:
            qty = raws_editados.get(raw.id, raw.quantity)
            snapshot_vals.append({
                'carga_id': self.id,
                'product_id': raw.product_id.id,
                'cantidad': qty,
                'uom_id': raw.product_uom.id,
            })
        if snapshot_vals:
            self.env['biocreto.carga.linea'].create(snapshot_vals)

        # 2) Aplicar cambios a la OF
        for raw in mo.move_raw_ids:
            qty = raws_editados.get(raw.id, raw.quantity)
            raw.quantity = qty
            raw.picked = True
        mo.qty_producing = self.volumen_operativo

        # 3) Marcar la carga terminada ANTES del button_mark_done
        # (asi al mo cerrarse, la carga ya tiene el name de esta OF pre-backorder)
        self.write({
            'estado': 'terminada',
            'hora_fin': fields.Datetime.now(),
        })

        # 4) Cerrar con o sin backorder segun saldo
        # Flags:
        #   skip_backorder: bypasea el wizard mrp.production.backorder
        #   skip_consumption: bypasea el wizard mrp.consumption.warning
        #     (aplica cuando cantidades editadas del plantero difieren de la BoM)
        saldo_restante = mo.product_qty - self.volumen_operativo
        mo_ids_to_backorder = [mo.id] if saldo_restante > 0.001 else []
        ctx = dict(self.env.context,
                   skip_backorder=True,
                   skip_consumption=True,
                   mo_ids_to_backorder=mo_ids_to_backorder)
        mo.with_context(**ctx).button_mark_done()

        # 5) Subentrega: el producto terminado ya entro a stock por el parcial
        # de la OF; ahora sale por su propia entrega validada. Misma
        # transaccion que todo terminar(): si la validacion del picking
        # falla, el rollback deshace tambien el parcial de la OF y el estado
        # de la carga — nunca queda una carga a medias.
        self._procesar_subentrega(ultima=not mo_ids_to_backorder)

        # 6) Devolver la nueva OF activa de la cadena (backorder) si existe
        if mo_ids_to_backorder:
            nueva = mo.production_group_id.production_ids.filtered(
                lambda p: p.id != mo.id and p.state in ('draft', 'confirmed', 'progress', 'to_close')
            )
            return {'nueva_of_id': nueva[:1].id, 'nueva_of_name': nueva[:1].name}
        return {'nueva_of_id': False, 'nueva_of_name': False}

    def _procesar_subentrega(self, ultima):
        """Valida un parcial del OUT de la OV como subentrega de esta carga.

        Mecanica de nombres: el OUT pendiente conserva SIEMPRE el name raiz
        (WH/OUT/00039). Al validar, la entrega hecha se renombra a
        raiz-{nn:03d} y el backorder nativo (que nace con un name nuevo de
        secuencia) se renombra de vuelta a la raiz. El correlativo nn se
        deriva contando pickings ya nombrados 'raiz-%' — no requiere campo
        auxiliar y sobrevive a borrados intermedios sin repetir numeros.

        ultima=True (la OF cerro sin backorder): valida TODO el remanente de
        la demanda de la linea, sin dejar backorder de esa linea.
        """
        self.ensure_one()
        line = self.sale_line_id
        if not line:
            return
        # OUT padre: el pendiente de la OV que aun mueve el producto de la linea
        out = self.sale_order_id.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing'
            and p.state not in ('done', 'cancel')
            and any(m.product_id == line.product_id and m.state not in ('done', 'cancel')
                    for m in p.move_ids)
        )[:1]
        if not out:
            # OV sin entrega pendiente (p.ej. ya validada a mano): la carga
            # queda sin picking_id, sin bloquear el cierre de la OF.
            return

        raiz = re.sub(r'-\d+$', '', out.name)
        nn = self.env['stock.picking'].search_count(
            [('name', '=like', raiz + '-%')]) + 1

        # Reservar (el parcial de la OF acaba de subir stock) y fijar hecho
        out.action_assign()
        moves = out.move_ids.filtered(
            lambda m: m.product_id == line.product_id and m.state not in ('done', 'cancel'))
        for i, move in enumerate(moves):
            move.quantity = move.product_uom_qty if ultima else (
                self.volumen_facturado if i == 0 else 0.0)
            move.picked = bool(move.quantity)
        # Moves de OTRAS lineas quedan picked=False => van integros al
        # backorder (la validacion no los toca).

        # skip_backorder bypasea el wizard stock.backorder.confirmation;
        # al NO estar el picking en picking_ids_not_to_backorder,
        # button_validate lo procesa con cancel_backorder=False y
        # _action_done crea el backorder por el saldo (stock_picking.py:1417).
        out.with_context(skip_backorder=True, skip_sms=True).button_validate()

        backorder = self.env['stock.picking'].search(
            [('backorder_id', '=', out.id)], limit=1)
        # stock.picking tiene unique (name, company_id): flushear el rename
        # de la validada ANTES de que el backorder tome la raiz. Sin el flush
        # intermedio ambos UPDATEs quedan en cache y el ORM puede ejecutarlos
        # en orden inverso -> UniqueViolation sobre la raiz.
        out.name = f'{raiz}-{nn:03d}'
        out.flush_recordset(['name'])
        if backorder:
            backorder.name = raiz
            backorder.flush_recordset(['name'])

        self.picking_id = out
        if self.codigo_presinto:
            out.write({'biocreto_codigo_presinto': self.codigo_presinto})

    def write(self, vals):
        res = super().write(vals)
        # Sincronizacion carga -> picking del presinto (contraparte del
        # write de stock.picking; el flag corta el rebote).
        if 'codigo_presinto' in vals and not self.env.context.get('biocreto_sync_presinto'):
            picks = self.picking_id.filtered(
                lambda p: p.biocreto_codigo_presinto != vals['codigo_presinto'])
            if picks:
                picks.with_context(biocreto_sync_presinto=True).write(
                    {'biocreto_codigo_presinto': vals['codigo_presinto']})
        return res

    def action_open_of(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'res_id': self.production_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class BiocretoCargaLinea(models.Model):
    _name = 'biocreto.carga.linea'
    _description = 'Snapshot de dosificacion de la carga'

    carga_id = fields.Many2one('biocreto.carga', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string="Componente")
    cantidad = fields.Float(digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string="UdM")
