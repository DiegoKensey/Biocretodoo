# -*- coding: utf-8 -*-
"""Migracion v19.0.1.5.0 -> v19.0.1.6.0 - reparacion geografica de Junin.

QUE REPARA
==========
En BIOCRETO_PILOTO alguien borro la provincia de Chupaca (ubigeo 1209)
desde la interfaz. El borrado se llevo por delante:

  · la fila de `res_city` y su xmlid en `ir_model_data`
  · el `city_id` de los 9 distritos de Chupaca (120901..120909), que
    quedaron colgando sin provincia

Como los distritos ya no aparecian en ningun desplegable, se crearon a
mano cinco distritos sin codigo ubigeo y sin provincia, y cuatro
partners -- incluido el de la propia compania -- acabaron apuntando a
ellos. Un partner con un distrito sin ubigeo es un comprobante que SUNAT
rechaza.

POR QUE UNA MIGRACION Y NO UN SCRIPT SUELTO
===========================================
Es la leccion del commit 941bc56fc: "este arreglo se habia aplicado solo
en el servidor con un script no versionado; cualquier pull lo revertia
sin dejar rastro". Una migracion viaja en git, llega sola a Concepcion y
a Comuneros, y sobrevive a recrear la base.

POR QUE `post` Y NO `pre`
=========================
El bloque 2 depende de que las provincias esten en su sitio, y el bloque
1 crea una. Ademas `data/l10n_pe_district_data.xml` se carga en este
mismo `-u` y su <function> reescribe nombres de distrito; conviene
reparar despues de que todos los datos del modulo esten cargados. El
stage 'post' corre justo ahi (odoo/modules/loading.py).

IDEMPOTENTE Y SIN IDS FIJOS
===========================
Cada bloque comprueba antes de escribir y registra en el log lo que hace
o lo que se salta. En una base sana recorre, no encuentra nada y termina
sin una sola escritura. Ningun id de registro aparece en el codigo: todo
se resuelve por codigo ubigeo, por `code` de departamento o de pais, y
por nombre.

El `if not version: return` de la primera linea es lo que impide que
corra en una instalacion nueva, donde no hay nada que reparar.
"""

import logging
import unicodedata

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Ubigeo de la provincia que hay que poder recrear. No es un id de
# registro: es el codigo INEI, estable y el mismo en las tres plantas.
CODIGO_CHUPACA = '1209'
CODIGO_DEPARTAMENTO_JUNIN = '12'

# Patron de xmlid de las 196 provincias, deducido de `ir_model_data`:
# las 196 filas de `res.city` son del modulo `l10n_pe` y siguen
# `city_pe_<ubigeo de 4 digitos>` sin una sola excepcion
# (city_pe_0101 .. city_pe_2601). La fuente es
# odoo/addons/l10n_pe/data/res.city.csv.
MODULO_XMLID_PROVINCIA = 'l10n_pe'
PREFIJO_XMLID_PROVINCIA = 'city_pe_'

# ─────────────────────────────────────────────────────────────────────
# Mapeo de los distritos inventados al distrito real del padron.
#
# La clave es el NOMBRE del distrito inventado, normalizado (sin tildes,
# en minusculas). El valor es el ubigeo de 6 digitos del distrito real.
#
# Va FIJO en el codigo, no resuelto por nombre en tiempo de ejecucion, y
# a proposito: resolver por nombre es justo lo que produjo el desastre.
# "Pomacocha" existe dos veces en el Peru y en ningun caso en Junin.
#
# ── PENDIENTE DE DECISION DEL USUARIO ────────────────────────────────
# De los cuatro nombres inventados solo uno se pudo confirmar contra el
# padron. Los otros tres NO EXISTEN como distrito del Peru:
#
#   Pomacocha  -> 2 candidatos, ninguno en Junin:
#                   030211 Pomacocha (Andahuaylas, Apurimac)
#                   090207 Pomacocha (Acobamba, Huancavelica)
#                 El unico parecido en Jauja es 120426 Pomacancha.
#   Incho      -> 0 candidatos en los 1874 distritos del padron.
#   Aza        -> 0 candidatos en los 1874 distritos del padron.
#
# Los tres son con toda probabilidad centros poblados, no distritos.
# Mientras no esten aqui, sus partners NO se tocan y sus distritos
# inventados NO se borran: el bloque 3 los registra como no resueltos y
# el bloque 4 los conserva porque siguen referenciados. Anadir una linea
# por nombre cuando el usuario confirme el ubigeo.
# ─────────────────────────────────────────────────────────────────────
MAPEO_DISTRITOS_INVENTADOS = {
    # 'San Agustin de Cajas' se llama 'San Agustin' en el padron; el
    # ubigeo 120129 (Huancayo, Junin) esta verificado contra la tabla.
    'san agustin de cajas': '120129',
}


