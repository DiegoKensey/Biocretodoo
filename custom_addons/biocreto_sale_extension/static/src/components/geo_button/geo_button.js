/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Widget OWL: SOLO BOTÓN de geolocalización GPS.
 *
 * Anclado a un campo Float (latitud). Al pulsar:
 *   1) Pide al navegador navigator.geolocation.getCurrentPosition.
 *   2) Toma lat/lng con 7 decimales (precisión ~1 cm).
 *   3) Valida rango (-90/90, -180/180).
 *   4) Escribe AMBOS campos en el record: la latitud (a la que se ancla)
 *      y la longitud (cuyo nombre viene por options.lng_field).
 *
 * Por qué SOLO botón (decisión consciente del rediseño v6.0):
 *   · Lat y Long se renderizan con el widget Float nativo de Odoo,
 *     sin envoltorios custom: input numérico estándar, alineación,
 *     localización de número, todo nativo.
 *   · El widget custom se reduce a lo único que aporta valor real:
 *     el botón de geolocalización del navegador.
 *
 * Patrón verificado en v19 para opción type="field" (ver
 * odoo/addons/web/static/src/views/fields/badge/badge_field.js:45-66).
 *
 * Uso en vista:
 *     <field name="biocreto_latitud"
 *            widget="biocreto_geo_field"
 *            options="{'lng_field': 'biocreto_longitud'}"/>
 */
export class BiocretoGeoField extends Component {
    static template = "biocreto_sale_extension.GeoField";
    static props = {
        ...standardFieldProps,
        lngField: { type: String, optional: true },
    };

    setup() {
        this.notification = useService("notification");
    }

    onClickGetLocation() {
        if (!navigator.geolocation) {
            this.notification.add(
                _t("Este navegador no soporta geolocalización. Ingrese las coordenadas manualmente."),
                { type: "warning", sticky: false }
            );
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = parseFloat(position.coords.latitude.toFixed(7));
                const lng = parseFloat(position.coords.longitude.toFixed(7));
                if (
                    isNaN(lat) || isNaN(lng) ||
                    Math.abs(lat) > 90 || Math.abs(lng) > 180
                ) {
                    this.notification.add(
                        _t("Coordenadas fuera de rango. No se guardaron."),
                        { type: "danger", sticky: false }
                    );
                    return;
                }
                const lngFieldName = this.props.lngField || "biocreto_longitud";
                this.props.record.update({
                    [this.props.name]: lat,
                    [lngFieldName]: lng,
                });
            },
            () => {
                this.notification.add(
                    _t("No se pudo obtener la ubicación. Ingrese las coordenadas manualmente."),
                    { type: "warning", sticky: false }
                );
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }
}

export const biocretoGeoField = {
    component: BiocretoGeoField,
    displayName: _t("Geolocalización GPS"),
    supportedTypes: ["float"],
    supportedOptions: [
        {
            label: _t("Longitude field"),
            name: "lng_field",
            type: "field",
            availableTypes: ["float"],
            help: _t("Float field for longitude that the GPS button will fill in along with the latitude."),
        },
    ],
    extractProps: ({ options }) => ({
        lngField: options.lng_field,
    }),
};

registry.category("fields").add("biocreto_geo_field", biocretoGeoField);
