# Address Fields Display Update

## Summary

Updated the Patient form to display standard address fields (Street, City, Province, Country) that were previously hidden. These fields are essential for automatic GPS geocoding.

## Changes Made

### File Modified
- `/Users/adity/Documents/GitHub/health-1/addons/health_base/views/health_patient_views.xml`

### Changes

#### 1. Made Address Fields Visible (Lines 118-122)

**Previously**: Fields were hidden with `invisible="1"`
```xml
<field name="street" invisible="1"/>
<field name="city" invisible="1"/>
<field name="state_id" invisible="1"/>
<field name="country_id" invisible="1"/>
```

**Now**: Fields are visible and properly configured
```xml
<field name="street" placeholder="Street name / Main road"/>
<field name="city" placeholder="District / City" required="1"/>
<field name="state_id" string="Province" placeholder="Select province" options="{'no_create': True}" required="1"/>
<field name="country_id" string="Country" options="{'no_create': True}"/>
```

**Features Added**:
- ✅ **street**: Now visible with helpful placeholder
- ✅ **city**: Required field, placeholder text
- ✅ **state_id**: Renamed to "Province", required, dropdown (no manual create)
- ✅ **country_id**: Visible, dropdown (no manual create)

#### 2. Added Vietnam as Default Country (Line 420)

**Action Context Updated**:
```xml
<field name="context">{
    'search_default_active_patients': 1,
    'default_is_patient': True,
    'default_customer_rank': 1,
    'default_country_id': ref('base.vn'),  <!-- NEW: Vietnam default -->
    'default_patient_status': 'new',
    ...
</field>
```

**Result**: When creating new patients, Country automatically defaults to "Vietnam"

## Form Field Order

The address section now displays fields in this logical order:

### Vietnamese-Specific Fields:
1. Province Code (Mã tỉnh)
2. House Number (Số nhà)
3. Sub-Alley Number (Số ngách)
4. Alley Number (Số ngõ)
5. Ward/Commune (Phường/Xã)
6. Named Area (Khu vực)
7. Apartment Number (Số căn hộ)
8. Building Name (Tên tòa nhà)
9. Postal Code (Mã bưu điện)

### Standard Address Fields (NEW - Now Visible):
10. **Street** - Street name / Main road
11. **City** - District / City (Required)
12. **Province** - Select province dropdown (Required)
13. **Country** - Country dropdown (Default: Vietnam)

### Auto-Computed Field:
14. **Full Vietnamese Address** - Read-only, auto-generated from all fields above

### Map Display:
15. **Interactive Map** - Shows GPS location (right column)

## User Experience

### When Creating New Patient:

1. **Form opens with**:
   - Country pre-filled: "Vietnam" ✅
   - Required fields marked with *
   - Helpful placeholders in each field

2. **User fills address** (example):
   ```
   Province Code: 01
   House Number: 125
   Alley Number: 12
   Street: Đường Láng
   Ward/Commune: Láng Thượng
   City: Đống Đa (Required)
   Province: Hà Nội (Required - dropdown)
   Country: Vietnam (Already filled)
   ```

3. **System auto-computes**:
   - Full Vietnamese Address field shows:
     ```
     125 Ngõ 12 Đường Láng, Phường/Xã Láng Thượng, Đống Đa, Hà Nội, Vietnam
     ```

4. **User clicks Save**:
   - ✅ Record saves
   - 🌐 GPS coordinates auto-calculated (background)
   - 📍 Map updates with marker
   - ✅ All automatic!

## Field Validation

### Required Fields:
- ✅ **City**: Must be filled
- ✅ **Province (state_id)**: Must be selected from dropdown

### Optional Fields:
- Street (recommended for better geocoding accuracy)
- All Vietnamese-specific fields
- Country (defaults to Vietnam)

### Dropdown Fields:
- **Province**: Dropdown list, cannot manually create new provinces
- **Country**: Dropdown list, cannot manually create new countries

## Integration with Geocoding

These visible fields work perfectly with the automatic geocoding system:

### Geocoding Priority:
1. **High Priority** (if filled):
   - House Number → Alley → Street
   - Ward/Commune
   - City (Required)
   - Province (Required)

2. **Context** (for accuracy):
   - Country (default: Vietnam)

### Address Building for API:
```python
# System builds query like:
"125 Ngõ 12 Đường Láng, Láng Thượng, Đống Đa, Hà Nội, Vietnam"

# Sends to Photon API
# Gets GPS coordinates back
# Updates map automatically
```

## Benefits

### 1. Better User Experience
- ✅ Clear, visible fields
- ✅ Helpful placeholders
- ✅ Required fields marked
- ✅ Vietnam pre-selected (saves time)

