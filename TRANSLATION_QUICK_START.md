# 🇻🇳 Vietnamese Translation - Quick Start Guide

## ✅ Setup Complete!

- [x] Vietnamese language is installed in Odoo
- [x] i18n directories created for all 10 modules
- [x] Ready to export and translate

---

## 📋 Your Next Steps (Do These Now!)

### STEP 1: Export Translations from Odoo ⏱️ 15 minutes

1. Open Odoo → Settings → Translations → **Export Translation**
2. For **each module** below, do this:
   - Language: `Vietnamese / Tiếng Việt`
   - Format: `PO File`
   - Apps to export: Click "Search More" → Select the module
   - Click `Export` → Save the file

**Export these 10 modules:**

| # | Module to Export | Save Downloaded File As |
|---|-----------------|------------------------|
| 1 | Health Base | `health_base_vi_VN.po` |
| 2 | Health CRM | `health_crm_vi_VN.po` |
| 3 | Health Field Service | `health_fieldservice_vi_VN.po` |
| 4 | Health Invoicing | `health_invoicing_vi_VN.po` |
| 5 | Health Landing | `health_landing_vi_VN.po` |
| 6 | Health PWA | `health_pwa_vi_VN.po` |
| 7 | Health Theme | `health_theme_vi_VN.po` |
| 8 | Advanced Pricing | `advanced_pricing_vi_VN.po` |
| 9 | Base User Role | `base_user_role_vi_VN.po` |
| 10 | Web Timeline | `web_timeline_vi_VN.po` |

**After exporting, you'll have 10 `.po` files in your Downloads folder.**

---

### STEP 2: Translate the .po Files ⏱️ 20-30 hours

**Option A: Use Poedit (Recommended)**
1. Download FREE Poedit: https://poedit.net/
2. Open each `.po` file in Poedit
3. Fill in Vietnamese translations in the `msgstr` fields
4. Save

**Option B: Send to Professional Translator**
- Send all 10 files to a Vietnamese medical translator
- Estimated cost: ~$500-800 USD (depends on word count)
- Turnaround: 3-5 days

**Translation Format Example:**
```po
msgid "Is Patient"
msgstr "Là Bệnh nhân"

msgid "Blood Group"
msgstr "Nhóm Máu"

msgid "Emergency Contact"
msgstr "Người Liên hệ Khẩn cấp"
```

---

### STEP 3: Copy Translated Files to Module Folders ⏱️ 2 minutes

After translation, copy the `.po` files to the correct locations:

```bash
# Copy from Downloads to module i18n folders
cp ~/Downloads/health_base_vi_VN.po addons/health_base/i18n/vi_VN.po
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

### STEP 4: Import Translations into Odoo ⏱️ 10 minutes

**Option A: Import via UI (Do this for each .po file)**
1. Odoo → Settings → Translations → **Import Translation**
2. Language: `Vietnamese / Tiếng Việt`
3. File: Upload your translated `.po` file
4. Overwrite: ☑ **Check this box!**
5. Click `Import`
6. Repeat for all 10 files

**Option B: Upgrade Modules**
1. Go to **Apps** menu
2. Remove "Apps" filter
3. Search for "Health Base"
4. Click **⚙ Upgrade**
5. Repeat for each health module

---

### STEP 5: Test Vietnamese Interface ⏱️ 5 minutes

1. **Switch Language**:
   - Click your name (top-right) → Preferences
   - Language: `Vietnamese / Tiếng Việt`
   - Save

2. **Reload Browser**: Press `Ctrl+Shift+R` (hard refresh)

3. **Check These**:
   - ✓ Health menu items in Vietnamese?
   - ✓ Patient form labels in Vietnamese?
   - ✓ Button labels in Vietnamese?
   - ✓ Error messages in Vietnamese?

**If some strings are still English**:
- Go to Settings → Translations → Translated Terms
- Filter: Module = "Health Base", Untranslated = ☑
- Translate missing terms directly in UI

---

## 📊 Translation Progress Tracker

Use this checklist as you work:

- [ ] STEP 1: Exported all 10 .po files from Odoo
- [ ] STEP 2: Translated all .po files to Vietnamese
- [ ] STEP 3: Copied files to module i18n folders
- [ ] STEP 4: Imported translations into Odoo
- [ ] STEP 5: Tested Vietnamese interface
- [ ] STEP 6: Fixed any untranslated strings
- [ ] ✅ DONE: Vietnamese language fully working!

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't find module to export | Remove "Apps" filter in Export screen |
| Translations don't show | Hard refresh browser (`Ctrl+Shift+R`) |
| Some strings still English | Import again with "Overwrite" checked |
| Import fails | Check .po file encoding is UTF-8 |
| Need to fix one translation | Settings → Translations → Translated Terms |

---

## 📚 Full Documentation

For detailed instructions, medical terminology guide, and troubleshooting:
👉 **See: `VIETNAMESE_TRANSLATION_GUIDE.md`**

---

## 💡 Pro Tips

1. **Start with Health Base** - It's the foundation module with most core terms
2. **Use Poedit's Translation Memory** - It remembers similar translations
3. **Keep it Consistent** - Use the same term for "Patient" throughout (e.g., always "Bệnh nhân")
4. **Test Incrementally** - Import and test one module at a time
5. **Save Original Files** - Keep backups of your translated .po files

---

## 🎯 Success Metrics

Your translation is successful when:
- ✅ User switches to Vietnamese → entire UI is in Vietnamese
- ✅ 90%+ of strings translated (some technical terms OK to keep in English)
- ✅ Medical terminology is accurate and consistent
- ✅ Forms, buttons, menus all display Vietnamese
- ✅ Mobile PWA also shows Vietnamese

---

**Estimated Total Time: ~30-40 hours** (mostly translation work in Step 2)

**Ready? Start with STEP 1 above! 🚀**

Chúc bạn thành công! (Good luck!)