def _normalizar(texto):
    """Minusculas y sin tildes, para emparejar nombres escritos a mano."""
    if not texto:
        return ''
    descompuesto = unicodedata.normalize('NFKD', texto)
    sin_tildes = ''.join(c for c in descompuesto
                         if not unicodedata.combining(c))
    return ' '.join(sin_tildes.lower().split())


# ═════════════════════════════════════════════════════════════════════
# BLOQUE 1 - recrear la provincia borrada
# ═════════════════════════════════════════════════════════════════════
def _recrear_provincia(env):
    Provincia = env['res.city']
    existente = Provincia.search([('l10n_pe_code', '=', CODIGO_CHUPACA)],
                                 limit=1)
    if existente:
        _logger.info(
            "BIOCRETO geo [1/4]: la provincia de ubigeo %s ya existe "
            "(%s); nada que recrear.",
            CODIGO_CHUPACA, existente.display_name)
        return existente

    pais = env['res.country'].search([('code', '=', 'PE')], limit=1)
    departamento = env['res.country.state'].search([
        ('country_id', '=', pais.id),
        ('code', '=', CODIGO_DEPARTAMENTO_JUNIN),
    ], limit=1) if pais else None
    if not pais or not departamento:
        _logger.warning(
            "BIOCRETO geo [1/4]: no se pudo resolver pais PE (%s) o "
            "departamento %s (%s); se salta la recreacion.",
            bool(pais), CODIGO_DEPARTAMENTO_JUNIN, bool(departamento))
        return Provincia.browse()

    # `name` es translate=True (base_address_extended/models/res_city.py:12):
    # un create escribe solo el idioma del entorno, que durante un `-u` es
    # en_US. Un toponimo no se traduce, asi que se fija el mismo valor en
    # todos los idiomas instalados. Mismo criterio que
    # l10n_pe_res_city_district._biocreto_propagar_nombre_a_idiomas.
    nombre = 'Chupaca'
    provincia = Provincia.create({
        'name': nombre,
        'l10n_pe_code': CODIGO_CHUPACA,
        'state_id': departamento.id,
        'country_id': pais.id,
    })
    idiomas = [codigo for codigo, _n in env['res.lang'].get_installed()]
    provincia.update_field_translations('name',
                                        dict.fromkeys(idiomas, nombre))

    # El xmlid se recrea en el namespace de `l10n_pe` a proposito: es el
    # que la propia localizacion busca. Sin el, un futuro `-u l10n_pe`
    # no encontraria la fila y crearia una SEGUNDA Chupaca.
    xmlid = PREFIJO_XMLID_PROVINCIA + CODIGO_CHUPACA
    Datos = env['ir.model.data']
    if not Datos.search([('module', '=', MODULO_XMLID_PROVINCIA),
                         ('name', '=', xmlid)], limit=1):
        Datos.create({
            'module': MODULO_XMLID_PROVINCIA,
            'name': xmlid,
            'model': 'res.city',
            'res_id': provincia.id,
            'noupdate': False,
        })
    _logger.info(
        "BIOCRETO geo [1/4]: RECREADA la provincia %r ubigeo %s en %s/%s "
        "con xmlid %s.%s",
        nombre, CODIGO_CHUPACA, pais.code, departamento.code,
        MODULO_XMLID_PROVINCIA, xmlid)
    return provincia


