# Translation Scripts - User Guide

## 📁 Available Translation Scripts

### 1. `translate_po_file.py` - Main Translation Script
**Location**: `/Users/adity/Documents/GitHub/health-1/translate_po_file.py`

**Purpose**: Automatically translates Odoo PO files from English to Vietnamese using a comprehensive medical/healthcare dictionary.

**Features**:
- 300+ medical and healthcare terms pre-configured
- Preserves HTML tags, format strings, and special characters
- Creates automatic backup before translation
- Shows progress during translation
- Reports translation coverage statistics

**Usage**:
```bash
python3 translate_po_file.py <path_to_po_file>

# Example:
python3 translate_po_file.py addons/health_crm/i18n/base.po
```

**What it does**:
1. Creates backup file (e.g., `base.po.backup`)
2. Reads the PO file
3. Translates all empty `msgstr` fields
4. Writes translated content back to original file
5. Shows statistics (e.g., "Translated 557/835 strings, Coverage: 66.7%")

---

### 2. `translate_po_improved.py` - Advanced Translation Script
**Location**: `/Users/adity/Documents/GitHub/health-1/translate_po_improved.py`

**Purpose**: Improved version with better HTML/CSS handling.

**Features**:
- Protects HTML class names from translation
- Better handling of HTML tags
- Separate input/output files

**Usage**:
```bash
python3 translate_po_improved.py <input.po> <output.po>

# Example:
python3 translate_po_improved.py addons/health_crm/i18n/base.po addons/health_crm/i18n/vi_VN.po
```

---

## 🚀 Quick Translation Workflow

### For Each Module (health_crm, health_fieldservice, etc.):

#### Step 1: Export PO file from Odoo
```
Odoo → Settings → Translations → Export Translation
- Language: Vietnamese / Tiếng Việt
- Format: PO File
- Apps: Select your module (e.g., Health CRM)
- Click Export
- Save as: base.po (or module_name.po)
```

#### Step 2: Copy to Module's i18n Folder
```bash
# Example for health_crm
cp ~/Downloads/base.po addons/health_crm/i18n/base.po
```

#### Step 3: Run Translation Script
```bash
# Translate the file
python3 translate_po_file.py addons/health_crm/i18n/base.po

# This will:
# - Create backup: base.po.backup
# - Translate all empty msgstr fields
# - Overwrite base.po with translations
```

#### Step 4: Fix Any Issues (if needed)
```python
# Run manual fixes for problematic translations
python3 << 'EOF'
with open('addons/health_crm/i18n/base.po', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix HTML class names
content = content.replace('class="Y tế-text-xs"', 'class="health-text-xs"')

# Add more fixes as needed
# content = content.replace('old_text', 'new_text')

with open('addons/health_crm/i18n/base.po', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed translations")
EOF
```

#### Step 5: Rename to vi_VN.po
```bash
mv addons/health_crm/i18n/base.po addons/health_crm/i18n/vi_VN.po
```

#### Step 6: Import to Odoo
```
Odoo → Settings → Translations → Import Translation
- Language: Vietnamese / Tiếng Việt
- File: Upload vi_VN.po
- Overwrite: ☑ Yes
- Click Import
```

---

## 📝 Modules to Translate

### Priority List:

| # | Module | Priority | Status |
|---|--------|----------|--------|
| 1 | health_base | HIGH | ✅ COMPLETED |
| 2 | health_crm | HIGH | ⏳ Pending |
| 3 | health_fieldservice | HIGH | ⏳ Pending |
| 4 | health_invoicing | HIGH | ⏳ Pending |
| 5 | health_pwa | MEDIUM | ⏳ Pending |
| 6 | advanced_pricing | MEDIUM | ⏳ Pending |
| 7 | health_landing | LOW | ⏳ Pending |
| 8 | health_theme | LOW | ⏳ Pending |
| 9 | base_user_role | LOW | ⏳ Pending (has partial translation) |
| 10 | web_timeline | LOW | ⏳ Pending |

### Batch Commands for All Modules:

```bash
# Translate all health modules at once
for module in health_crm health_fieldservice health_invoicing health_pwa health_landing health_theme advanced_pricing; do
    echo "=== Translating $module ==="
    if [ -f "addons/$module/i18n/base.po" ]; then
        python3 translate_po_file.py "addons/$module/i18n/base.po"
        mv "addons/$module/i18n/base.po" "addons/$module/i18n/vi_VN.po"
        echo "✅ $module translated and renamed"
    else
        echo "❌ base.po not found for $module"
    fi
done
```

