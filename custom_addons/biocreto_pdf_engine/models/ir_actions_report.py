import io
import logging
import os
import re
import tempfile
from collections import OrderedDict

from odoo import models

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # =================================================================
    # Hook de seleccion (lista interna, extensible por modulos hijos)
    # =================================================================
    # Cada modulo de reporte BIOCRETO que quiera usar PlutoPrint extiende
    # este metodo con super() y agrega su propio report_name al set.
    # El motor base NO conoce ningun reporte (set vacio) -> sin reportes
    # marcados, este modulo es invisible: todos los reportes siguen en
    # wkhtmltopdf via el _render_qweb_pdf nativo.
    #
    # Patron de extension (ej. desde biocreto_sale_report_cotizacion):
    #
    #     def _biocreto_usa_plutoprint(self):
    #         res = super()._biocreto_usa_plutoprint()
    #         res.add('biocreto_sale_report_cotizacion.report_cotizacion')
    #         return res
    #
    # Por que un set y no un campo en la BD:
    #   - Sin UI por diseno: nadie activa/desactiva PlutoPrint en runtime
    #     desde Odoo. La decision es de codigo, no de configuracion.
    #   - El owner de la decision es el modulo del reporte, no el motor.
    # =================================================================
    def _biocreto_usa_plutoprint(self):
        return set()

    # =================================================================
    # Override de _render_qweb_pdf_prepare_streams (Odoo 19, l.811)
    # =================================================================
    # v19.0.1.0.7: el override anterior estaba en `_render_qweb_pdf`
    # (top-level), pero el routing real de Odoo 19 hace:
    #
    #   _render_qweb_pdf(report_ref, res_ids, data)        # l.1030
    #     -> _pre_render_qweb_pdf(...)                     # l.1016
    #          -> _render_qweb_pdf_prepare_streams(...)    # l.811
    #               -> _run_wkhtmltopdf(...)               # l.888
    #     -> merge streams -> return (bytes, 'pdf')
    #
    # TODOS los caminos (boton individual, lote desde menu, correo,
    # portal) llegan a `_render_qweb_pdf_prepare_streams`. Override
    # arriba (`_render_qweb_pdf`) solo se disparaba en single-print y
    # cuando el HTML llegaba con N docs (multi-print), procesaba un
    # solo HTML con N <style>@page</style>, N `position: running()`,
    # etc. -> PlutoPrint reventaba -> super() caia a wkhtml con
    # tildes corruptas (sintoma confirmado por usuario).
    #
    # Solucion: override en `prepare_streams`, loopear POR res_id,
    # cada doc en su propio Book de PlutoPrint. Sin colisiones
    # multi-doc, cubre los 4 canales (single, multi, portal, correo)
    # porque todos pasan por aqui.
    #
    # Contrato: devolver OrderedDict {res_id: {'stream': BytesIO,
    # 'attachment': None|attachment}}. El nativo merge'a los streams
    # para single-PDF (multi-print) o usa stream individual (correo).
    #
    # Aislamiento total:
    #   - report_name NO en el set marcado -> super() inmediato.
    #   - ImportError / fallo por res_id -> super() para ese id solo.
    #     Los demas siguen por pluto. Bug en un doc no contamina lote.
    # =================================================================
    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        report = self._get_report(report_ref)
        if report.report_name not in self._biocreto_usa_plutoprint():
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids,
            )
        if not res_ids:
            # Sin res_ids: caso raro (preview sin docs). Dejar al nativo.
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids,
            )

        # Import diferido: sin plutoprint -> super() (cadena nativa).
        try:
            import plutoprint
        except ImportError:
            _logger.warning(
                "biocreto_pdf_engine: PlutoPrint no instalado; fallback "
                "a wkhtmltopdf para %s",
                report.report_name,
            )
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids,
            )

        collected_streams = OrderedDict()
        for res_id in res_ids:
            try:
                pdf_bytes = self._biocreto_render_one_pdf(
                    plutoprint, report, report_ref, res_id, data,
                )
                collected_streams[res_id] = {
                    'stream': io.BytesIO(pdf_bytes),
                    'attachment': None,
                }
            except Exception as exc:
                # Log con traceback completo. Fallback super() SOLO
                # para este res_id (los demas siguen por pluto si
                # tambien fueron solicitados).
                _logger.exception(
                    "biocreto_pdf_engine: PlutoPrint fallo en %s "
                    "para res_id=%s; fallback wkhtml para ese id: %s",
                    report.report_name, res_id, exc,
                )
                fallback = super()._render_qweb_pdf_prepare_streams(
                    report_ref, data, res_ids=[res_id],
                )
                collected_streams.update(fallback)
        return collected_streams

    # =================================================================
    # Render de UN solo res_id via PlutoPrint
    # =================================================================
    # Aislado en su propio metodo para que el loop de
    # `_render_qweb_pdf_prepare_streams` lo invoque sin duplicar
    # codigo y para que sea facil de testear / overridear desde un
    # modulo hijo si hace falta.
    # =================================================================
    def _biocreto_render_one_pdf(self, plutoprint, report, report_ref, res_id, data):
        # 1) Render HTML para UN solo res_id. Sin contaminacion multi-doc.
        html_result, _html_type = self._render_qweb_html(
            report_ref, [res_id], data=data,
        )
        if isinstance(html_result, bytes):
            html_result = html_result.decode('utf-8')

        # 2) Inline del CSS bundle (web.report_assets_common, etc.).
        html_result = self._biocreto_inline_assets(html_result)

        # 3) Tamano de pagina + margins NONE (el @page del CSS manda).
        paperformat = report.get_paperformat()
        page_size = self._biocreto_plutoprint_page_size(
            plutoprint, paperformat,
        )

        # 4) base_url para recursos no inlineados (QR ya no aplica
        # con -pluto-qrcode, pero imagenes/fonts pueden quedar).
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        ) or 'http://localhost:8069'

        # 5) Book con margins NONE (sino paperformat Odoo de 52mm
        # mete hueco arriba del header SVG).
        page_margins = getattr(plutoprint, 'PAGE_MARGINS_NONE', None)
        if page_margins is not None:
            book = plutoprint.Book(page_size, page_margins)
        else:
            _logger.warning(
                "biocreto_pdf_engine: plutoprint.PAGE_MARGINS_NONE "
                "no disponible; usando constructor de 1-arg"
            )
            book = plutoprint.Book(page_size)
        book.load_html(html_result, base_url + '/')

        # 6) write_to_pdf via tempfile (NO BytesIO; PlutoPrint 0.20.0
        # exige str/PathLike).
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            book.write_to_pdf(tmp_path)
            with open(tmp_path, 'rb') as fh:
                pdf_content = fh.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        if not pdf_content:
            raise RuntimeError("PlutoPrint devolvio PDF vacio")

        _logger.info(
            "biocreto_pdf_engine: PlutoPrint OK %s res_id=%s (%d bytes)",
            report.report_name, res_id, len(pdf_content),
        )
        return pdf_content

    # =================================================================
    # Mapeo paperformat (Odoo) -> PageSize (PlutoPrint)
    # =================================================================
    # PlutoPrint expone constantes de tamanos estandar y un metodo
    # .landscape() para rotar. Los MARGENES del PDF los maneja el propio
    # CSS del reporte via @page { margin: ... } (la cotizacion ya tiene
    # margenes laterales 0 desde su SCSS) -> aqui NO trasladamos los
    # margin_top/bottom/left/right del paperformat de Odoo. Eso pertenece
    # al CSS del template; pasar tamano+orientacion es suficiente.
    #
    # PageSize custom (page_width/page_height en mm en el paperformat)
    # queda pendiente como mejora futura: la API publica de plutoprint
    # 0.20.0 documenta PAGE_SIZE_A4 y landscape(), pero no acepta
    # dimensiones arbitrarias por API. Si algun reporte BIOCRETO requiere
    # un tamano distinto a A4, se evalua extender este helper cuando
    # surja la necesidad (override en el modulo del reporte).
    # =================================================================
    def _biocreto_plutoprint_page_size(self, plutoprint, paperformat):
        size = plutoprint.PAGE_SIZE_A4
        try:
            orient = (paperformat and paperformat.orientation or '').lower()
            if orient == 'landscape':
                size = size.landscape()
        except Exception:
            # Cualquier mismatch de API: el size default sigue siendo
            # valido (A4 vertical). El render no falla por esto.
            pass
        return size

    # =================================================================
    # Inline de bundles CSS (`/web/assets/...css`)
    # =================================================================
    # En Odoo 19 los asset bundles compilados se materializan como
    # ir.attachment con `url='/web/assets/<hash>/<bundle>.min.css'` y
    # los bytes del archivo en `raw` (verificado en odoo/addons/web/
    # controllers/binary.py y odoo/addons/base/models/assetsbundle.py).
    # Hacer search por nombre de bundle + leer .raw es la via directa
    # SIN pasar por HTTP, asi que funciona aunque el worker web no este
    # listo en el instante del render.
    #
    # v19.0.1.0.5: el match por URL exacta (con hash) es FRAGIL. El
    # `<link>` puede pedir un hash fantasma que no esta en BD (verificado
    # en shell: el HTML pide `/web/assets/d6d1164/...` pero el attachment
    # vive en `/web/assets/fa7331a/...`). Ademas pueden coexistir 3
    # attachments para el mismo bundle (autoprefixed stale + min fresco)
    # y el hash exacto no garantiza tomar el correcto. Cambio: match por
    # NOMBRE DE BUNDLE extraido del href, con seleccion entre candidatos
    # que prefiere el .min.css NO-autoprefixed mas reciente. Inmune a
    # recompilaciones que invalidan el hash del <link>.
    #
    # Alternativas descartadas:
    #   - `_get_asset_content()` / `_get_asset_bundle()`: APIs internas
    #     que cambian entre versiones; search por nombre es estable.
    #   - HTTP request al endpoint: re-introduce la dependencia de red
    #     que justamente queremos eliminar.
    # =================================================================
    def _biocreto_inline_assets(self, html):
        link_re = re.compile(
            r'<link[^>]+href="(/web/assets/[^"]+\.css)"[^>]*>'
        )
        hrefs = set(link_re.findall(html))
        if not hrefs:
            return html
        inlined = 0
        for href in hrefs:
            try:
                attachment = self._biocreto_pick_bundle(href)
                if not attachment or not attachment.raw:
                    _logger.warning(
                        "biocreto_pdf_engine: bundle no encontrado "
                        "para %s; <link> queda sin inlinear",
                        href,
                    )
                    continue
                css = attachment.raw.decode('utf-8', errors='ignore')
                # re.sub con lambda para evitar que el CSS se interprete
                # como replacement string (backrefs \1, \\, etc.).
                # Cubre cualquier orden/comillas de atributos en el <link>.
                html = re.sub(
                    r'<link[^>]+href="' + re.escape(href) + r'"[^>]*>',
                    lambda m, c=css: '<style>' + c + '</style>',
                    html,
                )
                inlined += 1
                _logger.info(
                    "biocreto_pdf_engine: inline %s -> attachment "
                    "id=%s (%s, %d bytes)",
                    href, attachment.id, attachment.url,
                    len(attachment.raw),
                )
            except Exception as exc:
                # Tolerante: un bundle fallido NO debe romper el render.
                # Si el <link> no se sustituye, PlutoPrint intentara
                # bajarlo por HTTP (fallback al comportamiento anterior).
                _logger.warning(
                    "biocreto_pdf_engine: error inlineando %s: %s",
                    href, exc,
                )
        if inlined:
            _logger.info(
                "biocreto_pdf_engine: inlineados %d bundle(s) CSS",
                inlined,
            )
        return html

    # =================================================================
    # Seleccion de attachment de bundle CSS, robusta al hash de la URL
    # =================================================================
    # Estrategia: extraer el nombre base del bundle del href, buscar
    # todos los candidatos por nombre + mimetype, y preferir el .min.css
    # NO-autoprefixed mas reciente. Cae a autoprefixed solo si no hay
    # alternativa. Inmune al hash en el href (que se desincroniza en
    # cada recompile del bundle).
    #
    # Ejemplos de parsing:
    #   /web/assets/d6d1164/web.report_assets_common.autoprefixed.min.css
    #     fname = 'web.report_assets_common.autoprefixed.min.css'
    #     base  = 'web.report_assets_common'
    #   /web/assets/fa7331a/web.report_assets_common.min.css
    #     fname = 'web.report_assets_common.min.css'
    #     base  = 'web.report_assets_common'
    # Mismo base -> mismos candidatos -> misma seleccion.
    # =================================================================
    def _biocreto_pick_bundle(self, href):
        fname = href.rsplit('/', 1)[-1]
        base = (
            fname
            .replace('.autoprefixed', '')
            .replace('.min.css', '')
            .replace('.css', '')
        )
        candidates = self.env['ir.attachment'].sudo().search([
            ('url', 'like', '%' + base + '%'),
            ('url', '=like', '%.css'),
            ('mimetype', '=', 'text/css'),
        ])
        if not candidates:
            return self.env['ir.attachment']
        # Preferir no-autoprefixed; dentro de cada grupo, el id mas
        # alto (proxy estable de recencia, no requiere parsear
        # create_date que puede ser None en attachments programaticos).
        def sort_key(a):
            is_autoprefixed = 'autoprefixed' in (a.url or '')
            return (is_autoprefixed, -(a.id or 0))
        return candidates.sorted(key=sort_key)[0]
