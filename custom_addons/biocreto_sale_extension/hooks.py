import logging

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Override del print_report_name de sale.action_report_saleorder.
#
# Por que esto NO se hace via <record id="sale.action_report_saleorder">:
#   El campo `print_report_name` es translate=True. Un <record> en XML
#   data de otro modulo no actualiza el JSONB de traducciones del campo
#   en buckets en_US/es_PE — diagnosticado por shell: tras el -u, los
#   buckets siguen con la traduccion del .po del core
#   (odoo/addons/sale/i18n/es.po:83-89 traduce "Quotation"/"Order" a
#   "Cotizacion"/"Orden", pero conserva el corte nativo en ('draft',
#   'sent')).
#
# Estrategia: escribir programaticamente AMBOS buckets via
# `update_field_translations` — API publica del ORM
# (odoo/orm/models.py:3492). Disponible para todo Model (ir.actions.report
# hereda).
#
# Por que cubrimos tanto -i (post_init_hook) como -u (<function> data):
#   - post_init_hook(env) solo se ejecuta en install
#     (odoo/modules/loading.py:240-243), NO en upgrade. Para los -u
#     posteriores (caso operativo real), un <function> en data XML que
#     invoca el metodo `_biocreto_init_saleorder_print_name` corre en
#     CADA -u (las <function> en data son data records que se reaplican).
#   - Ambos caminos comparten este mismo helper -> una sola fuente de
#     verdad. Idempotente: escribir el mismo valor multiples veces es
#     no-op.
# ──────────────────────────────────────────────────────────────────────
_PRINT_REPORT_NAME_EN = (
    "(object.state in ('draft', 'sent', 'contract', 'programado') "
    "and 'Quotation - %s' % (object.name)) "
    "or 'Order - %s' % (object.name)"
)

_PRINT_REPORT_NAME_ES = (
    "(object.state in ('draft', 'sent', 'contract', 'programado') "
    "and 'Cotización - %s' % (object.name)) "
    "or 'Orden - %s' % (object.name)"
)

_TRANSLATIONS_BY_LANG = {
    'en_US': _PRINT_REPORT_NAME_EN,
    'es_PE': _PRINT_REPORT_NAME_ES,
}


def _biocreto_set_saleorder_print_name(env):
    """Escribe `print_report_name` del action nativo `sale.action_report_saleorder`
    en TODOS los buckets de idioma instalados que conozcamos.

    Tolerante: si el idioma no esta instalado en la BD, lo omite (el ORM
    valida idiomas activos y lanzaria UserError; lo filtramos antes).
    """
    action = env.ref('sale.action_report_saleorder', raise_if_not_found=False)
    if not action:
        _logger.warning(
            "biocreto_sale_extension: sale.action_report_saleorder no "
            "encontrado; se omite el override del print_report_name."
        )
        return

    installed_codes = {code for code, _name in env['res.lang'].get_installed()} | {'en_US'}
    translations = {
        lang: value
        for lang, value in _TRANSLATIONS_BY_LANG.items()
        if lang in installed_codes
    }
    if not translations:
        _logger.warning(
            "biocreto_sale_extension: ningun idioma instalado coincide con "
            "los buckets a escribir (%s); se omite.",
            list(_TRANSLATIONS_BY_LANG),
        )
        return

    # Sembrar en_US primero para que sea base estable del JSONB.
    if 'en_US' in translations:
        action.with_context(lang='en_US').write({
            'print_report_name': translations['en_US'],
        })

    action.update_field_translations('print_report_name', translations)
    _logger.info(
        "biocreto_sale_extension: print_report_name de "
        "sale.action_report_saleorder actualizado en %s.",
        sorted(translations),
    )


def post_init_hook(env):
    """Hook que corre cuando el modulo se INSTALA (no en upgrades)."""
    _biocreto_set_saleorder_print_name(env)
