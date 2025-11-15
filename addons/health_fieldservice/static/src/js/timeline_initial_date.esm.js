/**
 * Extension for web_timeline to support initial_date from context
 * This allows opening the timeline view focused on a specific date instead of today
 */
import {TimelineRenderer} from "@web_timeline/views/timeline/timeline_renderer.esm";
import {patch} from "@web/core/utils/patch";

const {DateTime} = luxon;

patch(TimelineRenderer.prototype, {
    /**
     * Override _computeMode to check for initial_date in context
     * If initial_date is provided in context (from action), use it instead of DateTime.now()
     */
    _computeMode() {
        if (this.mode.data) {
            let start = false,
                end = false;

            // Check if initial_date is provided in context
            // Try multiple paths to access context from action
            let context = {};

            // Path 1: From props.model.config (most common for act_window)
            if (this.props?.model?.config?.context) {
                context = this.props.model.config.context;
            }
            // Path 2: From model.env.searchModel (search view context)
            else if (this.model?.env?.searchModel?.context) {
                context = this.model.env.searchModel.context;
            }
            // Path 3: From env.searchModel (alternative)
            else if (this.env?.searchModel?.context) {
                context = this.env.searchModel.context;
            }

            // Look for initial_date in context (keys: 'initial_date', 'date', 'timeline_date')
            let initial_date_str = context.initial_date || context.date || context.timeline_date;
            let current_date = DateTime.now();

            // Parse the initial_date if provided
            if (initial_date_str) {
                try {
                    // Handle different date formats
                    // YYYY-MM-DD format (most common)
                    if (typeof initial_date_str === 'string' && initial_date_str.length >= 10) {
                        current_date = DateTime.fromISO(initial_date_str);
                        console.log('📅 Timeline: Using initial date from context:', initial_date_str, '→', current_date.toISODate());
                    }
                } catch (e) {
                    console.warn('⚠️ Timeline: Failed to parse initial_date, using today:', e);
                    current_date = DateTime.now();
                }
            } else {
                console.log('ℹ️ Timeline: No initial_date in context, using today');
            }

            switch (this.mode.data) {
                case "day":
                    start = current_date.startOf("day");
                    end = current_date.endOf("day");
                    break;
                case "week":
                    start = current_date.startOf("week");
                    end = current_date.endOf("week");
                    break;
                case "month":
                    start = current_date.startOf("month");
                    end = current_date.endOf("month");
                    break;
            }
            if (end && start) {
                this.options.start = start.toJSDate();
                this.options.end = end.toJSDate();
            } else {
                this.mode.data = "fit";
            }
        }
    }
});
