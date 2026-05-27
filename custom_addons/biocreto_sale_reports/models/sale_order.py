from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                company_id = vals.get('company_id') or self.env.company.id
                user_id = vals.get('user_id') or self.env.user.id
                custom_name = self._biocreto_build_name(
                    company_id, user_id, vals.get('date_order'),
                )
                if custom_name:
                    vals['name'] = custom_name
        return super().create(vals_list)

    @api.model
    def _biocreto_build_name(self, company_id, user_id, date_order=None):
        """Construye AÑO-CFC-NV-0001. Devuelve None si la empresa no tiene plant_code."""
        company = self.env['res.company'].browse(company_id)
        if not company.plant_code:
            return None

        user = self.env['res.users'].browse(user_id)
        initials = self._biocreto_compute_initials(user.name)
        plant = company.plant_code.upper()

        seq_date = None
        if date_order:
            seq_date = fields.Datetime.context_timestamp(
                self, fields.Datetime.to_datetime(date_order),
            )
        year_dt = seq_date or fields.Datetime.now()
        year = str(year_dt.year)

        sequence = self._biocreto_ensure_sequence(company_id)
        correlative = sequence.with_company(company_id).next_by_id(sequence_date=seq_date)

        return f"{year}-{plant}-{initials}-{correlative}"

    @api.model
    def _biocreto_compute_initials(self, full_name):
        """2 letras mayúsculas: primera letra de las dos primeras palabras del nombre.

        - "Diego Orcón Gómez" -> "DO"
        - "Fissher Tunque" -> "FT"
        - "Juan" -> "JU"
        - vacío -> "XX"
        """
        if not full_name:
            return "XX"
        words = full_name.strip().split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        if len(words) == 1 and len(words[0]) >= 2:
            return words[0][:2].upper()
        return "XX"

    @api.model
    def _biocreto_ensure_sequence(self, company_id):
        """Crea la secuencia per-empresa si no existe.

        Padding 4, sin prefijo, con date_range anual.
        next_by_id() devuelve sólo el correlativo ('0001', '0002', ...) que se
        concatena en _biocreto_build_name con año-planta-iniciales.
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
                'prefix': '',
                'padding': 4,
                'number_increment': 1,
                'implementation': 'standard',
                'use_date_range': True,
            })
        return sequence

    def _biocreto_get_user_job_title(self):
        """Cargo del asesor con fallback en cascada.

        1) hr.employee.job_id.name (si el módulo hr está instalado)
        2) user_id.partner_id.function
        3) "Asesor Comercial"
        """
        self.ensure_one()
        if not self.user_id:
            return "Asesor Comercial"
        Employee = self.env.get('hr.employee')
        if Employee is not None:
            employee = Employee.sudo().search(
                [('user_id', '=', self.user_id.id)], limit=1,
            )
            if employee and employee.job_id:
                return employee.job_id.name
        if self.user_id.partner_id.function:
            return self.user_id.partner_id.function
        return "Asesor Comercial"

    def _biocreto_get_concreto_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: l.product_id.categ_id.name == 'Concreto'
        )

    def _biocreto_get_bombeo_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: l.product_id.categ_id.name == 'Bombeo'
        )

    def _biocreto_get_concreto_subtotal(self):
        self.ensure_one()
        return sum(self._biocreto_get_concreto_lines().mapped('price_subtotal'))

    def _biocreto_get_bombeo_subtotal(self):
        self.ensure_one()
        return sum(self._biocreto_get_bombeo_lines().mapped('price_subtotal'))

    def _biocreto_get_concreto_total_volume(self):
        self.ensure_one()
        return sum(self._biocreto_get_concreto_lines().mapped('product_uom_qty'))
