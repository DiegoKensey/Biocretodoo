from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ─────────────────────────────────────────────────────────────────
    # Campos de Datos de Obra
    # ─────────────────────────────────────────────────────────────────
    biocreto_direccion_proyecto = fields.Char(
        string="Dirección del proyecto",
        help="Dirección física de la obra o proyecto.",
    )
    biocreto_coordenadas = fields.Char(
        string="Coordenadas",
        help="Coordenadas GPS en formato decimal (latitud, longitud). "
             "Use el botón 'Obtener ubicación' o ingrese manualmente.",
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
        return super().create(vals_list)

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
    # Reemplaza al antiguo @api.constrains en sale.order.line, que creaba
    # un bucle: para llenar el popup había que guardar, y al guardar el
    # constrains bloqueaba si los campos técnicos aún no estaban llenos.
    # ─────────────────────────────────────────────────────────────────
    def action_confirm(self):
        """Valida que las líneas de Concreto tengan sus campos técnicos
        completos antes de confirmar la cotización.

        Nota sobre la cadena con biocreto_sale_contract_state: ese módulo
        depende de éste y también sobreescribe action_confirm. En su flujo
        draft/sent → contract NO llama super(), así que esta validación
        no corre en ese tránsito. Sí corre en contract → sale (donde
        contract_state sí llama super), evitando que una orden con datos
        BIOCRETO incompletos se convierta en venta confirmada.
        """
        for order in self:
            missing_lines = []
            for line in order.order_line:
                if line.display_type:
                    continue  # saltar secciones y notas
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
                    "\n\n%s"
                ) % "\n".join(missing_lines))
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
