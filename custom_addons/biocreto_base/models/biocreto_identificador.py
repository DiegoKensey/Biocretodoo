import re
import unicodedata

# ──────────────────────────────────────────────────────────────────────
# Identificador de un partner para componer nombres de archivo.
#
# FUNCION SUELTA, no método de modelo: la usan dos módulos que no se
# conocen entre sí —`biocreto_compras` para el nombre de la cotización y
# `biocreto_inventario` para el de los documentos de recepción— y ninguno
# de los dos debería tener que depender del otro para acceder a ella.
#
# Portada 1:1 de biocreto_compras/models/purchase_order.py:334-350
# (v19.0.4.0.0). El comportamiento NO cambia: los nombres que genera
# compras después de este movimiento son idénticos a los de antes.
# ──────────────────────────────────────────────────────────────────────

# Lo que se devuelve cuando no hay ni documento ni nombre aprovechable.
BIOCRETO_IDENT_VACIO = 'sin_ident'

# Tope del nombre saneado cuando se usa como identificador de respaldo.
BIOCRETO_IDENT_MAX = 40


def biocreto_identificador_partner(partner):
    """Devuelve el RUC/DNI del partner, o su nombre saneado como respaldo.

    La cadena, en orden:
      1. `commercial_partner_id.vat`. Si el proveedor es un contacto de una
         empresa, el documento está en la empresa padre: `vat` forma parte
         de `_synced_commercial_fields` (base/models/res_partner.py:695).
         Si es persona suelta, `commercial_partner_id == partner`.
      2. Si el `vat` trae letras —carné de extranjería, pasaporte— se le
         quitan y queda solo la parte numérica. Los RUC y DNI peruanos son
         solo dígitos por `biocreto_base._check_biocreto_id_length`
         (RUC 11 / DNI 8), así que para ellos este paso es no-op.
      3. Si tras limpiar no queda nada, el NOMBRE saneado: NFKD a ASCII
         para quitar tildes, todo lo no alfanumérico a `_`, y cortado a
         %(max)s caracteres.
      4. Si eso también queda vacío, el literal `%(vacio)s`.

    NUNCA lanza excepción por falta de documento: un proveedor sin RUC no
    puede impedir que se suba un archivo.

    :param partner: un recordset `res.partner` (se usa su
        `commercial_partner_id`). Admite recordset vacío.
    :return: str no vacío, apto para formar parte de un nombre de archivo.
    """
    comercial = partner.commercial_partner_id if partner else partner

    ident = (comercial.vat or '').strip() if comercial else ''
    if ident and not ident.isdigit():
        ident = re.sub(r'\D', '', ident)
    if ident:
        return ident

    nombre = (comercial.name if comercial else '') or BIOCRETO_IDENT_VACIO
    nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    nombre = re.sub(r'[^A-Za-z0-9]+', '_', nombre).strip('_')[:BIOCRETO_IDENT_MAX]
    return nombre or BIOCRETO_IDENT_VACIO


biocreto_identificador_partner.__doc__ = (
    biocreto_identificador_partner.__doc__
    % {'max': BIOCRETO_IDENT_MAX, 'vacio': BIOCRETO_IDENT_VACIO}
)
