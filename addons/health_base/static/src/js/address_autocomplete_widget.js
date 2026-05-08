/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class AddressAutocompleteWidget extends Component {
    static template = "health_address_autocomplete.AddressAutocomplete";

    static props = {
        record: Object,
        name: String,
        readonly: { type: Boolean, optional: true },
        id: { type: String, optional: true },
        type: { type: String, optional: true },
        class: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            searchText: "",
            suggestions: [],
            showDropdown: false,
            isLoading: false,
            selectedIndex: -1,
            hasError: false,
            errorMessage: "",
        });

        this.debounceTimer = null;
        this.DEBOUNCE_DELAY = 300; // milliseconds
        this.MIN_SEARCH_LENGTH = 3;

        onWillUnmount(() => {
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
        });
    }

    t(text) {
        return _t(text);
    }

    /**
     * Handle input change event
     */
    onInputChange(ev) {
        const query = ev.target.value;
        this.state.searchText = query;
        this.state.hasError = false;

        // Clear previous timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Clear suggestions if query too short
        if (query.length < this.MIN_SEARCH_LENGTH) {
            this.state.suggestions = [];
            this.state.showDropdown = false;
            this.state.selectedIndex = -1;
            return;
        }

        // Show loading indicator
        this.state.isLoading = true;

        // Debounce API call
        this.debounceTimer = setTimeout(async () => {
            await this.searchAddress(query);
        }, this.DEBOUNCE_DELAY);
    }

    /**
     * Search addresses using Photon API via backend
     */
    async searchAddress(query) {
        try {
            // Get country code from current record
            const countryId = this.props.record.data.country_id;
            let countryCode = null;

            if (countryId && countryId.length > 0) {
                // Extract country code (assuming country_id is Many2one [id, name])
                const countries = await this.orm.searchRead(
                    "res.country",
                    [["id", "=", countryId[0]]],
                    ["code"],
                    { limit: 1 }
                );
                if (countries.length > 0) {
                    countryCode = countries[0].code;
                }
            }

            // Call backend method to search addresses
            const suggestions = await this.orm.call(
                "res.partner",
                "photon_address_search",
                [],
                {
                    query: query,
                    country_code: countryCode,
                    limit: 10
                }
            );

            this.state.suggestions = suggestions || [];
            this.state.showDropdown = this.state.suggestions.length > 0;
            this.state.selectedIndex = -1;
            this.state.isLoading = false;

            if (this.state.suggestions.length === 0 && query.length >= this.MIN_SEARCH_LENGTH) {
                this.state.hasError = true;
                this.state.errorMessage = _t("No addresses found. Try a different search.");
            }

        } catch (error) {
            console.error("Address search failed:", error);
            this.state.suggestions = [];
            this.state.showDropdown = false;
            this.state.isLoading = false;
            this.state.hasError = true;
            this.state.errorMessage = _t("Search failed. Please check your connection.");
        }
    }

    /**
     * Select an address from suggestions
     */
    async selectAddress(suggestion, index) {
        try {
            this.state.selectedIndex = index;

            // Find country by code
            let countryId = null;
            if (suggestion.country_code) {
                const countries = await this.orm.searchRead(
                    "res.country",
                    [["code", "=", suggestion.country_code]],
                    ["id"],
                    { limit: 1 }
                );
                if (countries.length > 0) {
                    countryId = countries[0].id;
                }
            }

            // Find state by name (if provided)
            let stateId = null;
            if (suggestion.state && countryId) {
                const states = await this.orm.searchRead(
                    "res.country.state",
                    [
                        ["name", "=ilike", suggestion.state],
                        ["country_id", "=", countryId]
                    ],
                    ["id"],
                    { limit: 1 }
                );
                if (states.length > 0) {
                    stateId = states[0].id;
                }
            }

            // Build street from components
            let street = suggestion.street;
            if (suggestion.housenumber) {
                street = `${suggestion.housenumber} ${street}`.trim();
            }

            // Update record with all address fields and coordinates
            const updates = {
                street: street || suggestion.display.split(',')[0],
                street2: "",  // Clear street2 as Photon combines address
                city: suggestion.city || "",
                zip: suggestion.postcode || "",
                partner_latitude: suggestion.lat || 0,
                partner_longitude: suggestion.lon || 0,
                // Note: date_localization will be auto-set by Python compute method
            };

            if (countryId) {
                updates.country_id = countryId;
            }
            if (stateId) {
                updates.state_id = stateId;
            }

            await this.props.record.update(updates);

            // Update search text and close dropdown
            this.state.searchText = suggestion.display;
            this.state.showDropdown = false;
            this.state.suggestions = [];
            this.state.selectedIndex = -1;

        } catch (error) {
            console.error("Failed to select address:", error);
            this.state.hasError = true;
            this.state.errorMessage = _t("Failed to apply address. Please try again.");
        }
    }

    /**
     * Handle keyboard navigation
     */
    onKeydown(ev) {
        if (!this.state.showDropdown) {
            return;
        }

        switch (ev.key) {
            case 'ArrowDown':
                ev.preventDefault();
                this.state.selectedIndex = Math.min(
                    this.state.selectedIndex + 1,
                    this.state.suggestions.length - 1
                );
                break;

            case 'ArrowUp':
                ev.preventDefault();
                this.state.selectedIndex = Math.max(this.state.selectedIndex - 1, -1);
                break;

            case 'Enter':
                ev.preventDefault();
                if (this.state.selectedIndex >= 0 && this.state.selectedIndex < this.state.suggestions.length) {
                    this.selectAddress(this.state.suggestions[this.state.selectedIndex], this.state.selectedIndex);
                }
                break;

            case 'Escape':
                ev.preventDefault();
                this.state.showDropdown = false;
                this.state.selectedIndex = -1;
                break;
        }
    }

    /**
     * Handle click outside to close dropdown
     */
    onBlur() {
        // Delay to allow click on suggestion
        setTimeout(() => {
            this.state.showDropdown = false;
            this.state.selectedIndex = -1;
        }, 200);
    }

    /**
     * Clear search field
     */
    clearSearch() {
        this.state.searchText = "";
        this.state.suggestions = [];
        this.state.showDropdown = false;
        this.state.selectedIndex = -1;
        this.state.hasError = false;
    }

    /**
     * Get CSS class for suggestion item
     */
    getSuggestionClass(index) {
        return `address-suggestion-item ${index === this.state.selectedIndex ? 'selected' : ''}`;
    }
}

// Register widget
registry.category("fields").add("address_autocomplete", {
    component: AddressAutocompleteWidget,
    supportedTypes: ["char"],
});
