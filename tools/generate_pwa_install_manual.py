# -*- coding: utf-8 -*-
"""
Generate PWA Installation User Manual (Word Document)
Covers Android and iOS/iPadOS installation steps.
"""

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "..", "Viet_Uc_PWA_Installation_Guide.docx")

# Brand colors
BRAND_PURPLE = RGBColor(0x87, 0x5A, 0x7B)
BRAND_DARK = RGBColor(0x2D, 0x2D, 0x2D)
BRAND_GRAY = RGBColor(0x55, 0x55, 0x55)
BRAND_LIGHT_GRAY = RGBColor(0x99, 0x99, 0x99)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

APP_URL = "https://care.biztinct.com/health_pwa?install=1"
APP_NAME = "Viet Uc"
APP_FULL_NAME = "Viet Uc - Mobile Healthcare App"


def set_cell_shading(cell, color_hex):
    """Set cell background color."""
    from docx.oxml.ns import qn
    from lxml import etree
    shading = etree.SubElement(cell._tc.get_or_add_tcPr(), qn('w:shd'))
    shading.set(qn('w:fill'), color_hex)
    shading.set(qn('w:val'), 'clear')


def add_styled_heading(doc, text, level=1):
    """Add a heading with brand styling."""
    heading = doc.add_heading(text, level=level)
    for run in heading.runs:
        run.font.color.rgb = BRAND_PURPLE if level <= 2 else BRAND_DARK
    return heading


def add_step(doc, number, title, description, tip=None):
    """Add a numbered step with title and description."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)

    # Step number circle
    run_num = p.add_run(f"Step {number}: ")
    run_num.bold = True
    run_num.font.size = Pt(12)
    run_num.font.color.rgb = BRAND_PURPLE

    # Title
    run_title = p.add_run(title)
    run_title.bold = True
    run_title.font.size = Pt(12)
    run_title.font.color.rgb = BRAND_DARK

    # Description
    p_desc = doc.add_paragraph(description)
    p_desc.paragraph_format.left_indent = Cm(1)
    p_desc.paragraph_format.space_after = Pt(6)
    for run in p_desc.runs:
        run.font.size = Pt(11)
        run.font.color.rgb = BRAND_GRAY

    # Tip
    if tip:
        p_tip = doc.add_paragraph()
        p_tip.paragraph_format.left_indent = Cm(1)
        p_tip.paragraph_format.space_after = Pt(10)
        run_icon = p_tip.add_run("💡 Tip: ")
        run_icon.bold = True
        run_icon.font.size = Pt(10)
        run_icon.font.color.rgb = BRAND_PURPLE
        run_tip = p_tip.add_run(tip)
        run_tip.font.size = Pt(10)
        run_tip.font.color.rgb = BRAND_LIGHT_GRAY
        run_tip.italic = True

    # Placeholder for screenshot
    p_img = doc.add_paragraph()
    p_img.paragraph_format.left_indent = Cm(1)
    p_img.paragraph_format.space_after = Pt(12)
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_placeholder = p_img.add_run("[  Screenshot placeholder  ]")
    run_placeholder.font.size = Pt(10)
    run_placeholder.font.color.rgb = BRAND_LIGHT_GRAY
    run_placeholder.italic = True


def add_info_box(doc, title, content, is_warning=False):
    """Add a highlighted info/warning box using a table."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    bg_color = "FFF3CD" if is_warning else "E8DEF8"
    set_cell_shading(cell, bg_color)

    p = cell.paragraphs[0]
    icon = "⚠️" if is_warning else "ℹ️"
    run_title = p.add_run(f"{icon} {title}\n")
    run_title.bold = True
    run_title.font.size = Pt(11)
    run_title.font.color.rgb = BRAND_DARK

    run_content = p.add_run(content)
    run_content.font.size = Pt(10)
    run_content.font.color.rgb = BRAND_GRAY

    doc.add_paragraph()  # spacer


