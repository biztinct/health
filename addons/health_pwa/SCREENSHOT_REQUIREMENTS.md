# PWA Installation Screenshot Requirements

This document outlines the screenshots needed for the comprehensive PWA rollout training materials.

## Overview

Screenshots are required for:
- Installation guides (Vietnamese UI)
- iOS step-by-step installation
- Android step-by-step installation
- Training materials
- Documentation PDFs
- Print materials (posters, cards)

---

## iOS Installation Screenshots

### Device Requirements
- **Device**: iPhone (iOS 15+ recommended)
- **Browser**: Safari
- **Language**: Vietnamese
- **Resolution**: Native resolution (e.g., 390×844 for iPhone 12/13)

### Required Screenshots

#### 1. **ios-install-01-home.png**
- **Description**: Home screen showing Safari with installation page open
- **URL to capture**: `https://yourdomain.com/health_pwa/install`
- **Notes**:
  - Page should show platform detection (iOS detected)
  - Vietnamese language active
  - Installation instructions visible

#### 2. **ios-install-02-share-button.png**
- **Description**: Safari browser with Share button highlighted
- **Elements to highlight**:
  - Share button (upward arrow icon) at bottom of browser
- **Annotation**: Circle or arrow pointing to Share button

#### 3. **ios-install-03-share-menu.png**
- **Description**: Share menu opened showing "Add to Home Screen" option
- **Elements to highlight**:
  - "Add to Home Screen" option in share menu
  - May need to scroll down in share menu to show this option
- **Annotation**: Highlight "Add to Home Screen" option

#### 4. **ios-install-04-add-confirm.png**
- **Description**: "Add to Home Screen" confirmation dialog
- **Elements visible**:
  - App icon preview
  - App name: "Viet Uc"
  - "Add" button at top-right
- **Annotation**: Highlight "Add" button

#### 5. **ios-install-05-home-screen.png**
- **Description**: iPhone home screen showing installed Viet Uc icon
- **Elements visible**:
  - Viet Uc app icon on home screen
  - Other apps for context
- **Annotation**: Circle around Viet Uc icon

#### 6. **ios-install-06-app-launched.png**
- **Description**: Viet Uc app running in standalone mode (no Safari UI)
- **Elements visible**:
  - Full app interface
  - No Safari browser bars
  - Status bar showing app running
- **Notes**: This shows the app running in PWA standalone mode

### iOS Version-Specific Notes
- If capturing on iOS 16+, note any UI differences
- Safari UI may vary between iOS versions
- Ensure Vietnamese language is set in iOS settings

---

## Android Installation Screenshots

### Device Requirements
- **Device**: Android phone (Android 10+ recommended)
- **Browser**: Google Chrome
- **Language**: Vietnamese
- **Resolution**: Native resolution (e.g., 1080×2340 common)

### Required Screenshots

#### 1. **android-install-01-home.png**
- **Description**: Installation page open in Chrome
- **URL to capture**: `https://yourdomain.com/health_pwa/install`
- **Notes**:
  - Page should show platform detection (Android detected)
  - Vietnamese language active
  - May show "Install" banner at bottom

#### 2. **android-install-02-auto-prompt.png** (if available)
- **Description**: Chrome's automatic PWA install prompt
- **Elements visible**:
  - Install banner at bottom of screen
  - "Install" and "Not now" buttons
- **Notes**: This may appear automatically; if not, proceed to manual method

#### 3. **android-install-03-menu-button.png**
- **Description**: Chrome with menu button (three dots) highlighted
- **Elements to highlight**:
  - Three-dot menu button at top-right
- **Annotation**: Circle menu button

#### 4. **android-install-04-menu-opened.png**
- **Description**: Chrome menu opened showing "Add to Home screen" or "Install app" option
- **Elements to highlight**:
  - "Add to Home screen" or "Install app" option
- **Annotation**: Highlight this option

#### 5. **android-install-05-install-dialog.png**
- **Description**: Install confirmation dialog
- **Elements visible**:
  - App icon
  - App name: "Viet Uc"
  - "Install" button
