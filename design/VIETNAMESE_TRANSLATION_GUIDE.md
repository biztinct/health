# Vietnamese Translation Implementation Guide
## Option B: File-Based Translation (Bulk Translation)

**Status**: Ready to implement
**Estimated Time**: 30-40 hours (including translation)
**Target Language**: Vietnamese / Tiếng Việt (vi_VN)

---

## Prerequisites ✓

- [x] Vietnamese language installed in Odoo (Settings → Translations → Languages)
- [x] User can switch to Vietnamese in profile settings
- [x] Core Odoo modules already have Vietnamese translations

---

## Phase 1: Export Translatable Strings from Odoo

Odoo will automatically extract ALL translatable strings from your modules (Python code + XML views) without you needing to wrap them with `_()` manually!

### Step 1.1: Export health_base Module

1. **Navigate to**: Settings → Translations → Export Translation
2. **Configure export**:
   - Language: `Vietnamese / Tiếng Việt`
   - File Format: `PO File`
   - Apps to export: Click "Search More" → Find and select `Health Base`
3. **Click**: `Export` button
4. **Save file as**: `health_base_vi_VN.po` (your browser will download it)

### Step 1.2: Repeat for All Health Modules

Repeat Step 1.1 for each of these modules:

| Module Name | File Name to Save |
|-------------|------------------|
| Health Base | `health_base_vi_VN.po` |
| Health CRM | `health_crm_vi_VN.po` |
| Health Field Service | `health_fieldservice_vi_VN.po` |
| Health Invoicing | `health_invoicing_vi_VN.po` |
| Health Landing | `health_landing_vi_VN.po` |
| Health PWA | `health_pwa_vi_VN.po` |
| Health Theme | `health_theme_vi_VN.po` |
| Advanced Pricing | `advanced_pricing_vi_VN.po` |
| Base User Role | `base_user_role_vi_VN.po` (already has some translations) |
| Web Timeline | `web_timeline_vi_VN.po` |

**Expected Result**: You should have 10 `.po` files downloaded.

---

## Phase 2: Understand the PO File Format

### What is a PO File?

A `.po` file (Portable Object) is a plain text file containing translations. Each translatable string has this format:

```po
#. module: health_base
#: model:ir.model.fields,field_description:health_base.field_res_partner__is_patient
msgid "Is Patient"
msgstr ""
```

