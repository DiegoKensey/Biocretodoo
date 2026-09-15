import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# LA FUENTE DE VERDAD DEL FORMATO. Un solo sitio.
#
# `BIOCRETO_PATRON_CODIGO` es EL MISMO LITERAL que se usa en tres sitios:
#   1. el CHECK de formato del prefijo (aquí abajo, la parte de letras),
#   2. el índice único parcial de product.product (product_product.py),
#   3. el buscador de huecos (product_template.py).
# Si divergieran, el índice protegería un conjunto y el buscador miraría
# otro, y el fallo no aparecería hasta el primer choque real.
#
# El literal está escrito para que Python y PostgreSQL lo interpreten
# IGUAL: `[0-9]` y no `\d`, porque `\d` sí existe en las expresiones
# avanzadas de PostgreSQL pero no en las POSIX, y no merece la pena
# depender de en cuál está el servidor.
# ──────────────────────────────────────────────────────────────────────
BIOCRETO_LARGO_PREFIJO = 3
BIOCRETO_DIGITOS = 3

BIOCRETO_PATRON_PREFIJO = '^[A-Z]{%d}$' % BIOCRETO_LARGO_PREFIJO
BIOCRETO_PATRON_CODIGO = '^[A-Z]{%d}[0-9]{%d}$' % (
    BIOCRETO_LARGO_PREFIJO, BIOCRETO_DIGITOS)

# Tope de la serie: 999 con tres dígitos.
BIOCRETO_MAXIMO = 10 ** BIOCRETO_DIGITOS - 1


# ──────────────────────────────────────────────────────────────────────
# SEMILLA de categorías y prefijos.
#
# Esto NO es la tabla de prefijos del sistema: es la semilla que se
# escribe UNA vez en el campo `biocreto_prefijo` de cada categoría. A
# partir de ahí la fuente de verdad es el campo, y el administrador puede
# cambiarlo desde Inventario → Configuración → Categorías sin tocar
# código. El generador NUNCA lee este diccionario.
#
# Se busca por NOMBRE porque estas categorías no tienen xmlid (siete de
# las once de la base no lo tienen) y en producción los ids son otros.
# ──────────────────────────────────────────────────────────────────────
BIOCRETO_RENOMBRES = [
    # (nombre actual, nombre nuevo)
    ('Limpieza', 'Limpieza y mantenimiento'),
    # `Herramientas` se convierte en las MANUALES y conserva sus dos
    # productos; las eléctricas nacen como categoría aparte, vacía.
    ('Herramientas', 'Herramientas manuales'),
]

BIOCRETO_CATEGORIAS_NUEVAS = [
    'SSOMA',
    'Equipos y mobiliario',
    'Suministros para equipos y vehículos',
    'Productos alimenticios',
    'Servicios de terceros',
    'Herramientas eléctricas',
]

BIOCRETO_PREFIJOS = {
    'Materia Prima': 'MPR',
    'EPPS': 'EPP',
    'SSOMA': 'SSO',
    'Limpieza y mantenimiento': 'LIM',
    'Herramientas eléctricas': 'HEL',
    'Herramientas manuales': 'HMA',
    'Útiles de oficina': 'OFI',
    'Equipos y mobiliario': 'EQA',
    'Suministros para equipos y vehículos': 'SUM',
    'Productos alimenticios': 'ALI',
    'Concreto': 'CON',
    'Bombeo': 'BOM',
    'Servicios adicionales': 'SAD',
    'Servicios de terceros': 'SRV',
}

# Goods, Expenses y Services se quedan SIN prefijo a propósito: son
# categorías de Odoo, no del catálogo de BIOCRETO. Sus productos se
# seguirán guardando sin referencia y sin error.


