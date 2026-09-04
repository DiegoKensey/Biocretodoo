# Configuración pendiente — Entregas de materiales (19.0.1.2.0)

El código está instalado y probado, pero **el flujo de consumibles no funcionará
hasta que se resuelvan los dos puntos de abajo**. Ninguno de los dos se aplicó
automáticamente: el primero cambia la semántica de inventario y el segundo es un
permiso, y ambas son decisiones tuyas.

---

## 1. Las 7 ubicaciones de `Consumo/` son de tipo «Vista» — BLOQUEANTE

Verificado en base:

| id | nombre | usage |
|---|---|---|
| 65 | `Consumo` (raíz) | view |
| 76 | `Consumo/Administración` | **view** |
| 73 | `Consumo/Laboratorio` | **view** |
| 74 | `Consumo/Fabricación` | **view** |
| 75 | `Consumo/Logística` | **view** |
| 77 | `Consumo/SIG` | **view** |
| 78 | `Consumo/SSOMA` | **view** |
| 79 | `Consumo/Comercial` | **view** |

Una ubicación de tipo «Vista» **solo sirve para agrupar en el árbol**. Odoo
prohíbe explícitamente mover existencias hacia ella:

> `stock/models/stock_quant.py:608` —
> *"You cannot take products from or deliver products to a location of type view"*

El módulo detecta el caso y lanza un `UserError` legible en vez de dejar caer el
`ValidationError` crudo de Odoo, pero **la entrega de consumibles seguirá
fallando** hasta que cambies el tipo.

Las 7 de `WH/Áreas/` sí están bien (`internal`): los activos funcionan tal cual.

### Qué tipo poner

| usage | Efecto | Cuándo |
|---|---|---|
| **`customer`** ← recomendado | El material **sale** del inventario. `qty_available` baja. | Es lo que pide la especificación: *"los consumibles salen del inventario al entregarse"*. |
| `inventory` | También sale, pero contablemente cuenta como pérdida de inventario. | Si tu contabilidad prefiere tratarlo como ajuste. |
| `internal` | El material **sigue** contando en el inventario de la compañía. | Solo si quieres controlar también los consumibles ya entregados. |

Deja la raíz `Consumo` (id 65) como `view`: es la agrupadora y nunca es destino.

### Cómo aplicarlo

Por interfaz: *Inventario → Configuración → Ubicaciones*, abrir cada una de las 7
y cambiar **Tipo de ubicación** a «Ubicación de cliente».

O de una vez desde el shell:

```python
raiz = env['stock.location'].search([('complete_name', '=', 'Consumo')], limit=1)
env['stock.location'].search([('location_id', '=', raiz.id)]).write({'usage': 'customer'})
env.cr.commit()
```

---

## 2. Enganchar cada departamento con sus dos ubicaciones

Los campos existen y salen en *Empleados → Departamentos*, apartado
**«BIOCRETO — Entregas de materiales»**, pero están **vacíos**. El módulo resuelve
el destino SIEMPRE desde ahí — nunca por nombre, id fijo ni xmlid — así que sin
esto toda entrega que afecte inventario da `UserError` nombrando el área y el
campo que falta.

Los nombres coinciden 1:1 con los de las ubicaciones, así que puede hacerse de
golpe. **Revisa el resultado antes de hacer commit**: el emparejamiento por
nombre es cómodo aquí, pero es una decisión tuya, no del código.

```python
Loc = env['stock.location']
areas = {l.name: l for l in Loc.search([('location_id.complete_name', '=', 'WH/Áreas')])}
raiz_consumo = Loc.search([('complete_name', '=', 'Consumo')], limit=1)
consumo = {l.name: l for l in Loc.search([('location_id', '=', raiz_consumo.id)])}

for dep in env['hr.department'].search([]):
    dep.write({
        'biocreto_ubicacion_activos': areas.get(dep.name, Loc).id or False,
        'biocreto_ubicacion_consumo': consumo.get(dep.name, Loc).id or False,
    })
    print(dep.name, '->', dep.biocreto_ubicacion_activos.complete_name,
          '/', dep.biocreto_ubicacion_consumo.complete_name)
# env.cr.commit()   <- descomentar cuando el listado de arriba se vea bien
```

---

## 3. Marcar qué categorías son de activos

*Inventario → Configuración → Categorías de producto* → casilla **«Es activo»**.

- **Marcada** → va a `WH/Áreas/<área>` y **sigue contando** en el inventario del
  almacén (esas ubicaciones cuelgan de `WH`).
- **Sin marcar** → va a `Consumo/<área>` y sale del inventario.

