import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { patch } from "@web/core/utils/patch";

patch(CalendarCommonPopover, {
    subTemplates: {
        ...CalendarCommonPopover.subTemplates,
        footer: "health_fieldservice.FSO_CalendarPopover.footer",
    },
});