class ProductCategory(models.Model):
    _inherit = 'product.category'

    biocreto_prefijo = fields.Char(
        string="Prefijo de referencia",
        # SIN `size`: `fields.Char(size=3)` TRUNCA en silencio. Un import
        # con 'ABCD' se guardaría como 'ABC' sin avisar a nadie, y el
        # encargo pide que un prefijo de 2 o 4 caracteres se RECHACE.
        # Comprobado: con `size` puesto, 'ABCD' pasaba el CHECK porque
        # llegaba ya recortado. El CHECK de abajo es quien rechaza, y lo
        # hace venga el valor del formulario, de un import o de SQL.
        help="Tres letras mayúsculas con las que arranca la referencia "
             "interna de los productos de esta categoría (EPP001, HER076…). "
             "Vacío = los productos de la categoría se guardan sin "
             "referencia automática.",
    )

    # Dos restricciones de BASE, no `@api.constrains`. Además de respetar
    # el principio del proyecto, así quedan protegidas también las
    # escrituras que no pasan por el ORM (imports, SQL directo).
    #
    # UNIQUE con NULL: PostgreSQL admite varios NULL en un UNIQUE, así que
    # las categorías sin prefijo conviven sin estorbarse. Odoo guarda el
    # Char vacío como NULL, no como cadena vacía.
    _biocreto_prefijo_uniq = models.Constraint(
        'UNIQUE(biocreto_prefijo)',
        "Dos categorías no pueden compartir el mismo prefijo: sus series de "
        "correlativos se pisarían.",
    )
    _biocreto_prefijo_formato = models.Constraint(
        "CHECK (biocreto_prefijo IS NULL OR biocreto_prefijo ~ '%s')"
        % BIOCRETO_PATRON_PREFIJO,
        "El prefijo debe ser exactamente de %d letras mayúsculas."
        % BIOCRETO_LARGO_PREFIJO,
    )

    # ─────────────────────────────────────────────────────────────────
    # Siembra: renombrar, crear y asignar prefijos.
    #
    # Se invoca desde dos sitios y hacen falta los dos:
    #   - `post_init_hook`, que cubre la INSTALACIÓN.
    #   - la `<function>` de data/, que se reejecuta en cada `-u`.
    # Mismo patrón que biocreto_sale_extension. Idempotente de principio
    # a fin: nada se renombra dos veces, nada se duplica y un prefijo ya
    # escrito no se pisa.
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _biocreto_sembrar_categorias(self):
        self._biocreto_renombrar()
        self._biocreto_crear_faltantes()
        self._biocreto_asignar_prefijos()

    @api.model
    def _biocreto_renombrar(self):
        for viejo, nuevo in BIOCRETO_RENOMBRES:
            if self.search_count([('name', '=', nuevo)]):
                _logger.info(
                    "biocreto_producto_codigo: la categoría %r ya existe; "
                    "no se renombra nada.", nuevo)
                continue
            categoria = self.search([('name', '=', viejo)], limit=1)
            if not categoria:
                _logger.info(
                    "biocreto_producto_codigo: no hay categoría %r que "
                    "renombrar.", viejo)
                continue
            categoria.name = nuevo
            _logger.info(
                "biocreto_producto_codigo: categoría id=%s renombrada de %r "
                "a %r.", categoria.id, viejo, nuevo)

    @api.model
    def _biocreto_crear_faltantes(self):
        for nombre in BIOCRETO_CATEGORIAS_NUEVAS:
            if self.search_count([('name', '=', nombre)]):
                _logger.info(
                    "biocreto_producto_codigo: la categoría %r ya existe; "
                    "no se crea.", nombre)
                continue
            categoria = self.create({'name': nombre})
            _logger.info(
                "biocreto_producto_codigo: creada la categoría %r (id=%s).",
                nombre, categoria.id)

    @api.model
    def _biocreto_asignar_prefijos(self):
        for nombre, prefijo in BIOCRETO_PREFIJOS.items():
            categoria = self.search([('name', '=', nombre)], limit=1)
            if not categoria:
                _logger.warning(
                    "biocreto_producto_codigo: no existe la categoría %r; "
                    "el prefijo %r queda sin asignar.", nombre, prefijo)
                continue
            if categoria.biocreto_prefijo:
                _logger.info(
                    "biocreto_producto_codigo: %r ya tiene prefijo %r; se "
                    "respeta.", nombre, categoria.biocreto_prefijo)
                continue
            ocupado = self.search(
                [('biocreto_prefijo', '=', prefijo), ('id', '!=', categoria.id)],
                limit=1)
            if ocupado:
                # No se lanza: dejar el módulo sin instalar por una semilla
                # sería peor que dejar una categoría sin prefijo. Queda en
                # el log y el administrador lo resuelve a mano.
                _logger.warning(
                    "biocreto_producto_codigo: el prefijo %r ya lo usa la "
                    "categoría %r (id=%s); %r se queda sin prefijo.",
                    prefijo, ocupado.name, ocupado.id, nombre)
                continue
            categoria.biocreto_prefijo = prefijo
            _logger.info(
                "biocreto_producto_codigo: categoría %r (id=%s) -> prefijo %r.",
                nombre, categoria.id, prefijo)

    def _biocreto_bloquear_fila(self):
        """Serializa a los que crean a la vez en esta categoría.

        `SELECT … FOR UPDATE` sobre la fila de la categoría: el segundo
        que llegue espera a que el primero termine su transacción y
        vuelve a calcular el hueco con el código del primero ya escrito.
        Es lo mismo que hace `ir.sequence` (`_update_nogap`,
        ir_sequence.py:53-59), aplicado a la categoría en vez de a la
        secuencia — porque `ir.sequence` solo sabe avanzar y aquí hace
        falta el menor hueco.

        El bloqueo se suelta solo, al cerrar la transacción.
        """
        self.ensure_one()
        if not self.id:
            return
        self.env.cr.execute(
            "SELECT id FROM product_category WHERE id = %s FOR UPDATE",
            [self.id],
        )
