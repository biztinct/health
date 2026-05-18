/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { onWillStart, useState, onWillUpdateProps, Component } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * Relationship Hierarchy Widget
 * Organization chart-style display of patient-representative relationships
 *
 * Similar to Odoo's hr_department_chart but for healthcare relationships.
 * Shows the current partner at center with relationships branching out by role.
 */
export class RelationshipHierarchyWidget extends Component {
    static template = "health_base.RelationshipHierarchyWidget";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        super.setup();

        this.action = useService("action");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.state = useState({
            hierarchy: {
                self: {},
                as_patient: {},
                as_representative: {},
            },
            loading: true,
        });

        onWillStart(async () => {
            await this.fetchHierarchy(this.props.record.resId);
        });

        onWillUpdateProps(async (nextProps) => {
            await this.fetchHierarchy(nextProps.record.resId);
        });
    }

    /**
     * Fetch relationship hierarchy data from backend
     */
    async fetchHierarchy(partnerId) {
        this.state.loading = true;
        try {
            this.state.hierarchy = await this.orm.call(
                "res.partner",
                "get_relationship_hierarchy",
                [partnerId]
            );
        } catch (error) {
            console.error("Error fetching relationship hierarchy:", error);
            this.state.hierarchy = {
                self: {},
                as_patient: {},
                as_representative: {},
            };
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Open a partner record in form view
     * When clicked, that partner becomes the center and shows THEIR relationships
     */
    async openPartnerCard(partnerId) {
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: partnerId,
            views: [[false, 'form']],
            view_mode: 'form',
            target: 'new',
            context: {
                form_view_ref: 'health_base.view_relationship_contact_popup',
            },
        };
        this.action.doAction(action);
    }

    /**
     * Get role categories with cards for rendering
     */
    getRoleCategories(side) {
        const data = this.state.hierarchy[side];
        if (!data || Object.keys(data).length === 0) {
            return [];
        }

        // Convert object to array for t-foreach
        return Object.entries(data).map(([key, value]) => ({
            key: key,
            label: value.label,
            count: value.count,
            cards: value.cards || [],
        }));
    }

    /**
     * Get role color class for styling
     */
    getRoleColorClass(role) {
        const roleColors = {
            'caregiver': 'success',      // Green
            'payer': 'info',             // Blue
            'referrer': 'warning',       // Yellow
            'emergency_contact': 'danger', // Red
            'legal_guardian': 'primary',  // Purple
            'healthcare_proxy': 'secondary',
            'client_representative': 'dark',
            'family_member': 'light',
            'friend': 'light',
            'professional': 'secondary',
        };
        return roleColors[role] || 'secondary';
    }

    /**
     * Add a new relationship for a specific role
     */
    async addRelationship(role, side) {
        const partnerId = this.props.record.resId;

        try {
            // Call backend to open wizard
            const action = await this.orm.call(
                'res.partner',
                'action_add_relationship_for_role',
                [partnerId, role, side]
            );

            // Open wizard with onClose callback
            await this.action.doAction(action, {
                onClose: async () => {
                    // Refresh hierarchy after wizard closes
                    await this.fetchHierarchy(partnerId);
                }
            });
        } catch (error) {
            console.error('Error adding relationship:', error);
        }
    }

    /**
     * Delete a relationship
     */
    async deleteRelationship(relationId, partnerName) {
        const partnerId = this.props.record.resId;

        // Show confirmation dialog
        this.dialog.add(ConfirmationDialog, {
            title: 'Remove Relationship',
            body: `Are you sure you want to remove the relationship with ${partnerName}?`,
            confirm: async () => {
                try {
                    // Delete the relationship record (NOT the partner)
                    await this.orm.unlink('health.client.relation', [relationId]);

                    // Refresh hierarchy
                    await this.fetchHierarchy(partnerId);

                    // Show success notification
                    this.notification.add(
                        `Relationship with ${partnerName} has been removed.`,
                        { type: 'success' }
                    );
                } catch (error) {
                    console.error('Error deleting relationship:', error);
                    this.notification.add(
                        'Failed to remove relationship. Please try again.',
                        { type: 'danger' }
                    );
                }
            },
            cancel: () => {},
        });
    }
}

export const relationshipHierarchyWidget = {
    component: RelationshipHierarchyWidget,
};

registry.category("view_widgets").add("relationship_hierarchy", relationshipHierarchyWidget);