**Explanation**:
- `#.` and `#:` are comments showing where the string comes from
- `msgid` = English source string (don't change this!)
- `msgstr` = Vietnamese translation (this is what you fill in!)

### Example Translations

```po
msgid "Is Patient"
msgstr "Là Bệnh nhân"

msgid "Primary Facility"
msgstr "Cơ sở Y tế Chính"

msgid "Emergency Contact"
msgstr "Người Liên hệ Khẩn cấp"

msgid "Blood Group"
msgstr "Nhóm Máu"

msgid "Date of Birth"
msgstr "Ngày Sinh"
```

---

## Phase 3: Translate the PO Files

### Translation Options

#### Option A: Manual Translation with Text Editor
1. Open `.po` file in any text editor (VS Code, Sublime, Notepad++)
2. Find empty `msgstr ""` entries
3. Fill in Vietnamese translation between the quotes
4. Save file

#### Option B: Use Poedit (Recommended - FREE)
1. **Download Poedit**: https://poedit.net/ (free version is sufficient)
2. **Open** your `.po` file in Poedit
3. **Interface benefits**:
   - Shows untranslated strings at the top
   - Has translation memory (remembers similar translations)
   - Validates PO file format automatically
   - Can use machine translation to pre-fill (then you review/edit)
4. **Save** when done - Poedit ensures correct format

#### Option C: Professional Translator Service
1. Send the 10 `.po` files to a Vietnamese translator
2. **Important**: Instruct them to:
   - ONLY modify `msgstr` lines (not `msgid`)
   - Keep file encoding as UTF-8
   - Preserve special characters like `%s`, `%d`, `{variable_name}`
   - Use standard Vietnamese medical terminology

### Translation Guidelines

**Medical Terms** (Use Ministry of Health standard terms):
- Patient → "Bệnh nhân"
- Client → "Khách hàng" or "Thân chủ"
- Doctor → "Bác sĩ"
- Nurse → "Y tá" or "Điều dưỡng"
- Facility → "Cơ sở Y tế"
- Appointment → "Cuộc hẹn" or "Lịch hẹn"
- Medical History → "Tiền sử bệnh"
- Prescription → "Đơn thuốc"
- Diagnosis → "Chẩn đoán"

**Vietnamese Name Order**:
- First Name → "Tên"
- Last Name → "Họ"
- Middle Name → "Tên đệm"
- Full Name → "Họ và tên"

**Form Labels**:
- Save → "Lưu"
- Cancel → "Hủy"
- Create → "Tạo mới"
- Edit → "Chỉnh sửa"
- Delete → "Xóa"
- Search → "Tìm kiếm"
- Filter → "Lọc"
- Export → "Xuất"
- Import → "Nhập"
- Print → "In"

**Special Characters to Preserve**:
- `%s` → String placeholder (keep as-is in translation)
- `%(variable)s` → Named placeholder (keep as-is)
- `\n` → Newline (keep as-is)
- HTML tags like `<b>`, `</b>`, `<p>` (keep as-is)

---

## Phase 4: Create i18n Directories

Before importing translations, you need to create `i18n` folders in each module:

```bash
# Run these commands from your project root
mkdir -p addons/health_base/i18n
mkdir -p addons/health_crm/i18n
mkdir -p addons/health_fieldservice/i18n
mkdir -p addons/health_invoicing/i18n
mkdir -p addons/health_landing/i18n
mkdir -p addons/health_pwa/i18n
mkdir -p addons/health_theme/i18n
mkdir -p addons/advanced_pricing/i18n
# base_user_role and web_timeline already have i18n folders
```

---

## Phase 5: Move Translated Files to Modules

Copy your translated `.po` files to the correct module folders:

```bash
# Example for health_base
cp ~/Downloads/health_base_vi_VN.po addons/health_base/i18n/vi_VN.po

# Repeat for all modules
cp ~/Downloads/health_crm_vi_VN.po addons/health_crm/i18n/vi_VN.po
cp ~/Downloads/health_fieldservice_vi_VN.po addons/health_fieldservice/i18n/vi_VN.po
cp ~/Downloads/health_invoicing_vi_VN.po addons/health_invoicing/i18n/vi_VN.po
cp ~/Downloads/health_landing_vi_VN.po addons/health_landing/i18n/vi_VN.po
cp ~/Downloads/health_pwa_vi_VN.po addons/health_pwa/i18n/vi_VN.po
cp ~/Downloads/health_theme_vi_VN.po addons/health_theme/i18n/vi_VN.po
cp ~/Downloads/advanced_pricing_vi_VN.po addons/advanced_pricing/i18n/vi_VN.po
cp ~/Downloads/base_user_role_vi_VN.po addons/base_user_role/i18n/vi_VN.po
cp ~/Downloads/web_timeline_vi_VN.po addons/web_timeline/i18n/vi_VN.po
```

---

## Phase 6: Import Translations into Odoo

### Method 1: Import via Odoo UI (Recommended)

1. **Navigate to**: Settings → Translations → Import Translation
2. **Configure**:
   - Language: `Vietnamese / Tiếng Việt`
   - File: Click "Upload your file" → Select your `.po` file
   - Overwrite Existing Terms: `☑ Yes` (check this box)
3. **Click**: Import
4. **Repeat for all 10 modules**

### Method 2: Update Module to Auto-Load Translations

After placing `.po` files in `i18n/` folders, you can force Odoo to reload them:

1. Go to: **Apps** menu
2. Remove the "Apps" filter (click ×)
3. Search for your module (e.g., "Health Base")
4. Click: **⚙ Upgrade** button

This will automatically load the `vi_VN.po` file from the module's `i18n/` folder.

---

## Phase 7: Test Vietnamese Translations

### Test Steps

1. **Switch User Language**:
   - Click your name (top-right corner) → Preferences
   - Language: Select `Vietnamese / Tiếng Việt`
   - Click: Save

2. **Reload Browser**: Press `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)

3. **Verify Translations**:
   - Open Health → Patients → Create
   - Check if labels are in Vietnamese
   - Check form field labels
   - Check button labels
   - Check menu items

4. **Check Specific Areas**:
   - ✓ Patient form fields
   - ✓ Facility records
   - ✓ CRM leads/contacts
   - ✓ Field service orders
   - ✓ Invoices
   - ✓ Menu items
   - ✓ Error messages
   - ✓ Button labels

### Troubleshooting

**Problem**: Some strings still appear in English

**Solutions**:
1. **Clear browser cache**: Hard refresh (`Ctrl+Shift+R`)
2. **Check translation file**: Make sure `msgstr` is not empty for that string
3. **Re-import**: Go to Settings → Translations → Import Translation and import again with "Overwrite" checked
4. **Update module**: Apps → Remove "Apps" filter → Find module → Upgrade

**Problem**: Translations not loading

**Solutions**:
1. **Check file location**: Ensure `.po` files are in `addons/<module>/i18n/vi_VN.po`
2. **Check file encoding**: Must be UTF-8
3. **Validate PO syntax**: Use Poedit to open and validate the file
4. **Check Odoo logs**: Look for i18n-related errors

---

## Phase 8: Incremental Improvements

### Finding Untranslated Terms

1. **Navigate to**: Settings → Translations → Translated Terms
2. **Filter**:
   - Language: Vietnamese / Tiếng Việt
   - Untranslated: ☑ (check this)
   - Module: Select specific module
3. **Translate directly in UI**: Click each term and add Vietnamese translation
4. **No import needed**: Changes are immediate

### Exporting Updates

After making changes via UI, export again to keep your `.po` files up-to-date:

1. Settings → Translations → Export Translation
2. Select: Vietnamese / Tiếng Việt
3. Select: Your module
4. Export and save

---

## Expected Translation Counts (Estimates)

| Module | Estimated Strings | Priority |
|--------|------------------|----------|
| health_base | ~300 | HIGH |
| health_crm | ~200 | HIGH |
| health_fieldservice | ~150 | MEDIUM |
| health_invoicing | ~100 | HIGH |
| health_pwa | ~80 | MEDIUM |
| advanced_pricing | ~60 | MEDIUM |
| health_landing | ~40 | LOW |
| health_theme | ~30 | LOW |
| base_user_role | ~50 (already partial) | LOW |
| web_timeline | ~25 | LOW |
| **TOTAL** | **~1,035 strings** | - |

**Translation Time Estimate**:
- Professional translator: ~20-25 hours
- Manual translation: ~30-40 hours
- Machine + review: ~15-20 hours

---

## Useful Vietnamese Medical Terminology Reference

### Body Parts (Bộ phận cơ thể)
- Head → Đầu
- Heart → Tim
- Lungs → Phổi
- Stomach → Dạ dày
- Liver → Gan
- Kidney → Thận

### Common Medical Terms
- Allergy → Dị ứng
- Symptom → Triệu chứng
- Treatment → Điều trị
- Surgery → Phẫu thuật
- Medicine → Thuốc
- Vaccine → Vắc-xin
- Test → Xét nghiệm
- Result → Kết quả
- Emergency → Khẩn cấp
- Insurance → Bảo hiểm

### Administrative Terms
- Registration → Đăng ký
- Appointment → Lịch hẹn / Cuộc hẹn
- Payment → Thanh toán
- Invoice → Hóa đơn
- Receipt → Biên lai
- Report → Báo cáo
- Status → Trạng thái
- Active → Đang hoạt động
- Inactive → Ngừng hoạt động

---

## Quick Reference: Commands

```bash
# Create i18n directories for all health modules
for module in health_base health_crm health_fieldservice health_invoicing health_landing health_pwa health_theme advanced_pricing; do
    mkdir -p addons/$module/i18n
done

# Check which modules need i18n folders
ls -d addons/health_*/i18n addons/advanced_pricing/i18n addons/base_user_role/i18n addons/web_timeline/i18n 2>/dev/null

# List all .po files
find addons -name "vi_VN.po" -o -name "*vi*.po"
```

---

## Success Criteria

✓ All 10 modules have `i18n/vi_VN.po` files
✓ Vietnamese language is active in Odoo
✓ User can switch to Vietnamese in preferences
✓ 90%+ of UI strings display in Vietnamese
✓ Medical terminology is accurate and consistent
✓ Forms, menus, buttons all translated
✓ Error messages display in Vietnamese

---

## Support & Resources

- **Odoo i18n Documentation**: https://www.odoo.com/documentation/18.0/developer/reference/backend/translations.html
- **Poedit Download**: https://poedit.net/
- **Vietnamese Medical Dictionary**: Contact Vietnamese medical association for terminology standards
- **Test Database**: Always test translations in development environment first

---

## Next Steps

1. ✅ Read this guide completely
2. ⏳ Export all module translations (Phase 1)
3. ⏳ Translate .po files (Phase 3) - Can outsource to professional translator
4. ⏳ Create i18n folders (Phase 4)
5. ⏳ Import translations (Phase 6)
6. ⏳ Test with Vietnamese user (Phase 7)
7. ⏳ Iterate and improve (Phase 8)

---

**Questions?** Review the Troubleshooting section or check Odoo logs for errors.

**Good luck with the translation! Chúc bạn thành công! 🇻🇳**