Hoy **ninguna** categoría la tiene marcada, así que todo se trataría como
consumible. Candidata evidente: `EPPS`. `Limpieza` y `Útiles de oficina` es
correcto dejarlas sin marcar.

Es data-driven a propósito: no hay ningún nombre de categoría escrito en el
código Python.

---

## 4. Producto sin categoría

`Cemento` (product.template id 9) no tiene `categ_id`. No es un error del módulo:
un producto sin categoría se trata como **consumible**, tal como pide la
especificación. Solo tenlo presente si algún día se entrega.

---

## 5. Código SIG de la constancia — `[POR CONFIRMAR]`

La cabecera del PDF imprime literalmente `[POR CONFIRMAR]` en Código, Versión y
Fecha, porque **no existe** un `biocreto.documento.control` para este formato.
Los 7 que hay en base son: `cotizacion_menor`, `cotizacion_mayor`, `contrato`,
`satisfaccion`, `reclamo`, `compras_sc` y `compras_oc`.

Cuando SIG asigne el código real, basta con crear el registro con
`codigo_documento = 'entrega_materiales'` — el reporte lo tomará solo, sin tocar
código:

*BIOCRETO SIG → Documentos* → nuevo registro con ese `codigo_documento`, más su
código (p. ej. `BC-LG-FR-XX`), versión y fecha.

---

## 6. Empleados sin departamento

Solo existe **1 `hr.employee`** en base (TICA → Administración) y **2 de los 3
usuarios internos activos no tienen empleado asociado**.

El receptor de una entrega es un `hr.employee`, y su departamento es obligatorio
(el módulo lo valida con un mensaje que explica dónde arreglarlo). Habrá que dar
de alta a los trabajadores que vayan a firmar entregas, cada uno con su
departamento.

---

## 7. Crear categorías de producto desde el modal de búsqueda — BLOQUEANTE

Desde la **19.0.1.3.0**, en la línea de requerimiento el campo *Categoría*
muestra el botón **Crear** dentro del modal `Buscar: Categoría`, pero solo para
*Requerimientos / Encargado de solicitudes* y *Administrador*. El solicitante lo
sigue viendo sin botón.

**El botón aparece pero fallará al guardar.** Verificado en base: el único ACL
con `perm_create` sobre `product.category` está atado al grupo **Productos /
Crear**, y ninguno de los tres grupos de Requerimientos lo hereda.

| ACL | crear | grupo |
|---|---|---|
| `product.category.manager` | sí | **Productos / Crear** |
| `product.category.user` | no | Rol / Usuario |

No se amplió ningún permiso: es una decisión tuya. Para habilitarlo hay dos vías,
y la diferencia importa:

- **Por usuario** (recomendado): *Ajustes → Usuarios*, abrir a quien lleve
  logística y marcarle **Productos / Crear**. Afecta solo a esa persona.
- **Por grupo**: añadir *Productos / Crear* a los grupos implicados de
  *Requerimientos / Encargado de solicitudes*. Se lo da a todo el que sea
  encargado, hoy y en el futuro — y ese grupo también permite crear y editar
  **productos**, no solo categorías.

Se usa `no_quick_create` y no `no_create`, así que crear una categoría obliga a
pasar por el formulario completo: nace con su casilla **«Es activo»** decidida
(punto 3 de este documento) en vez de crearse solo con el nombre.

---

## 8. Firmar desde el móvil — gira la pantalla ANTES de abrir

El recuadro de firma se dimensiona **una sola vez, al montarse**. Verificado en
el fuente de Odoo: `resizeSignature()` lee `clientWidth` y calcula la altura con
la proporción 3:1 (`web/static/src/core/signature/name_and_signature.js:292-297`),
y solo se llama desde `resetSignature()`, que a su vez corre dentro del
`useEffect` de montaje del componente (`:71-85`). **No hay ningún listener de
`resize` ni de `orientationchange`** en todo el módulo de firma de Odoo.

Consecuencia práctica:

> Si giras el móvil con el asistente de entrega **ya abierto**, el recuadro no
> se vuelve a escalar: se queda con el ancho que tenía al abrirse.

**Gira el teléfono a horizontal antes de pulsar «Registrar entrega»**, no
después. En horizontal hay bastante más ancho y la firma sale más cómoda.

Si ya lo abriste en vertical y quieres más espacio, cierra el asistente y
vuelve a abrirlo con el teléfono ya girado.

No se ha parcheado con JavaScript propio a propósito: haría falta un
`ResizeObserver` sobre un componente del núcleo, y eso se rompe en cada
actualización de Odoo. El recuadro sí cabe en pantalla en vertical, así que la
limitación es de comodidad, no de uso.
