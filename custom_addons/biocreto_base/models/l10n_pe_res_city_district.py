import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class L10nPeResCityDistrict(models.Model):
    _inherit = 'l10n_pe.res.city.district'

    @api.model
    def _biocreto_propagar_nombre_a_idiomas(self, xmlids):
        """Copiar el nombre de `en_US` a todos los idiomas instalados.

        POR QUE HACE FALTA. `name` es `translate=True`
        (l10n_pe/models/res_city_district.py:10), asi que en base es un
        jsonb por idioma. Un `<record>` de datos escribe UNICAMENTE el
        idioma del entorno de carga, que durante la instalacion de un
        modulo es siempre `en_US`. El resultado, verificado en crudo:

            {"en_US": "San Juan de Yscos", "es_PE": "San Juan de Iscos"}

        El usuario trabaja en es_PE (es el unico idioma activo de esta
        base), o sea que veria el nombre viejo y creeria que el arreglo
        no se aplico. Renombrar sin esto no sirve de nada.

        Un toponimo no se traduce: el nombre debe ser identico en todos
        los idiomas. Se toma `en_US` como fuente porque es lo que acaban
        de fijar los <record> de este mismo archivo, y asi el nombre vive
        en un solo sitio: el XML. Aqui no se repite ningun literal.

        Se invoca desde un <function> y no desde un hook a proposito: un
        `post_init_hook` corre solo al instalar y una post-migration solo
        cuando cambia la version. El <function> corre en CADA carga del
        archivo, que es justo lo que hace falta para que un
        `-u biocreto_base` deshaga lo que un `-u l10n_pe` revirtio.
        """
        idiomas = [code for code, _nombre in self.env['res.lang'].get_installed()]
        for xmlid in xmlids:
            distrito = self.env.ref(xmlid, raise_if_not_found=False)
            if not distrito:
                _logger.warning(
                    "biocreto_base: xmlid %s no existe; no se propaga el nombre. "
                    "Revisar si l10n_pe cambio sus identificadores.", xmlid)
                continue
            origen = distrito.with_context(lang='en_US').name
            if not origen:
                continue
            distrito.update_field_translations('name', dict.fromkeys(idiomas, origen))
            _logger.info(
                "biocreto_base: distrito %s (ubigeo %s) fijado a %r en %s",
                xmlid, distrito.code, origen, idiomas)
