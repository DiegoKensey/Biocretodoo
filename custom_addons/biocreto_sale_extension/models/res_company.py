import logging

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.mail import is_html_empty

from .cot_textos import TEXTOS_COT

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Categoría de fleet.vehicle (modelo 'fleet.vehicle.model.category')
    # usada para filtrar el Vehículo Asignado en líneas de Bombeo.
    # Verificado en fleet/models/fleet_vehicle.py: fleet.vehicle.category_id
    # apunta a 'fleet.vehicle.model.category'.
    biocreto_bomba_categ_id = fields.Many2one(
        comodel_name='fleet.vehicle.model.category',
        string="Categoría Bomba Telescópica",
        help="Categoría de la flota usada para filtrar el Vehículo Asignado "
             "en líneas de Bombeo. El usuario crea la categoría en Flota → "
             "Configuración → Categorías y la selecciona aquí.",
    )

    # ═════════════════════════════════════════════════════════════════
    # Textos configurables de los reportes de cotizacion (FR-09/FR-10).
    #
    # Seis bloques que hasta ahora eran literales en el QWeb y ahora se
    # editan por planta desde la pestana "Cotizacion" de la compania.
    #
    # DECISIONES QUE EXPLICAN LA FORMA DE ESTOS CAMPOS:
    #
    # · CON `default`, y ademas sembrado. v19.0.1.11.0 revierte la
    #   decision anterior de dejarlos vacios. El problema de un `default`
    #   suelto es que solo alcanza a companias NUEVAS: la que ya existe se
    #   quedaria con el campo vacio y el usuario no tendria de donde
    #   partir para editar. Por eso van las dos piezas:
    #     - `default` -> companias que se creen de aqui en adelante
    #     - `_biocreto_cot_sembrar_textos` -> las que ya existen, en cada
    #       `-i` (hooks.py) y en cada `-u` (<function> de data/)
    #   Los dos leen del mismo diccionario `TEXTOS_COT` (cot_textos.py),
    #   igual que el `t-else` del QWeb. Un solo sitio que editar.
    #
    # · El `t-else` del QWeb NO se quita. Deja de ser la fuente del texto
    #   y pasa a ser red de seguridad: cubre el hueco entre que el campo
    #   se crea y que el sembrado corre, y cubre que alguien vacie el
    #   campo a mano en produccion.
    #
    # · `sanitize=True` (el default, no se declara). Verificado contra
    #   html_sanitize: conserva <ul>, <li>, <ol>, <b>, <i>, <u>, <br> y
    #   <p>, y mata <script>, <style> e <iframe>. O sea, el usuario puede
    #   hacer listas de vinetas con el editor y no puede inyectar codigo
    #   en el PDF ni en el portal. `sanitize=False` no aportaria ninguna
    #   etiqueta util y si abriria esa puerta.
    #
    # · Sin `groups=`. El ACL de res.company ya limita la escritura a
    #   base.group_erp_manager (verificado en ir.model.access: es el
    #   unico grupo con perm_write). `groups=` en un campo solo RESTRINGE
    #   (odoo/orm/models.py:3377-3416), nunca amplia, asi que anadirlo
    #   aqui no daria acceso a nadie y si podria quitarselo al admin.
    #
    # · El TITULO de cada bloque no esta aqui: se queda fijo en el QWeb.
    #   El <h3> es hermano del <ul>, no lo contiene, asi que el campo
    #   puede sustituir la lista sin tocar la cabecera.
    # ═════════════════════════════════════════════════════════════════
    _AYUDA_COMUN = (
        "El titulo del bloque no se edita desde aqui: es fijo en el "
        "reporte. Si deja este campo vacio se imprime el texto por "
        "defecto del sistema. Use el editor para escribir una lista de "
        "vinetas."
    )

    biocreto_cot_menor_condiciones = fields.Html(
        string="Condiciones Generales (menor)",
        default=lambda self: self._biocreto_cot_texto_base(
            'biocreto_cot_menor_condiciones'),
        help="Bloque 'Condiciones Generales' de la cotizacion de MENOR "
             "envergadura. " + _AYUDA_COMUN + " NO escriba aqui la forma "
             "de pago ni la vigencia: la forma de pago se toma sola del "
             "termino de pago de la orden y se imprime como primera "
             "vineta; la vigencia se calcula de la fecha de validez y se "
             "imprime como ultima.",
    )
    biocreto_cot_mayor_info_complementaria = fields.Html(
        string="Información Complementaria (mayor)",
        default=lambda self: self._biocreto_cot_texto_base(
            'biocreto_cot_mayor_info_complementaria'),
        help="Tarjeta 'Informacion Complementaria' de la cotizacion de "
             "MAYOR envergadura. " + _AYUDA_COMUN + " NO escriba aqui la "
             "vigencia de la cotizacion: se calcula sola y se imprime "
             "como ultima vineta del bloque.",
    )
    biocreto_cot_mayor_terminos = fields.Html(
        string="Términos y Condiciones (mayor)",
        default=lambda self: self._biocreto_cot_texto_base(
            'biocreto_cot_mayor_terminos'),
        help="Tarjeta 'Terminos y Condiciones' de la cotizacion de MAYOR "
             "envergadura. " + _AYUDA_COMUN + " NO escriba aqui la moneda "
             "ni la forma de pago: se imprimen solas como primera vineta, "
             "tomando el texto del termino de pago de la orden.",
    )
    biocreto_cot_mayor_especificaciones = fields.Html(
        string="Especificaciones Técnicas (mayor)",
        default=lambda self: self._biocreto_cot_texto_base(
            'biocreto_cot_mayor_especificaciones'),
        help="Tarjeta 'Especificaciones Tecnicas' de la cotizacion de "
             "MAYOR envergadura. " + _AYUDA_COMUN + " Ojo: este bloque "
             "cita normas tecnicas (NTP, ASTM, RNE); revise cualquier "
             "cambio con el area tecnica antes de publicarlo.",
    )
    biocreto_cot_mayor_servicios = fields.Html(
        string="Servicios Incluidos (mayor)",
        default=lambda self: self._biocreto_cot_texto_base(
            'biocreto_cot_mayor_servicios'),
        help="Tarjeta 'Servicios Incluidos' de la cotizacion de MAYOR "
             "envergadura. " + _AYUDA_COMUN,
    )
    biocreto_cot_mayor_capacidad = fields.Html(
        string="Capacidad Operativa (mayor)",
        default=lambda self: self._biocreto_cot_texto_base(
            'biocreto_cot_mayor_capacidad'),
        help="Banda 'Capacidad Operativa' de la cotizacion de MAYOR "
             "envergadura. " + _AYUDA_COMUN + " Este bloque se imprime a "
             "DOS COLUMNAS; escriba las vinetas seguidas y el reporte las "
             "reparte solo.",
    )

    # ─────────────────────────────────────────────────────────────────
    # Fuente unica de los textos base: los tres consumidores leen de
    # `TEXTOS_COT` (models/cot_textos.py) y ninguno tiene el texto
    # escrito dentro.
    #   · el `default` de los seis campos de arriba
    #   · `_biocreto_cot_sembrar_textos`, para las companias existentes
    #   · el `t-else` del QWeb, que llama a `_biocreto_cot_texto_base`
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _biocreto_cot_texto_base(self, campo):
        """Texto base de uno de los seis bloques, listo para pintar.

        Devuelve `Markup` y no `str` a proposito: el QWeb lo saca con
        `t-out`, que escapa las cadenas normales. Sin el Markup, el PDF
        imprimiria "&lt;li&gt;..." en vez de la lista.

        Si el nombre no existe devuelve vacio en vez de reventar: esto lo
        llama tambien el `default` de un campo, y una KeyError ahi
        impediria crear cualquier compania.
        """
        texto = TEXTOS_COT.get(campo)
        if texto is None:
            _logger.warning(
                "biocreto_sale_extension: no hay texto base para '%s'; "
                "se devuelve vacio.", campo,
            )
            return Markup('')
        return Markup(texto)

    @api.model
    def _biocreto_cot_sembrar_textos(self):
        """Puebla los seis campos de cotizacion en las companias existentes.

        Lo llaman dos caminos, con la misma logica que ya usaba el
        override de `print_report_name` (ver hooks.py):
          · `post_init_hook`  -> cubre el `-i`
          · `<function>` de data/biocreto_cot_textos.xml -> cubre el `-u`
        `post_init_hook` NO corre en upgrade (odoo/modules/loading.py),
        y el caso operativo real de este modulo es el `-u`.

        SOLO escribe donde el campo esta vacio. Lo que alguien haya
        personalizado no se toca nunca, por muchos `-u` que pasen. El
        criterio de vacio es `is_html_empty`, el mismo que usa el QWeb,
        para que "vacio para el sembrado" y "vacio para el reporte"
        signifiquen exactamente lo mismo (cubre False, '', <p></p>,
        <p><br></p> y &nbsp;).

        Idempotente: la segunda pasada no encuentra nada que escribir.
        """
        campos = list(TEXTOS_COT)
        sembradas = 0
        for compania in self.sudo().search([]):
            valores = {
                campo: TEXTOS_COT[campo]
                for campo in campos
                if is_html_empty(compania[campo])
            }
            if valores:
                compania.write(valores)
                sembradas += 1
                _logger.info(
                    "biocreto_sale_extension: textos de cotizacion "
                    "sembrados en '%s' (%s).",
                    compania.display_name, ', '.join(sorted(valores)),
                )
        if not sembradas:
            _logger.info(
                "biocreto_sale_extension: los textos de cotizacion ya "
                "estaban poblados en todas las companias; nada que hacer."
            )
