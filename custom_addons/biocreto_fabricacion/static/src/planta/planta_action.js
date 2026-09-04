/** @odoo-module **/

import { Component, useState, onWillStart, useSubEnv, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

import { PlantaOnboarding } from "./onboarding";
import { PlantaRecordOrden } from "./record_orden";
import { PlantaRecordOf } from "./record_of";
import { PlantaProduccion } from "./produccion";
import { PlantaEmployeesPanel } from "./employees_panel";

/**
 * Client action "biocreto_planta" — Centro de control del plantero.
 *
 * Navegacion jerarquica (3 niveles, sin subacciones):
 *   1) Tarjetas por orden de venta (agrupadas client-side por origin/sale_line_id.order_id)
 *   2) Tarjetas por OF/cadena dentro de la orden (agrupadas por production_group_id)
 *   3) Panel de produccion de la cadena
 *
 * Datos: orm.searchRead directo (simplificacion vs RelationalModel del recon A3).
 * Refresh manual (burger) + post-accion via env.reload (recon riesgo 10).
 * Multi-cia: filtro implicito via ir.rule nativa mrp.production (recon E18).
 * Onboarding + activacion via flag en localStorage por company.
 */
export class PlantaAction extends Component {
    static template = "biocreto_fabricacion.PlantaAction";
    static components = {
        PlantaOnboarding,
        PlantaRecordOrden,
        PlantaRecordOf,
        PlantaProduccion,
        PlantaEmployeesPanel,
    };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.homeMenu = useService("home_menu");

        this.state = useState({
            level: "list",              // "list" (nivel 1), "of" (nivel 2), "prod" (nivel 3)
            selectedOrdenKey: null,     // origin string (nivel 2 depende de esto)
            selectedGroupId: null,      // production_group_id (nivel 3 depende)
            activo: false,              // false -> onboarding; true -> panel
            filterHoy: true,            // filtro "Hoy" activo por defecto
            searchQuery: "",            // busqueda libre
            productions: [],            // records mrp.production con sub-datos
            burgerOpen: false,
            employeesOpen: false,       // panel operadores (lateral)
        });

        this.rootRef = useRef("root");

        useSubEnv({
            reload: () => this.reload(),
            openProduccion: (groupId) => this.openProduccion(groupId),
            back: () => this.back(),
        });

        onWillStart(async () => {
            await this.checkActivo();
            if (this.state.activo) {
                await this.reload();
            }
        });
    }

    // -------------------- Onboarding / activacion --------------------

    get storageKey() {
        // flag por compañia activa (cada sede su planta)
        return `biocreto_fabricacion.activo.${user.activeCompany.id}`;
    }

    async checkActivo() {
        this.state.activo = !!window.localStorage.getItem(this.storageKey);
    }

    async activarCentro() {
        window.localStorage.setItem(this.storageKey, "1");
        this.state.activo = true;
        await this.reload();
    }

    // -------------------- Carga de datos --------------------

    get domain() {
        const dom = [["state", "in", ["confirmed", "progress", "to_close"]]];
        if (this.state.filterHoy) {
            const start = luxon.DateTime.now().startOf("day");
            const end = start.plus({ days: 1 });
            dom.push(["date_start", ">=", start.toFormat("yyyy-MM-dd HH:mm:ss")]);
            dom.push(["date_start", "<", end.toFormat("yyyy-MM-dd HH:mm:ss")]);
        }
        if (this.state.searchQuery) {
            const q = this.state.searchQuery;
            dom.push("|", ["name", "ilike", q], ["origin", "ilike", q]);
        }
        return dom;
    }

    async reload() {
        // 1) Cargar mrp.production con campos necesarios para tarjetas
        const productions = await this.orm.searchRead(
            "mrp.production",
            this.domain,
            [
                "id", "name", "state", "origin", "date_start",
                "sale_line_id", "product_id", "product_qty", "qty_producing",
                "bom_id", "production_group_id", "backorder_sequence",
                "biocreto_producido_cadena", "biocreto_total_cadena",
                "biocreto_estado_cadena",
                "biocreto_carga_ids",
            ],
            { order: "date_start asc, id asc" },
        );

        // 2) Cargar sale.order (para display_name) de todas las lineas referenciadas
        const saleLineIds = productions.map(p => p.sale_line_id?.[0]).filter(Boolean);
        let saleLinesById = {};
        let saleOrdersById = {};
        if (saleLineIds.length) {
            const saleLines = await this.orm.searchRead(
                "sale.order.line",
                [["id", "in", saleLineIds]],
                ["id", "order_id", "product_uom_qty"],
            );
            saleLines.forEach(sl => { saleLinesById[sl.id] = sl; });
            const orderIds = [...new Set(saleLines.map(sl => sl.order_id[0]))];
            const orders = await this.orm.searchRead(
                "sale.order",
                [["id", "in", orderIds]],
                ["id", "name", "partner_id"],
            );
            orders.forEach(o => { saleOrdersById[o.id] = o; });
        }

        // 3) Denormalizar cada production con su sale_order info
        productions.forEach(p => {
            const slId = p.sale_line_id?.[0];
            const sl = slId ? saleLinesById[slId] : null;
            const so = sl ? saleOrdersById[sl.order_id[0]] : null;
            p._orden = so ? { id: so.id, name: so.name, partner: so.partner_id[1] } : null;
            p._orden_key = so ? so.name : (p.origin || `MO-${p.id}`);
        });

        this.state.productions = productions;
    }

    // -------------------- Agrupaciones para niveles 1 y 2 --------------------

    get ordenesAgrupadas() {
        // Nivel 1: agrupar productions por _orden_key (nombre OV)
        const groups = {};
        for (const p of this.state.productions) {
            const key = p._orden_key;
            if (!groups[key]) {
                groups[key] = {
                    key,
                    orden: p._orden,
                    productions: [],
                };
            }
            groups[key].productions.push(p);
        }
        // Calcular producido/total por orden y estado agregado
        return Object.values(groups).map(g => {
            // Grupos de cadenas dentro de esta orden (por production_group_id)
            const cadenas = this._agruparCadenas(g.productions);
            const producido = cadenas.reduce((s, c) => s + (c.producido || 0), 0);
            const total = cadenas.reduce((s, c) => s + (c.total || 0), 0);
            const estados = new Set(cadenas.map(c => c.estado_cadena));
            let estado = "confirmada";
            if ([...estados].every(s => s === "terminada")) estado = "terminada";
            else if (estados.has("en_proceso")) estado = "en_proceso";
            else if (estados.has("cancelada") && [...estados].every(s => s === "cancelada" || s === "terminada")) estado = "cancelada";
            return {
                ...g,
                cadenas,
                producido,
                total,
                estado,
                productos: [...new Set(g.productions.map(p => p.product_id[1]))],
            };
        });
    }

    _agruparCadenas(productions) {
        // Agrupar por production_group_id
        const groups = {};
        for (const p of productions) {
            const gid = p.production_group_id?.[0];
            if (!gid) continue;
            if (!groups[gid]) {
                groups[gid] = {
                    group_id: gid,
                    productions: [],
                };
            }
            groups[gid].productions.push(p);
        }
        return Object.values(groups).map(g => {
            const sorted = g.productions.slice().sort(
                (a, b) => (a.backorder_sequence || 0) - (b.backorder_sequence || 0)
            );
            const base = sorted[0];
            const activa = sorted.filter(p => ["confirmed", "progress", "to_close"].includes(p.state))
                                  .sort((a, b) => (b.backorder_sequence || 0) - (a.backorder_sequence || 0))[0]
                          || base;
            // Titulo canonico de la cadena: quitar sufijo -NNN que Odoo agrega al
            // hacer el primer parcial (V5 confirmado). WH/MO/00001-001 -> WH/MO/00001.
            const baseName = base.name.replace(/-\d+$/, "");
            return {
                group_id: g.group_id,
                base_name: baseName,         // titulo fijo de la tarjeta (invariante)
                active_production: activa,   // la OF abierta actual (para "Producir")
                product: base.product_id[1],
                bom: base.bom_id ? base.bom_id[1] : null,
                total: base.biocreto_total_cadena || base.product_qty,
                producido: base.biocreto_producido_cadena || 0,
                estado_cadena: base.biocreto_estado_cadena || "confirmada",
                all_productions: sorted,
            };
        });
    }

    get cadenasDeOrdenSeleccionada() {
        const orden = this.ordenesAgrupadas.find(o => o.key === this.state.selectedOrdenKey);
        return orden ? orden.cadenas : [];
    }

    get ordenSeleccionada() {
        return this.ordenesAgrupadas.find(o => o.key === this.state.selectedOrdenKey);
    }

    get cadenaSeleccionada() {
        for (const orden of this.ordenesAgrupadas) {
            const c = orden.cadenas.find(c => c.group_id === this.state.selectedGroupId);
            if (c) return c;
        }
        return null;
    }

    // -------------------- Navegacion --------------------

    openOrden(key) {
        this.state.selectedOrdenKey = key;
        this.state.level = "of";
    }

    openProduccion(groupId) {
        this.state.selectedGroupId = groupId;
        this.state.level = "prod";
    }

    back() {
        if (this.state.level === "prod") {
            this.state.level = "of";
            this.state.selectedGroupId = null;
        } else if (this.state.level === "of") {
            this.state.level = "list";
            this.state.selectedOrdenKey = null;
        }
    }

    // -------------------- Burger --------------------

    toggleBurger() { this.state.burgerOpen = !this.state.burgerOpen; }
    toggleEmployees() { this.state.employeesOpen = !this.state.employeesOpen; }

    async onReloadClick() {
        this.state.burgerOpen = false;
        await this.reload();
        this.notification.add(_t("Datos recargados"), { type: "success" });
    }

    onCloseClick() {
        this.state.burgerOpen = false;
        this.homeMenu.toggle();
    }

    // -------------------- Search --------------------

    toggleHoy() {
        this.state.filterHoy = !this.state.filterHoy;
        this.reload();
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        // debounce simple
        clearTimeout(this._searchDebounce);
        this._searchDebounce = setTimeout(() => this.reload(), 300);
    }

    // -------------------- Kebab nivel 1 --------------------

    onOrdenNota(orden) {
        // Abre el form de la OV en modo lectura para acceso rapido al chatter
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: orden.orden.id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onOrdenCancelar(orden) {
        const confirm = window.confirm(
            _t("Cancelar TODAS las OF abiertas de %(name)s?", { name: orden.orden.name })
        );
        if (!confirm) return;
        // Cancelar todas las MO abiertas de la orden
        const idsAbiertas = orden.cadenas.flatMap(c =>
            c.all_productions.filter(p => !["done", "cancel"].includes(p.state)).map(p => p.id)
        );
        if (idsAbiertas.length) {
            await this.orm.call("mrp.production", "action_cancel", [idsAbiertas]);
            await this.reload();
            this.notification.add(
                _t("%(n)s OF canceladas", { n: idsAbiertas.length }),
                { type: "success" },
            );
        }
    }

    // -------------------- Kebab nivel 2 --------------------

    onOfAbrir(cadena) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: cadena.active_production.id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("biocreto_planta", PlantaAction);
