# Viet UC CMS — User Manual

The end-user manual for the Viet UC CMS platform: a menu-by-menu, workflow-driven
guide covering every left-sidebar item (CRM, Operations Manager, Finance, Admin)
plus the mobile Nurse App, with screenshots.

## Deliverables

- **`VietUC_CMS_User_Manual.pdf`** — the shareable manual (64 pages, populated TOC).
- **`VietUC_CMS_User_Manual.docx`** — the editable source (client edits this).

## Sources

- `content/*.md` — chapter prose (one file per chapter), the editable text source.
- `img/*.png` — screenshots; `img/manifest.json` maps each file → section + caption.
- `build_manual.py` — python-docx assembler (cover, TOC field, headings, callout
  boxes, button tables, embedded screenshots) → builds the `.docx`.
- `seed_demo.py` — seeds clean sample data on UAT for polished screenshots
  (run via `odoo-bin shell -d vietuat --no-http < seed_demo.py`).

## Rebuilding

1. Edit `content/*.md` (or re-capture screenshots into `img/`).
2. Build the Word document:

   ```sh
   python3 build_manual.py
   ```

3. Export the PDF **with the Table of Contents populated**. The plain
   `soffice --convert-to pdf` does *not* refresh the TOC field, so run the
   bundled `UpdateToc` Basic macro instead (it loads the doc, updates the TOC,
   and exports the PDF):

   ```sh
   soffice --headless --invisible --norestore \
     "vnd.sun.star.script:Standard.Module1.UpdateToc?language=Basic&location=application"
   ```

   (`export_pdf.py` does the same via python-UNO where that interpreter is
   available.)

Opening the `.docx` in Word and pressing Ctrl+A → F9 also refreshes the TOC.