# ═════════════════════════════════════════════════════════════════════
# BLOQUE 2 - reconectar los distritos huerfanos
# ═════════════════════════════════════════════════════════════════════
def _reconectar_distritos(env):
    """Devuelve a su provincia todo distrito con codigo y sin city_id.

    Generico a proposito: no menciona Chupaca. Resuelve la provincia por
    los 4 primeros digitos del ubigeo, que es como esta construido el
    padron INEI, asi que repara este caso y cualquier otro igual que
    aparezca en Concepcion o en Comuneros.
    """
    Distrito = env['l10n_pe.res.city.district']
    Provincia = env['res.city']
    huerfanos = Distrito.search([('city_id', '=', False)])
    reparables = huerfanos.filtered(lambda d: d.code and len(d.code) >= 4)
    sin_codigo = huerfanos - reparables

    if not huerfanos:
        _logger.info("BIOCRETO geo [2/4]: no hay distritos sin provincia.")
        return
    _logger.info(
        "BIOCRETO geo [2/4]: %s distrito(s) sin provincia; %s con codigo "
        "(reparables) y %s sin codigo (los ve el bloque 4).",
        len(huerfanos), len(reparables), len(sin_codigo))

    # Una sola lectura de provincias, indexada por ubigeo.
    por_ubigeo = {p.l10n_pe_code: p for p in Provincia.search(
        [('l10n_pe_code', '!=', False)])}
    reconectados = 0
    for distrito in reparables:
        provincia = por_ubigeo.get(distrito.code[:4])
        if not provincia:
            _logger.warning(
                "BIOCRETO geo [2/4]: el distrito %s (%s) apunta al ubigeo "
                "de provincia %s, que no existe; NO se toca.",
                distrito.code, distrito.name, distrito.code[:4])
            continue
        distrito.city_id = provincia.id
        reconectados += 1
        _logger.info(
            "BIOCRETO geo [2/4]: reconectado %s %r -> provincia %s %r",
            distrito.code, distrito.name, provincia.l10n_pe_code,
            provincia.name)
    _logger.info("BIOCRETO geo [2/4]: %s distrito(s) reconectado(s).",
                 reconectados)


# ═════════════════════════════════════════════════════════════════════
# BLOQUE 3 - repuntar los partners al distrito real
# ═════════════════════════════════════════════════════════════════════
def _repuntar_partners(env):
    """Mueve al distrito real los partners colgados de uno inventado.

    Se toca UNICAMENTE al partner cuyo distrito actual no tiene ubigeo.
    El que ya apunta a un distrito con codigo no se mira siquiera.

    Se escribe tambien `city_id` y `state_id`, porque si no el partner
    queda con la provincia y el departamento del distrito inventado (o
    sea, vacios) y la direccion se imprime coja.
    """
    Distrito = env['l10n_pe.res.city.district']
    Partner = env['res.partner']
    candidatos = Partner.search([('l10n_pe_district', '!=', False)])
    afectados = candidatos.filtered(lambda p: not p.l10n_pe_district.code)
    if not afectados:
        _logger.info(
            "BIOCRETO geo [3/4]: ningun partner apunta a un distrito sin "
            "ubigeo (%s partners con distrito revisados).", len(candidatos))
        return
    _logger.info("BIOCRETO geo [3/4]: %s partner(s) con distrito sin ubigeo.",
                 len(afectados))

    repuntados = 0
    for partner in afectados:
        viejo = partner.l10n_pe_district
        codigo = MAPEO_DISTRITOS_INVENTADOS.get(_normalizar(viejo.name))
        if not codigo:
            _logger.warning(
                "BIOCRETO geo [3/4]: NO RESUELTO. El partner %s (id=%s) "
                "apunta al distrito inventado %r, que no esta en el mapeo. "
                "No se toca. Anadir su ubigeo a "
                "MAPEO_DISTRITOS_INVENTADOS para repararlo.",
                partner.display_name, partner.id, viejo.name)
            continue
        nuevo = Distrito.search([('code', '=', codigo)], limit=1)
        if not nuevo:
            _logger.warning(
                "BIOCRETO geo [3/4]: el mapeo manda %r al ubigeo %s, que no "
                "existe en el padron; el partner %s no se toca.",
                viejo.name, codigo, partner.display_name)
            continue
        antes = (viejo.name, partner.city_id.name, partner.state_id.name)
        partner.write({
            'l10n_pe_district': nuevo.id,
            'city_id': nuevo.city_id.id,
            'state_id': nuevo.city_id.state_id.id,
        })
        repuntados += 1
        _logger.info(
            "BIOCRETO geo [3/4]: partner %s (id=%s) repuntado. "
            "ANTES distrito=%r provincia=%r depto=%r -- "
            "AHORA distrito=%r (%s) provincia=%r depto=%r",
            partner.display_name, partner.id, antes[0], antes[1], antes[2],
            nuevo.name, nuevo.code, nuevo.city_id.name,
            nuevo.city_id.state_id.name)
    _logger.info("BIOCRETO geo [3/4]: %s partner(s) repuntado(s), %s sin "
                 "resolver.", repuntados, len(afectados) - repuntados)