---

## 🔧 Troubleshooting

### Issue: HTML class names getting translated
**Example**: `class="health-text-xs"` becomes `class="Y tế-text-xs"`

**Fix**:
```python
# Run this after translation
python3 << 'EOF'
import glob
for po_file in glob.glob('addons/*/i18n/vi_VN.po'):
    with open(po_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix common issues
    content = content.replace('class="Y tế-', 'class="health-')
    content = content.replace('class="Lịch', 'class="fa fa-calendar')

    with open(po_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Fixed {po_file}")
EOF
```

### Issue: Some strings still in English after translation
**Reason**: The term is not in the translation dictionary

**Fix**: Add the term to `TRANSLATION_DICT` in `translate_po_file.py` and re-run

---

## 📚 Translation Dictionary

The main script (`translate_po_file.py`) contains 300+ pre-configured translations organized by category:

- **Core Medical Terms**: Patient, Doctor, Nurse, Clinical, etc.
- **Patient Information**: First Name, Last Name, Date of Birth, etc.
- **Medical Information**: Blood Group, Allergies, Medical History, etc.
- **Contact Information**: Emergency Contact, Phone, Email, Address, etc.
- **Healthcare Roles**: Caregiver, Payer, Referrer, etc.
- **UI Elements**: Save, Cancel, Create, Edit, Delete, etc.
- **Vietnamese Specific**: CCCD/CMND, Province, District, etc.

### To Add New Terms:

Edit `translate_po_file.py` and add to `TRANSLATION_DICT`:

```python
TRANSLATION_DICT = {
    # ... existing terms ...

    # Add your new terms here:
    "New English Term": "Thuật ngữ tiếng Việt mới",
    "Another Term": "Thuật ngữ khác",
}
```

---

## 📊 Translation Statistics

### health_base Results:
- **Total translatable strings**: 835
- **Successfully translated**: 557
- **Translation coverage**: 66.7%
- **File size**: 179 KB (vi_VN.po)

### Expected Results for Other Modules:
- health_crm: ~200 strings
- health_fieldservice: ~150 strings
- health_invoicing: ~100 strings
- health_pwa: ~80 strings
- advanced_pricing: ~60 strings

---

## ✅ Completed Work

### health_base Module:
- [x] Exported base.po from Odoo
- [x] Translated using script (557/835 strings)
- [x] Fixed HTML class name issues
- [x] Renamed to vi_VN.po
- [x] File location: `addons/health_base/i18n/vi_VN.po`
- [x] Backup available: `addons/health_base/i18n/base.po.backup`

### Sample Translations (health_base):
```po
msgid "Patient ID"
msgstr "Mã bệnh nhân"

msgid "Blood Group"
msgstr "Nhóm máu"

msgid "Emergency Contact"
msgstr "Liên hệ khẩn cấp"

msgid "First Name"
msgstr "Tên"

msgid "Medical History"
msgstr "Tiền sử bệnh"
```

---

## 🎯 Next Steps

1. **Export PO files** from Odoo for remaining 9 modules
2. **Run translation script** on each PO file
3. **Fix any HTML/CSS issues** if needed
4. **Rename to vi_VN.po** for each module
5. **Import back to Odoo** via Settings → Translations → Import
6. **Test** by switching user language to Vietnamese

---

## 💾 Backup Strategy

**Automatic Backups**: The script creates `.backup` files automatically

**Manual Backups**: Before translating multiple modules:
```bash
# Backup all existing PO files
tar -czf po_files_backup_$(date +%Y%m%d).tar.gz addons/*/i18n/*.po

# Restore if needed
tar -xzf po_files_backup_20251029.tar.gz
```

---

## 🔄 Re-translation Process

If you need to update translations after code changes:

```bash
# 1. Export fresh PO file from Odoo (will include new strings)
# 2. Copy to module folder
cp ~/Downloads/base.po addons/health_crm/i18n/base_new.po

# 3. Merge with existing translations (keeps existing, adds new)
msgmerge addons/health_crm/i18n/vi_VN.po addons/health_crm/i18n/base_new.po -o addons/health_crm/i18n/vi_VN_merged.po

# 4. Translate new strings only
python3 translate_po_file.py addons/health_crm/i18n/vi_VN_merged.po

# 5. Replace old file
mv addons/health_crm/i18n/vi_VN_merged.po addons/health_crm/i18n/vi_VN.po
```

---

## 📖 Related Documentation

