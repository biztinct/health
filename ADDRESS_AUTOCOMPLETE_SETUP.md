# Address Autocomplete Setup Instructions

## Issues Fixed

### 1. OWL Template Syntax Error ✅
**Error**: `Unexpected identifier 'ctx'` - caused by using `not` instead of `!` in template conditions

**Fix Applied**: Changed all `not` operators to `!` in `/addons/health_base/static/src/xml/address_autocomplete_widget.xml`
- Line 27: `t-if="state.searchText and !state.isLoading"`
- Line 36: `t-if="!state.searchText and !state.isLoading"`
- Line 79: `t-if="!state.showDropdown and !state.searchText and !state.hasError"`

### 2. Database Schema Missing Fields
**Error**: `column res_partner.address_search does not exist`

**Cause**: New model fields defined in Python but not yet created in database

## Setup Steps

### Option A: Manual SQL Update (Fastest)

1. **Connect to your PostgreSQL database**:
   ```bash
   # SSH into your server or use pgAdmin
   psql -U odoo -d odoo18
   ```

2. **Run the migration script**:
   ```bash
   \i /path/to/health-1/add_address_fields.sql
   ```

   Or copy-paste the SQL commands from `add_address_fields.sql`

3. **Restart Odoo server** (via your hosting panel or SSH)

4. **Clear browser cache** and reload Odoo

5. **Test**: Open a patient record and try the address autocomplete

### Option B: Module Upgrade (Standard Method)

1. **Restart Odoo server first** to load new Python model definitions

2. **In Odoo UI**:
   - Go to Apps
   - Remove "Apps" filter
   - Search for "Healthcare Base"
   - Click "Upgrade" button

3. **Clear browser cache** and reload

4. **Test the feature**

### Option C: Command Line Upgrade (If you have CLI access)

```bash
# Stop Odoo
docker-compose stop odoo

# Run upgrade
docker-compose run --rm odoo odoo -d odoo18 -u health_base --stop-after-init

# Start Odoo
docker-compose start odoo
```

## Files Modified

1. **`/addons/health_base/models/res_partner.py`**
   - Added 5 new fields: `address_search`, `partner_latitude`, `partner_longitude`, `date_localization`, `geo_coordinates_display`
   - Added `_compute_geo_coordinates()` method
   - Added `action_geocode_address_photon()` method (manual geocoding button)
   - Added `photon_address_search()` method (autocomplete API)

2. **`/addons/health_base/static/src/js/address_autocomplete_widget.js`**
   - OWL widget component for autocomplete functionality

3. **`/addons/health_base/static/src/xml/address_autocomplete_widget.xml`**
   - Widget template (fixed `not` → `!` syntax)

4. **`/addons/health_base/static/src/scss/address_autocomplete_widget.scss`**
   - Professional styling for autocomplete dropdown

5. **`/addons/health_base/views/health_patient_views.xml`**
   - Added address autocomplete fields to patient form
   - Added country selection (VN, ID, SG, JP)
   - Added GPS coordinates display
   - Added "Refresh GPS Coordinates" button

6. **`/addons/health_base/__manifest__.py`**
   - Version bumped to 18.0.1.1.0
   - Added widget assets to `web.assets_backend`
   - Added `external_dependencies` for `requests` library

## Feature Overview

### Address Autocomplete
- Type minimum 3 characters in "Address Search" field
- Powered by **Photon API** (free, no API key required)
- OpenStreetMap data with 285M+ addresses worldwide
- Country filtering for accurate results
- Auto-fills: street, city, state, zip, country, GPS coordinates

### Geolocation
- Automatic GPS coordinates when selecting from autocomplete
- Manual "Refresh GPS Coordinates" button for manual addresses
- Displays: latitude, longitude, formatted coordinates
- Date stamp for last geolocation update

### Supported Countries (Initial)
- Vietnam (VN) - Default
- Indonesia (ID)
- Singapore (SG)
- Japan (JP)

**Easy to expand**: Remove domain filter in `health_patient_views.xml` line 103 to enable all countries

## Testing Checklist

After setup, verify:

- [ ] Patient form loads without errors
- [ ] Country dropdown shows only VN, ID, SG, JP
- [ ] Address search field appears above street field
- [ ] Typing shows autocomplete suggestions (min 3 chars)
- [ ] Selecting suggestion auto-fills all address fields
- [ ] GPS coordinates display in right column
- [ ] "Refresh GPS Coordinates" button works for manual addresses
- [ ] Date stamp shows when coordinates were updated

## Troubleshooting

### Template still shows errors
1. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Clear Odoo assets cache: Settings → Technical → Assets → Clear Cache
3. Restart browser completely

### Database fields still missing
1. Verify SQL script ran successfully
2. Check PostgreSQL logs for errors
3. Manually verify columns exist:
   ```sql
   \d+ res_partner
   ```

### Autocomplete not working
1. Check browser console for JavaScript errors
2. Verify internet connection (Photon API requires network)
3. Test API directly: `https://photon.komoot.io/api/?q=Nguyen%20Hue&countrycodes=VN`
4. Check Odoo server logs for Python errors

### "requests" module not found
1. Install in Odoo Python environment:
   ```bash
   pip3 install requests
   ```
2. Restart Odoo server

## API Details

**Photon API**: https://photon.komoot.io/api/
- **Free**: No API key required
- **Rate Limit**: Fair use policy (~1000 requests/hour recommended)
- **Coverage**: Worldwide (OpenStreetMap data)
- **Response Format**: GeoJSON with coordinates as [longitude, latitude]

## Next Steps

1. **Complete setup** using one of the options above
2. **Test functionality** with sample addresses
3. **Train users** on new address autocomplete feature
4. **Monitor usage** and API response times
5. **Expand countries** when ready (remove domain filter)

## Future Enhancements

- Map widget displaying patient location (top-right of form)
- Reverse geocoding (get address from coordinates)
- Batch geocoding for existing patient records
- Offline mode with cached addresses
- Alternative API fallback (Nominatim)

---

**Module**: health_base v18.0.1.1.0
**Technology**: Odoo 18 CE, OWL Framework, Photon API
**Documentation**: See `addons/health_address_autocomplete/README.md` (archived)
