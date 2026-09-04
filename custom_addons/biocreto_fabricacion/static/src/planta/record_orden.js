/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/**
 * Tarjeta nivel 1: una por ORDEN DE VENTA.
 * Muestra badge de estado agregado, productos, producido/total.
 * Footer: "Iniciar produccion" + kebab (nota, cancelar).
 */
export class PlantaRecordOrden extends Component {
    static template = "biocreto_fabricacion.RecordOrden";
    static props = {
        orden: Object,
        onOpen: Function,
        onNota: Function,
        onCancelar: Function,
    };

    setup() {
        this.state = useState({ kebabOpen: false });
    }

    toggleKebab(ev) {
        ev.stopPropagation();
        this.state.kebabOpen = !this.state.kebabOpen;
    }

    onNota(ev) {
        ev.stopPropagation();
        this.state.kebabOpen = false;
        this.props.onNota();
    }

    onCancelar(ev) {
        ev.stopPropagation();
        this.state.kebabOpen = false;
        this.props.onCancelar();
    }

    get badgeClass() {
        return {
            confirmada: "text-bg-info",
            en_proceso: "text-bg-warning",
            terminada: "text-bg-success",
            cancelada: "text-bg-danger",
        }[this.props.orden.estado] || "text-bg-secondary";
    }

    get badgeLabel() {
        return {
            confirmada: "Confirmada",
            en_proceso: "En proceso",
            terminada: "Terminada",
            cancelada: "Cancelada",
        }[this.props.orden.estado] || this.props.orden.estado;
    }
}
