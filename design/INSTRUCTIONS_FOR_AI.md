# 🤖 Instructions for AI Assistants (Haiku/Claude Models)

> Historical document. Use `VietTranslation/README.md` and the utilities in
> `VietTranslation/scripts/` for the current Odoo 19 translation workflow.

## 📋 Quick Context

**Project**: Vietnamese translation for VAFHS Healthcare Management System
**Status**: 1/10 modules completed (health_base ✅)
**Your job**: Translate remaining 9 modules using existing scripts

---

## 🎯 What User Will Ask

### Request Type 1: "Translate health_crm module"

**Your response workflow**:

```bash
# Step 1: Check if base.po exists
ls addons/health_crm/i18n/base.po

# Step 2: Run translation script
python3 translate_po_file.py addons/health_crm/i18n/base.po

# Step 3: Check for HTML class issues in output
# If you see messages about class="Y tế-" or similar, fix:
python3 << 'EOF'
with open('addons/health_crm/i18n/base.po', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('class="Y tế-', 'class="health-')
content = content.replace('class="Lịch', 'class="fa fa-calendar')
with open('addons/health_crm/i18n/base.po', 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ Fixed HTML classes")
EOF

# Step 4: Rename to vi_VN.po
mv addons/health_crm/i18n/base.po addons/health_crm/i18n/vi_VN.po

# Step 5: Verify with samples
grep -A 1 "Patient\|Client\|Appointment" addons/health_crm/i18n/vi_VN.po | head -20
```

**Tell user**:
```
✅ Translated health_crm module
   - Translated: X/Y strings (Z% coverage)
   - File: addons/health_crm/i18n/vi_VN.po
   - Backup: addons/health_crm/i18n/base.po.backup

Sample translations:
[show 3-5 examples]

Next: Import to Odoo via Settings → Translations → Import Translation
```

---

### Request Type 2: "Translate all remaining modules"

**Your response**:

```bash
# Batch translation for all modules
for module in health_crm health_fieldservice health_invoicing health_pwa health_landing health_theme advanced_pricing; do
    echo ""
    echo "========================================="
    echo "Translating: $module"
    echo "========================================="

    if [ -f "addons/$module/i18n/base.po" ]; then
        # Translate
        python3 translate_po_file.py "addons/$module/i18n/base.po"

        # Fix HTML classes
        python3 << EOF
with open('addons/$module/i18n/base.po', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('class="Y tế-', 'class="health-')
content = content.replace('class="Lịch', 'class="fa fa-calendar')
with open('addons/$module/i18n/base.po', 'w', encoding='utf-8') as f:
    f.write(content)
EOF

        # Rename
        mv "addons/$module/i18n/base.po" "addons/$module/i18n/vi_VN.po"
        echo "✅ $module completed → vi_VN.po"
    else
        echo "❌ base.po not found - user needs to export from Odoo"
    fi
done

echo ""
echo "========================================="
echo "Summary"
echo "========================================="
ls -lh addons/health_*/i18n/vi_VN.po addons/advanced_pricing/i18n/vi_VN.po
```

---

### Request Type 3: "Add new translation term"

**Your response**:

```bash
# Read current dictionary size
python3 << 'EOF'
import re
with open('translate_po_file.py', 'r') as f:
    content = f.read()
matches = re.findall(r'"([^"]+)":\s*"([^"]+)"', content)
print(f"Current dictionary: {len(matches)} terms")
EOF

# Add new term (example)
# User will tell you: English term and Vietnamese translation
# Edit translate_po_file.py and add to TRANSLATION_DICT
```

**Tell user**:
```
To add new terms:
1. Edit translate_po_file.py
2. Find TRANSLATION_DICT = { around line 20
3. Add new entry:
   "Your English Term": "Bản dịch tiếng Việt",
4. Save and re-run translation script
```

---

## 📂 File Locations (Memorize These)

