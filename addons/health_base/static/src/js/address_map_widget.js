/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUpdateProps, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";

/**
 * Address Map Widget - Interactive OpenStreetMap display for patient addresses
 * Uses Leaflet.js library with OpenStreetMap tiles (free, no API key required)
 */
export class AddressMapWidget extends Component {
    static template = "health_base.AddressMapWidget";

    static props = {
        record: Object,
        name: String,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.mapContainer = useRef("mapContainer");
        this.map = null;
        this.marker = null;

        onWillStart(async () => {
            // Load Leaflet.js library from CDN (free, no API key needed)
            await loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");

            // Load Leaflet CSS
            if (!document.getElementById('leaflet-css')) {
                const link = document.createElement('link');
                link.id = 'leaflet-css';
                link.rel = 'stylesheet';
                link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
                document.head.appendChild(link);
            }
        });

        onMounted(() => {
            this.initMap();
        });

        onWillUpdateProps(() => {
            this.updateMap();
        });
    }

    /**
     * Initialize Leaflet map
     */
    initMap() {
        if (!window.L || !this.mapContainer.el) {
            console.warn("Leaflet not loaded or container not ready");
            return;
        }

        const lat = this.props.record.data.partner_latitude || 16.0;
        const lon = this.props.record.data.partner_longitude || 106.0;
        const hasCoords = this.props.record.data.partner_latitude && this.props.record.data.partner_longitude;

        console.log("🗺️ Map Init - Lat:", lat, "Lon:", lon, "Has Coords:", hasCoords);
        console.log("🗺️ Record Data:", this.props.record.data);

        // Create map centered on coordinates
        this.map = window.L.map(this.mapContainer.el, {
            center: [lat, lon],
            zoom: hasCoords ? 15 : 6,
            zoomControl: true,
            attributionControl: true,
        });

        // Add OpenStreetMap tile layer (free, no API key)
        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(this.map);

        // Add marker if coordinates exist
        if (hasCoords) {
            console.log("🗺️ Adding marker at:", lat, lon);
            this.addMarker(lat, lon);
        } else {
            console.log("🗺️ No coordinates, showing default map");
        }
    }

    /**
     * Add or update marker on map
     */
    addMarker(lat, lon) {
        if (!this.map) {
            console.error("🗺️ Cannot add marker - map not initialized");
            return;
        }

        console.log("🗺️ addMarker called with lat:", lat, "lon:", lon);

        // Remove existing marker
        if (this.marker) {
            this.map.removeLayer(this.marker);
            console.log("🗺️ Removed existing marker");
        }

        // Create custom icon with healthcare theme color
        const customIcon = window.L.divIcon({
            className: 'custom-map-marker',
            html: `<div style="
                background-color: #0F6D66;
                width: 30px;
                height: 30px;
                border-radius: 50% 50% 50% 0;
                transform: rotate(-45deg);
                border: 3px solid #fff;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                position: relative;
            ">
                <i class="fa fa-home" style="
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%) rotate(45deg);
                    color: white;
                    font-size: 14px;
                "></i>
            </div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 30],
        });

        // Add marker
        this.marker = window.L.marker([lat, lon], { icon: customIcon }).addTo(this.map);
        console.log("🗺️ Marker added successfully:", this.marker);

        // Add popup with address info
        const address = this.getAddressString();
        if (address) {
            this.marker.bindPopup(`
                <div style="padding: 5px; min-width: 200px;">
                    <strong style="color: #0F6D66;">Patient Address</strong><br/>
                    <div style="margin-top: 5px; font-size: 13px;">
                        ${address}
                    </div>
                    <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                        <i class="fa fa-map-marker"></i> ${lat.toFixed(6)}, ${lon.toFixed(6)}
                    </div>
                </div>
            `);
        }

        // Center map on marker
        this.map.setView([lat, lon], 15);
    }

    /**
     * Update map when coordinates change
     */
    updateMap() {
        if (!this.map) return;

        const lat = this.props.record.data.partner_latitude;
        const lon = this.props.record.data.partner_longitude;

        if (lat && lon) {
            this.addMarker(lat, lon);
        } else {
            // Remove marker if no coordinates
            if (this.marker) {
                this.map.removeLayer(this.marker);
                this.marker = null;
            }
            // Reset to default view
            this.map.setView([16.0, 106.0], 6);
        }
    }

    /**
     * Get formatted address string from record
     */
    getAddressString() {
        const data = this.props.record.data;
        const parts = [];

        if (data.street) parts.push(data.street);
        if (data.street2) parts.push(data.street2);
        if (data.city) parts.push(data.city);
        if (data.state_id && data.state_id[1]) parts.push(data.state_id[1]);
        if (data.zip) parts.push(data.zip);
        if (data.country_id && data.country_id[1]) parts.push(data.country_id[1]);

        return parts.join(', ');
    }
}

// Register as field widget
registry.category("fields").add("address_map", {
    component: AddressMapWidget,
    supportedTypes: ["char", "float"],  // Supports char (geo_coordinates_display) and float fields
});