- **Annotation**: Highlight "Install" button

#### 6. **android-install-06-installing.png** (optional)
- **Description**: Brief "Installing..." message (if visible)
- **Notes**: This may be too brief to capture

#### 7. **android-install-07-home-screen.png**
- **Description**: Android home screen showing installed Viet Uc icon
- **Elements visible**:
  - Viet Uc app icon
  - App drawer or home screen context
- **Annotation**: Circle Viet Uc icon

#### 8. **android-install-08-app-launched.png**
- **Description**: Viet Uc app running in standalone mode
- **Elements visible**:
  - Full app interface
  - No Chrome browser UI
  - Android status bar
- **Notes**: Shows standalone PWA mode

---

## Desktop Installation Screenshots

### Requirements
- **OS**: Windows 10/11 or macOS
- **Browser**: Chrome, Edge, or Safari (macOS)
- **Language**: Vietnamese
- **Resolution**: 1920×1080 or higher

### Required Screenshots

#### 1. **desktop-install-01-browser.png**
- **Description**: Installation page in browser with install icon visible
- **Browser**: Chrome recommended
- **Elements to highlight**:
  - Install icon in address bar (⊕ or ⬇ symbol)
- **URL**: `https://yourdomain.com/health_pwa/install`

#### 2. **desktop-install-02-install-prompt.png**
- **Description**: Install confirmation dialog
- **Elements visible**:
  - App name and icon
  - "Install" button

#### 3. **desktop-install-03-installed.png**
- **Description**: Viet Uc running as standalone desktop app
- **Elements visible**:
  - Separate app window (not browser tab)
  - App toolbar/title bar

---

## Application UI Screenshots (Vietnamese)

These screenshots show the actual application interface for training materials.

### Required Screenshots

#### 1. **app-ui-01-dashboard.png**
- **Screen**: Dashboard/Home screen
- **Language**: Vietnamese
- **Notes**: Show main navigation and key features

#### 2. **app-ui-02-bookings-list.png**
- **Screen**: Bookings/Appointments list view
- **Language**: Vietnamese
- **Data**: Use demo data with Vietnamese names

#### 3. **app-ui-03-booking-detail.png**
- **Screen**: Single booking detail view
- **Language**: Vietnamese
- **Notes**: Show all booking information fields

#### 4. **app-ui-04-calendar.png**
- **Screen**: Calendar view with appointments
- **Language**: Vietnamese
- **Notes**: Show calendar with sample bookings

#### 5. **app-ui-05-offline-mode.png**
- **Screen**: App in offline mode (with indicator)
- **Notes**:
  - Put device in airplane mode
  - Show offline indicator/banner
  - Demonstrate offline functionality

#### 6. **app-ui-06-sync.png** (optional)
- **Screen**: Data syncing indicator
- **Notes**: Show sync in progress when coming back online

---

## QR Code Images

### Required Files

#### 1. **qr-code-install-page.png**
- **Description**: QR code pointing to installation page
- **URL**: `https://yourdomain.com/health_pwa/install?source=qr&campaign=training`
- **Size**: 500×500px minimum
- **Format**: PNG with transparent background if possible
- **Tool**: Use QRCode.js or online generator like qr-code-generator.com

#### 2. **qr-code-main-app.png**
- **Description**: QR code pointing directly to main app
- **URL**: `https://yourdomain.com/health_pwa?source=qr&campaign=direct`
- **Size**: 500×500px minimum
- **Format**: PNG

---

## File Organization

Create the following directory structure:

