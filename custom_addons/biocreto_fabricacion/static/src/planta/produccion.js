/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Nivel 3: panel de produccion de una cadena.
 *
 * Layout:
 *   [a) TIRA SUPERIOR: V.Operativo total/restante · V.Facturado total/restante · Diseno]
 *   [b) IZQ: carga en curso                       ][c) DER: tabla de cargas de la cadena]
 *
 * INICIAR: crea biocreto.carga en_curso, setea qty_producing → OF "En proceso".
 * TERMINAR: escribe move_raw_ids editados + button_mark_done (bypass wizard).
 */
export class PlantaProduccion extends Component {
    static template = "biocreto_fabricacion.Produccion";
    static props = {
        cadena: Object,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            // Datos de la OF activa cargada (raws + info)
            activeOfId: null,
            activeOfName: null,
            activeOfSaldo: 0,
            rawLines: [],           // [{move_id, product_id, product_name, qty, uom_name, uom_id}]
            // Carga en curso (formulario izq)
            volumenOperativo: 0,
            volumenFacturado: 0,
            vehiculoId: null,
            codigoPresinto: "",
            vehiculos: [],
            // Cargas de la cadena (panel derecho)
            cargas: [],
            // Bandera: hay una carga en_curso creada, boton TERMINAR habilitado
            cargaEnCursoId: null,
            loading: false,
        });

        onWillStart(async () => {
            await this._loadInitial();
        });
    }

    // -------------------- Carga inicial + refresh --------------------

    async _loadInitial() {
        this.state.loading = true;
        try {
            const cadena = this.props.cadena;
            const active = cadena.active_production;
            this.state.activeOfId = active.id;
            this.state.activeOfName = active.name;
            this.state.activeOfSaldo = (active.product_qty || 0) - (active.qty_producing || 0);

            // 1) Cargar raws con DEMANDA (product_uom_qty), NO consumido (quantity=0
            // hasta que se produzca). Calcular ratio por m3 de producto para
            // reescalado en vivo cliente sin llamar al server.
            const raws = await this.orm.searchRead(
                "stock.move",
                [["raw_material_production_id", "=", active.id]],
                ["id", "product_id", "product_uom", "quantity", "product_uom_qty"],
            );
            const baseQty = active.product_qty || 1;
            this.state.rawLines = raws.map(r => ({
                move_id: r.id,
                product_id: r.product_id[0],
                product_name: r.product_id[1],
                uom_id: r.product_uom[0],
                uom_name: r.product_uom[1],
                // demanda por m3 de producto — invariante para regla de tres.
                // Base: product_uom_qty de la OF activa / product_qty de la OF activa.
                demand_per_unit: r.product_uom_qty / baseQty,
                // qty visible/editable en la tabla. Arranca en 0; se llena al
                // cambiar el volumen operativo (o via edicion manual del plantero).
                qty: 0,
            }));

            // 2) Cargar vehiculos (todos por ahora)
            this.state.vehiculos = await this.orm.searchRead(
                "fleet.vehicle", [], ["id", "license_plate", "name"],
                { order: "license_plate asc" },
            );

            // 3) Cargar cargas ya existentes de la cadena
            await this._loadCargasCadena();

            // 4) Detectar si hay una carga en_curso pendiente
            const enCurso = this.state.cargas.find(c => c.estado === "en_curso");
            if (enCurso) {
                this.state.cargaEnCursoId = enCurso.id;
                this.state.volumenOperativo = enCurso.volumen_operativo;
                this.state.volumenFacturado = enCurso.volumen_facturado;
                this.state.vehiculoId = enCurso.vehiculo_id?.[0] || null;
                this.state.codigoPresinto = enCurso.codigo_presinto || "";
            }
        } finally {
            this.state.loading = false;
        }
    }

    async _loadCargasCadena() {
        const cargas = await this.orm.searchRead(
            "biocreto.carga",
            [["production_group_id", "=", this.props.cadena.group_id]],
            [
                "id", "name", "vehiculo_id", "volumen_operativo", "volumen_facturado",
                "production_id", "estado", "hora_fin", "hora_inicio",
                "picking_id", "codigo_presinto", "tipo_guia", "guia_pdf_disponible",
            ],
            { order: "hora_inicio asc, id asc" },
        );
        this.state.cargas = cargas;
    }

    // -------------------- Reescalado en vivo --------------------

    onVolumenOperativoChange(ev) {
        const nuevo = parseFloat(ev.target.value) || 0;
        this.state.volumenOperativo = nuevo;
        // Reescalar raws: regla de tres sobre demand_per_unit (invariante calculado
        // en _loadInitial desde product_uom_qty). Cambiar volumen re-explode toda
        // la dosificacion — el plantero puede editar celdas DESPUES para ajustes
        // finos, pero volver a cambiar el volumen los sobrescribe.
        for (const line of this.state.rawLines) {
            line.qty = line.demand_per_unit * nuevo;
        }
    }

    onVolumenFacturadoChange(ev) {
        this.state.volumenFacturado = parseFloat(ev.target.value) || 0;
    }

    onVehiculoChange(ev) {
        this.state.vehiculoId = parseInt(ev.target.value, 10) || null;
    }

    onCodigoPresintoChange(ev) {
        this.state.codigoPresinto = ev.target.value || "";
    }

    onRawChange(line, ev) {
        line.qty = parseFloat(ev.target.value) || 0;
    }

    // -------------------- INICIAR / TERMINAR --------------------

    async onIniciar() {
        if (this.state.volumenOperativo <= 0) {
            this.notification.add(_t("Ingresa un volumen operativo mayor a 0"),
                                  { type: "warning" });
            return;
        }
        if (this.state.cargaEnCursoId) {
            this.notification.add(_t("Ya hay una carga en curso"), { type: "warning" });
            return;
        }
        this.state.loading = true;
        try {
            // orm.create en v19 con vals_list [{...}] devuelve array de ids [N].
            // Destructurar el escalar; sin esto el id queda [N] y contamina las
            // llamadas siguientes (iniciar/write/terminar) con browse([[N]])
            // -> TypeError: unhashable type: 'list'.
            const [id] = await this.orm.create("biocreto.carga", [{
                production_id: this.state.activeOfId,
                vehiculo_id: this.state.vehiculoId,
                volumen_operativo: this.state.volumenOperativo,
                volumen_facturado: this.state.volumenFacturado,
                codigo_presinto: this.state.codigoPresinto,
                estado: "en_curso",
                hora_inicio: false,   // el modelo pone default now()
            }]);
            await this.orm.call("biocreto.carga", "iniciar", [[id]]);
            this.state.cargaEnCursoId = id;
            await this._loadCargasCadena();
            this.notification.add(_t("Carga iniciada"), { type: "success" });
        } finally {
            this.state.loading = false;
        }
    }

    async onTerminar() {
        if (!this.state.cargaEnCursoId) {
            this.notification.add(_t("No hay carga en curso"), { type: "warning" });
            return;
        }
        // Validacion: la suma no puede exceder el total de la cadena
        const acumuladoTerminado = this.state.cargas
            .filter(c => c.estado === "terminada")
            .reduce((s, c) => s + c.volumen_operativo, 0);
        const total = this.props.cadena.total;
        if (acumuladoTerminado + this.state.volumenOperativo > total + 0.001) {
            this.notification.add(
                _t("La suma de cargas (%(s)s) excederia el total (%(t)s).", {
                    s: (acumuladoTerminado + this.state.volumenOperativo).toFixed(2),
                    t: total.toFixed(2),
                }),
                { type: "warning" },
            );
            return;
        }

        // Cierre corto: si el saldo restante tras esta carga es minimo, avisar
        const saldoTrasCierre = total - (acumuladoTerminado + this.state.volumenOperativo);
        if (saldoTrasCierre > 0.001 && saldoTrasCierre < 0.5) {
            const ok = window.confirm(
                _t("Cerrar aqui dejara %(s)s m³ sin producir. Confirmar?", {
                    s: saldoTrasCierre.toFixed(2),
                })
            );
            if (!ok) return;
        }

        this.state.loading = true;
        try {
            // Escribir volumen_operativo/facturado/vehiculo actualizados
            await this.orm.write("biocreto.carga", [this.state.cargaEnCursoId], {
                vehiculo_id: this.state.vehiculoId,
                volumen_operativo: this.state.volumenOperativo,
                volumen_facturado: this.state.volumenFacturado,
                codigo_presinto: this.state.codigoPresinto,
            });
            // Preparar el dict raws_editados {move_id: qty}
            const rawsEditados = {};
            for (const line of this.state.rawLines) {
                rawsEditados[line.move_id] = line.qty;
            }
            const result = await this.orm.call(
                "biocreto.carga", "terminar",
                [[this.state.cargaEnCursoId], rawsEditados],
            );
            this.state.cargaEnCursoId = null;
            this.state.codigoPresinto = "";
            this.notification.add(_t("Carga terminada"), { type: "success" });
            // Notificar al root para reload global (tarjetas nivel 1/2 acumulan producido)
            this.env.reload && await this.env.reload();

            // Si hubo backorder: repuntar a la nueva OF activa
            if (result?.nueva_of_id) {
                // La cadena se refresco desde el root; buscar nueva active_production
                // No siempre esta disponible aca — pedir un _loadInitial completo
                // que refresca todo con el nuevo active_production_id de la cadena
            } else {
                // Cadena cerrada — volver al nivel 2 (o mostrar mensaje)
                this.notification.add(_t("Cadena %(name)s cerrada", {
                    name: this.props.cadena.base_name,
                }), { type: "info" });
            }
            // Recargar los datos del panel para reflejar la nueva OF o el cierre
            await this._loadInitial();
        } finally {
            this.state.loading = false;
        }
    }

    // -------------------- Guias (columna de la tabla) --------------------

    /**
     * Descarga directa del binario "Guia electronica" del picking de la carga
     * (ruta nativa /web/content de web/controllers/binary.py; filename_field
     * resuelve el nombre real del archivo subido).
     */
    onDescargarGuia(carga) {
        const pickingId = carga.picking_id[0];
        const url = `/web/content/stock.picking/${pickingId}/biocreto_guia_electronica` +
            `?download=true&filename_field=biocreto_guia_electronica_filename`;
        window.open(url, "_blank");
    }

    /**
     * Imprime el MISMO reporte nativo del boton Imprimir del picking:
     * do_print_picking marca printed=True y devuelve el report_action de
     * stock.action_report_picking (stock_picking.py:1169); se despacha con
     * el action service igual que el boton nativo.
     */
    async onImprimirPicking(carga) {
        const action = await this.orm.call(
            "stock.picking", "do_print_picking", [[carga.picking_id[0]]],
        );
        await this.action.doAction(action);
    }

    get guiaHeader() {
        const tipos = new Set(
            this.state.cargas.map(c => c.tipo_guia).filter(Boolean));
        if (tipos.size === 1) {
            return tipos.has("guia_e") ? "Guía E." : "C. Salida";
        }
        return "Guía";
    }

    // -------------------- Getters computados --------------------

    get volumenOperativoRestante() {
        const acumTerm = this.state.cargas
            .filter(c => c.estado === "terminada")
            .reduce((s, c) => s + c.volumen_operativo, 0);
        return Math.max(0, this.props.cadena.total - acumTerm);
    }

    get volumenFacturadoAcumulado() {
        return this.state.cargas
            .filter(c => c.estado === "terminada")
            .reduce((s, c) => s + c.volumen_facturado, 0);
    }

    get vehiculoLabel() {
        const v = this.state.vehiculos.find(x => x.id === this.state.vehiculoId);
        return v ? (v.license_plate || v.name) : "";
    }
}
