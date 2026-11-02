# -*- coding: utf-8 -*-
{
    'name': 'Healthcare: Form Studio',
    'summary': 'Form Studio on the clinic screens: the Booking, Client, '
               'Contact and Incident forms and their lists, the clinic '
               'administrator as the gate, the Settings entry',
    'description': """
The clinic's side of Form Studio. Data only, plus two small hooks:

  * who may open Studio (the clinic administrator), and the groups behind
    "Staff" and "Admins";
  * the screens that support Studio, with their locked fields and the areas
    shown dimmed: the Incident form, and the Booking, Client and Contact
    records (Workspace forms: new sections become cards at the end of the
    Overview pack, and fold into "Not filled yet" when empty);
  * the list each of those screens' records appear in (Bookings, Clients,
    Contacts, Incidents) and the column new columns follow;
  * the Studio button in the Booking, Client and Contact records' own top
    bars (they hide the standard control panel), and the "Not filled yet"
    tray on the Contact Overview, which had none;
  * the records a "Link to a record" field may point at (staff member,
    facility, client, contact, service or package, catchment area);
  * the Form Studio entry in the Settings section of the left menu, for the
    Owner and Admin roles, and a Form Studio tile on the Settings landing;
  * the Vietnamese words of all of the above, and the incident's lock reasons
    in the reader's language;
  * Field Requirements rules counted as a place a field is still used;
  * health information: on the Client record a text field marked health
    information is stored encrypted with the client's own key and token
    format (the cipher comes from the encryption module); on the other
    screens it is hidden from lists, exports, reports and the nurse app;
  * the nurse app shows the Client and Booking screens: a field switched on
    for it appears there, read-only, under "More details".
""",
    'version': '19.0.1.3.0',
    'category': 'Healthcare',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    'depends': [
        'biz_form_studio',
        'health_theme',
        'health_access',
        'health_incident',
        'health_cms_sidebar',
        # the Client and Contact records (FS-H2) and the Settings landing
        'health_fieldservice',
        'health_crm',
        'health_landing',
        # the cipher behind encrypted Studio fields on the Client (FS-H4)
        'health_phi_encryption',
    ],
    'data': [
        'data/fs_parameters.xml',
        'data/fs_hosts.xml',
        'data/fs_link_targets.xml',
        'data/cms_sidebar.xml',
        'views/crm_contact_tray.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_form_studio/static/src/scss/ws_headers.scss',
            'health_form_studio/static/src/xml/ws_header_client.xml',
            'health_form_studio/static/src/xml/ws_header_contact.xml',
            'health_form_studio/static/src/xml/ws_header_booking.xml',
            'health_form_studio/static/src/xml/admin_settings.xml',
            'health_form_studio/static/src/js/admin_settings.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
