# Business Analytics Dashboard

A state-of-the-art analytics dashboard module for Odoo 18 CE with drag-and-drop chart builder, advanced filtering, and professional visualization capabilities.

## Features

### 🎯 Core Functionality
- **Interactive Dashboard Builder**: Create professional analytics dashboards with drag-and-drop interface
- **Advanced Chart Types**: Bar, Line, Pie, Doughnut, Area, Scatter, Radar, and Gauge charts
- **Real-time Data Visualization**: Connect to any Odoo model for live data updates
- **Multi-criteria Filtering**: Advanced filtering system with date ranges, selections, and numeric filters
- **Responsive Design**: Mobile-first PWA-ready interface that works on all devices

### 📊 Chart & Analytics
- **Chart.js Integration**: Leverages Odoo 18's native Chart.js library for high-performance rendering
- **Drag & Drop Field Selector**: Intuitive field selection with visual drag-and-drop interface
- **Custom Aggregations**: Sum, Average, Min, Max, Count, and Count Distinct aggregations
- **Dynamic Color Schemes**: Built-in themes and custom color palette support
- **Interactive Charts**: Click events, drill-down capabilities, and hover interactions

### 🎨 Professional UI/UX
- **Modern Design**: Clean, professional interface inspired by top-tier analytics applications
- **Theme Support**: Light, dark, and automatic theme switching
- **Grid Layout System**: Flexible 12-column responsive grid with precise widget positioning
- **Animation Support**: Smooth transitions and chart animations (can be disabled for accessibility)

### 🔧 Technical Excellence
- **OWL Framework**: Built with Odoo 18's native OWL (Odoo Web Library) framework
- **Model-Controller-Renderer Pattern**: Clean separation of concerns following Odoo's architecture
- **Lazy Loading**: Efficient resource loading for optimal performance
- **Auto-refresh**: Configurable automatic data refresh intervals
- **Export Capabilities**: PDF, Excel, and PNG export support

### 🛡️ Enterprise Features
- **Access Control**: User and group-based dashboard access management
- **Multi-language Support**: Fully translatable interface
- **Audit Trail**: Complete tracking of dashboard changes with Odoo's chatter integration
- **Data Security**: Respects Odoo's record rules and access controls

## Installation

1. Copy the module to your Odoo addons directory
2. Update the app list in Odoo
3. Install the "Business Analytics Dashboard" module
4. Navigate to Analytics menu to start building dashboards

## Usage

### Quick Start
1. **Create Dataset**: Go to Analytics > Configuration > Datasets
2. **Configure Fields**: Select your data source and configure available fields
3. **Build Dashboard**: Create a new dashboard and add widgets using the drag-and-drop interface
4. **Apply Filters**: Use the advanced filtering system to focus on specific data

### Advanced Configuration
- **Custom Chart Types**: Configure advanced chart options using JSON configuration
- **Automated Refresh**: Set up automatic data refresh for real-time dashboards
- **Shared Dashboards**: Create public dashboards or restrict access to specific users/groups

## Architecture

### Models
- `analytics.dashboard`: Dashboard configuration and layout
- `analytics.dataset`: Data source definitions with field mappings
- `analytics.dataset.field`: Individual field configurations for analytics
- `analytics.widget`: Chart and widget configurations

### Components
- **DashboardView**: Main OWL view component with MVC pattern
- **FieldSelector**: Drag-and-drop field selection interface  
- **FilterPanel**: Advanced multi-criteria filtering system
- **DashboardRenderer**: Chart rendering and layout management

### Technology Stack
- **Frontend**: OWL Framework, Chart.js, Bootstrap 5, SCSS
- **Backend**: Python 3, Odoo 18 CE Framework
- **Database**: PostgreSQL (via Odoo ORM)

## Contributing

This module follows Odoo development best practices:
- Clean code with comprehensive documentation
- Extensible architecture for custom requirements
- Security-first approach with proper access controls
- Mobile-responsive design principles

## Support

For issues and feature requests, please contact the development team or create an issue in the project repository.

## License

This module is licensed under LGPL-3.0 to ensure compatibility with Odoo Community Edition.

---

**Built for Vietnam-Australia Family Health Service Company Limited (VAFHS)**  
*Professional healthcare analytics and business intelligence solution*