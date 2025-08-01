/** @odoo-module **/

/**
 * VAFHS Healthcare Management System - Base JavaScript
 * Professional, mobile-first interactive components
 * PWA-optimized for offline functionality
 */

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Healthcare Base Widget
 * Provides common functionality for all healthcare components
 */
export class HealthcareBaseWidget extends Component {
    static template = "health_base.HealthcareBaseWidget";
    
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: false,
            offline: !navigator.onLine
        });
        
        // Bind offline/online event listeners
        this.onOnline = this.onOnline.bind(this);
        this.onOffline = this.onOffline.bind(this);
        
        onMounted(() => {
            window.addEventListener('online', this.onOnline);
            window.addEventListener('offline', this.onOffline);
            this.initializeHealthcareFeatures();
        });
        
        onWillUnmount(() => {
            window.removeEventListener('online', this.onOnline);
            window.removeEventListener('offline', this.onOffline);
        });
    }
    
    /**
     * Initialize healthcare-specific features
     */
    initializeHealthcareFeatures() {
        this.initializeTouchFriendlyControls();
        this.initializeAccessibilityFeatures();
        this.initializePWAFeatures();
        this.initializeFormValidation();
    }
    
    /**
     * Make controls touch-friendly for mobile healthcare staff
     */
    initializeTouchFriendlyControls() {
        // Ensure all clickable elements are at least 44px for touch
        const clickableElements = document.querySelectorAll('.health-btn, .health-time-slot, .health-date-cell');
        clickableElements.forEach(element => {
            const computedStyle = window.getComputedStyle(element);
            const height = parseInt(computedStyle.height);
            if (height < 44) {
                element.style.minHeight = '44px';
                element.style.display = 'flex';
                element.style.alignItems = 'center';
                element.style.justifyContent = 'center';
            }
        });
        
        // Add touch feedback
        document.addEventListener('touchstart', (e) => {
            if (e.target.classList.contains('health-btn') || 
                e.target.classList.contains('health-time-slot') || 
                e.target.classList.contains('health-date-cell')) {
                e.target.style.transform = 'scale(0.98)';
                e.target.style.opacity = '0.8';
            }
        });
        
        document.addEventListener('touchend', (e) => {
            if (e.target.classList.contains('health-btn') || 
                e.target.classList.contains('health-time-slot') || 
                e.target.classList.contains('health-date-cell')) {
                setTimeout(() => {
                    e.target.style.transform = '';
                    e.target.style.opacity = '';
                }, 150);
            }
        });
    }
    
    /**
     * Initialize accessibility features for healthcare compliance
     */
    initializeAccessibilityFeatures() {
        // Keyboard navigation for custom components
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                const focusedElement = document.activeElement;
                if (focusedElement.classList.contains('health-time-slot') || 
                    focusedElement.classList.contains('health-date-cell')) {
                    e.preventDefault();
                    focusedElement.click();
                }
            }
        });
        
        // Add ARIA labels for screen readers
        const timeSlots = document.querySelectorAll('.health-time-slot');
        timeSlots.forEach((slot, index) => {
            if (!slot.getAttribute('aria-label')) {
                const timeText = slot.textContent.trim();
                slot.setAttribute('aria-label', `Time slot ${timeText}`);
                slot.setAttribute('role', 'button');
                slot.setAttribute('tabindex', '0');
            }
        });
        
        // Announce important changes to screen readers
        this.announceToScreenReader = (message) => {
            const announcement = document.createElement('div');
            announcement.setAttribute('aria-live', 'polite');
            announcement.setAttribute('aria-atomic', 'true');
            announcement.className = 'sr-only';
            announcement.textContent = message;
            document.body.appendChild(announcement);
            setTimeout(() => document.body.removeChild(announcement), 1000);
        };
    }
    
    /**
     * Initialize PWA features for offline functionality
     */
    initializePWAFeatures() {
        // Service Worker registration for offline caching
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/health_base/static/src/js/sw.js')
                .then(registration => {
                    console.log('Healthcare SW registered:', registration);
                })
                .catch(error => {
                    console.log('Healthcare SW registration failed:', error);
                });
        }
        
        // Cache critical healthcare data for offline use
        this.cacheHealthcareData();
        
        // Install prompt for PWA
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallPrompt();
        });
    }
    
    /**
     * Cache critical healthcare data for offline use
     */
    async cacheHealthcareData() {
        if ('caches' in window) {
            try {
                const cache = await caches.open('healthcare-data-v1');
                
                // Cache essential healthcare lookups
                const criticalUrls = [
                    '/web/dataset/call_kw/health.service.type/search_read',
                    '/web/dataset/call_kw/health.patient.category/search_read',
                    '/web/dataset/call_kw/health.urgency.level/search_read',
                    '/web/dataset/call_kw/health.facility/search_read'
                ];
                
                await cache.addAll(criticalUrls);
            } catch (error) {
                console.log('Healthcare data caching failed:', error);
            }
        }
    }
    
    /**
     * Show PWA install prompt
     */
    showInstallPrompt() {
        const installBanner = document.createElement('div');
        installBanner.className = 'health-install-prompt';
        installBanner.innerHTML = `
            <div class="health-card" style="position: fixed; bottom: 20px; right: 20px; z-index: 1000; max-width: 300px;">
                <div class="health-card-header">
                    <h4>Install VAFHS App</h4>
                    <button class="health-btn-close" onclick="this.closest('.health-install-prompt').remove()">×</button>
                </div>
                <div class="health-card-body">
                    <p>Install the VAFHS healthcare app for quick access and offline functionality.</p>
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <button class="health-btn health-btn-primary health-btn-sm" onclick="healthcareApp.installPWA()">Install</button>
                        <button class="health-btn health-btn-outline health-btn-sm" onclick="this.closest('.health-install-prompt').remove()">Later</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(installBanner);
    }
    
    /**
     * Install PWA
     */
    async installPWA() {
        if (this.deferredPrompt) {
            this.deferredPrompt.prompt();
            const { outcome } = await this.deferredPrompt.userChoice;
            if (outcome === 'accepted') {
                this.notification.add('VAFHS app installed successfully!', { type: 'success' });
            }
            this.deferredPrompt = null;
        }
        document.querySelector('.health-install-prompt')?.remove();
    }
    
    /**
     * Initialize form validation with healthcare-specific rules
     */
    initializeFormValidation() {
        // Phone number validation for Vietnamese numbers
        const phoneInputs = document.querySelectorAll('input[type="tel"], .health-input[data-type="phone"]');
        phoneInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const value = e.target.value;
                const vietnamesePhoneRegex = /^(\+84|84|0)(3|5|7|8|9)[0-9]{8}$/;
                
                if (value && !vietnamesePhoneRegex.test(value.replace(/\s/g, ''))) {
                    e.target.setCustomValidity('Please enter a valid Vietnamese phone number');
                    e.target.classList.add('error');
                } else {
                    e.target.setCustomValidity('');
                    e.target.classList.remove('error');
                    e.target.classList.add('success');
                }
            });
        });
        
        // Email validation
        const emailInputs = document.querySelectorAll('input[type="email"], .health-input[data-type="email"]');
        emailInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const value = e.target.value;
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                
                if (value && !emailRegex.test(value)) {
                    e.target.setCustomValidity('Please enter a valid email address');
                    e.target.classList.add('error');
                } else {
                    e.target.setCustomValidity('');
                    e.target.classList.remove('error');
                    if (value) e.target.classList.add('success');
                }
            });
        });
        
        // National ID validation for Vietnamese CCCD/CMND
        const nationalIdInputs = document.querySelectorAll('.health-input[data-type="national-id"]');
        nationalIdInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const value = e.target.value;
                // Vietnamese CCCD: 12 digits, CMND: 9-12 digits
                const nationalIdRegex = /^[0-9]{9,12}$/;
                
                if (value && !nationalIdRegex.test(value)) {
                    e.target.setCustomValidity('Please enter a valid National ID (CCCD/CMND)');
                    e.target.classList.add('error');
                } else {
                    e.target.setCustomValidity('');
                    e.target.classList.remove('error');
                    if (value) e.target.classList.add('success');
                }
            });
        });
    }
    
    /**
     * Handle online event
     */
    onOnline() {
        this.state.offline = false;
        document.querySelector('.health-offline-banner')?.classList.remove('show');
        this.syncOfflineData();
        this.notification.add('Connection restored. Syncing data...', { type: 'info' });
    }
    
    /**
     * Handle offline event
     */
    onOffline() {
        this.state.offline = true;
        this.showOfflineBanner();
        this.notification.add('You are now offline. Some features may be limited.', { type: 'warning' });
    }
    
    /**
     * Show offline banner
     */
    showOfflineBanner() {
        let banner = document.querySelector('.health-offline-banner');
        if (!banner) {
            banner = document.createElement('div');
            banner.className = 'health-offline-banner';
            banner.innerHTML = '⚠️ You are offline. Some features may be limited.';
            document.body.appendChild(banner);
        }
        banner.classList.add('show');
    }
    
    /**
     * Sync offline data when connection is restored
     */
    async syncOfflineData() {
        try {
            // Get offline data from localStorage
            const offlineData = JSON.parse(localStorage.getItem('healthcare_offline_data') || '[]');
            
            if (offlineData.length > 0) {
                for (const data of offlineData) {
                    try {
                        await this.orm.call(data.model, data.method, data.args);
                    } catch (error) {
                        console.error('Failed to sync offline data:', error);
                    }
                }
                
                // Clear offline data after successful sync
                localStorage.removeItem('healthcare_offline_data');
                this.notification.add(`Synced ${offlineData.length} offline changes`, { type: 'success' });
            }
        } catch (error) {
            console.error('Offline data sync failed:', error);
        }
    }
    
    /**
     * Store data for offline sync
     */
    storeOfflineData(model, method, args) {
        if (this.state.offline) {
            const offlineData = JSON.parse(localStorage.getItem('healthcare_offline_data') || '[]');
            offlineData.push({
                model,
                method,
                args,
                timestamp: new Date().toISOString()
            });
            localStorage.setItem('healthcare_offline_data', JSON.stringify(offlineData));
            return true;
        }
        return false;
    }
    
    /**
     * Format Vietnamese phone number
     */
    formatVietnamesePhone(phone) {
        if (!phone) return '';
        
        // Remove all non-digits
        const digits = phone.replace(/\D/g, '');
        
        // Format based on length
        if (digits.length === 10 && digits.startsWith('0')) {
            return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`;
        } else if (digits.length === 11 && digits.startsWith('84')) {
            return `+${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
        }
        
        return phone;
    }
    
    /**
     * Format Vietnamese currency
     */
    formatVietnameseCurrency(amount) {
        if (!amount) return '0 ₫';
        
        return new Intl.NumberFormat('vi-VN', {
            style: 'currency',
            currency: 'VND',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }
    
    /**
     * Get Vietnamese date format
     */
    formatVietnameseDate(date) {
        if (!date) return '';
        
        return new Intl.DateTimeFormat('vi-VN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        }).format(new Date(date));
    }
    
    /**
     * Show loading state
     */
    showLoading(message = 'Đang tải...') {
        this.state.loading = true;
        
        // Create loading overlay
        const overlay = document.createElement('div');
        overlay.className = 'health-loading-overlay';
        overlay.innerHTML = `
            <div class="health-loading">
                <div class="health-spinner"></div>
                <p style="margin-top: 1rem; color: var(--health-gray-600);">${message}</p>
            </div>
        `;
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        
        document.body.appendChild(overlay);
    }
    
    /**
     * Hide loading state
     */
    hideLoading() {
        this.state.loading = false;
        document.querySelector('.health-loading-overlay')?.remove();
    }
}

// Create global healthcare app instance
window.healthcareApp = new HealthcareBaseWidget();

// Register the component
registry.category("web.components").add("HealthcareBaseWidget", HealthcareBaseWidget);

/**
 * Healthcare-specific utility functions
 */
export const HealthcareUtils = {
    
    /**
     * Validate Vietnamese National ID
     */
    validateNationalId(id) {
        if (!id) return false;
        const cleanId = id.replace(/\D/g, '');
        return /^[0-9]{9,12}$/.test(cleanId);
    },
    
    /**
     * Validate Vietnamese phone number
     */
    validateVietnamesePhone(phone) {
        if (!phone) return false;
        const cleanPhone = phone.replace(/\D/g, '');
        return /^(84|0)(3|5|7|8|9)[0-9]{8}$/.test(cleanPhone);
    },
    
    /**
     * Calculate age from birth date
     */
    calculateAge(birthDate) {
        if (!birthDate) return 0;
        const today = new Date();
        const birth = new Date(birthDate);
        let age = today.getFullYear() - birth.getFullYear();
        const monthDiff = today.getMonth() - birth.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    },
    
    /**
     * Get urgency color based on level
     */
    getUrgencyColor(urgencyLevel) {
        const colors = {
            'emergency': 'var(--health-error)',
            'high': 'var(--health-warning)',
            'medium': 'var(--health-info)',
            'low': 'var(--health-success)'
        };
        return colors[urgencyLevel] || 'var(--health-gray-400)';
    },
    
    /**
     * Format medical record number
     */
    formatMedicalRecordNumber(number) {
        if (!number) return '';
        return number.replace(/(.{4})/g, '$1-').slice(0, -1);
    },
    
    /**
     * Get Vietnamese district from address
     */
    parseVietnameseAddress(address) {
        if (!address) return { district: '', city: '', province: '' };
        
        const parts = address.split(',').map(part => part.trim());
        return {
            district: parts[0] || '',
            city: parts[1] || '',
            province: parts[2] || ''
        };
    }
};

// Make utils globally available
window.HealthcareUtils = HealthcareUtils;