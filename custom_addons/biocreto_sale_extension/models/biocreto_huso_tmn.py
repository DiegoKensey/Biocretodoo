from odoo import fields, models


class BiocretoHusoTmn(models.Model):
    _name = 'biocreto.huso.tmn'
    _description = 'Huso TMN (BIOCRETO)'
    _order = 'sequence, name'

    name = fields.Char(
        string="Huso TMN",
        required=True,
        translate=False,
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(string="Activo", default=True)

    # ════════════════════════════════════════════════════════════════
    # v19.0.1.12.0: maestro GLOBAL. Se elimino `company_id`.
    #
    # Antes el catalogo era por compania (`company_id` required, con
    # default `self.env.company`). Ahora una sola lista compartida: lo que
    # se crea desde una planta se ve en las tres.
    #
    # QUE PASA CON LA COLUMNA. No hace falta migracion: el `-u` la
    # ELIMINA de la tabla, con sus datos. Al desaparecer el campo del
    # codigo, el upgrade borra su fila de `ir.model.fields`, y
    # `IrModelFields.unlink` llama a `_drop_column`
    # (odoo/addons/base/models/ir_model.py:991 -> :843-857), que ejecuta
    # `ALTER TABLE ... DROP COLUMN ... CASCADE`. Verificado tras el -u:
    # las tres tablas quedan con id, sequence, name, active y las
    # columnas magicas; ni rastro de company_id.
    #
    # Ojo: eso significa que los valores de compania de los registros
    # existentes se PIERDEN. Volver atras no es cuestion de reponer el
    # campo: habria que repoblarlo a mano.
    #
    # (La otra via del ORM, `_check_removed_columns`, models.py:3109-3135,
    # solo suelta el NOT NULL de columnas que sobreviven sin campo. Aqui
    # no llega a intervenir porque la columna ya no existe.)
    #
    # Los campos de `sale.order.line` que apuntan aqui perdieron a la vez
    # su `check_company=True` y su `domain` por compania: apuntar
    # `check_company` a un comodelo SIN `company_id` lanza
    # `ValueError: Invalid field ...` (verificado). Ver sale_order_line.py.
    # ════════════════════════════════════════════════════════════════
