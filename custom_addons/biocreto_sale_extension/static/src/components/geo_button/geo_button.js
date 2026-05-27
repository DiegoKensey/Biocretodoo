/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useService } from "@web/core/utils/hooks";

/**
 * Widget OWL: campo Char con botón auxiliar de geolocalización.
 * Uso en XML: widget="biocreto_geo_field"
 *
 * Extiende CharField nativo (mismo patrón que PhoneField/UrlField de Odoo 19):
 * el <input> mantiene t-ref="input" para que el useInputField de CharField
 * gestione la lectura/escritura del valor; el botón sólo rellena el campo.
 */
export class BiocretoGeoField extends CharField {
    static template = "biocreto_sale_extension.GeoField";

    setup() {
        super.setup();
        this.notification = useService("notification");
    }

    /**
     * Solicita la posición GPS al navegador.
     * Éxito: rellena el campo con "lat, lng" en decimales con 6 dígitos.
     * Error: muestra advertencia no bloqueante.
     */
    onClickGetLocation() {
        if (!navigator.geolocation) {
            this.notification.add(
                "Este navegador no soporta geolocalización. Ingrese las coordenadas manualmente.",
                { type: "warning", sticky: false }
            );
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude.toFixed(6);
                const lng = position.coords.longitude.toFixed(6);
                this.props.record.update({
                    [this.props.name]: `${lat}, ${lng}`,
                });
            },
            () => {
                this.notification.add(
                    "No se pudo obtener la ubicación. Ingrese las coordenadas manualmente.",
                    { type: "warning", sticky: false }
                );
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }
}

export const biocretoGeoField = {
    ...charField,
    component: BiocretoGeoField,
};

registry.category("fields").add("biocreto_geo_field", biocretoGeoField);