# ═════════════════════════════════════════════════════════════════════
# BLOQUE 4 - borrar los distritos inventados, si nadie los referencia
# ═════════════════════════════════════════════════════════════════════
def _referencias_a(env, distrito):
    """Todos los registros que apuntan a `distrito`, en CUALQUIER modelo.

    No basta con mirar res.partner y sale.order: cualquier modulo puede
    haber anadido un Many2one al distrito, y un borrado a ciegas dejaria
    la referencia en NULL sin que nadie se entere. Se recorre
    `ir.model.fields`, que es el inventario real de la base.
    """
    referencias = []
    campos = env['ir.model.fields'].search([
        ('relation', '=', 'l10n_pe.res.city.district'),
        ('ttype', 'in', ('many2one', 'many2many')),
    ])
    for campo in campos:
        modelo = env.get(campo.model)
        if modelo is None or not modelo._auto:
            continue
        definicion = modelo._fields.get(campo.name)
        if definicion is None or not definicion.store:
            continue
        try:
            encontrados = modelo.sudo().with_context(active_test=False).search(
                [(campo.name, 'in', distrito.ids)])
        except Exception as exc:      # modelo sin tabla, ACL raro, etc.
            _logger.warning(
                "BIOCRETO geo [4/4]: no se pudo consultar %s.%s (%s); se "
                "asume que hay referencia y NO se borra.",
                campo.model, campo.name, exc)
            return [('%s.%s' % (campo.model, campo.name), '?')]
        if encontrados:
            referencias.append(
                ('%s.%s' % (campo.model, campo.name), len(encontrados)))
    return referencias


def _borrar_inventados(env):
    Distrito = env['l10n_pe.res.city.district']
    inventados = Distrito.search(
        ['|', ('code', '=', False), ('code', '=', '')])
    if not inventados:
        _logger.info("BIOCRETO geo [4/4]: no hay distritos sin ubigeo.")
        return
    _logger.info("BIOCRETO geo [4/4]: %s distrito(s) sin ubigeo: %s",
                 len(inventados),
                 [(d.id, d.name) for d in inventados])

    borrados = 0
    for distrito in inventados:
        refs = _referencias_a(env, distrito)
        if refs:
            _logger.warning(
                "BIOCRETO geo [4/4]: el distrito %r (id=%s) sigue "
                "referenciado por %s; NO se borra.",
                distrito.name, distrito.id, refs)
            continue
        nombre, did = distrito.name, distrito.id
        distrito.unlink()
        borrados += 1
        _logger.info(
            "BIOCRETO geo [4/4]: borrado el distrito inventado %r (id=%s), "
            "sin referencias.", nombre, did)
    _logger.info("BIOCRETO geo [4/4]: %s borrado(s), %s conservado(s) por "
                 "tener referencias.", borrados, len(inventados) - borrados)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("BIOCRETO geo: iniciando reparacion geografica "
                 "(desde version %s).", version)
    _recrear_provincia(env)
    _reconectar_distritos(env)
    _repuntar_partners(env)
    _borrar_inventados(env)
    _logger.info("BIOCRETO geo: reparacion geografica terminada.")