def build_document():
    doc = Document()

    # =========================================================================
    # Configure default styles
    # =========================================================================
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = BRAND_DARK

    for i in range(1, 4):
        hs = doc.styles[f'Heading {i}']
        hs.font.name = 'Calibri'
        hs.font.color.rgb = BRAND_PURPLE

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    for _ in range(4):
        doc.add_paragraph()

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_title.add_run(APP_FULL_NAME)
    run.font.size = Pt(28)
    run.bold = True
    run.font.color.rgb = BRAND_PURPLE

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_sub.add_run("Mobile App Installation Guide")
    run.font.size = Pt(18)
    run.font.color.rgb = BRAND_GRAY

    doc.add_paragraph()

    p_ver = doc.add_paragraph()
    p_ver.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_ver.add_run("Version 1.0  •  May 2026")
    run.font.size = Pt(12)
    run.font.color.rgb = BRAND_LIGHT_GRAY

    doc.add_paragraph()
    doc.add_paragraph()

    p_conf = doc.add_paragraph()
    p_conf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_conf.add_run("CONFIDENTIAL")
    run.font.size = Pt(10)
    run.bold = True
    run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)

    p_org = doc.add_paragraph()
    p_org.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_org.add_run("Viet Uc Allied Friendly Health Service")
    run.font.size = Pt(12)
    run.font.color.rgb = BRAND_GRAY

    doc.add_page_break()

    # =========================================================================
    # TABLE OF CONTENTS
    # =========================================================================
    add_styled_heading(doc, "Table of Contents", level=1)
    toc_items = [
        ("1.", "Introduction"),
        ("2.", "Requirements"),
        ("3.", "Installation on Android"),
        ("4.", "Installation on iPhone / iPad (iOS / iPadOS)"),
        ("5.", "Logging In"),
        ("6.", "Troubleshooting"),
        ("7.", "Uninstalling the App"),
    ]
    for num, title in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        run_num = p.add_run(f"{num}  ")
        run_num.font.size = Pt(12)
        run_num.font.color.rgb = BRAND_PURPLE
        run_num.bold = True
        run_title = p.add_run(title)
        run_title.font.size = Pt(12)
        run_title.font.color.rgb = BRAND_DARK

    doc.add_page_break()

    # =========================================================================
    # 1. INTRODUCTION
    # =========================================================================
    add_styled_heading(doc, "1. Introduction", level=1)

    doc.add_paragraph(
        f"The {APP_NAME} mobile application is a Progressive Web App (PWA) that allows "
        "healthcare staff to manage patient data, bookings, and field service orders "
        "directly from their mobile device — even when offline."
    )
    doc.add_paragraph(
        "Unlike traditional apps from the App Store or Google Play, a PWA is installed "
        "directly from your web browser. This means:"
    )

    benefits = [
        ("No App Store required", "Install instantly from your browser — no downloads from Google Play or Apple App Store."),
        ("Always up to date", "The app updates automatically. You always have the latest version."),
        ("Works offline", "Once installed, core features work without an internet connection. Data syncs when you're back online."),
        ("Lightweight", "The app uses minimal storage space on your device."),
        ("Secure", "All data is transmitted over HTTPS and protected by your login credentials."),
    ]

    for title, desc in benefits:
        p = doc.add_paragraph()
        run_b = p.add_run(f"✓  {title}: ")
        run_b.bold = True
        run_b.font.size = Pt(11)
        run_b.font.color.rgb = BRAND_PURPLE
        run_d = p.add_run(desc)
        run_d.font.size = Pt(11)
        run_d.font.color.rgb = BRAND_GRAY

    doc.add_paragraph()

    # =========================================================================
    # 2. REQUIREMENTS
    # =========================================================================
    add_styled_heading(doc, "2. Requirements", level=1)

    doc.add_paragraph("Before installing, please ensure you meet the following requirements:")
    doc.add_paragraph()

    # Requirements table
    table = doc.add_table(rows=5, cols=2)
    table.style = 'Light List Accent 1'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Requirement", "Details"]
    rows_data = [
        ("Android Device", "Android 8.0 or later with Google Chrome browser"),
        ("iPhone / iPad", "iOS 16.4 or later with Safari browser"),
        ("Internet Connection", "Required for initial installation and login. Offline mode available after."),
        ("Login Credentials", "Username and password provided by your administrator."),
    ]

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(11)

    for row_idx, (col1, col2) in enumerate(rows_data, start=1):
        table.rows[row_idx].cells[0].text = col1
        table.rows[row_idx].cells[1].text = col2
        for cell in table.rows[row_idx].cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)

    doc.add_paragraph()
    add_info_box(doc, "Important",
        "On iPhone and iPad, you MUST use Safari. Chrome and other browsers on iOS "
        "do not support PWA installation. On Android, Google Chrome is recommended.")

    doc.add_page_break()

    # =========================================================================
    # 3. ANDROID INSTALLATION
    # =========================================================================
    add_styled_heading(doc, "3. Installation on Android", level=1)

    doc.add_paragraph(
        "Follow these steps to install the Viet Uc app on your Android phone or tablet "
        "using Google Chrome."
    )
    doc.add_paragraph()

    add_styled_heading(doc, "3.1  Open Chrome and Navigate to the App", level=2)
    add_step(doc, 1, "Open Google Chrome",
        "Tap the Chrome icon on your Android device to open the browser. "
        "If Chrome is not installed, download it from the Google Play Store.",
        tip="Make sure you are using Google Chrome, not Samsung Internet or another browser.")

    add_step(doc, 2, "Enter the App URL",
        f"In the address bar at the top of Chrome, type the following URL and press Enter:\n\n"
        f"  {APP_URL}\n\n"
        "The Viet Uc app page will load in your browser.",
        tip="You can also scan the QR code provided by your administrator if available.")

    add_step(doc, 3, "Wait for the Install Prompt",
        "After the page loads, Chrome will display an automatic installation banner at the "
        "bottom of the screen that says \"Add Viet Uc to Home screen\" or similar. "
        "If you see this banner, tap \"Install\" or \"Add\".",
        tip="If the banner does not appear automatically, proceed to Step 4.")

    add_styled_heading(doc, "3.2  Manual Installation (if banner doesn't appear)", level=2)
    add_step(doc, 4, "Open Chrome Menu",
        "Tap the three-dot menu icon (⋮) in the top-right corner of Chrome.")

    add_step(doc, 5, 'Select "Add to Home Screen" or "Install App"',
        'In the menu that appears, look for "Add to Home screen" or "Install app". '
        "Tap on it.\n\n"
        "• On newer Chrome versions, this option may say \"Install app\"\n"
        "• On older versions, it will say \"Add to Home screen\"")

    add_step(doc, 6, "Confirm Installation",
        'A dialog box will appear asking you to confirm. You can edit the app name if you wish. '
        'Tap "Add" or "Install" to complete the installation.')

    add_step(doc, 7, "App Installed!",
        f"The {APP_NAME} app icon will now appear on your home screen, just like any other app. "
        "Tap it to open the app at any time.\n\n"
        "The app will open in its own window (without the browser address bar), "
        "giving you a full-screen app experience.")

    add_info_box(doc, "Success!",
        f"The {APP_NAME} app is now installed on your Android device. "
        "You can find it on your home screen and in your app drawer.")

    doc.add_page_break()

    # =========================================================================
    # 4. iOS INSTALLATION
    # =========================================================================
    add_styled_heading(doc, "4. Installation on iPhone / iPad", level=1)

    doc.add_paragraph(
        "Follow these steps to install the Viet Uc app on your iPhone or iPad. "
        "You must use Safari — this will not work with Chrome or other browsers on iOS."
    )
    doc.add_paragraph()

    add_info_box(doc, "Important — Safari Only",
        "On Apple devices (iPhone and iPad), PWA installation is ONLY supported in Safari. "
        "If you are using Chrome, Firefox, or any other browser, please switch to Safari now.",
        is_warning=True)

    add_styled_heading(doc, "4.1  Open Safari and Navigate to the App", level=2)
    add_step(doc, 1, "Open Safari",
        "Tap the Safari icon (the blue compass) on your iPhone or iPad to open the browser.\n\n"
        "Safari is pre-installed on all Apple devices. If you cannot find it, "
        "swipe down on your home screen and search for \"Safari\".",
        tip="Make sure you are using Safari, NOT Chrome or another browser.")

    add_step(doc, 2, "Enter the App URL",
        f"Tap the address bar at the top (or bottom on iPhone) of Safari and type:\n\n"
        f"  {APP_URL}\n\n"
        "Press Go on the keyboard. The Viet Uc app page will load.")

    add_styled_heading(doc, "4.2  Add to Home Screen", level=2)
    add_step(doc, 3, 'Tap the Share Button',
        "Once the page has loaded, tap the Share button:\n\n"
        "• On iPhone: Tap the Share icon (□↑) at the bottom center of the screen\n"
        "• On iPad: Tap the Share icon (□↑) at the top-right of the address bar\n\n"
        "The Share icon looks like a square with an upward arrow.",
        tip="If you don't see the bottom toolbar on iPhone, scroll up slightly to reveal it.")

    add_step(doc, 4, 'Scroll Down and Tap "Add to Home Screen"',
        "In the Share menu that appears, scroll down through the list of options. "
        'Look for "Add to Home Screen" (with a + icon) and tap on it.\n\n'
        "You may need to scroll down to find this option — it is usually below the list of apps.",
        tip='If you don\'t see "Add to Home Screen", make sure you are using Safari and not another browser.')

    add_step(doc, 5, "Confirm the App Name",
        f'A dialog will appear showing the app name "{APP_NAME}" and its icon. '
        "You can keep the default name or edit it.\n\n"
        'Tap "Add" in the top-right corner to confirm.')

    add_step(doc, 6, "App Installed!",
        f"The {APP_NAME} app icon will now appear on your home screen. "
        "Tap it to open the app — it will launch in full-screen mode, "
        "just like a native app.\n\n"
        "You can move the icon to any location on your home screen or "
        "add it to a folder, just like any other app.")

    add_info_box(doc, "Success!",
        f"The {APP_NAME} app is now installed on your iPhone/iPad. "
        "You can find it on your home screen alongside your other apps.")

    doc.add_page_break()

    # =========================================================================
    # 5. LOGGING IN
    # =========================================================================
    add_styled_heading(doc, "5. Logging In", level=1)

    doc.add_paragraph(
        "After installing the app, follow these steps to log in:"
    )
    doc.add_paragraph()

    add_step(doc, 1, "Open the App",
        f"Tap the {APP_NAME} icon on your home screen to open the app.")

    add_step(doc, 2, "Enter Your Credentials",
        "On the login screen, enter:\n\n"
        "• Username: Your work email or username (provided by your administrator)\n"
        "• Password: Your password\n\n"
        "Then tap the \"Log In\" button.")

    add_step(doc, 3, "Allow Notifications (Optional)",
        "The app may ask permission to send notifications. "
        "Tap \"Allow\" to receive updates about bookings and patient assignments. "
        "You can change this later in your device settings.")

    add_step(doc, 4, "Start Using the App",
        "After successful login, you will see the main dashboard. "
        "From here you can:\n\n"
        "• View and manage your patient list\n"
        "• Check your field service bookings\n"
        "• Record visit notes and observations\n"
        "• Sync data when you're back online")

    add_info_box(doc, "Forgot Your Password?",
        "Contact your system administrator to reset your password. "
        "Do not share your login credentials with others.")

    doc.add_page_break()

    # =========================================================================
    # 6. TROUBLESHOOTING
    # =========================================================================
    add_styled_heading(doc, "6. Troubleshooting", level=1)

    doc.add_paragraph("If you encounter issues during installation, try the following solutions:")
    doc.add_paragraph()

    issues = [
        (
            '"Add to Home Screen" option is missing',
            "Android: Make sure you are using Google Chrome (not Samsung Internet or other browsers).\n"
            "iPhone/iPad: You MUST use Safari. This option is not available in Chrome on iOS.\n"
            "Also ensure you have visited the correct URL: " + APP_URL
        ),
        (
            "The app does not load or shows a blank screen",
            "1. Check your internet connection — WiFi or mobile data must be active for the first install.\n"
            "2. Clear your browser cache: Settings → Chrome/Safari → Clear Browsing Data.\n"
            "3. Try closing and reopening the browser.\n"
            "4. If the problem persists, restart your device and try again."
        ),
        (
            "The app icon disappeared from my home screen",
            "Simply repeat the installation steps above. Navigate to the URL in your browser and "
            "add it to your home screen again."
        ),
        (
            "The app is not updating / showing old data",
            "1. Open the app and pull down to refresh.\n"
            "2. If that doesn't work, clear the app by removing it from your home screen "
            "and reinstalling from the URL.\n"
            "3. Make sure you have an active internet connection for syncing."
        ),
        (
            "Login fails — incorrect username or password",
            "1. Double-check your credentials (username and password are case-sensitive).\n"
            "2. Ensure you're using the correct login provided by your administrator.\n"
            "3. Contact your administrator to verify your account is active."
        ),
        (
            "The install banner does not appear on Android",
            "This can happen if:\n"
            "• You've previously dismissed the banner (it won't appear again for a while)\n"
            "• You're using an incognito/private browsing window\n"
            "Solution: Use the manual method — tap the ⋮ menu → \"Add to Home screen\" or \"Install app\"."
        ),
    ]

    for title, solution in issues:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        run = p.add_run(f"❓ {title}")
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = BRAND_DARK

        p_sol = doc.add_paragraph()
        p_sol.paragraph_format.left_indent = Cm(0.5)
        p_sol.paragraph_format.space_after = Pt(12)
        run = p_sol.add_run(solution)
        run.font.size = Pt(10)
        run.font.color.rgb = BRAND_GRAY

    doc.add_page_break()

    # =========================================================================
    # 7. UNINSTALLING
    # =========================================================================
    add_styled_heading(doc, "7. Uninstalling the App", level=1)

    doc.add_paragraph("If you need to remove the app from your device:")
    doc.add_paragraph()

    add_styled_heading(doc, "Android", level=2)
    doc.add_paragraph(
        "1. Long-press the Viet Uc app icon on your home screen.\n"
        "2. Drag it to \"Remove\" or \"Uninstall\" at the top of the screen.\n"
        "3. Alternatively: Go to Settings → Apps → Viet Uc → Uninstall."
    )

    add_styled_heading(doc, "iPhone / iPad", level=2)
    doc.add_paragraph(
        "1. Long-press the Viet Uc app icon on your home screen.\n"
        "2. Tap \"Remove App\" or \"Delete Bookmark\".\n"
        "3. Confirm by tapping \"Delete\"."
    )

    doc.add_paragraph()
    add_info_box(doc, "Note",
        "Uninstalling the app does not delete your account or data on the server. "
        "You can reinstall at any time by following the installation steps again.")

    # =========================================================================
    # FOOTER — Support Contact
    # =========================================================================
    doc.add_paragraph()
    doc.add_paragraph()

    p_support = doc.add_paragraph()
    p_support.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_support.paragraph_format.space_before = Pt(20)
    run = p_support.add_run("— Need Help? —")
    run.font.size = Pt(14)
    run.bold = True
    run.font.color.rgb = BRAND_PURPLE

    p_contact = doc.add_paragraph()
    p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_contact.add_run(
        "Contact your system administrator or IT support team for assistance.\n"
        "Please have your device model, OS version, and browser version ready when reporting issues."
    )
    run.font.size = Pt(10)
    run.font.color.rgb = BRAND_GRAY

    # =========================================================================
    # Save
    # =========================================================================
    doc.save(OUTPUT_FILE)
    print(f"✓ Document saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_document()
