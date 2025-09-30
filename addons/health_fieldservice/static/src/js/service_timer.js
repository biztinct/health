/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class ServiceTimer extends Component {
    static template = "health_fieldservice.ServiceTimer";
    static supportedTypes = ["char"];

    // Define all required props for Odoo 18 field widgets
    static props = {
        record: Object,
        name: String,
        readonly: { type: Boolean, optional: true },
        id: { type: String, optional: true },
        type: { type: String, optional: true },
        class: { type: String, optional: true },
        nolabel: { type: Boolean, optional: true },
        placeholder: { type: String, optional: true },
    };
    
    setup() {
        console.log("ServiceTimer props:", this.props);
        console.log("ServiceTimer props.name:", this.props.name);
        console.log("ServiceTimer props.record:", this.props.record);

        this.state = useState({
            hours: 0,
            minutes: 0,
            seconds: 0,
            isRunning: false,
            totalSeconds: 0,
            startTime: null,
            displayText: "00:00:00",
            currentRecordId: null  // Track which record we're displaying
        });

        this.interval = null;
        this.recordWatcher = null;

        onMounted(() => {
            console.log("ServiceTimer: Component mounted");
            const recordId = this.props.record?.data?.id || this.props.record?.resId;
            console.log("ServiceTimer: Mounted for record ID:", recordId);
            this.state.currentRecordId = recordId;
            this.initializeTimer();

            // Watch for record changes to detect when Start Service is clicked
            this.watchRecordChanges();
        });

        // onPatched is called whenever the component re-renders due to prop changes
        onPatched(() => {
            const recordId = this.props.record?.data?.id || this.props.record?.resId;
            console.log("ServiceTimer: Component patched for record ID:", recordId);

            // Check if we're viewing a different record
            if (recordId && recordId !== this.state.currentRecordId) {
                console.log("ServiceTimer: Record changed from", this.state.currentRecordId, "to", recordId, "- reinitializing");
                this.state.currentRecordId = recordId;

                // Stop any running timers
                if (this.interval) {
                    clearInterval(this.interval);
                    this.interval = null;
                }

                // Reinitialize with new record data
                this.initializeTimer();
            } else {
                // Same record, just check for state changes
                this.checkForStateChanges();
            }
        });

        onWillUnmount(() => {
            console.log("ServiceTimer: Component unmounting");
            if (this.interval) {
                clearInterval(this.interval);
            }
            if (this.recordWatcher) {
                clearInterval(this.recordWatcher);
            }
        });
    }

    checkForStateChanges() {
        // Check if timer state needs to change based on current record data
        const record = this.props.record;
        const currentStartTime = record.data?.actual_start_datetime;
        const currentEndTime = record.data?.actual_end_datetime;

        // Check if timer should start
        if (currentStartTime && !currentEndTime && !this.state.isRunning) {
            console.log("ServiceTimer: State change detected - starting timer");
            this.state.isRunning = true;
            this.state.startTime = new Date(currentStartTime);
            this.startTimer();
        }

        // Check if timer should stop
        if (currentStartTime && currentEndTime && this.state.isRunning) {
            console.log("ServiceTimer: State change detected - stopping timer");
            this.state.isRunning = false;
            const start = new Date(currentStartTime);
            const end = new Date(currentEndTime);
            const duration = Math.floor((end - start) / 1000);
            this.updateDisplay(duration);
            if (this.interval) {
                clearInterval(this.interval);
            }
        }
    }

    watchRecordChanges() {
        // In Odoo 18, we can use the reactive record system
        // The record is a Proxy that triggers updates when fields change
        const record = this.props.record;

        // Set up an interval to check for record changes
        // This will catch when actual_start_datetime or actual_end_datetime changes
        this.recordWatcher = setInterval(() => {
            this.checkForStateChanges();
        }, 1000); // Check every second
    }
    
    initializeTimer() {
        try {
            // Safely access record data with comprehensive fallbacks
            const record = this.props.record;
            const recordId = record?.data?.id || record?.resId;

            console.log("ServiceTimer: Initializing timer for record:", recordId);

            if (!record) {
                console.warn("ServiceTimer: No record found in props");
                this.resetTimer();
                return;
            }

            // Try different ways to access the data
            let data = record.data;
            if (!data && record.evalContext) {
                data = record.evalContext;
            }
            if (!data) {
                console.warn("ServiceTimer: No data found in record");
                this.resetTimer();
                return;
            }

            const startTime = data.actual_start_datetime;
            const endTime = data.actual_end_datetime;

            console.log("ServiceTimer: Record", recordId, "- Start:", startTime, "End:", endTime);

            if (startTime && !endTime) {
                // Service is running
                console.log("ServiceTimer: Service is running - starting timer");
                this.state.isRunning = true;
                this.state.startTime = new Date(startTime);
                this.startTimer();
            } else if (startTime && endTime) {
                // Service completed - show final duration
                console.log("ServiceTimer: Service completed - showing final duration");
                this.state.isRunning = false;
                const start = new Date(startTime);
                const end = new Date(endTime);
                const duration = Math.floor((end - start) / 1000);
                this.updateDisplay(duration);
            } else {
                // Service not started
                console.log("ServiceTimer: Service not started - resetting display");
                this.resetTimer();
            }
        } catch (error) {
            console.error("ServiceTimer initialization error:", error);
            this.resetTimer();
        }
    }

    resetTimer() {
        // Reset timer to initial state
        this.state.isRunning = false;
        this.state.startTime = null;
        this.updateDisplay(0);
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }
    
    startTimer() {
        if (this.interval) {
            clearInterval(this.interval);
        }
        
        this.interval = setInterval(() => {
            if (this.state.isRunning && this.state.startTime) {
                const now = new Date();
                const elapsed = Math.floor((now - this.state.startTime) / 1000);
                this.updateDisplay(elapsed);
            }
        }, 1000);
    }
    
    updateDisplay(totalSeconds) {
        this.state.totalSeconds = totalSeconds;
        
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        
        this.state.hours = hours;
        this.state.minutes = minutes;
        this.state.seconds = seconds;
        
        this.state.displayText = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    
    getTimerClass() {
        if (!this.state) return 'service-timer-container stopped';
        
        if (this.state.isRunning) {
            return 'service-timer-container active running';
        } else if (this.state.totalSeconds > 0) {
            return 'service-timer-container completed';
        } else {
            return 'service-timer-container stopped';
        }
    }
    
    getStatusText() {
        if (!this.state) return 'Loading...';
        
        if (this.state.isRunning) {
            return 'Service in Progress';
        } else if (this.state.totalSeconds > 0) {
            return 'Service Completed';
        } else {
            return 'Service Not Started';
        }
    }
    
    getStatusIcon() {
        if (!this.state) return '⏰';
        
        if (this.state.isRunning) {
            return '⏱️';
        } else if (this.state.totalSeconds > 0) {
            return '✅';
        } else {
            return '⏰';
        }
    }
    
    formatDuration() {
        if (!this.state || this.state.totalSeconds === 0) {
            return 'Ready to Start';
        }

        const hours = this.state.hours || 0;
        const minutes = this.state.minutes || 0;

        if (hours > 0) {
            return `${hours}h ${minutes}m total`;
        } else if (minutes > 0) {
            return `${minutes} minutes`;
        } else {
            return 'Just started';
        }
    }

    // Helper methods for template formatting
    getFormattedHours() {
        const hours = this.state.hours || 0;
        return String(hours).padStart(2, '0');
    }

    getFormattedMinutes() {
        const minutes = this.state.minutes || 0;
        return String(minutes).padStart(2, '0');
    }

    getFormattedSeconds() {
        const seconds = this.state.seconds || 0;
        return String(seconds).padStart(2, '0');
    }
}

// Register the component as a field widget
registry.category("fields").add("service_timer", {
    component: ServiceTimer,
    supportedTypes: ["char"],
});