```
addons/health_pwa/static/screenshots/
├── ios/
│   ├── ios-install-01-home.png
│   ├── ios-install-02-share-button.png
│   ├── ios-install-03-share-menu.png
│   ├── ios-install-04-add-confirm.png
│   ├── ios-install-05-home-screen.png
│   └── ios-install-06-app-launched.png
├── android/
│   ├── android-install-01-home.png
│   ├── android-install-02-auto-prompt.png
│   ├── android-install-03-menu-button.png
│   ├── android-install-04-menu-opened.png
│   ├── android-install-05-install-dialog.png
│   ├── android-install-07-home-screen.png
│   └── android-install-08-app-launched.png
├── desktop/
│   ├── desktop-install-01-browser.png
│   ├── desktop-install-02-install-prompt.png
│   └── desktop-install-03-installed.png
├── app-ui/
│   ├── app-ui-01-dashboard.png
│   ├── app-ui-02-bookings-list.png
│   ├── app-ui-03-booking-detail.png
│   ├── app-ui-04-calendar.png
│   ├── app-ui-05-offline-mode.png
│   └── app-ui-06-sync.png
└── qr-codes/
    ├── qr-code-install-page.png
    └── qr-code-main-app.png
```

---

## Screenshot Capture Tools

### iOS
- **Built-in**: Press Side Button + Volume Up
- **Simulator**: Xcode Simulator (Cmd+S for screenshot)
- **Recommended**: Use actual iPhone for realistic screenshots

### Android
- **Built-in**: Press Power + Volume Down
- **Simulator**: Android Studio Emulator (screenshot toolbar button)
- **Recommended**: Use actual Android phone

### Desktop
- **Windows**: Snipping Tool or Win+Shift+S
- **macOS**: Cmd+Shift+4 (select area) or Cmd+Shift+3 (full screen)
- **Browser DevTools**: Can simulate mobile devices

### Annotation Tools
- **macOS**: Preview (built-in markup tools)
- **Windows**: Paint, Snip & Sketch
- **Cross-platform**:
  - Skitch (free)
  - Greenshot (free, Windows)
  - Shottr (free, macOS)

---

## Image Processing Guidelines

### Resolution
- **Mobile**: Keep native resolution
- **Desktop**: 1920×1080 recommended
- **QR Codes**: 500×500px minimum

### Format
- **Format**: PNG (preferred for screenshots)
- **Compression**: Optimize with TinyPNG or similar
- **File size**: Target <500KB per screenshot

### Annotations
- **Circles/Arrows**: Use bright color (e.g., #FF0000 red or #00FF00 green)
- **Text**: Use clear, readable font (16px+ for mobile screenshots)
- **Highlight**: Semi-transparent overlays when needed

---

## Vietnamese UI Checklist

Before capturing screenshots, ensure:

- [ ] Device/browser language set to Vietnamese
- [ ] App displays Vietnamese text (not English)
- [ ] Demo data uses Vietnamese names (e.g., "Nguyễn Văn An", not "John Smith")
- [ ] Date/time formats use Vietnamese locale (dd/mm/yyyy)
- [ ] All buttons and labels show Vietnamese translations

---

## Next Steps

1. **Capture screenshots** following this guide
2. **Organize files** in the directory structure above
3. **Create composite images** for training materials:
   - Step-by-step installation guides (combine multiple screenshots)
   - Side-by-side iOS vs Android comparisons
   - Annotated versions with arrows and highlights
4. **Update manifest.json** `screenshots` array with actual file paths
5. **Create video tutorials** using these screenshots as reference

---

## Notes

- All screenshots should be captured with **Vietnamese language active**
- Use **demo/test data** that looks realistic but doesn't expose real patient information
- Keep **consistent device appearance** (e.g., same iPhone model for all iOS screenshots)
- Ensure **good lighting and clarity** if photographing physical devices
- Consider **different screen sizes** (small phone, large phone, tablet) if targeting multiple form factors

---

## Reference Sizes

### Icons (already created)
- `/health_pwa/static/icons/icon-72.png` - 72×72
- `/health_pwa/static/icons/icon-192.png` - 192×192
- `/health_pwa/static/icons/icon-512.png` - 512×512

### Screenshots (to be created)
- **Mobile narrow**: 390×844 (iPhone reference)
- **Tablet wide**: 1024×768 (iPad reference)
- **Desktop**: 1920×1080

These dimensions should match what's declared in [manifest.json](addons/health_pwa/static/manifest.json).
