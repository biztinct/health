/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUpdateProps, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";

/**
 * Address Map Widget - Interactive map display for patient addresses
 * Supports both OpenStreetMap (Leaflet) and Google Maps
 * Shows driving route and distance to primary facility
 */
export class AddressMapWidget extends Component {
    static template = "health_base.AddressMapWidget";

    static props = {
        record: Object,
        name: String,
        readonly: { type: Boolean, optional: true },
        "*": true,
    };

    setup() {
        this.mapContainer = useRef("mapContainer");
        this.map = null;
        this.patientMarker = null;
        this.facilityMarker = null;
        this.directionsRenderer = null;
        this.routeLine = null;
        this.lastLat = null;
        this.lastLon = null;

        this.state = useState({
            mapProvider: 'openstreetmap',
            googleApiKey: '',
            drivingDistance: null,
            drivingDuration: null,
            facilityName: '',
            facilityLat: null,
            facilityLon: null,
            isLoadingRoute: false,
            routeError: null,
        });

        onWillStart(async () => {
            await this.fetchMapSettings();
            if (this.state.mapProvider === 'google' && this.state.googleApiKey) {
                await this.loadGoogleMaps();
            } else {
                await this.loadLeaflet();
            }
        });

        onMounted(() => {
            this.initMap();
            this.lastLat = parseFloat(this.props.record.data.partner_latitude) || null;
            this.lastLon = parseFloat(this.props.record.data.partner_longitude) || null;
            this.fetchFacilityAndShowRoute();

            // Poll for coordinate changes
            this.coordinatePoller = setInterval(() => {
                const currentLat = parseFloat(this.props.record.data.partner_latitude);
                const currentLon = parseFloat(this.props.record.data.partner_longitude);

                if (currentLat !== this.lastLat || currentLon !== this.lastLon) {
                    if (!isNaN(currentLat) && !isNaN(currentLon)) {
                        this.lastLat = currentLat;
                        this.lastLon = currentLon;
                        this.updatePatientMarker(currentLat, currentLon);
                        this.fetchFacilityAndShowRoute();
                    }
                }
            }, 500);
        });

        onWillUpdateProps((nextProps) => {
            const newLat = parseFloat(nextProps.record.data.partner_latitude) || null;
            const newLon = parseFloat(nextProps.record.data.partner_longitude) || null;

            if (this.lastLat !== newLat || this.lastLon !== newLon) {
                this.lastLat = newLat;
                this.lastLon = newLon;
                this.updatePatientMarker(newLat, newLon);
                this.fetchFacilityAndShowRoute();
            }
        });

        onWillUnmount(() => {
            if (this.coordinatePoller) {
                clearInterval(this.coordinatePoller);
            }
        });
    }