- **Full Guide**: `VIETNAMESE_TRANSLATION_GUIDE.md` - Complete implementation guide
- **Quick Start**: `TRANSLATION_QUICK_START.md` - Quick reference card
- **Sample File**: `addons/health_base/i18n/SAMPLE_TRANSLATION.po` - Example translations

---

## ⚠️ Important Notes

1. **Always backup** before running translation scripts
2. **Test translations** in development environment first
3. **HTML class names** should NOT be translated (script may need manual fixes)
4. **Format strings** like `%s`, `%(variable)s` should be preserved
5. **Medical terminology** should follow Ministry of Health standards
6. **Encoding must be UTF-8** for Vietnamese characters

---

## 🤖 AI Assistant Instructions

**For future AI assistants working on this project:**

### Context:
- Project: Vietnamese healthcare management system (VAFHS)
- Framework: Odoo 18 Community Edition
- Translation: English → Vietnamese (vi_VN)
- 10 modules need translation

### Available Tools:
1. `translate_po_file.py` - Main translation script with medical dictionary
2. `translate_po_improved.py` - Advanced script with HTML protection
3. Pre-translated: health_base module (557/835 strings)

### Common Tasks:

#### Task 1: Translate a new module
```bash
# User will provide: module name (e.g., health_crm)
# Steps:
1. Verify PO file exists: ls addons/<module>/i18n/base.po
2. Run script: python3 translate_po_file.py addons/<module>/i18n/base.po
3. Fix HTML classes if needed (check for "Y tế-" in class names)
4. Rename: mv addons/<module>/i18n/base.po addons/<module>/i18n/vi_VN.po
5. Report statistics and show sample translations
```

#### Task 2: Add new translation terms
```python
# Edit translate_po_file.py
# Add to TRANSLATION_DICT around line 20
# Format: "English Term": "Bản dịch tiếng Việt"
# Then re-run translation
```

#### Task 3: Fix incorrect translations
```python
# Post-processing script pattern:
python3 << 'EOF'
with open('addons/<module>/i18n/vi_VN.po', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('incorrect', 'correct')

with open('addons/<module>/i18n/vi_VN.po', 'w', encoding='utf-8') as f:
    f.write(content)
EOF
```

#### Task 4: Batch translate all modules
```bash
# Use the batch command from "Batch Commands for All Modules" section above
# Check each module after translation for issues
```

### Key Reminders for AI:
- ✅ **DO**: Create backups before translation
- ✅ **DO**: Preserve HTML tags, CSS classes, format strings
- ✅ **DO**: Use medical terminology from dictionary
- ✅ **DO**: Report statistics after translation
- ✅ **DO**: Show sample translations for verification
- ❌ **DON'T**: Translate technical terms like class names, variable names
- ❌ **DON'T**: Translate empty msgid entries (header)
- ❌ **DON'T**: Change file encoding (must stay UTF-8)
- ❌ **DON'T**: Translate format placeholders (%s, %d, {})

### Expected User Requests:
1. "Translate health_crm module" → Run translation workflow
2. "Fix translation in health_base" → Post-process specific fixes
3. "Add new term to dictionary" → Edit translate_po_file.py
4. "Translate all modules" → Batch translation command
5. "Check translation coverage" → Count msgstr "" entries

### Medical Terminology Standards:
- Patient → "Bệnh nhân"
- Client → "Khách hàng" (VAFHS prefers this)
- Doctor → "Bác sĩ"
- Nurse → "Y tá" or "Điều dưỡng"
- Appointment → "Cuộc hẹn" or "Lịch hẹn"
- Medical History → "Tiền sử bệnh"
- Emergency → "Khẩn cấp"
- Insurance → "Bảo hiểm"

### File Paths to Remember:
- Scripts: `/Users/adity/Documents/GitHub/health-1/*.py`
- Modules: `/Users/adity/Documents/GitHub/health-1/addons/<module_name>/`
- PO files: `addons/<module_name>/i18n/vi_VN.po`
- Completed: `addons/health_base/i18n/vi_VN.po` ✅

### Testing Instructions:
After translation, user should:
1. Import PO file: Odoo → Settings → Translations → Import Translation
2. Switch language: User profile → Language: Vietnamese
3. Hard refresh: Ctrl+Shift+R
4. Check: Menus, forms, buttons display in Vietnamese

---

**End of Guide**

Last updated: 2025-10-29
Translated modules: 1/10 (health_base ✅)
Total coverage: ~560 strings translated
