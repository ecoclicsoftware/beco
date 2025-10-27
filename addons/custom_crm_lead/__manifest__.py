{
    'name': 'Extends crm lead',
    'version': '16.0.1.0.0',
    'summary': 'Extends crm lead for a many2many tags products',
    'description': 'Extends crm lead for a many2many tags products',
    'category': 'Tools',
    # 'author': 'Nico Mesa',
    # 'website': 'https://github.com/nicomesa230',
    'depends': ['base', 'product', 'crm'],
    'data': [
        'views/crm_product_menu.xml',
        'views/form_crm_lead.xml',
        'views/crm_lead_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
