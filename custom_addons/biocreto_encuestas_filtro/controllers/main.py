"""
Override del controller Survey para anadir filtro de fecha por create_date
en /survey/results/<survey>.

Diseno (server-side URL-driven, identico al patron nativo "finished/passed"):
  - El JS de la barra de filtros hace:
      params.set("date_from", "YYYY-MM-DD"); params.set("date_to", "YYYY-MM-DD");
      redirect(window.location.pathname + "?" + params.toString());
  - El controller relee `**post` y este override anade los Domain extra antes
    de devolver el dominio combinado.
  - El DOM resultante ya esta filtrado en server-side -> el boton imprimir
    (window.print() puro, ver survey_result.js:107-117) imprime lo filtrado
    automaticamente. CERO trabajo extra para que imprimir respete el filtro.

Punto de extension elegido: `_get_results_page_user_input_domain`. Es el unico
metodo del flujo de resultados que devuelve un Domain sobre survey.user_input
(donde vive `create_date`). Lo usan TANTO `_extract_filters_data` (linea 837 de
survey/controllers/main.py) COMO el render directo del template (via survey_data
en _prepare_statistics). Override 1 sola vez -> aplica en todo el flujo.

NO se overrida `survey_report` (renderiza el template): el template hereda
los <input> con `request.params.get('date_from'/'date_to')` directamente —
`request` es global en QWeb, evitamos replicar el metodo entero del nativo
y mantenemos cero divergencia con futuros upgrades del addon `survey`.
"""
from datetime import datetime, timedelta

from odoo.fields import Domain
from odoo.addons.survey.controllers.main import Survey


class BiocretoSurveyFiltro(Survey):

    def _get_results_page_user_input_domain(self, survey, **post):
        domain = super()._get_results_page_user_input_domain(survey, **post)

        extras = []

        date_from = (post.get('date_from') or '').strip()
        if date_from:
            try:
                dt_from = datetime.strptime(date_from[:10], '%Y-%m-%d')
                extras.append(Domain('create_date', '>=', dt_from))
            except ValueError:
                # Querystring corrupta -> ignora silenciosamente, no rompemos
                # la pagina por una fecha mal formada.
                pass

        date_to = (post.get('date_to') or '').strip()
        if date_to:
            try:
                dt_to = datetime.strptime(date_to[:10], '%Y-%m-%d')
                # "Hasta X" debe incluir TODO el dia X (00:00 -> 23:59:59),
                # no cortar al amanecer.
                dt_to_eod = dt_to + timedelta(days=1, seconds=-1)
                extras.append(Domain('create_date', '<=', dt_to_eod))
            except ValueError:
                pass

        if extras:
            domain = Domain.AND([domain, *extras])

        return domain
