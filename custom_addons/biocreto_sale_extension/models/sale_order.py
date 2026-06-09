from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ─────────────────────────────────────────────────────────────────
    # Dirección estructurada de la obra (no afecta res.partner)
    # Cascada: Departamento → Provincia → Distrito.
    # Modelos:
    #   - res.country.state           (provisto por base, filtrado a PE)
    #   - res.city                    (provisto por base_address_extended)
    #   - l10n_pe.res.city.district   (provisto por l10n_pe)
    # ─────────────────────────────────────────────────────────────────
    biocreto_state_id = fields.Many2one(
        comodel_name='res.country.state',
        string="Departamento",
        domain="[('country_id.code', '=', 'PE')]",
    )
    biocreto_city_id = fields.Many2one(
        comodel_name='res.city',
        string="Provincia",
        domain="[('state_id', '=', biocreto_state_id)]",
    )
    biocreto_district_id = fields.Many2one(
        comodel_name='l10n_pe.res.city.district',
        string="Distrito",
        domain="[('city_id', '=', biocreto_city_id)]",
    )
    biocreto_street = fields.Char(
        string="Calle / Dirección",
        help="Calle, avenida, jirón y número de la obra.",
    )
    biocreto_direccion_completa = fields.Char(
        string="Dirección completa",
        compute='_compute_biocreto_direccion_completa',
        store=True,
        help="Línea concatenada de la dirección de obra para el reporte.",
    )

    # ─────────────────────────────────────────────────────────────────
    # Geolocalización de la obra (latitud / longitud).
    #
    # Migración v19.0.1.6.0: antes era un Char `biocreto_coordenadas`
    # con formato "lat, lng". Ahora son DOS Float (mismo digits=(10,7)
    # que res.partner.partner_latitude/longitude, addons/base/models/
    # res_partner.py:270-271). El parseo del Char a los dos Float se
    # ejecuta en migrations/19.0.1.6.0/post-migration.py.
    #
    # Por qué Float separados:
    #   · Validables/consultables individualmente (range, group by, etc.).
    #   · Consumibles por la vista <map> (web_map) cuando se inyecten
    #     en un partner espejo (ver investigación documentada).
    #   · Reflejan los mismos bounds que el validador del map_view:
    #     -90 ≤ lat ≤ 90, -180 ≤ lng ≤ 180
    #     (verificado en odoo/addons/web_map/static/src/map_view/
    #     map_model.js:162-174).
    # ─────────────────────────────────────────────────────────────────
    biocreto_latitud = fields.Float(
        string="Latitud",
        digits=(10, 7),
        help="Latitud de la obra en grados decimales. Ej.: -12.0653000",
    )
    biocreto_longitud = fields.Float(
        string="Longitud",
        digits=(10, 7),
        help="Longitud de la obra en grados decimales. Ej.: -75.2049000",
    )
    biocreto_tipo_proyecto = fields.Selection(
        selection=[
            ('menor', 'Menor envergadura'),
            ('mayor', 'Mayor envergadura'),
        ],
        string="Tipo de proyecto",
        default='menor',
    )

    # ─────────────────────────────────────────────────────────────────
    # Fecha de vaceo (rango fecha+hora). El widget 'daterange' usa el
    # mismo patrón que event.event (date_begin/date_end). El inicio se
    # sincroniza a commitment_date (campo nativo de sale.order) — así
    # los procesos de Programación/Stock leen una sola fuente.
    # ─────────────────────────────────────────────────────────────────
    biocreto_fecha_vaceo_inicio = fields.Datetime(string="Fecha de vaceo (inicio)")
    biocreto_fecha_vaceo_fin = fields.Datetime(string="Fecha de vaceo (fin)")

    # ─────────────────────────────────────────────────────────────────
    # URL de Google Maps Directions hacia la obra (computed, no-store).
    #
    # Vive en sale_extension (no en biocreto_programacion) porque la URL
    # depende directamente de campos de extension (latitud/longitud y
    # biocreto_direccion_completa). Otros módulos —reportes, portal,
    # programación, etc.— pueden consumir esta misma URL.
    #
    # Reglas:
    #   · Si lat y lng son ambas distintas de 0 y respetan rango
    #     (-90 ≤ lat ≤ 90, -180 ≤ lng ≤ 180): usa "lat,lng".
    #   · "(0,0)" se trata como ausencia (default vacío) para no marcar
    #     al Golfo de Guinea por accidente.
    #   · Fallback: dirección textual URL-encoded.
    #   · Si nada: False → el botón "Ir a" no se renderiza.
    # ─────────────────────────────────────────────────────────────────
    biocreto_gmaps_url = fields.Char(
        string="URL Google Maps",
        compute='_compute_biocreto_gmaps_url',
        help="URL de Google Maps Directions hacia la obra. Computada al vuelo "
             "desde biocreto_latitud/biocreto_longitud (preferente) o "
             "biocreto_direccion_completa. No se almacena.",
    )

    @api.depends('biocreto_latitud', 'biocreto_longitud', 'biocreto_direccion_completa')
    def _compute_biocreto_gmaps_url(self):
        base = "https://www.google.com/maps/dir/?api=1&destination="
        for order in self:
            lat = order.biocreto_latitud
            lng = order.biocreto_longitud
            destino = False
            if lat and lng and -90 <= lat <= 90 and -180 <= lng <= 180:
                destino = f"{lat},{lng}"
            elif order.biocreto_direccion_completa:
                destino = quote(order.biocreto_direccion_completa)
            order.biocreto_gmaps_url = (base + destino) if destino else False

    # ─────────────────────────────────────────────────────────────────
    # Estado de diseño (computed): tag rojo/verde según si las líneas
    # de Concreto tienen ya bom_id (Boom) asignado.
    # ─────────────────────────────────────────────────────────────────
    biocreto_estado_diseno = fields.Selection(
        selection=[
            ('pendiente', 'Pendiente diseño'),
            ('asignado', 'Diseño asignado'),
        ],
        string="Estado de diseño",
        compute='_compute_biocreto_estado_diseno',
        store=True,
    )

    @api.depends(
        'order_line.bom_id',
        'order_line.biocreto_product_categ',
        'order_line.product_id',
        'order_line.display_type',
    )
    def _compute_biocreto_estado_diseno(self):
        for order in self:
            concreto_lines = order.order_line.filtered(
                lambda l: not l.display_type and l.biocreto_product_categ == 'Concreto'
            )
            if not concreto_lines:
                order.biocreto_estado_diseno = False
            elif all(line.bom_id for line in concreto_lines):
                order.biocreto_estado_diseno = 'asignado'
            else:
                order.biocreto_estado_diseno = 'pendiente'

    # ─────────────────────────────────────────────────────────────────
    # Sincronización Fecha de vaceo (inicio) → commitment_date.
    # Se hace en onchange (UI) y se asegura también en create/write para
    # entradas vía RPC / import / portal.
    # ─────────────────────────────────────────────────────────────────
    @api.onchange('biocreto_fecha_vaceo_inicio')
    def _onchange_biocreto_fecha_vaceo_inicio(self):
        if self.biocreto_fecha_vaceo_inicio:
            self.commitment_date = self.biocreto_fecha_vaceo_inicio

    # ─────────────────────────────────────────────────────────────────
    # Concatenación: "Distrito, Provincia, Departamento - Calle"
    # ─────────────────────────────────────────────────────────────────
    @api.depends(
        'biocreto_street',
        'biocreto_district_id',
        'biocreto_city_id',
        'biocreto_state_id',
    )
    def _compute_biocreto_direccion_completa(self):
        # v19.0.1.6.1: orden visual = "calle - distrito, provincia, depto".
        # (Antes era "distrito, provincia, depto - calle"; el cliente prefiere
        # la calle primero porque es lo más específico para identificar la
        # obra en el reporte y en el popup del mapa.)
        for order in self:
            partes_zona = []
            if order.biocreto_district_id:
                partes_zona.append(order.biocreto_district_id.name)
            if order.biocreto_city_id:
                partes_zona.append(order.biocreto_city_id.name)
            if order.biocreto_state_id:
                partes_zona.append(order.biocreto_state_id.name)
            zona = ", ".join(partes_zona)
            calle = order.biocreto_street or ""
            if calle and zona:
                order.biocreto_direccion_completa = "%s - %s" % (calle, zona)
            else:
                # Solo uno de los dos (o ninguno). Sin separador colgante.
                order.biocreto_direccion_completa = calle or zona or False

    # ─────────────────────────────────────────────────────────────────
    # Cascada: limpiar campos hijos cuando cambia el padre
    # ─────────────────────────────────────────────────────────────────
    @api.onchange('biocreto_state_id')
    def _onchange_biocreto_state_id(self):
        if self.biocreto_city_id and self.biocreto_city_id.state_id != self.biocreto_state_id:
            self.biocreto_city_id = False
            self.biocreto_district_id = False

    @api.onchange('biocreto_city_id')
    def _onchange_biocreto_city_id(self):
        if self.biocreto_district_id and self.biocreto_district_id.city_id != self.biocreto_city_id:
            self.biocreto_district_id = False

    # ─────────────────────────────────────────────────────────────────
    # Naming custom: AÑO-CFC-NV-0001
    # ─────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Solo asignar nombre custom si:
            # 1. No viene un name explícito (o viene 'New' / vacío)
            # 2. La empresa tiene plant_code configurado
            if vals.get('name', _('New')) == _('New') or not vals.get('name'):
                company_id = vals.get('company_id') or self.env.company.id
                user_id = vals.get('user_id') or self.env.user.id
                custom_name = self._biocreto_build_name(company_id, user_id)
                if custom_name:
                    vals['name'] = custom_name
                # Si custom_name es None, deja que Odoo asigne el name nativo
            # Replicar el onchange en create: si entra fecha de vaceo (RPC,
            # import, portal) pero no commitment_date, propagar el inicio.
            if vals.get('biocreto_fecha_vaceo_inicio') and not vals.get('commitment_date'):
                vals['commitment_date'] = vals['biocreto_fecha_vaceo_inicio']
        return super().create(vals_list)

    def write(self, vals):
        # Idem create: mantener commitment_date alineado con el inicio del
        # rango cuando el cliente edita la fecha desde cualquier canal.
        if 'biocreto_fecha_vaceo_inicio' in vals and 'commitment_date' not in vals:
            vals['commitment_date'] = vals['biocreto_fecha_vaceo_inicio']
        return super().write(vals)

    @api.model
    def _biocreto_build_name(self, company_id, user_id):
        """Construye AÑO-CFC-NV-0001. Retorna None si la empresa no tiene plant_code."""
        company = self.env['res.company'].browse(company_id)
        if not company.plant_code:
            return None

        user = self.env['res.users'].browse(user_id)
        initials = self._biocreto_compute_initials(user.name)
        plant = company.plant_code.upper()
        year = str(fields.Date.context_today(self).year)

        sequence = self._biocreto_ensure_sequence(company_id)
        correlative = sequence.with_company(company_id).next_by_id()

        return f"{year}-{plant}-{initials}-{correlative}"

    @api.model
    def _biocreto_compute_initials(self, full_name):
        """
        Calcula 2 letras mayúsculas desde el nombre del vendedor:
        - 'Diego Orcón Gómez' → 'DO'
        - 'Fissher Tunque'    → 'FT'
        - 'Juan' (una palabra) → 'JU'
        - vacío               → 'XX'
        """
        if not full_name:
            return "XX"
        words = full_name.strip().split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        if len(words) == 1 and len(words[0]) >= 2:
            return words[0][:2].upper()
        return "XX"

    # ─────────────────────────────────────────────────────────────────
    # Validación al CONFIRMAR (no en cada guardado)
    #
    # Por qué está en un helper público y no SOLO dentro de action_confirm:
    # biocreto_sale_contract_state sobreescribe action_confirm e intercepta
    # el flujo draft/sent → contract SIN llamar super() (sólo escribe el
    # estado). En ese tránsito, nuestro action_confirm nunca corre. Para
    # que la validación dispare ANTES de pasar a Contrato, contract_state
    # debe poder invocarla explícitamente — por eso la lógica vive en un
    # helper público (_biocreto_validate_before_confirm) que contract_state
    # llama antes de su write({'state': 'contract'}).
    #
    # No usa @api.constrains a propósito: causaría un bucle al impedir
    # guardar la cotización en borrador para abrir el popup de la línea.
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_validate_before_confirm(self):
        """Validaciones pre-confirmación (en orden):
        1. Debe existir al menos una línea de producto (no sección/nota).
        2. Las líneas de Concreto deben tener completos sus 4 campos técnicos.
        3. Debe existir Fecha de vaceo (inicio y fin) y fin >= inicio.

        Lanza ValidationError ante el primer problema encontrado.

        Llamado desde:
        - SaleOrder.action_confirm (este módulo): valida en contract → sale.
        - SaleOrder.action_confirm (biocreto_sale_contract_state): valida
          en draft/sent → contract, ANTES del write que cambia el estado.
        """
        for order in self:
            # ── Validación 1: al menos una línea de producto real ──
            lineas_producto = order.order_line.filtered(
                lambda l: not l.display_type
            )
            if not lineas_producto:
                raise ValidationError(_(
                    "No se puede confirmar la cotización porque no tiene "
                    "ningún producto. Agregue al menos una línea de producto "
                    "(Concreto o Bombeo) antes de confirmar."
                ))

            # ── Validación 2: campos técnicos de Concreto completos ──
            missing_lines = []
            for line in lineas_producto:
                if line.biocreto_product_categ == 'Concreto':
                    faltantes = []
                    if not line.biocreto_estructura:
                        faltantes.append("Estructura")
                    if not line.biocreto_tipo_cemento:
                        faltantes.append("Tipo de cemento")
                    if not line.biocreto_huso_tmn:
                        faltantes.append("Huso TMN")
                    if not line.biocreto_slump:
                        faltantes.append("Slump")
                    if faltantes:
                        missing_lines.append(
                            "  • %s: falta %s" % (
                                line.product_id.display_name or "(sin producto)",
                                ", ".join(faltantes),
                            )
                        )
            if missing_lines:
                raise ValidationError(_(
                    "No se puede confirmar la cotización. Las siguientes "
                    "líneas de Concreto tienen campos técnicos incompletos:"
                    "\n\n%s\n\n"
                    "Complete los campos abriendo el detalle de cada línea "
                    "(ícono de expandir) antes de confirmar."
                ) % "\n".join(missing_lines))

            # ── Validación 3: Fecha de vaceo (inicio y fin) ──
            if not order.biocreto_fecha_vaceo_inicio or not order.biocreto_fecha_vaceo_fin:
                raise ValidationError(_(
                    "Debe registrar la Fecha de vaceo (inicio y fin) en "
                    "Información de Suministro antes de continuar."
                ))
            if order.biocreto_fecha_vaceo_fin < order.biocreto_fecha_vaceo_inicio:
                raise ValidationError(_(
                    "La Fecha de vaceo (fin) no puede ser anterior al inicio."
                ))

    def action_confirm(self):
        self._biocreto_validate_before_confirm()
        return super().action_confirm()

    @api.model
    def _biocreto_ensure_sequence(self, company_id):
        """
        Garantiza que existe una secuencia para la empresa indicada.
        Prefijo vacío (solo correlativo), padding 4, reinicio anual.
        Si no existe, la crea.
        """
        Sequence = self.env['ir.sequence'].sudo()
        seq_code = f'biocreto.sale.order.{company_id}'
        sequence = Sequence.search([
            ('code', '=', seq_code),
            ('company_id', '=', company_id),
        ], limit=1)
        if not sequence:
            company = self.env['res.company'].browse(company_id)
            sequence = Sequence.create({
                'name': f'BIOCRETO Cotización - {company.name}',
                'code': seq_code,
                'company_id': company_id,
                'padding': 4,
                'number_increment': 1,
                'implementation': 'standard',
                'use_date_range': True,
                'prefix': '',
            })
        return sequence
