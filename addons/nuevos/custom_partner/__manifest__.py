{
    'name': 'Extends Partner',
    'version': '16.0.1.1.0',  # Incrementamos la versión
    'summary': 'Extends partner for a many2many tags products',
    'description': 'Extends partner for a many2many tags products',
    'category': 'Tools',
    'depends': ['base', 'product', 'custom_department'],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_partner.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
