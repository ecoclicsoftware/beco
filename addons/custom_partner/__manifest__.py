{
    'name': 'Extends Partner',
    'version': '16.0.1.1.0',  # Incrementamos la versión
    'summary': 'Extends partner for a many2many tags products',
    'description': 'Extends partner for a many2many tags products',
    'category': 'Tools',
    'author': 'Nico Mesa',
    'website': 'https://github.com/nicomesa230',
    'depends': ['base', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_partner.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
