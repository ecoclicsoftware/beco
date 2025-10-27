from odoo import models, fields

class Department(models.Model):
    _name = 'res.partner.department'
    _description = 'Departamentos de Comerciales'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El nombre del departamento debe ser único!'),
    ]