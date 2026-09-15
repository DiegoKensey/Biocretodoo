{
    'name': 'BIOCRETO - Código de producto por categoría',
    'version': '19.0.1.1.0',
    'category': 'Inventory',
    'summary': 'Referencia interna automática: prefijo de la categoría + correlativo de 3 dígitos.',
    'description': """
BIOCRETO - Código de producto por categoría
===========================================

Genera la referencia interna del producto a partir de su categoría, con
formato PREFIJO (3 letras) + 3 dígitos: EPP001, HER076, CON010.

  * El prefijo es un campo de `product.category`, único y de tres letras.
    No hay ninguna tabla de prefijos en el código.
  * El correlativo es el MENOR HUECO LIBRE de la serie, no el siguiente
    al mayor: si se borra el EPP045, el siguiente producto lo reutiliza.
  * Se genera en `create()` y solo si la referencia viene vacía. Una
    referencia escrita a mano se respeta siempre.
  * Una categoría sin prefijo no genera nada y no bloquea el guardado.
  * Los productos ARCHIVADOS mantienen su código ocupado.
  * Cambiar de categoría regenera el código, salvo que el producto tenga
    movimientos: entonces se bloquea con una explicación.

Concurrencia resuelta en tres capas: bloqueo de la fila de la categoría,
índice único parcial en base y reintento acotado.
""",
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        # `biocreto_base` ya extiende product.template y trae la categoría
        # Concreto con xmlid.
        'biocreto_base',
        # `stock` y `sale` los pide el criterio de "tiene movimientos":
        # stock.move, stock.quant y sale.order.line. Es la razón por la
        # que este módulo NO va dentro de biocreto_base: aquel depende
        # solo de base/mail/contacts/product/l10n_pe y hay SEIS módulos
        # colgando de él; meterle Inventario y Ventas encima sería
        # arrastrar toda la serie.
        'stock',
        'sale',
    ],
    'data': [
        'views/product_category_views.xml',
        'data/biocreto_categorias_codigo.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
