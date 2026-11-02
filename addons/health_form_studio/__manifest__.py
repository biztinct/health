# -*- coding: utf-8 -*-
{
    'name': 'Healthcare: Form Studio',
    'summary': 'Form Studio on the clinic screens: the Incident form, the '
               'clinic administrator as the gate, the Settings entry',
    'description': """
The clinic's side of Form Studio. Data only, plus two small hooks:

  * who may open Studio (the clinic administrator), and the groups behind
    "Staff" and "Admins";
  * the Incident form as the first screen that supports Studio, with its
    locked fields and the counters area shown dimmed;
  * the records a "Link to a record" field may point at (staff member,
    facility, client, contact, service or package, catchment area);
  * the Form Studio entry in the Settings section of the left menu, for the
    Owner and Admin roles;
  * the Vietnamese words of all of the above, and the incident's lock reasons
    in the reader's language;
  * Field Requirements rules counted as a place a field is still used.
""",
    'version': '19.0.1.0.0',
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
    ],
    'data': [
        'data/fs_parameters.xml',
        'data/fs_hosts.xml',
        'data/fs_link_targets.xml',
        'data/cms_sidebar.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
