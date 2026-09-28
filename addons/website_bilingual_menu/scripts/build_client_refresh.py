"""Build the September 2026 client content from the original supplied artefacts.

Run locally with Python 3 and Poppler. Outputs are reproducible, reviewed inputs
for apply_client_refresh.py, never an automatic overwrite on module upgrade.
"""
from pathlib import Path
import hashlib
import html
import json
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

MODULE = Path(__file__).resolve().parents[1]
SOURCE = MODULE.parents[1] / "Taupo Website"
OUT = MODULE / "static/client_2026"
OUT.mkdir(parents=True, exist_ok=True)
NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
DECK = zipfile.ZipFile(SOURCE / "THHS mockup website Deb 010926.pptx")
assets = {}
pages = []


def esc(value):
    return html.escape(str(value), quote=True)


def asset(path, name=None):
    path = Path(path)
    name = name or re.sub(r"[^a-z0-9.-]+", "-", path.name.lower()).strip("-")
    dest = OUT / name
    shutil.copyfile(path, dest)
    assets[name] = {"file": name, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}
    return f"@@ASSET:{name}@@"


def embedded(number, label):
    source = next(n for n in DECK.namelist() if re.match(fr"ppt/media/image{number}\.[^.]+$", n))
    name = label + Path(source).suffix
    data = DECK.read(source)
    (OUT / name).write_bytes(data)
    assets[name] = {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
    return f"@@ASSET:{name}@@"


def paragraphs(slide):
    root = ET.fromstring(DECK.read(f"ppt/slides/slide{slide}.xml"))
    return ["".join(t.text or "" for t in p.findall(".//a:t", NS)).strip()
            for p in root.findall(".//a:p", NS)
            if "".join(t.text or "" for t in p.findall(".//a:t", NS)).strip()]


def image(src, alt, cls="", style=""):
    return f'<img src="{src}" alt="{esc(alt)}" class="img img-fluid {cls}" style="{style}" loading="lazy"/>'


def section(content, cls="", snippet="s_text_block", padding="pt32 pb32"):
    return f'<section class="{snippet} o_colored_level {cls} {padding}" data-snippet="{snippet}" data-name="Taupō {esc(cls.replace("thhs26-", ""))}"><div class="container">{content}</div></section>'


def watermark_section(content, background, cls):
    return f'''<section class="s_text_block o_colored_level oe_img_bg o_bg_img_center thhs26-watermark-section {cls} pt32 pb32" data-snippet="s_text_block" data-name="Editable illustrated content" style="background-image:url('{background}');"><div class="o_we_bg_filter" style="background-color:rgba(255,255,255,0.8);"/><div class="container thhs26-copy">{content}</div></section>'''


lake = embedded(4, "lake-title")
welcome = asset(SOURCE / "Photos/Deb Focus maunga (2).jpeg", "welcome-lake.jpeg")
old_hospital = asset(SOURCE / "Photos/Taupo Hospital old.jpg", "hospital-history.jpg")
vision_img = asset(SOURCE / "Photos/vision image.jpg", "vision.jpg")
purpose_img = embedded(7, "purpose")


def title(en, mi):
    return f'''<section class="s_title thhs26-title o_colored_level oe_img_bg o_bg_img_center pt24 pb24" data-vcss="001" data-snippet="s_title" data-name="Lake page title" style="background-image:url('{lake}');"><div class="container s_allow_columns"><h1>{esc(en)}<span class="thhs26-maori"> / {esc(mi)}</span></h1></div></section>'''


def add(url, name, content):
    pages.append({"url": url, "name": name, "content": content})


add("/", "Home", f'''<section class="s_cover thhs26-welcome o_colored_level pt0 pb0" data-snippet="s_cover" data-name="Welcome lake photograph"><div class="thhs26-welcome-frame">{image(welcome, 'Lake Taupō and the maunga', 'thhs26-welcome-photo')}<div class="thhs26-welcome-copy"><h1>Welcome</h1><h2>Nau mai haere mai</h2><p><strong>Taupō Hospital &amp; Health Society<br/>Supporting the Taupō–Tūrangi &amp; Mangakino region by strengthening and supporting our local hospital and the health services it provides to our community.</strong></p><p><a href="/contactus" class="btn btn-primary thhs26-button">Get in Touch</a></p></div></div></section>''')

history = paragraphs(4)[1:] + paragraphs(5)[2:]
history_html = ''
for p in history:
    if p in ["OUR HISTORY", "OUR HISTORY…"]:
        history_html += '<h2 class="thhs26-label">OUR HISTORY</h2>' if not history_html else ''
    elif p in ['Community beginnings', 'Community leadership', 'Fundraising and community support', 'Our district and ongoing partnership']:
        history_html += f'<h3>{esc(p)}</h3>'
    else:
        history_html += f'<p>{esc(p)}</p>'
add('/background', 'History', title('Background', 'Horopaki') + watermark_section(history_html, old_hospital, 'thhs26-history'))
vision = next(p for p in paragraphs(7) if 'Society is committed' in p).strip('“”  "')
add('/our-vision', 'Mission/Vision', title('Our Vision', 'Tō mātou tirohanga') + watermark_section(f'<h2 class="thhs26-label">MISSION/VISION</h2><p>{esc(vision)}</p>', vision_img, 'thhs26-vision'))
purpose = paragraphs(9)
items = [p for p in purpose if p.startswith(('Support the continuation', 'Promote initiatives', 'Use the Society', 'Support the advancement', 'Work collaboratively'))]
add('/what-we-do', 'What we do', title('What we do?', 'Ā mātou mahi') + watermark_section('<h2 class="thhs26-label">PURPOSE</h2><p>The <strong>Taupō Hospital &amp; Health Society</strong> is established and operated exclusively for charitable purposes. Our objectives are to:</p><ul>'+''.join(f'<li>{esc(p)}</li>' for p in items)+'</ul>', purpose_img, 'thhs26-purpose'))


def profile(slide, filename):
    root = ET.fromstring(DECK.read(f'ppt/slides/slide{slide}.xml'))
    candidates = []
    for shape in root.findall('.//p:sp', NS):
        ps = [''.join(t.text or '' for t in p.findall('.//a:t', NS)).strip() for p in shape.findall('.//a:p', NS)]
        candidates.append([p for p in ps if p])
    ps = max(candidates, key=lambda p: sum(map(len, p)))
    name, role, *body = ps
    if slide == 20:
        name = 'LAURIE BURDETT QSM'
    photo = asset(SOURCE / filename)
    copy = ''.join(f'<p class="{"thhs26-skills" if p.startswith("Key Skills") else ""}">{esc(p)}</p>' for p in body)
    return name, f'<div class="row g-4"><div class="col-md-2 o_colored_level">{image(photo,name,"thhs26-profile-photo")}</div><div class="col-md-10 o_colored_level"><h2>{esc(name)}</h2><p class="thhs26-role">{esc(role)}</p>{copy}</div></div>'


def carousel(profiles, identifier):
    slides = ''.join(f'<div class="carousel-item {"active" if i == 0 else ""} pt24 pb64 o_colored_level" data-name="{esc(name)}"><div class="container oe_unremovable"><div class="carousel-content">{content}</div></div></div>' for i,(name,content) in enumerate(profiles))
    indicators = ''.join(f'<button type="button" data-bs-target="#{identifier}" data-bs-slide-to="{i}" class="{"active" if i == 0 else ""}" aria-label="{esc(name)}" title="{esc(name)}"/>' for i,(name,_) in enumerate(profiles))
    return f'''<section class="s_carousel_wrapper thhs26-profiles p-0" data-snippet="s_carousel" data-name="Editable board profiles" data-vxml="001" data-vcss="001"><div id="{identifier}" class="s_carousel s_carousel_default carousel slide" data-bs-interval="false"><div class="carousel-inner">{slides}</div><button class="carousel-control-prev o_not_editable" contenteditable="false" data-bs-target="#{identifier}" data-bs-slide="prev" aria-label="Previous profile"><span class="carousel-control-prev-icon" aria-hidden="true"/><span class="visually-hidden">Previous</span></button><button class="carousel-control-next o_not_editable" contenteditable="false" data-bs-target="#{identifier}" data-bs-slide="next" aria-label="Next profile"><span class="carousel-control-next-icon" aria-hidden="true"/><span class="visually-hidden">Next</span></button><div class="carousel-indicators o_not_editable">{indicators}</div></div></section>'''


board = [(11,'Lil2.jpeg'),(13,'Gilma2.jpeg'),(14,'Deb.jpeg'),(15,'trent2.jpeg'),(16,'mark2.jpeg'),(17,'Sandra & David.jpeg'),(18,'John2.jpeg'),(19,'Aruna2.jpeg')]
add('/our-board','Our Board',title('Our Board','Mana whakahaere')+carousel([profile(n,'Board/Board photos/'+f) for n,f in board],'thhsBoard'))
add('/our-patrons','Our Patrons',title('Our Patrons','Kaitautoko')+carousel([profile(20,'Board/Board photos/Laurie3.jpeg'),profile(21,'Board/Les winslade.png')],'thhsPatrons'))
add('/associate-members','Associate members',title('Associate members','Mema hono')+carousel([profile(22,'Board/Board photos/Kathryn3.jpeg'),profile(23,'Board/Board photos/RhondaF.png')],'thhsAssociates'))

rules_image = asset(SOURCE/'Icons/Incorporated image1.png')
rules_icon = asset(SOURCE/'Icons/Rules icon.png')
add('/incorporated-society','Incorporated Society',title('Rules','Ngā ture')+section(f'<div class="row align-items-center g-5"><div class="col-md-8 o_colored_level">{image(rules_image,"Community working together","thhs26-incorporated")}</div><div class="col-md-4 text-center o_colored_level"><h2 class="thhs26-label">INCORPORATED SOCIETY</h2><p><a href="@@CONSTITUTION@@" aria-label="Read the Society constitution">{image(rules_icon,"Read the Society constitution","thhs26-rule-icon")}</a></p></div></div>',snippet='s_image_text'))

news_specs = [
 ('NODA-News-Update.pdf','2026-09-04','No One Dies Alone Taupō marks its first year','News update'),
 ('Flu-Season-Healthcare-Options-Media-News-19-August-2026.pdf','2026-08-19','Surge in flu season sickness a reminder of alternative healthcare options for non-urgent cases','Media news'),
 ('Lucy-Harrison-News-Update-6-August-2026.pdf','2026-08-06','Lactation consultants make a big difference for first-time mothers','News – Lucy Harrison'),
 ('GM-Taupo-News-Update-24-July-2026.pdf','2026-07-24','Ten months on in Taupō','News update'),
 ('PGY1-Rural-Medicine-News-Update-24-July-2026.pdf','2026-07-24','Taupō experience leads PGY1 to rural medicine','News update'),
 ('Co-Response-Teams-Media-News-30-June-2026.pdf','2026-06-30','Six new Co-Response Team locations announced to strengthen support for people in mental distress','Media news'),
 ('Rural-Medical-Programme-Expands-to-Taupo-2027.pdf','2026-06-24','Rural medical programme expands to Taupō in 2027','News update'),
 ('Resident-Doctors-Day-Felicity-Williams-23-June-2026.pdf','2026-06-23',"Resident Doctors’ Day 2026: Felicity Williams – Taupō",'News update'),
 ('Taupo-Doctor-Returns-News-Update-22-April-2026.pdf','2026-04-22','Taupō doctor returns home as a specialist','News update'),
]
from datetime import date
news_sections=''
for filename, day, headline, category in news_specs:
    link = asset(SOURCE/'Hospital News updates/Hospital News updates/Latest News'/filename)
    date_label = date.fromisoformat(day).strftime('%-d %B %Y')
    news_card = f'<div class="thhs26-news-item"><div class="thhs26-news-meta"><span>{esc(category)}</span><time datetime="{day}">{date_label}</time></div><h3>{esc(headline)}</h3><p class="text-end"><a class="thhs26-read-more" href="{link}" target="_blank" rel="noopener" aria-label="Read {esc(headline)}">READ MORE</a></p></div>'
    label='<h2 class="thhs26-label">LATEST NEWS</h2>' if not news_sections else ''
    news_sections += section(f'<div class="row g-4"><div class="col-md-2 o_colored_level">{label}</div><div class="col-md-10 o_colored_level">{news_card}</div></div>','thhs26-news',padding='pt16 pb0')
add('/news','Latest News',title('News','Ngā Kārere')+news_sections)
add('/archive-news','Archived News',title('News','Ngā Kārere')+section('<div class="row"><div class="col-md-2 o_colored_level"><h2 class="thhs26-label">ARCHIVED NEWS</h2></div><div class="col-md-10 o_colored_level"><p>There are no archived news items yet.</p><p><a href="/news">Read the latest news</a></p></div></div>','thhs26-news'))

reports=''
for year in range(2019,2027):
    icon = asset(SOURCE/f'Annual reports/{year}.png')
    pdf = SOURCE/f'Annual reports/THHS AGM booklet {year}.pdf'
    item=image(icon,f'{year} Annual Report')
    if pdf.exists():
        item=f'<a href="{asset(pdf)}" target="_blank" rel="noopener" aria-label="Open {year} Annual Report">{item}</a>'
    else:
        item += '<span class="small d-block">Report not yet available</span>'
    reports += f'<div class="col-4 col-md o_colored_level">{item}</div>'
annual_illustration=embedded(31,'annual-reports-illustration')
add('/annual-report','Annual Reports',title('News','Ngā Kārere')+section('<h2 class="thhs26-label text-center">ANNUAL REPORTS</h2><div class="row align-items-center g-4"><div class="col-lg-9"><div class="row g-3 align-items-end">'+reports+f'</div></div><div class="col-lg-3">{image(annual_illustration,"Annual reports and accountability")}</div></div>','thhs26-reports'))
facebook=embedded(32,'facebook')
add('/social-media','Social Media',title('News','Ngā Kārere')+section(f'<h2 class="thhs26-label text-center">SOCIAL MEDIA</h2><p class="text-center"><a href="@@FACEBOOK@@" target="_blank" rel="noopener" aria-label="Visit our Facebook page">{image(facebook,"Facebook","thhs26-social-icon")}</a></p>','thhs26-social'))

success = paragraphs(33)
table='<div class="table-responsive"><table class="table thhs26-grants"><thead><tr><th>YEAR</th><th>TOTAL</th><th>EXAMPLES OF GRANTS AND PURCHASES</th></tr></thead><tbody>'
values=success[5:]
for i in range(0,len(values),3):
    row=values[i:i+3]
    if len(row)!=3: raise ValueError(row)
    if row[0]=='Year not shown': row[0]='2018'  # Year supplied in the companion Word document.
    table+='<tr>'+''.join(f'<td>{esc(x)}</td>' for x in row)+'</tr>'
table+='</tbody></table></div>'
thermometer=embedded(34,'grants-thermometer')
cheque=asset(SOURCE/'Photos/Cheque handover (1).jpg','cheque-handover.jpg')
add('/successes','Successes',section('<h1 class="text-center">SUCCESSES</h1><p class="text-center thhs26-label">Selected grants and purchases supported since 1993<br/>Latest recorded cumulative value: $2,074,136</p><div class="row g-4"><div class="col-md-2">'+image(thermometer,'Cumulative value of grants: $2,074,136','thhs26-thermometer')+'</div><div class="col-md-10">'+table+'</div></div>','thhs26-successes')+section('<h2 class="text-center">SUCCESSES</h2>'+image(cheque,'Community cheque presentation for the cardiac heart scanner','d-block mx-auto thhs26-cheque'),'thhs26-success-photo',snippet='s_picture'))

testimonials = [
 (37,'Testimonial - Echocardiogram.pdf','Echocardiogram'),
 (38,'Thanking-Our-Hospital-Staff-Testimonial.pdf','Hospital Staff'),
 (40,'RISC-Trauma-Course-Testimonial.pdf','RISC Trauma'),
 (41,'Paediatric-Murals-Testimonial.pdf','Paediatric Room Murals'),
 (42,'CT-Scanner-Closer-to-Home-Testimonial.pdf','CT Scanning'),
 (43,'Chemo-Chairs-Testimonial.pdf','Chemo Chairs'),
 (44,'Cancer-Care-Closer-to-Home-Testimonial.pdf','Cancer Care'),
 (39,'Testimonial - AccuVein 500.pdf','AccuVein 500'),
]
testimonial_header=asset(SOURCE/'Photos/chque image.png','testimonial-cheque.png')
stories=''
for number,filename,label in testimonials:
    thumb=embedded(number,'testimonial-'+str(number))
    link=asset(SOURCE/'Projects'/filename)
    stories+=f'<div class="col-6 col-md-3 col-xl o_colored_level"><a href="{link}" target="_blank" rel="noopener" aria-label="Read {esc(label)} testimonial">{image(thumb,label)}</a></div>'
add('/projects','Testimonials',title('Our Projects','Ā mātou kaupapa')+section(f'<div class="thhs26-testimonial-head">{image(testimonial_header,"Community support for cardiac care")}<h2>TESTIMONIALS</h2></div><div class="row g-3">{stories}</div>','thhs26-testimonials',snippet='s_three_columns'))

calendar_icon=asset(SOURCE/'Icons/Calendar icon.png')
dates=[('November 2026','18','NOV','Annual General Meeting (AGM)','Taupō Hospital & Health Society'),('','18','NOV','Next Society Meeting','Scheduled meeting date'),('December 2026','31','DEC','Charities Commission Filing','Annual accounts filing deadline'),('December 2028','31','DEC','Charities Three-Year Review','Three-year review due date')]
calendar='<h2 class="thhs26-label">Taupō Hospital &amp; Health Society</h2><p>Key Dates Calendar</p>'
for month,day,short,label,description in dates:
    if month: calendar+=f'<h3>{month}</h3>'
    calendar+=f'<div class="thhs26-date"><div><strong>{day}</strong><span>{short}</span></div><div><h4>{esc(label)}</h4><p>{esc(description)}</p></div></div>'
add('/calendar','Key Calendar Dates',title('Events','Takahanga')+section(f'<div class="row align-items-center g-5"><div class="col-md-9 o_colored_level">{calendar}</div><div class="col-md-3 text-center o_colored_level"><h2 class="thhs26-label">KEY CALENDAR DATES</h2>{image(calendar_icon,"Calendar")}</div></div>','thhs26-calendar'))

membership=asset(SOURCE/'Word documents/THHS Membership and donation form Draft.pdf','membership-and-donation-form.pdf')
support=''
for filename,label,link in [('Become a member.png','Become a member',membership),('donate.png','Donate',membership),('Givealittle icon.png','Givealittle','@@GIVEALITTLE@@'),('Philanthrophy.png','Philanthropy','/contactus'),('Volunteer.png','Volunteer','/contactus')]:
    icon=asset(SOURCE/'Photos'/filename)
    support+=f'<div class="col-6 col-md-4 o_colored_level"><a href="{link}" aria-label="{label}">{image(icon,label)}</a></div>'
support+='<div class="col-6 col-md-4 o_colored_level"><a href="/contactus" class="btn btn-primary thhs26-button">Contact Us</a></div>'
add('/how-can-i-help','Get Involved',title('Get Involved','Whai wāhi mai')+section('<h2 class="thhs26-label">HOW CAN YOU SUPPORT US – CLICK ON THE RELEVANT ICON</h2><div class="row g-5 align-items-center text-center">'+support+'</div>','thhs26-support',snippet='s_three_columns'))

contact='''<div class="thhs26-contact-heading text-center"><p class="thhs26-label">TAUPŌ HOSPITAL &amp; HEALTH SOCIETY</p><h1>Contact the Society</h1><p>We welcome enquiries from members of our community, organisations and supporters.</p></div><div class="thhs26-contact-intro"><h2>How to contact us</h2><p>Email the Society or speak directly with our Chairperson or Secretary.</p></div><div class="row g-2 thhs26-contact-details"><div class="col-lg-4 o_colored_level"><p><strong>EMAIL</strong> <a href="mailto:admin@thhs.org.nz">admin@thhs.org.nz</a></p></div><div class="col-lg-4 o_colored_level"><p><strong>CHAIR</strong> <a href="tel:+64273030642">027 303 0642</a></p></div><div class="col-lg-4 o_colored_level"><p><strong>SECRETARY</strong> <a href="tel:+64273374804">027 337 4804</a></p></div></div><h2 class="text-center">Tell us why you are contacting the Society</h2><p class="text-center">Please state the reason in your email subject line or at the beginning of your message.</p><div class="row g-3 thhs26-contact-reasons">'''
for label,copy in [('Donation','Make a donation or discuss supporting the Society.'),('Funding request','Ask about funding or submit a request for support.'),('General enquiry','Ask about the Society, its work or getting involved.'),('Philanthropy','Discuss supporting the Society.')]:
    contact+=f'<div class="col-md-3 o_colored_level"><div><h3><a href="mailto:admin@thhs.org.nz?subject={esc(label)}">{label}</a></h3><p>{copy}</p></div></div>'
contact+='''</div><div class="row g-4 mt-2"><div class="col-md-9 o_colored_level"><h2>Please include</h2><div class="row"><div class="col-md-6"><ul><li>Your full name and preferred contact details</li><li>A brief summary of your enquiry or request</li></ul></div><div class="col-md-6"><ul><li>The reason for your email or call</li><li>Any relevant organisation or supporting information</li></ul></div></div></div><div class="col-md-3 o_colored_level text-center"><a class="btn btn-primary thhs26-button" href="mailto:admin@thhs.org.nz">Contact us</a></div></div>'''
add('/contactus','Contact Us',section(contact,'thhs26-contact'))
hospital_photo=asset(SOURCE/'Photos/Taupo Hospital now.jpg','hospital-now.jpg')
hospital_logo=asset(SOURCE/'Photos/Taupo Hospital icon.png','hospital-icon.png')
add('/our-hospital','Our Hospital',title('Our Hospital','Ā mātou Hōhipera')+section(f'<div class="row g-5 align-items-center"><div class="col-md-6 o_colored_level">{image(hospital_logo,"Health New Zealand | Te Whatu Ora – Taupō Hospital","thhs26-hospital-details")}</div><div class="col-md-6 o_colored_level">{image(hospital_photo,"Taupō Hospital entrance","thhs26-hospital-photo")}</div></div>','thhs26-hospital',snippet='s_image_text'))

menus = [
 ('About Us|Ā mātou tangata',[('History','/background'),('Mission/Vision','/our-vision'),('What we do?','/what-we-do'),('Our Board','/our-board'),('Our Patrons','/our-patrons'),('Associate members','/associate-members'),('Incorporated Society','/incorporated-society')]),
 ('News|Ngā Kārere',[('Latest News','/news'),('Archived News','/archive-news'),('Annual reports','/annual-report'),('Social Media','/social-media')]),
 ('Projects|Kaupapa',[('Successes','/successes'),('Testimonials','/projects')]),
 ('Events|Takahanga',[('Calendar dates','/calendar'),('Get Involved','/how-can-i-help'),('Contact Us','/contactus')]),
 ('Our Hospital|Ā mātou Hōhipera',[('History','/our-hospital')]),
]
payload={'source':'THHS mockup website Deb 010926.pptx','assets':assets,'pages':pages,'menus':menus}
(MODULE/'data').mkdir(exist_ok=True)
(MODULE/'data/client_refresh_2026.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
print(f'Built {len(pages)} editable pages and {len(assets)} original client assets.')
