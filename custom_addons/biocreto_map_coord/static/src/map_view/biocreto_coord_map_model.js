/** @odoo-module **/

import { MapModel } from "@web_map/map_view/map_model";

/**
 * MapModel extendido: ubica cada record por sus PROPIAS coordenadas
 * (lat/lng en dos Float del modelo principal) en lugar de geocodificar
 * el res.partner asociado.
 *
 * Puntos de inyección (verificados contra
 * odoo/addons/web_map/static/src/map_view/map_model.js):
 *
 *   · _getRecordSpecification (línea 256-280): se llama dentro del flujo
 *     de _fetchData → _fetchRecordData para construir la `specification`
 *     del webSearchRead. Override que agrega los dos Float a la spec sin
 *     que aparezcan declarados como <field> del <map> (evita que entren
 *     a fieldNamesMarkerPopup y ensucien el popup con filas extra —
 *     ver map_arch_parser.js:62-68 que registra todo <field> ahí).
 *
 *   · _addPartnerToRecord (línea 142-151): el método que asigna
 *     record.partner = data.partners[id] (referencia compartida). Tras
 *     este método, _updatePartnerCoordinate (línea 252) ejecuta el
 *     geocoder. Nuestro override corre el super, luego REEMPLAZA
 *     record.partner por un objeto SINTÉTICO con las coords del record.
 *     El geocoder no se llama para esos partners porque la rama nativa
 *     itera data.partners (no record.partner) y, sobre el partner del
 *     cliente real, conserva las coords del cliente (sin re-geocoding
 *     porque ya las tiene válidas — ver map_model.js:443-468 MapBox y
 *     :566-583 OSM, ambas saltan geocoding cuando hay lat/lng).
 *
 * Por qué objeto SINTÉTICO (no mutación del compartido):
 *   Si la BD tiene N órdenes del mismo cliente, sus record.partner
 *   apuntan al MISMO objeto en data.partners[id]. Mutar lat/lng en él
 *   pondría todas las órdenes en la última posición leída. El sintético
 *   rompe la referencia compartida solo para este record y deja el
 *   partner original intacto.
 */
export class BiocretoCoordMapModel extends MapModel {
    // Configurables por context. Default sale.order BIOCRETO. Getters
    // (no setup cache) para reflejar cambios de context en runtime.
    get biocretoLatField() {
        return this.metaData.context?.lat_field || "biocreto_latitud";
    }

    get biocretoLngField() {
        return this.metaData.context?.lng_field || "biocreto_longitud";
    }

    /**
     * Campo del record cuyo VALOR se muestra como fila "Address" del popup
     * en lugar de partner.contact_address_complete. Esto resuelve el
     * conflicto entre el href del botón "Ir a" (que usa
     * contact_address_complete = "lat,lng") y la fila "Address" del popup
     * (que ahora puede tener una dirección legible distinta).
     *
     * Default `biocreto_direccion_completa` (Char computed en
     * biocreto_sale_extension/models/sale_order.py:37). Configurable por
     * context.address_field para reutilizar el js_class en otros modelos.
     *
     * Si el modelo no tiene este field declarado, _getRecordSpecification
     * lo omite del webSearchRead y el patch del renderer cae al
     * comportamiento nativo (contact_address_complete).
     */
    get biocretoAddressField() {
        return this.metaData.context?.address_field || "biocreto_direccion_completa";
    }

    _getRecordSpecification(metaData, data) {
        const spec = super._getRecordSpecification(metaData, data);
        spec[this.biocretoLatField] = {};
        spec[this.biocretoLngField] = {};
        // Solo pedimos el address field si el modelo realmente lo declara
        // (defensivo: el js_class podría reusarse en un modelo sin él).
        const addrField = this.biocretoAddressField;
        if (metaData.fields[addrField]) {
            spec[addrField] = {};
        }
        return spec;
    }

    _addPartnerToRecord(metaData, data) {
        super._addPartnerToRecord(metaData, data);
        const latField = this.biocretoLatField;
        const lngField = this.biocretoLngField;
        for (const record of data.records) {
            const lat = record[latField];
            const lng = record[lngField];
            if (!this._biocretoValidCoords(lat, lng)) {
                continue;
            }
            const original = record.partner || {};
            record.partner = {
                id: original.id ?? record.id,
                display_name: original.display_name || "",
                // El MapRenderer nativo (map_renderer.js:267-271) usa
                // partner.contact_address_complete para armar el href del
                // botón "Ir a" del popup:
                //     `https://www.google.com/maps/dir/?api=1&destination=${encodedAddress}`
                // Sobreescribirlo con "lat,lng" hace que el botón apunte al
                // punto EXACTO de la obra en lugar de a la dirección textual
                // del partner cliente (que apunta a la oficina del cliente,
                // no a la obra).
                //
                // Efecto colateral consciente: el popup también renderiza
                // este mismo campo como fila "Address" (map_renderer.js:339-345
                // y :377-385) cuando hide_address no está set. Por eso la
                // vista de Ventas debe declarar hide_address="1" para que la
                // fila desaparezca; el botón "Ir a" no la necesita.
                contact_address_complete: `${lat},${lng}`,
                partner_latitude: lat,
                partner_longitude: lng,
            };
        }
    }

    /**
     * Mismos bounds que el validador nativo (map_model.js:162-174),
     * más exclusión explícita de (0, 0) para no marcar Golfo de Guinea
     * en órdenes con defaults Float vacíos.
     */
    _biocretoValidCoords(lat, lng) {
        return (
            typeof lat === "number" &&
            typeof lng === "number" &&
            !(lat === 0 && lng === 0) &&
            lat >= -90 && lat <= 90 &&
            lng >= -180 && lng <= 180
        );
    }
}