### 2. Better Geocoding Accuracy
- ✅ Street name improves precision
- ✅ City/Province required = always have context
- ✅ Country set = proper location bias

### 3. Data Completeness
- ✅ Required fields ensure minimum data
- ✅ Dropdown prevents typos (Province/Country)
- ✅ Standard fields + Vietnamese fields = comprehensive

### 4. Consistency
- ✅ Standard Odoo fields (street, city, state_id, country_id)
- ✅ Compatible with other Odoo modules
- ✅ Follows Odoo conventions

## Testing

### Test Case 1: Create New Patient
```
Expected:
- Form opens
- Country = "Vietnam" (pre-filled)
- City field shows * (required)
- Province field shows * (required)
- All address fields visible
```

### Test Case 2: Fill Minimal Address
```
User fills:
- City: Hà Nội
- Province: Hà Nội

Expected:
- Can save (required fields filled)
- Vietnamese Address shows: "Hà Nội, Vietnam"
- GPS geocodes to Hanoi city center
```

### Test Case 3: Fill Complete Address
```
User fills:
- House Number: 125
- Alley: 12
- Street: Đường Láng
- Ward: Láng Thượng
- City: Đống Đa
- Province: Hà Nội
- Country: Vietnam (already filled)

Expected:
- Full Vietnamese Address auto-computes
- GPS geocodes with high precision
- Map shows exact location
```

## Technical Details

### Field Attributes

**street**:
- Type: Char
- Required: No (but recommended)
- Placeholder: "Street name / Main road"
- Used for: Geocoding precision

**city**:
- Type: Char
- Required: Yes
- Placeholder: "District / City"
- Used for: Geocoding context

**state_id**:
- Type: Many2one (res.country.state)
- Required: Yes
- Label: "Province"
- Options: {'no_create': True} (dropdown only)
- Used for: Geographic region

**country_id**:
- Type: Many2one (res.country)
- Required: No (has default)
- Default: Vietnam (base.vn)
- Options: {'no_create': True} (dropdown only)
- Used for: Country context

### Default Value Implementation

```xml
<!-- In action context -->
'default_country_id': ref('base.vn')

<!-- This references Odoo's base module Vietnam record -->
<!-- XML ID: base.vn -->
<!-- Display Name: "Vietnam" -->
```

## Module Upgrade

To apply these changes:

```bash
# Option 1: Via Odoo UI
Apps → Search "Health Base" → Upgrade

# Option 2: Via command line
odoo-bin -u health_base -d <database>
```

After upgrade:
1. Refresh browser (Ctrl+Shift+R)
2. Open patient form
3. Verify address fields visible
4. Verify Vietnam is default country

## Backward Compatibility

✅ **Existing Records**: No impact
- All existing patient records keep their data
- No data migration needed
- Existing addresses remain unchanged

✅ **Existing Workflows**: Enhanced
- Create/Edit forms now have more fields
- Geocoding works better with visible fields
- No breaking changes

## Related Features

### Works With:
1. **Automatic Geocoding** (AUTO_GEOCODING_IMPLEMENTATION.md)
   - Uses these fields to build address query
   - Triggers on save when fields change

2. **Vietnamese Address Computation**
   - Combines all fields into `vietnamese_address`
   - Updates automatically when any field changes

3. **Map Widget**
   - Displays location based on GPS coordinates
   - Updates when geocoding completes

## Future Enhancements

### Possible Improvements:
1. **Address Autocomplete**: Add suggestions as user types
2. **Province Filtering**: Filter provinces by country
3. **Ward/Commune Dropdown**: Pre-populate based on city
4. **Postal Code Validation**: Check format based on country
5. **Address Verification**: Validate address exists in map service

## Screenshots Location

When documenting for users, include screenshots showing:
- [ ] Empty form with Vietnam pre-selected
- [ ] Required field indicators (*) on City and Province
- [ ] Dropdown lists for Province and Country
- [ ] Auto-computed Vietnamese Address field
- [ ] Map update after save

## Summary

✅ **Street, City, Province, Country fields now visible**
✅ **Vietnam set as default country**
✅ **Required fields enforced (City, Province)**
✅ **Dropdown lists prevent typos**
✅ **Helpful placeholders guide users**
✅ **Integrates perfectly with auto-geocoding**

**Result**: Users now have clear, visible address fields with Vietnam pre-selected and intelligent validation! 🎉

---

**Implementation Date**: 2025-10-29
**Module**: health_base
**File Modified**: `views/health_patient_views.xml`
**Lines Modified**: 2 sections (form fields + action context)
**Backward Compatible**: ✅ Yes
