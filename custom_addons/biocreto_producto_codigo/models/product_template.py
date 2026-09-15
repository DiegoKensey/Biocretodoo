import logging
import re

from psycopg2 import errors

from odoo import _, api, models
from odoo.exceptions import UserError

from .product_category import (
    BIOCRETO_DIGITOS,
    BIOCRETO_LARGO_PREFIJO,
    BIOCRETO_MAXIMO,
)

_logger = logging.getLogger(__name__)

# Vueltas del reintento cuando el índice único atrapa un choque. Dos
# usuarios simultáneos se resuelven en la primera; tres es holgura de
# sobra y evita que un fallo real se convierta en un bucle infinito.
BIOCRETO_INTENTOS = 3


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # =================================================================
    # EL CRITERIO DE "TIENE MOVIMIENTOS" — UN SOLO SITIO
    # =================================================================
    def _biocreto_motivo_congelado(self):
        """Devuelve el motivo por el que el producto no se puede recodificar,
        o False si está libre.

        UN SOLO MÉTODO para las tres reglas que dependen de esto:
        bloquear el cambio de categoría, bloquear el borrado y decidir si
        se regenera el código. Si el criterio cambia, cambia aquí y en
        ningún otro sitio.

        QUÉ CUENTA Y QUÉ NO, Y POR QUÉ
        ------------------------------
        Cuentan:
          · `stock.move`  — se movió físicamente; su código está impreso
            en guías y constancias.
          · `stock.quant` con cantidad — incluye los inventarios
            iniciales, que son movimiento aunque no tengan un stock.move
            detrás.
          · `sale.order.line` de órdenes CONFIRMADAS — un servicio nunca
            tendrá stock.move, pero su código sí sale impreso en la
            cotización y el contrato.

        No cuentan, y es deliberado:
          · `purchase.order.line` — una línea en borrador es una
            intención, no un movimiento. Es además el candidato más
            amplio: 14 de 19 productos de la base de desarrollo.
          · `account.move.line` y `mrp.production` — redundantes: sus
            productos son un subconjunto de los que ya tienen stock.move.
          · `stock.valuation.layer` — el modelo NO EXISTE en Odoo 19.

        Con los tres primeros juntos se congelarían 18 de 19 productos;
        con este criterio, 11.
        """
        self.ensure_one()
        variantes = self.with_context(active_test=False).product_variant_ids
        if not variantes:
            return False

        if self.env['stock.move'].sudo().search_count(
                [('product_id', 'in', variantes.ids)], limit=1):
            return _("tiene movimientos de inventario")

        if self.env['stock.quant'].sudo().search_count(
                [('product_id', 'in', variantes.ids),
                 ('quantity', '!=', 0)], limit=1):
            return _("tiene existencias en almacén")

        if self.env['sale.order.line'].sudo().search_count(
                [('product_id', 'in', variantes.ids),
                 ('order_id.state', 'not in', ('draft', 'sent', 'cancel'))],
                limit=1):
            return _("figura en una venta confirmada")

        return False

    # =================================================================
    # EL GENERADOR
    # =================================================================
    def _biocreto_menor_hueco(self, prefijo):
        """El menor correlativo libre del prefijo. UNA sola consulta.

        No es un bucle de 999 consultas: se traen de golpe los códigos que
        empiezan por el prefijo —`=like` con guiones bajos, que aprovecha
        el índice btree de `default_code`— y el hueco se busca en memoria.

        `active_test=False` NO ES OPCIONAL. Un producto archivado
        conserva su `default_code` y sigue apareciendo en los documentos
        históricos; si se le pisa el número, dos productos distintos
        comparten referencia en papeles de fechas distintas. Sin este
        contexto los archivados son invisibles y el generador les pisa el
        número — es el error más fácil de cometer en todo este módulo.

        Se busca por PREFIJO y no por categoría: si un código de esa serie
        quedó en un producto que cambió de categoría, sigue contando como
        ocupado.
        """
        patron = re.compile(
            '^%s([0-9]{%d})$' % (re.escape(prefijo), BIOCRETO_DIGITOS))
        molde = prefijo + '_' * BIOCRETO_DIGITOS

        filas = self.env['product.product'].with_context(
            active_test=False).sudo().search_read(
                [('default_code', '=like', molde)], ['default_code'])

        usados = set()
        for fila in filas:
            casa = patron.match(fila['default_code'] or '')
            if casa:
                usados.add(int(casa.group(1)))

        for numero in range(1, BIOCRETO_MAXIMO + 1):
            if numero not in usados:
                return '%s%0*d' % (prefijo, BIOCRETO_DIGITOS, numero)

        raise UserError(_(
            "La serie %(prefijo)s está agotada: los %(maximo)s correlativos "
            "de %(digitos)s dígitos están ocupados. Cree una categoría nueva "
            "con otro prefijo.",
            prefijo=prefijo, maximo=BIOCRETO_MAXIMO, digitos=BIOCRETO_DIGITOS,
        ))

    def _biocreto_asignar_codigo(self):
        """Escribe la referencia interna si procede. Idempotente.

        LAS TRES CAPAS DE LA CONCURRENCIA, por orden:
          1. `SELECT … FOR UPDATE` sobre la categoría — serializa a los
             que crean a la vez (product_category._biocreto_bloquear_fila).
          2. el índice único parcial de product.product — la red que
             atrapa el choque si la capa 1 no llegó a tiempo.
          3. este reintento con SAVEPOINT — para que el usuario no vea un
             error feo cuando la red salta.

        Sin la 1, dos transacciones leen el mismo hueco y escriben el
        mismo código, que es justo el agujero del patrón de
        `biocreto_carga.create` (biocreto_carga.py:88-96), donde el
        `search_count` no bloquea nada.
        """
        self.ensure_one()
        if self.default_code:
            return False

        categoria = self.categ_id
        prefijo = categoria.biocreto_prefijo
        if not prefijo:
            # Categoría sin prefijo: el producto se guarda igual, sin
            # referencia y sin error. Decisión del usuario.
            return False

        # VARIANTES: acotado a plantilla de variante única a propósito.
        # `product.template.default_code` es compute+inverse+store y
        # `_compute_template_field_from_variant_field` lo pone a False
        # cuando hay varias variantes (product_template.py:263-284). Con
        # dos variantes, la regla "solo si está vacío" se cumpliría
        # siempre y el generador reasignaría en bucle. Hoy no hay ninguna
        # plantilla con más de una variante (0 de 19), pero llegará.
        if len(self.with_context(active_test=False).product_variant_ids) > 1:
            _logger.info(
                "biocreto_producto_codigo: %r tiene varias variantes; no se "
                "genera referencia automática.", self.display_name)
            return False

        categoria._biocreto_bloquear_fila()

        for intento in range(1, BIOCRETO_INTENTOS + 1):
            codigo = self._biocreto_menor_hueco(prefijo)
            try:
                with self.env.cr.savepoint():
                    self.default_code = codigo
                    self.env.flush_all()
            except errors.UniqueViolation:
                self.env.invalidate_all()
                _logger.warning(
                    "biocreto_producto_codigo: choque en %r (intento %s de "
                    "%s); se recalcula el hueco.",
                    codigo, intento, BIOCRETO_INTENTOS)
                continue
            _logger.info(
                "biocreto_producto_codigo: %r -> referencia %r.",
                self.display_name, codigo)
            return codigo

        raise UserError(_(
            "No se pudo asignar una referencia interna de la serie "
            "%(prefijo)s tras %(intentos)s intentos. Vuelva a guardar.",
            prefijo=prefijo, intentos=BIOCRETO_INTENTOS,
        ))

    def _biocreto_codigo_es_generado(self, prefijo):
        """¿La referencia actual la puso este módulo, o alguien a mano?"""
        self.ensure_one()
        if not (self.default_code and prefijo):
            return False
        return bool(re.match(
            '^%s[0-9]{%d}$' % (re.escape(prefijo), BIOCRETO_DIGITOS),
            self.default_code))

    # =================================================================
    # LOS TRES ENGANCHES
    # =================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Genera la referencia después de crear, nunca antes.

        POR QUÉ AQUÍ Y NO EN UN COMPUTE: `_compute_default_code` ya existe
        en el core (product_template.py:431-433) y es la mitad del espejo
        plantilla↔variante; sobrescribirlo entra en conflicto con él. En
        `create` la regla "solo si está vacío" es una condición y no un
        campo minado.

        Después de `super()` porque hacen falta la categoría resuelta y la
        variante creada: el `default_code` de la plantilla se escribe por
        su `inverse` hacia la variante, que es donde vive el dato.
        """
        plantillas = super().create(vals_list)
        for plantilla, vals in zip(plantillas, vals_list):
            if vals.get('default_code'):
                # Escrito a mano: se respeta y no se toca.
                continue
            plantilla._biocreto_asignar_codigo()
        return plantillas

    def write(self, vals):
        """Al cambiar de categoría: o se regenera, o se bloquea.

        La validación va AQUÍ y no en `@api.constrains`: un `constrains`
        valida pero no puede reescribir un campo, y además el mensaje
        tiene que poder decir QUÉ movimiento retiene al producto. Es
        también el principio del proyecto: validaciones en métodos de
        acción.
        """
        if 'categ_id' not in vals:
            return super().write(vals)

        nueva = vals['categ_id']
        anteriores = {}
        for plantilla in self:
            if plantilla.categ_id.id == nueva:
                continue
            motivo = plantilla._biocreto_motivo_congelado()
            if motivo:
                raise UserError(_(
                    "No se puede cambiar la categoría de «%(producto)s» "
                    "porque %(motivo)s: su referencia interna "
                    "%(codigo)s ya está impresa en documentos emitidos.\n\n"
                    "Archive este producto y cree uno nuevo en la categoría "
                    "de destino.",
                    producto=plantilla.display_name,
                    motivo=motivo,
                    codigo=plantilla.default_code or _("(sin referencia)"),
                ))
            anteriores[plantilla.id] = plantilla.categ_id.biocreto_prefijo

        resultado = super().write(vals)

        for plantilla in self:
            prefijo_viejo = anteriores.get(plantilla.id)
            if prefijo_viejo is None:
                continue
            # Solo se regenera lo que generó este módulo. Una referencia
            # escrita a mano sobrevive al cambio de categoría: las dos
            # reglas del encargo —"regenera al cambiar de categoría" y "no
            # pisar lo escrito a mano"— solo conviven así.
            if plantilla.default_code and not plantilla._biocreto_codigo_es_generado(
                    prefijo_viejo):
                _logger.info(
                    "biocreto_producto_codigo: %r conserva su referencia "
                    "manual %r al cambiar de categoría.",
                    plantilla.display_name, plantilla.default_code)
                continue
            plantilla.default_code = False
            plantilla._biocreto_asignar_codigo()

        return resultado

    @api.ondelete(at_uninstall=False)
    def _biocreto_bloquear_borrado_con_movimientos(self):
        """Explica en castellano lo que hoy dice PostgreSQL en jerga.

        El borrado ya está bloqueado por las claves foráneas
        `ON DELETE RESTRICT` de stock_move, stock_quant, sale_order_line,
        purchase_order_line, account_move_line y mrp_production. Pero lo
        que ve el usuario es un error genérico de integridad referencial
        que no dice qué lo retiene ni dónde mirar.

        Este `ondelete` usa EL MISMO criterio que el resto del módulo, así
        que puede dar un mensaje concreto. No sustituye a las foráneas:
        las de purchase y account siguen bloqueando por su cuenta, y eso
        está bien — este método solo mejora el mensaje de los casos que
        controlamos.
        """
        for plantilla in self:
            motivo = plantilla._biocreto_motivo_congelado()
            if motivo:
                raise UserError(_(
                    "No se puede eliminar «%(producto)s» porque "
                    "%(motivo)s.\n\n"
                    "Archívelo en lugar de eliminarlo: así conserva su "
                    "referencia %(codigo)s y los documentos ya emitidos "
                    "siguen cuadrando.",
                    producto=plantilla.display_name,
                    motivo=motivo,
                    codigo=plantilla.default_code or _("(sin referencia)"),
                ))
