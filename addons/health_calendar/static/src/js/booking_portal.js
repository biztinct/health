/**
 * VAFHS Healthcare - State-of-the-Art Booking Portal JavaScript
 * Inspired by Calendly, Zocdoc, Square Appointments
 * Mobile-first, accessible, and exceptional UX
 */

(function() {
    'use strict';

    // ============================================================================
    // Global Variables & Configuration
    // ============================================================================

    let selectedAppointmentType = null;
    let selectedDate = null;
    let selectedTime = null;
    let availableSlots = [];
    let currentCalendar = null;

    // ============================================================================
    // Utility Functions
    // ============================================================================

    function formatTime(floatTime) {
        const hours = Math.floor(floatTime);
        const minutes = Math.floor((floatTime - hours) * 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    }

    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    function showLoading(element) {
        element.innerHTML = `
            <div class="loading-spinner text-center">
                <i class="fa fa-spinner fa-spin fa-2x text-primary mb-3"></i>
                <p>Loading...</p>
            </div>
        `;
    }

    function showError(element, message) {
        element.innerHTML = `
            <div class="error-message text-center">
                <i class="fa fa-exclamation-triangle fa-2x text-danger mb-3"></i>
                <p class="text-danger">${message}</p>
            </div>
        `;
    }

    // ============================================================================
    // Step 1: Appointment Type Selection
    // ============================================================================

    function initAppointmentTypeSelection() {
        const typeCards = document.querySelectorAll('.appointment-type-card');
        const selectButtons = document.querySelectorAll('.btn-select-type');

        // Add click handlers to type cards
        typeCards.forEach(card => {
            card.addEventListener('click', function() {
                const typeId = this.dataset.typeId;
                selectAppointmentType(typeId);
            });

            // Add keyboard support
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const typeId = this.dataset.typeId;
                    selectAppointmentType(typeId);
                }
            });

            // Make cards focusable
            card.setAttribute('tabindex', '0');
        });

        // Add click handlers to select buttons
        selectButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.stopPropagation();
                const typeId = this.dataset.typeId;
                selectAppointmentType(typeId);
            });
        });
    }

    function selectAppointmentType(typeId) {
        selectedAppointmentType = typeId;
        
        // Add visual feedback
        const selectedCard = document.querySelector(`[data-type-id="${typeId}"]`);
        if (selectedCard) {
            // Remove previous selections
            document.querySelectorAll('.appointment-type-card').forEach(card => {
                card.classList.remove('selected');
            });
            
            selectedCard.classList.add('selected');
            
            // Smooth transition to next step
            setTimeout(() => {
                window.location.href = `/book-appointment/step2?appointment_type_id=${typeId}`;
            }, 300);
        }
    }

    // ============================================================================
    // Step 2: Calendar & Time Selection
    // ============================================================================

    function initDateTimeSelection() {
        const calendarWidget = document.querySelector('.calendar-widget');
        const timeSlotsContainer = document.querySelector('.time-slots-container');
        const continueBtn = document.getElementById('continueBtn');

        if (!calendarWidget) return;

        const appointmentTypeId = calendarWidget.dataset.appointmentType;
        const minDate = calendarWidget.dataset.minDate;
        const maxDate = calendarWidget.dataset.maxDate;

        // Initialize calendar
        initCalendar(calendarWidget, appointmentTypeId, minDate, maxDate);

        // Back button handler
        const backBtn = document.querySelector('.btn-back');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.href = '/book-appointment';
            });
        }

        // Continue button handler
        if (continueBtn) {
            continueBtn.addEventListener('click', () => {
                if (selectedDate && selectedTime) {
                    window.location.href = 
                        `/book-appointment/step3?appointment_type_id=${appointmentTypeId}&selected_date=${selectedDate}&selected_time=${selectedTime}`;
                }
            });
        }
    }

    function initCalendar(container, appointmentTypeId, minDate, maxDate) {
        // Create modern calendar interface
        const calendarHTML = `
            <div class="modern-calendar">
                <div class="calendar-header">
                    <button class="calendar-nav-btn" id="prevMonth">
                        <i class="fa fa-chevron-left"></i>
                    </button>
                    <h3 class="calendar-month-year" id="monthYear"></h3>
                    <button class="calendar-nav-btn" id="nextMonth">
                        <i class="fa fa-chevron-right"></i>
                    </button>
                </div>
                <div class="calendar-weekdays">
                    <div class="weekday">Sun</div>
                    <div class="weekday">Mon</div>
                    <div class="weekday">Tue</div>
                    <div class="weekday">Wed</div>
                    <div class="weekday">Thu</div>
                    <div class="weekday">Fri</div>
                    <div class="weekday">Sat</div>
                </div>
                <div class="calendar-days" id="calendarDays"></div>
            </div>
        `;

        container.innerHTML = calendarHTML;

        // Initialize calendar functionality
        currentCalendar = new ModernCalendar(appointmentTypeId, minDate, maxDate);
    }

    // Modern Calendar Class
    class ModernCalendar {
        constructor(appointmentTypeId, minDate, maxDate) {
            this.appointmentTypeId = appointmentTypeId;
            this.minDate = new Date(minDate);
            this.maxDate = new Date(maxDate);
            this.currentDate = new Date();
            this.selectedDate = null;

            this.monthYearEl = document.getElementById('monthYear');
            this.calendarDaysEl = document.getElementById('calendarDays');
            this.prevBtn = document.getElementById('prevMonth');
            this.nextBtn = document.getElementById('nextMonth');

            this.init();
        }

        init() {
            this.render();
            this.attachEventListeners();
        }

        attachEventListeners() {
            this.prevBtn.addEventListener('click', () => {
                this.currentDate.setMonth(this.currentDate.getMonth() - 1);
                this.render();
            });

            this.nextBtn.addEventListener('click', () => {
                this.currentDate.setMonth(this.currentDate.getMonth() + 1);
                this.render();
            });
        }

        render() {
            this.renderHeader();
            this.renderDays();
        }

        renderHeader() {
            const monthNames = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ];

            this.monthYearEl.textContent = 
                `${monthNames[this.currentDate.getMonth()]} ${this.currentDate.getFullYear()}`;
        }

        renderDays() {
            const year = this.currentDate.getFullYear();
            const month = this.currentDate.getMonth();
            const firstDay = new Date(year, month, 1);
            const lastDay = new Date(year, month + 1, 0);
            const startDate = new Date(firstDay);
            startDate.setDate(startDate.getDate() - firstDay.getDay());

            let html = '';
            const today = new Date();

            for (let i = 0; i < 42; i++) {
                const date = new Date(startDate);
                date.setDate(startDate.getDate() + i);

                const isCurrentMonth = date.getMonth() === month;
                const isToday = date.toDateString() === today.toDateString();
                const isPast = date < this.minDate;
                const isFuture = date > this.maxDate;
                const isDisabled = !isCurrentMonth || isPast || isFuture;
                const isSelected = this.selectedDate && 
                    date.toDateString() === this.selectedDate.toDateString();

                let classes = 'calendar-day';
                if (!isCurrentMonth) classes += ' other-month';
                if (isToday) classes += ' today';
                if (isDisabled) classes += ' disabled';
                if (isSelected) classes += ' selected';

                html += `
                    <div class="${classes}" 
                         data-date="${date.toISOString().split('T')[0]}"
                         ${!isDisabled ? 'tabindex="0"' : ''}>
                        ${date.getDate()}
                    </div>
                `;
            }

            this.calendarDaysEl.innerHTML = html;

            // Add click handlers
            this.calendarDaysEl.querySelectorAll('.calendar-day:not(.disabled)').forEach(day => {
                day.addEventListener('click', (e) => {
                    this.selectDate(e.target.dataset.date);
                });

                day.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        this.selectDate(e.target.dataset.date);
                    }
                });
            });
        }

        selectDate(dateString) {
            selectedDate = dateString;
            this.selectedDate = new Date(dateString);

            // Update visual selection
            this.calendarDaysEl.querySelectorAll('.calendar-day').forEach(day => {
                day.classList.remove('selected');
            });
            this.calendarDaysEl.querySelector(`[data-date="${dateString}"]`).classList.add('selected');

            // Load time slots for selected date
            this.loadTimeSlots(dateString);
        }

        async loadTimeSlots(dateString) {
            const timeSlotsContainer = document.querySelector('.time-slots-container');
            const timeSlotsGrid = document.getElementById('timeSlots');

            timeSlotsContainer.style.display = 'block';
            showLoading(timeSlotsGrid);

            try {
                const response = await fetch('/book-appointment/api/available-slots', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: {
                            appointment_type_id: parseInt(this.appointmentTypeId),
                            date: dateString,
                        }
                    })
                });

                const result = await response.json();
                
                if (result.error) {
                    showError(timeSlotsGrid, 'Failed to load available times');
                    return;
                }

                availableSlots = result.result.slots || [];
                this.renderTimeSlots();

            } catch (error) {
                console.error('Error loading time slots:', error);
                showError(timeSlotsGrid, 'Failed to load available times');
            }
        }

        renderTimeSlots() {
            const timeSlotsGrid = document.getElementById('timeSlots');
            
            if (availableSlots.length === 0) {
                timeSlotsGrid.innerHTML = `
                    <div class="no-slots-message">
                        <i class="fa fa-calendar-times-o fa-2x text-muted mb-3"></i>
                        <p>No available times for this date.</p>
                        <p class="small text-muted">Please select another date.</p>
                    </div>
                `;
                return;
            }

            let html = '';
            availableSlots.forEach(slot => {
                const classes = `time-slot ${!slot.available ? 'unavailable' : ''}`;
                html += `
                    <div class="${classes}" 
                         data-time="${slot.time}" 
                         ${slot.available ? 'tabindex="0"' : ''}>
                        ${slot.time_str}
                    </div>
                `;
            });

            timeSlotsGrid.innerHTML = html;

            // Add click handlers for time slots
            timeSlotsGrid.querySelectorAll('.time-slot:not(.unavailable)').forEach(slot => {
                slot.addEventListener('click', (e) => {
                    this.selectTimeSlot(e.target);
                });

                slot.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        this.selectTimeSlot(e.target);
                    }
                });
            });
        }

        selectTimeSlot(slotElement) {
            selectedTime = slotElement.dataset.time;

            // Update visual selection
            document.querySelectorAll('.time-slot').forEach(slot => {
                slot.classList.remove('selected');
            });
            slotElement.classList.add('selected');

            // Enable continue button
            const continueBtn = document.getElementById('continueBtn');
            if (continueBtn) {
                continueBtn.disabled = false;
            }
        }
    }

    // ============================================================================
    // Step 3: Patient Information Form
    // ============================================================================

    function initPatientInfoForm() {
        const form = document.getElementById('patientInfoForm');
        const backBtn = document.querySelector('.btn-back');

        if (!form) return;

        // Form validation
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (!validateForm(form)) {
                return;
            }

            // Show loading state
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin mr-2"></i>Processing...';
            submitBtn.disabled = true;

            // Double-check slot availability before submission
            const isStillAvailable = await validateTimeSlot();
            
            if (!isStillAvailable) {
                alert('Sorry, this time slot is no longer available. Please select another time.');
                window.location.href = '/book-appointment/step2';
                return;
            }

            // Submit form
            form.submit();
        });

        // Back button
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                history.back();
            });
        }

        // Real-time form validation
        const requiredFields = form.querySelectorAll('input[required], textarea[required]');
        requiredFields.forEach(field => {
            field.addEventListener('blur', () => validateField(field));
            field.addEventListener('input', () => clearFieldError(field));
        });

        // Phone number formatting
        const phoneField = form.querySelector('#patient_phone');
        if (phoneField) {
            phoneField.addEventListener('input', formatPhoneNumber);
        }

        // Email validation
        const emailField = form.querySelector('#patient_email');
        if (emailField) {
            emailField.addEventListener('blur', validateEmail);
        }
    }

    function validateForm(form) {
        let isValid = true;
        const requiredFields = form.querySelectorAll('input[required], textarea[required]');

        requiredFields.forEach(field => {
            if (!validateField(field)) {
                isValid = false;
            }
        });

        return isValid;
    }

    function validateField(field) {
        const value = field.value.trim();
        let isValid = true;
        let errorMessage = '';

        // Required field validation
        if (field.hasAttribute('required') && !value) {
            isValid = false;
            errorMessage = 'This field is required';
        }

        // Email validation
        if (field.type === 'email' && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid email address';
            }
        }

        // Phone validation
        if (field.type === 'tel' && value) {
            const phoneRegex = /^[\+]?[0-9\s\-\(\)]{10,}$/;
            if (!phoneRegex.test(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid phone number';
            }
        }

        // Show/hide error
        if (!isValid) {
            showFieldError(field, errorMessage);
        } else {
            clearFieldError(field);
        }

        return isValid;
    }

    function showFieldError(field, message) {
        clearFieldError(field);
        
        field.classList.add('is-invalid');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error text-danger small mt-1';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    }

    function clearFieldError(field) {
        field.classList.remove('is-invalid');
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
    }

    function formatPhoneNumber(e) {
        let value = e.target.value.replace(/\D/g, '');
        
        if (value.startsWith('84')) {
            value = '+' + value;
        } else if (value.startsWith('0') && value.length > 1) {
            value = '+84' + value.substring(1);
        }
        
        e.target.value = value;
    }

    function validateEmail(e) {
        validateField(e.target);
    }

    async function validateTimeSlot() {
        try {
            const response = await fetch('/book-appointment/api/validate-slot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        appointment_type_id: parseInt(selectedAppointmentType),
                        date: selectedDate,
                        time: selectedTime,
                    }
                })
            });

            const result = await response.json();
            return result.result && result.result.available;
        } catch (error) {
            console.error('Error validating time slot:', error);
            return false;
        }
    }

    // ============================================================================
    // General UI Enhancements
    // ============================================================================

    function initGeneralEnhancements() {
        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });

        // Add loading states to all buttons
        document.querySelectorAll('button[type="submit"], .btn-primary').forEach(button => {
            button.addEventListener('click', function() {
                if (!this.disabled) {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fa fa-spinner fa-spin mr-2"></i>Loading...';
                    this.disabled = true;
                    
                    // Re-enable after 5 seconds as fallback
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.disabled = false;
                    }, 5000);
                }
            });
        });

        // Mobile menu toggle (if needed)
        const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
        if (mobileMenuToggle) {
            mobileMenuToggle.addEventListener('click', function() {
                const menu = document.querySelector('.mobile-menu');
                if (menu) {
                    menu.classList.toggle('active');
                }
            });
        }

        // Intersection Observer for animations
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, observerOptions);

        // Observe elements for animation
        document.querySelectorAll('.appointment-type-card, .feature-box').forEach(el => {
            observer.observe(el);
        });
    }

    // ============================================================================
    // Initialization
    // ============================================================================

    document.addEventListener('DOMContentLoaded', function() {
        // Initialize based on current page
        const currentPage = document.body.getAttribute('data-page') || 
                           window.location.pathname.split('/').pop();

        switch (currentPage) {
            case 'book-appointment':
            case 'booking_portal_main':
                initAppointmentTypeSelection();
                break;
            case 'step2':
            case 'booking_portal_step2':
                initDateTimeSelection();
                break;
            case 'step3':
            case 'booking_portal_step3':
                initPatientInfoForm();
                break;
        }

        // Always initialize general enhancements
        initGeneralEnhancements();
    });

    // ============================================================================
    // Export for testing (if needed)
    // ============================================================================

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            formatTime,
            formatDate,
            validateForm,
            ModernCalendar
        };
    }

})();