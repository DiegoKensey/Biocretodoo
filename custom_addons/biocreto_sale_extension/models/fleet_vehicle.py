# -*- coding: utf-8 -*-
"""Extension de fleet.vehicle para el servicio de bombeo.

Aporta dos cosas y solo dos:

  1. `biocreto_brazo_m`: la longitud del brazo hidraulico, que es el dato
     que el cliente pregunta primero al cotizar un bombeo.
  2. Una etiqueta de vehiculo legible en la cotizacion, en el contrato y
     en el desplegable de la linea de venta.

POR QUE NO SE TOCA `name`
=========================
La tentacion era reescribir `_compute_vehicle_name`
(fleet/models/fleet_vehicle.py:234-237), que es de donde sale hoy
"Mercedes/Zoomlion D11C 330 SCR/EVH127". No se hace, por tres razones
medidas:

  · `name` es un compute ALMACENADO (fleet_vehicle.py:39). Cambiar la
    formula obliga a un recompute masivo en cada `-u`.
  · Arrastraria a todo lo demas: el modulo de Flota, los registros de
    `biocreto.carga` (el selector de Mixer), contabilidad
    (account.move.line.vehicle_id, account.asset.vehicle_id) y
    `biocreto.slump`.
  · `biocreto_fabricacion/static/src/planta/produccion.js:87-88` hace un
    searchRead de `name` CRUDO, sin pasar por `display_name`. Un cambio
    en `name` le cambia el desplegable de la planta sin que nadie lo
    note hasta que el operador lo abre.

LA VIA ELEGIDA: display_name dependiente de contexto
====================================================
Se sobrescribe `_compute_display_name` con `@api.depends_context`. Sin
ninguna clave de contexto el resultado es IDENTICO al de hoy, porque se
delega en `super()`. La etiqueta nueva sale solo donde se pide
explicitamente: el `<field>` de la linea de venta y los `t-out` de los
dos reportes.

Es el patron del core, no un invento: `product.product` hace exactamente
esto para el codigo interno entre corchetes
(product/models/product_product.py:559-568), y el propio docstring del
metodo generico lo autoriza (odoo/orm/models.py:1429-1431).

DOS CLAVES, NO UNA
==================
El papel y la pantalla piden formatos distintos:

  biocreto_vehiculo_label      -> "EVH127 - 32m"
  biocreto_vehiculo_label_pdf  -> "Bomba Telescopica - EVH127 - 32m"

En pantalla el desplegable ya esta filtrado por la categoria de bomba
(sale_order_line._compute_biocreto_vehiculo_domain), asi que repetir la
categoria en cada opcion seria ruido. En el PDF no hay filtro visible y
el cliente necesita saber que tipo de equipo va a recibir.
"""

from odoo import api, fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # ─────────────────────────────────────────────────────────────────
    # Integer, no Float ni Char.
    #
    # Float imprimiria "32.0m" y obligaria a un '%d' % en cada sitio
    # donde se use; `digits=(3,0)` no arregla eso, porque solo controla
    # el redondeo almacenado, no la representacion en Python.
    # Char admitiria "32 m", "32m" y "treintaidos" en el mismo campo, y
    # no permitiria ordenar ni filtrar por rango.
    #
    # Con Integer, ademas, el 0 es falsy y sirve de "sin tamano" sin
    # necesidad de un campo booleano extra: no existe pluma de 0 m.
    # ─────────────────────────────────────────────────────────────────
    biocreto_brazo_m = fields.Integer(
        string="Tamaño de brazo hidráulico (m)",
        help="Longitud del brazo en metros. Se usa en la etiqueta del "
             "vehículo en cotizaciones y contratos.",
    )

    # ─────────────────────────────────────────────────────────────────
    # Auxiliar SOLO para la visibilidad en la vista. Compute, NO
    # almacenado: no hay dato que guardar, es una comparacion.
    #
    # Por que existe en lugar de un invisible="category_id != 1":
    # las categorias de flota las creo el usuario por interfaz y NO
    # tienen xmlid (verificado en ir.model.data). Hardcodear el id
    # ataria la vista a los ids de ESTA base y fallaria en cuanto
    # Concepcion o Comuneros tengan los suyos.
    #
    # company_id de fleet.vehicle NO es required (fleet_vehicle.py:46-49,
    # solo tiene `default`). Un vehiculo sin compania caeria en
    # `False.biocreto_bomba_categ_id` y el campo no apareceria nunca.
    # Por eso el fallback a self.env.company, que es lo que la interfaz
    # esta mirando en ese momento; y por eso el depends_context sobre
    # allowed_company_ids, que es de donde env.company se lee.
    # ─────────────────────────────────────────────────────────────────
    biocreto_es_bomba = fields.Boolean(
        string="Es bomba telescópica",
        compute='_compute_biocreto_es_bomba',
        help="Técnico: verdadero si la categoría del vehículo coincide "
             "con la categoría de bomba configurada en la compañía. "
             "Solo gobierna la visibilidad del tamaño de brazo.",
    )

    @api.depends('category_id', 'company_id',
                 'company_id.biocreto_bomba_categ_id')
    @api.depends_context('allowed_company_ids')
    def _compute_biocreto_es_bomba(self):
        for record in self:
            compania = record.company_id or self.env.company
            categoria_bomba = compania.biocreto_bomba_categ_id
            record.biocreto_es_bomba = bool(
                categoria_bomba and record.category_id == categoria_bomba
            )

    # ─────────────────────────────────────────────────────────────────
    # Etiqueta del vehiculo.
    #
    # El orden de la logica importa y es el del prompt:
    #   1. sin placa            -> lo de siempre (record.name). FIN.
    #   2. base                 -> la placa
    #   3. con brazo            -> " - {brazo}m"
    #   4. solo _pdf, con categ -> "{categoria} - " delante
    #
    # El paso 1 no necesita codigo propio: el super() ya dejo
    # display_name valiendo `name`, asi que basta con no tocar ese
    # registro. Eso ademas garantiza que si manana el core cambia como
    # compone `name`, el fallback lo sigue solo.
    #
    # `license_plate` es Char y NO es required (fleet_vehicle.py:52-53),
    # de ahi que el caso 1 sea real y no defensivo.
    # ─────────────────────────────────────────────────────────────────
    @api.depends('name', 'license_plate', 'biocreto_brazo_m', 'category_id')
    @api.depends_context('biocreto_vehiculo_label',
                         'biocreto_vehiculo_label_pdf')
    def _compute_display_name(self):
        con_pdf = self.env.context.get('biocreto_vehiculo_label_pdf')
        con_selector = self.env.context.get('biocreto_vehiculo_label')
        if not (con_pdf or con_selector):
            # Sin clave de contexto, el comportamiento es exactamente el
            # de antes de este modulo. Flota, fabricacion, laboratorio y
            # contabilidad entran por aqui.
            return super()._compute_display_name()

        # Deja display_name = name en todos; es el fallback del caso 1.
        super()._compute_display_name()
        for record in self:
            if not record.license_plate:
                continue
            etiqueta = record.license_plate
            if record.biocreto_brazo_m:
                etiqueta = "%s - %dm" % (etiqueta, record.biocreto_brazo_m)
            if con_pdf and record.category_id:
                etiqueta = "%s - %s" % (record.category_id.name, etiqueta)
            record.display_name = etiqueta
