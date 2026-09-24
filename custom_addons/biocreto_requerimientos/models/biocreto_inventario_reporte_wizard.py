# ═══════════════════════════════════════════════════════════════════════
#  Dialogo de impresion del inventario de activos (BC-GL-FR-15)
#
#  TransientModel, siguiendo el patron de
#  `biocreto.requerimiento.cotizacion.wizard` (models/consolidado.py:629):
#  campos en el propio dialogo, un solo `action_*` que hace el trabajo y
#  devuelve una accion. Sin estados y sin datos persistentes.
#
#  Se puede descargar SIEMPRE. No hay cierre de periodo que abrir ni
#  cerrar: el corte lo pone la fecha del dialogo.
# ═══════════════════════════════════════════════════════════════════════
from odoo import _, fields, models
from odoo.exceptions import UserError


class BiocretoInventarioReporteWizard(models.TransientModel):
    _name = 'biocreto.inventario.reporte.wizard'
    _description = 'Imprimir inventario de activos por área'

    # Vacio = TODAS las areas. No se pone un valor "todas" en un
    # Selection aparte: un Many2one vacio ya significa "sin filtro" en
    # todo Odoo, y asi el campo se puede usar tal cual en el dominio.
    department_id = fields.Many2one(
        'hr.department', string="Área", check_company=True,
        help="Vacío: se imprimen todas las áreas que tengan conteo.")

    estado = fields.Selection(
        [('todos', "Todos los productos"),
         ('fuera', "Solo los que tienen unidades fuera de Bueno")],
        string="Estado", default='todos', required=True)

    fecha_corte = fields.Date(
        string="Fecha de corte", required=True,
        default=fields.Date.context_today,
        help="Se imprime, de cada área, su último conteo VALIDADO con fecha "
             "igual o anterior a esta.")

    company_id = fields.Many2one(
        'res.company', string="Compañía", required=True,
        default=lambda self: self.env.company)

    # ─────────────────────────────────────────────────────────────────
    # EL FILTRO POR FECHA DE CORTE
    #
    # La pregunta que responde el reporte es «cómo estaba el inventario a
    # fecha X», no «qué conteos hubo antes de X». Así que NO basta con
    # filtrar `fecha <= corte`: eso imprimiría los doce conteos del año
    # de un área. Hay que quedarse con UNO por área, el último.
    #
    # Implementacion: un solo `search` ordenado `fecha desc, id desc`
    # —que es ya el `_order` del modelo— y una pasada quedandose con el
    # PRIMER conteo que aparece de cada departamento. Al venir ordenado,
    # el primero que se ve de cada area es su mas reciente. Una sola
    # consulta, sin read_group ni subconsultas.
    #
    # El desempate por `id desc` importa de verdad: dos conteos del mismo
    # dia son un caso real (se rehace uno) y gana el creado despues.
    # ─────────────────────────────────────────────────────────────────
    def _biocreto_conteos(self):
        self.ensure_one()
        dominio = [
            ('company_id', '=', self.company_id.id),
            ('fecha', '<=', self.fecha_corte),
            # SOLO VALIDADOS. Sin este filtro, un borrador a medias
            # —con los tres estados a cero y sin revisar— saldria como
            # el inventario oficial del periodo, que es justo el
            # documento que alguien archiva y firma. Un borrador se
            # imprime desde su propio formulario, y sale rotulado.
            ('state', '=', 'validado'),
        ]
        if self.department_id:
            dominio.append(('department_id', '=', self.department_id.id))

        ultimos = {}
        for conteo in self.env['biocreto.inventario.conteo'].search(
                dominio, order='fecha desc, id desc'):
            ultimos.setdefault(conteo.department_id.id, conteo)

        # Se devuelve un recordset, no una lista: `report_action` lo
        # exige, y ademas asi el reporte recibe los documentos en el
        # orden del modelo. Se reordena por nombre de area para que el
        # PDF de "todas" salga alfabetico y no por fecha.
        ids = [c.id for c in sorted(
            ultimos.values(), key=lambda c: (c.department_id.name or '').lower())]
        return self.env['biocreto.inventario.conteo'].browse(ids)

    def action_imprimir(self):
        self.ensure_one()
        conteos = self._biocreto_conteos()
        if not conteos:
            raise UserError(_(
                "No hay ningún conteo VALIDADO con fecha igual o anterior al "
                "%(fecha)s%(area)s.\n\n"
                "Un conteo en borrador o pendiente de validar se imprime "
                "desde su propio formulario, y sale rotulado como borrador.",
                fecha=fields.Date.to_string(self.fecha_corte),
                area=(_(" para el área «%s»", self.department_id.name)
                      if self.department_id else _(" en esta compañía")),
            ))
        return self.env.ref(
            'biocreto_requerimientos.action_report_inventario_activos'
        ).report_action(conteos, data={'estado': self.estado})


class ReportInventarioActivos(models.AbstractModel):
    """Modelo de render del reporte.

    Existe SOLO para que `data` llegue a la plantilla. El
    `_get_report_values` por defecto no propaga el diccionario `data` de
    `report_action`, y el filtro de estado del diálogo viaja justamente
    ahí. El nombre del modelo es obligatorio: `report.<módulo>.<template>`
    es lo que busca `ir.actions.report._render_qweb_html`.
    """
    _name = 'report.biocreto_requerimientos.report_inventario_activos'
    _description = 'Render del inventario de activos por área'

    def _get_report_values(self, docids, data=None):
        conteos = self.env['biocreto.inventario.conteo'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'biocreto.inventario.conteo',
            'docs': conteos,
            # 'todos' cuando se imprime desde el boton de la lista o el
            # menu de Imprimir, sin pasar por el dialogo.
            'estado': (data or {}).get('estado') or 'todos',
        }
