/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/**
 * Tarjeta nivel 2: una por CADENA de OF (production_group_id).
 * Titulo fijo con el name de la OF base (menor backorder_sequence).
 * Footer: "Producir" (nivel 3) + kebab (abrir OF nativa).
 */
export class PlantaRecordOf extends Component {
    static template = "biocreto_fabricacion.RecordOf";
    static props = {
        cadena: Object,
        onOpen: Function,
        onAbrirOF: Function,
    };

    setup() {
        this.state = useState({ kebabOpen: false });
    }

    toggleKebab(ev) {
        ev.stopPropagation();
        this.state.kebabOpen = !this.state.kebabOpen;
    }

    onAbrirOF(ev) {
        ev.stopPropagation();
        this.state.kebabOpen = false;
        this.props.onAbrirOF();
    }

    get badgeClass() {
        return {
            confirmada: "text-bg-info",
            en_proceso: "text-bg-warning",
            terminada: "text-bg-success",
            cancelada: "text-bg-danger",
        }[this.props.cadena.estado_cadena] || "text-bg-secondary";
    }

    get badgeLabel() {
        return {
            confirmada: "Confirmada",
            en_proceso: "En proceso",
            terminada: "Terminada",
            cancelada: "Cancelada",
        }[this.props.cadena.estado_cadena] || this.props.cadena.estado_cadena;
    }

    get fcResistencia() {
        // f'c del producto - por convencion nombre "Concreto FC 210" → extrae dígitos
        const name = this.props.cadena.product || "";
        const match = name.match(/(\d+)/);
        return match ? `f'c ${match[1]}` : "";
    }
}