    async fetchMapSettings() {
        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "ir.config_parameter",
                method: "get_param",
                args: ["health_base.map_provider"],
                kwargs: {},
            });
            this.state.mapProvider = result || 'openstreetmap';

            if (this.state.mapProvider === 'google') {
                const apiKey = await rpc("/web/dataset/call_kw", {
                    model: "ir.config_parameter",
                    method: "get_param",
                    args: ["health_base.google_maps_api_key"],
                    kwargs: {},
                });
                this.state.googleApiKey = apiKey || '';
            }
        } catch (error) {
            console.warn("Could not fetch map settings:", error);
            this.state.mapProvider = 'openstreetmap';
        }
    }

    async loadLeaflet() {
        await loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
        if (!document.getElementById('leaflet-css')) {
            const link = document.createElement('link');
            link.id = 'leaflet-css';
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(link);
        }
    }

    async loadGoogleMaps() {
        if (!this.state.googleApiKey) {
            this.state.mapProvider = 'openstreetmap';
            await this.loadLeaflet();
            return;
        }

        if (window.google && window.google.maps) {
            return;
        }

        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${this.state.googleApiKey}&libraries=places,geometry`;
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = () => {
                this.state.mapProvider = 'openstreetmap';
                this.loadLeaflet().then(resolve);
            };
            document.head.appendChild(script);
        });
    }

    initMap() {
        if (!this.mapContainer.el) return;

        const lat = parseFloat(this.props.record.data.partner_latitude) || 16.0;
        const lon = parseFloat(this.props.record.data.partner_longitude) || 106.0;
        const hasCoords = this.hasValidCoords(this.props.record.data.partner_latitude, this.props.record.data.partner_longitude);

        if (this.state.mapProvider === 'google' && window.google && window.google.maps) {
            this.initGoogleMap(lat, lon, hasCoords);
        } else {
            this.initLeafletMap(lat, lon, hasCoords);
        }
    }

    hasValidCoords(lat, lon) {
        const latNum = parseFloat(lat);
        const lonNum = parseFloat(lon);
        return !isNaN(latNum) && !isNaN(lonNum) && (latNum !== 0 || lonNum !== 0);
    }

    initLeafletMap(lat, lon, hasCoords) {
        if (!window.L) return;

        this.map = window.L.map(this.mapContainer.el, {
            center: [lat, lon],
            zoom: hasCoords ? 13 : 6,
        });

        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19,
        }).addTo(this.map);

        if (hasCoords) {
            this.addLeafletPatientMarker(lat, lon);
        }
    }

    initGoogleMap(lat, lon, hasCoords) {
        this.map = new google.maps.Map(this.mapContainer.el, {
            center: { lat, lng: lon },
            zoom: hasCoords ? 13 : 6,
            mapTypeControl: true,
            streetViewControl: false,
            fullscreenControl: true,
        });

        // Initialize DirectionsRenderer for route display
        this.directionsRenderer = new google.maps.DirectionsRenderer({
            map: this.map,
            suppressMarkers: true, // We'll add custom markers
            polylineOptions: {
                strokeColor: '#4285F4',
                strokeWeight: 5,
                strokeOpacity: 0.8,
            },
        });

        if (hasCoords) {
            this.addGooglePatientMarker(lat, lon);
        }
    }

    addLeafletPatientMarker(lat, lon) {
        if (!this.map || !window.L) return;

        if (this.patientMarker) {
            this.map.removeLayer(this.patientMarker);
        }

        const patientIcon = window.L.divIcon({
            className: 'custom-patient-marker',
            html: `<div style="
                background-color: #E53935;
                width: 32px;
                height: 32px;
                border-radius: 50% 50% 50% 0;
                transform: rotate(-45deg);
                border: 3px solid #fff;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <i class="fa fa-user" style="
                    transform: rotate(45deg);
                    color: white;
                    font-size: 14px;
                "></i>
            </div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 32],
        });

        this.patientMarker = window.L.marker([lat, lon], { icon: patientIcon }).addTo(this.map);
        this.patientMarker.bindPopup('<strong>Patient Location</strong>');
    }

    addGooglePatientMarker(lat, lon) {
        if (!this.map || !window.google) return;

        if (this.patientMarker) {
            this.patientMarker.setMap(null);
        }

        this.patientMarker = new google.maps.Marker({
            position: { lat, lng: lon },
            map: this.map,
            title: 'Patient Location',
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 12,
                fillColor: '#E53935',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 3,
            },
            label: {
                text: 'P',
                color: 'white',
                fontSize: '11px',
                fontWeight: 'bold',
            },
        });
    }

    addLeafletFacilityMarker(lat, lon, name) {
        if (!this.map || !window.L) return;

        if (this.facilityMarker) {
            this.map.removeLayer(this.facilityMarker);
        }

        const facilityIcon = window.L.divIcon({
            className: 'custom-facility-marker',
            html: `<div style="
                background-color: #0F6D66;
                width: 32px;
                height: 32px;
                border-radius: 50% 50% 50% 0;
                transform: rotate(-45deg);
                border: 3px solid #fff;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <i class="fa fa-hospital-o" style="
                    transform: rotate(45deg);
                    color: white;
                    font-size: 14px;
                "></i>
            </div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 32],
        });

        this.facilityMarker = window.L.marker([lat, lon], { icon: facilityIcon }).addTo(this.map);
        this.facilityMarker.bindPopup(`<strong>${name}</strong><br/>Primary Facility`);
    }

    addGoogleFacilityMarker(lat, lon, name) {
        if (!this.map || !window.google) return;

        if (this.facilityMarker) {
            this.facilityMarker.setMap(null);
        }

        this.facilityMarker = new google.maps.Marker({
            position: { lat, lng: lon },
            map: this.map,
            title: name,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 12,
                fillColor: '#0F6D66',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 3,
            },
            label: {
                text: 'F',
                color: 'white',
                fontSize: '11px',
                fontWeight: 'bold',
            },
        });

        const infoWindow = new google.maps.InfoWindow({
            content: `<strong>${name}</strong><br/>Primary Facility`,
        });
        this.facilityMarker.addListener('click', () => infoWindow.open(this.map, this.facilityMarker));
    }

    updatePatientMarker(lat, lon) {
        if (!this.map) return;

        if (this.hasValidCoords(lat, lon)) {
            if (this.state.mapProvider === 'google' && window.google) {
                this.addGooglePatientMarker(lat, lon);
            } else if (window.L) {
                this.addLeafletPatientMarker(lat, lon);
                this.map.invalidateSize(true);
            }
        }
    }

    async fetchFacilityAndShowRoute() {
        const patientLat = parseFloat(this.props.record.data.partner_latitude);
        const patientLon = parseFloat(this.props.record.data.partner_longitude);
        const facilityIdRaw = this.props.record.data.primary_facility_id;

        // Extract facility ID - could be [id, name] array or just id
        let facilityId = null;
        if (facilityIdRaw) {
            if (Array.isArray(facilityIdRaw)) {
                facilityId = facilityIdRaw[0];
            } else if (typeof facilityIdRaw === "object") {
                facilityId = facilityIdRaw.id || facilityIdRaw.resId || null;
            } else {
                facilityId = facilityIdRaw;
            }
        }

        console.log("Map Widget Debug:", {
            patientLat,
            patientLon,
            facilityIdRaw,
            facilityId,
            hasValidPatientCoords: this.hasValidCoords(patientLat, patientLon),
        });

        if (!this.hasValidCoords(patientLat, patientLon) || !facilityId) {
            this.state.drivingDistance = null;
            this.state.drivingDuration = null;
            if (!facilityId && this.hasValidCoords(patientLat, patientLon)) {
                this.state.routeError = 'No primary facility assigned';
            }
            this.clearRoute();
            return;
        }

        this.state.isLoadingRoute = true;
        this.state.routeError = null;

        try {
            // Use correct RPC format - read expects array of IDs
            const facilityData = await rpc(`/web/dataset/call_kw/health.facility/read`, {
                model: "health.facility",
                method: "read",
                args: [[facilityId], ["name", "latitude", "longitude"]],
                kwargs: {},
            });

            if (facilityData && facilityData.length > 0) {
                const facility = facilityData[0];
                this.state.facilityName = facility.name;
                this.state.facilityLat = facility.latitude;
                this.state.facilityLon = facility.longitude;

                if (this.hasValidCoords(facility.latitude, facility.longitude)) {
                    // Add facility marker
                    if (this.state.mapProvider === 'google' && window.google) {
                        this.addGoogleFacilityMarker(facility.latitude, facility.longitude, facility.name);
                        await this.showGoogleDrivingRoute(patientLat, patientLon, facility.latitude, facility.longitude);
                    } else if (window.L) {
                        this.addLeafletFacilityMarker(facility.latitude, facility.longitude, facility.name);
                        await this.showOSRMDrivingRoute(patientLat, patientLon, facility.latitude, facility.longitude);
                    }
                } else {
                    this.state.routeError = 'Facility has no coordinates';
                }
            }
        } catch (error) {
            console.warn("Could not fetch facility data:", error);
            this.state.routeError = 'Failed to load facility';
        } finally {
            this.state.isLoadingRoute = false;
        }
    }

    async showGoogleDrivingRoute(fromLat, fromLon, toLat, toLon) {
        if (!window.google || !window.google.maps || !this.directionsRenderer) return;

        const directionsService = new google.maps.DirectionsService();

        try {
            const result = await new Promise((resolve, reject) => {
                directionsService.route({
                    origin: { lat: fromLat, lng: fromLon },
                    destination: { lat: toLat, lng: toLon },
                    travelMode: google.maps.TravelMode.DRIVING,
                }, (response, status) => {
                    if (status === 'OK') {
                        resolve(response);
                    } else {
                        reject(new Error(status));
                    }
                });
            });

            this.directionsRenderer.setDirections(result);

            // Extract distance and duration
            const leg = result.routes[0].legs[0];
            this.state.drivingDistance = (leg.distance.value / 1000).toFixed(1);
            this.state.drivingDuration = leg.duration.text;

            // Fit map to show the route
            const bounds = new google.maps.LatLngBounds();
            bounds.extend({ lat: fromLat, lng: fromLon });
            bounds.extend({ lat: toLat, lng: toLon });
            this.map.fitBounds(bounds, { padding: 50 });

        } catch (error) {
            console.warn("Google Directions failed:", error);
            this.state.routeError = 'Could not calculate route';
            // Fallback: show straight line
            this.showStraightLine(fromLat, fromLon, toLat, toLon);
        }
    }

    async showOSRMDrivingRoute(fromLat, fromLon, toLat, toLon) {
        if (!window.L || !this.map) return;

        try {
            // OSRM public routing API
            const url = `https://router.project-osrm.org/route/v1/driving/${fromLon},${fromLat};${toLon},${toLat}?overview=full&geometries=geojson`;

            const response = await fetch(url);
            const data = await response.json();

            if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
                const route = data.routes[0];

                // Clear previous route
                if (this.routeLine) {
                    this.map.removeLayer(this.routeLine);
                }

                // Draw the route
                const coordinates = route.geometry.coordinates.map(coord => [coord[1], coord[0]]);
                this.routeLine = window.L.polyline(coordinates, {
                    color: '#4285F4',
                    weight: 5,
                    opacity: 0.8,
                }).addTo(this.map);

                // Set distance and duration
                this.state.drivingDistance = (route.distance / 1000).toFixed(1);
                this.state.drivingDuration = this.formatDuration(route.duration);

                // Fit bounds to show the route
                const bounds = window.L.latLngBounds([
                    [fromLat, fromLon],
                    [toLat, toLon],
                ]);
                this.map.fitBounds(bounds, { padding: [50, 50] });
            } else {
                throw new Error('No route found');
            }
        } catch (error) {
            console.warn("OSRM routing failed:", error);
            this.state.routeError = 'Could not calculate driving route';
            this.showStraightLine(fromLat, fromLon, toLat, toLon);
        }
    }

    showStraightLine(fromLat, fromLon, toLat, toLon) {
        // Fallback: show straight line between points
        if (this.state.mapProvider === 'google' && window.google && this.map) {
            if (this.routeLine) {
                this.routeLine.setMap(null);
            }
            this.routeLine = new google.maps.Polyline({
                path: [
                    { lat: fromLat, lng: fromLon },
                    { lat: toLat, lng: toLon },
                ],
                strokeColor: '#999999',
                strokeWeight: 3,
                strokeOpacity: 0.6,
                geodesic: true,
                map: this.map,
            });

            // Calculate straight-line distance
            const distance = this.haversineDistance(fromLat, fromLon, toLat, toLon);
            this.state.drivingDistance = distance.toFixed(1) + ' (straight)';
            this.state.drivingDuration = null;

        } else if (window.L && this.map) {
            if (this.routeLine) {
                this.map.removeLayer(this.routeLine);
            }
            this.routeLine = window.L.polyline([
                [fromLat, fromLon],
                [toLat, toLon],
            ], {
                color: '#999999',
                weight: 3,
                opacity: 0.6,
                dashArray: '10, 10',
            }).addTo(this.map);

            const distance = this.haversineDistance(fromLat, fromLon, toLat, toLon);
            this.state.drivingDistance = distance.toFixed(1) + ' (straight)';
            this.state.drivingDuration = null;
        }
    }

    clearRoute() {
        if (this.directionsRenderer) {
            this.directionsRenderer.setDirections({ routes: [] });
        }
        if (this.routeLine) {
            if (this.state.mapProvider === 'google' && this.routeLine.setMap) {
                this.routeLine.setMap(null);
            } else if (this.map && this.map.removeLayer) {
                this.map.removeLayer(this.routeLine);
            }
            this.routeLine = null;
        }
        if (this.facilityMarker) {
            if (this.state.mapProvider === 'google' && this.facilityMarker.setMap) {
                this.facilityMarker.setMap(null);
            } else if (this.map && this.map.removeLayer) {
                this.map.removeLayer(this.facilityMarker);
            }
            this.facilityMarker = null;
        }
    }

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        }
        return `${minutes} min`;
    }

    haversineDistance(lat1, lon1, lat2, lon2) {
        const R = 6371;
        const dLat = this.toRadians(lat2 - lat1);
        const dLon = this.toRadians(lon2 - lon1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }
}

registry.category("fields").add("address_map", {
    component: AddressMapWidget,
    supportedTypes: ["char", "float"],
});
