/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { MapRenderer } from "@web_map/map_view/map_renderer";

/**
 * Parche MÍNIMO del MapRenderer nativo.
 *
 * Por qué: el href del botón "Ir a" del popup
 * (map_renderer.js:267-271 → createMarkerPopup) Y la fila "Address" del
 * popup (map_renderer.js:339-345 → getMarkerPopupRecordData; :377-385 →
 * getMarkerPopupData) están HARDCODEADAS al MISMO campo:
 *   partner.contact_address_complete
 * No hay configuración del <map> ni archInfo para separarlas.
 *
 * BiocretoCoordMapModel sobrescribe contact_address_complete con
 * "lat,lng" para que el botón "Ir a" navegue al punto exacto. Sin un
 * parche del renderer, la fila "Address" del popup mostraría también
 * "lat,lng" (legible pero feo).
 *
 * Solución mínima: tras llamar super, ubicar la fila "Address" en el
 * array fieldsView y reemplazar su `value` por
 * record[biocretoAddressField] cuando exista. El botón "Ir a" NO se toca
 * (sigue leyendo contact_address_complete del partner sintético del
 * Model). Los demás métodos del renderer (icon de pin, lista lateral,
 * popup multi-pin, etc.) quedan nativos.
 *
 * Selectividad: el patch es defensivo. Si el record NO tiene el address
 * field (porque el mapa NO usa el js_class biocreto_coord_map, o el
 * modelo no tiene el campo configurado), el fallback es la fila Address
 * nativa intacta. Por tanto Contactos / CRM / etc. NO se ven afectados.
 */
patch(MapRenderer.prototype, {
    /**
     * Reemplaza in-place el value de la fila "Address" en fieldsView
     * por record[addressField] cuando ese campo existe en el record.
     * Si no, deja fieldsView sin cambios.
     */
    _biocretoOverrideAddressRow(fieldsView, record) {
        if (!record || this.props.model.metaData.hideAddress) {
            return fieldsView;
        }
        const addressField = this.props.model.biocretoAddressField;
        if (!addressField) {
            return fieldsView;
        }
        const realAddress = record[addressField];
        if (!realAddress) {
            return fieldsView;
        }
        // La fila "Address" tiene value === partner.contact_address_complete
        // (ver getMarkerPopupRecordData y getMarkerPopupData nativos).
        // Como nuestro Model lo sobrescribió a "lat,lng", buscamos esa fila
        // por valor exacto y la reemplazamos.
        const partnerAddress = record.partner?.contact_address_complete;
        if (!partnerAddress) {
            return fieldsView;
        }
        const addressRow = fieldsView.find((f) => f.value === partnerAddress);
        if (addressRow) {
            addressRow.value = realAddress;
        }
        return fieldsView;
    },

    getMarkerPopupRecordData(record) {
        const fieldsView = super.getMarkerPopupRecordData(record);
        return this._biocretoOverrideAddressRow(fieldsView, record);
    },

    getMarkerPopupData(markerInfo) {
        const fieldsView = super.getMarkerPopupData(markerInfo);
        return this._biocretoOverrideAddressRow(fieldsView, markerInfo.record);
    },
});