### Scripts:
- Main: `/Users/adity/Documents/GitHub/health-1/translate_po_file.py`
- Advanced: `/Users/adity/Documents/GitHub/health-1/translate_po_improved.py`

### Documentation:
- **Start here**: `TRANSLATION_SCRIPTS_GUIDE.md`
- Quick ref: `TRANSLATION_QUICK_START.md`
- Full guide: `VIETNAMESE_TRANSLATION_GUIDE.md`
- Summary: `TRANSLATION_SUMMARY.md`

### Module PO Files:
- Pattern: `addons/<module_name>/i18n/vi_VN.po`
- Completed example: `addons/health_base/i18n/vi_VN.po` ✅

---

## ✅ Always Do This

1. **Create backup** - Script does this automatically as `.backup`
2. **Check HTML classes** - Replace "Y tế-" with "health-"
3. **Show statistics** - Report "X/Y strings translated (Z% coverage)"
4. **Show samples** - Display 3-5 example translations
5. **Tell user location** - Show exact file path of vi_VN.po

---

## ❌ Never Do This

1. ❌ Don't translate empty msgid (header entry)
2. ❌ Don't change file encoding (must be UTF-8)
3. ❌ Don't translate variable names, class names
4. ❌ Don't translate format strings (%s, %d, {})
5. ❌ Don't skip the HTML fix step

---

## 🔑 Key Medical Translations (Quick Reference)

```
Patient → Bệnh nhân
Client → Khách hàng
Doctor → Bác sĩ
Nurse → Y tá
Appointment → Cuộc hẹn
Medical History → Tiền sử bệnh
Blood Group → Nhóm máu
Emergency Contact → Liên hệ khẩn cấp
Insurance → Bảo hiểm
Primary Facility → Cơ sở y tế chính
Registration Date → Ngày đăng ký
First Name → Tên
Last Name → Họ
Gender → Giới tính
Age → Tuổi
Male → Nam
Female → Nữ
Active → Đang hoạt động
Inactive → Không hoạt động
Save → Lưu
Cancel → Hủy
Create → Tạo mới
Edit → Chỉnh sửa
Delete → Xóa
```

---

## 🐛 Common Issues & Fixes

### Issue 1: "File not found: addons/health_crm/i18n/base.po"
**Response**:
```
❌ base.po not found for health_crm

User needs to:
1. Go to Odoo → Settings → Translations → Export Translation
2. Language: Vietnamese / Tiếng Việt
3. Format: PO File
4. Apps: Health CRM
5. Export and save as: addons/health_crm/i18n/base.po

Then I can translate it.
```

### Issue 2: HTML classes getting translated
**Fix automatically**:
```python
content = content.replace('class="Y tế-', 'class="health-')
content = content.replace('class="Lịch', 'class="fa fa-calendar')
content = content.replace('class="Dòng thời gian', 'class="fa fa-timeline')
```

### Issue 3: Low translation coverage (e.g., only 40%)
**Response**:
```
⚠️ Translation coverage is only X%

This means many terms aren't in dictionary yet.
Common missing terms can be added to translate_po_file.py

Would you like me to:
1. Show untranslated strings
2. Add common terms to dictionary
3. Continue anyway (user can translate manually in Odoo)
```

---

## 📊 Expected Results Per Module

| Module | Expected Strings | Expected Coverage |
|--------|-----------------|-------------------|
| health_base | 835 | 66% ✅ DONE |
| health_crm | ~200 | 60-70% |
| health_fieldservice | ~150 | 60-70% |
| health_invoicing | ~100 | 60-70% |
| health_pwa | ~80 | 50-60% |
| advanced_pricing | ~60 | 60-70% |
| health_landing | ~40 | 60-70% |
| health_theme | ~30 | 60-70% |

---

## 💬 Sample Conversations

