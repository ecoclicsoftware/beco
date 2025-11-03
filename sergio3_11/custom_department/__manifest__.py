{
    'name': 'Partner Departments',
    'version': '16.0.1.0.0',
    'summary': 'Modelo y vistas de departamentos para comerciales',
    'description': 'Permite gestionar departamentos y asignarlos a contactos',
    'category': 'Tools',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/department_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