### Good Response Example:
```
✅ Successfully translated health_crm module

Translation Statistics:
- File: addons/health_crm/i18n/vi_VN.po
- Translated: 134 out of 198 strings
- Coverage: 67.7%
- Backup: addons/health_crm/i18n/base.po.backup

Sample Translations:
msgid "Lead Source"
msgstr "Nguồn khách hàng"

msgid "Service Interest"
msgstr "Dịch vụ quan tâm"

msgid "Clinical Priority"
msgstr "Ưu tiên lâm sàng"

Next Steps:
1. Import to Odoo: Settings → Translations → Import Translation
2. Upload: addons/health_crm/i18n/vi_VN.po
3. Overwrite: ☑ Yes
4. Test: Switch user language to Vietnamese
```

### Bad Response Example (Don't do this):
```
❌ I translated the file.
```
^^ Too brief, no details, no verification

---

## 🎓 Learning Tips for Haiku

1. **Always run the script** - Don't try to translate manually
2. **Check the output** - Script shows progress and statistics
3. **Fix HTML issues** - Common problem, easy fix
4. **Show samples** - User wants to verify quality
5. **Be specific** - Exact file paths, exact statistics

---

## 📝 Complete Example Workflow

```bash
# User asks: "Translate health_fieldservice module"

# 1. Check file
ls -lh addons/health_fieldservice/i18n/base.po

# 2. Translate
python3 translate_po_file.py addons/health_fieldservice/i18n/base.po
# Output shows: "Translated 98 out of 145 strings (67.6% coverage)"

# 3. Fix HTML
python3 << 'EOF'
with open('addons/health_fieldservice/i18n/base.po', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('class="Y tế-', 'class="health-')
with open('addons/health_fieldservice/i18n/base.po', 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ Fixed HTML")
EOF

# 4. Rename
mv addons/health_fieldservice/i18n/base.po addons/health_fieldservice/i18n/vi_VN.po

# 5. Show samples
grep -A 1 "Field Service\|Assignment\|Booking" addons/health_fieldservice/i18n/vi_VN.po | head -15
```

**Report to user**:
```
✅ health_fieldservice module translated

Statistics:
- Translated: 98/145 strings (67.6%)
- File: addons/health_fieldservice/i18n/vi_VN.po
- Size: 42 KB

Sample translations:
msgid "Field Service Order"
msgstr "Đơn dịch vụ hiện trường"

msgid "Assignment"
msgstr "Phân công"

Next: Import this file to Odoo
```

---

## 🚀 Quick Commands Cheat Sheet

```bash
# List all modules needing translation
ls -d addons/health_*/ addons/advanced_pricing/

# Check if PO file exists
ls addons/<module>/i18n/base.po

# Translate
python3 translate_po_file.py addons/<module>/i18n/base.po

# Fix HTML
sed -i '' 's/class="Y tế-/class="health-/g' addons/<module>/i18n/base.po

# Rename
mv addons/<module>/i18n/base.po addons/<module>/i18n/vi_VN.po

# Verify
grep -c 'msgstr ""' addons/<module>/i18n/vi_VN.po  # Count untranslated

# Show samples
grep -A 1 "msgid" addons/<module>/i18n/vi_VN.po | head -20
```

---

## 🎯 Success Criteria

After translating all modules, verify:
- ✅ 10 vi_VN.po files created
- ✅ All files ~60-70% coverage
- ✅ No HTML class translation issues
- ✅ UTF-8 encoding preserved
- ✅ Backups created (.backup files)

---

## 📞 When to Ask User

1. **PO file not found** → User needs to export from Odoo
2. **Unknown module name** → Ask for clarification
3. **Very low coverage (<40%)** → Ask if they want to add terms
4. **Unusual errors** → Show error and ask for help

---

**Remember**: The script does the heavy lifting. Your job is to:
1. Run the script correctly
2. Fix HTML issues
3. Report results clearly
4. Guide user on next steps

**Good luck!** 🚀

---

**Last updated**: 2025-10-29
**Tested with**: health_base module (557/835 strings translated)
**Script version**: translate_po_file.py v1.0
