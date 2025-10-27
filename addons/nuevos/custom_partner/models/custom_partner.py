from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    worker = fields.Boolean(
        string='Comercial',
        default=False,
        help='Indica si este contacto es un Comercial'
    )
    
    supervisor = fields.Boolean(
        string='Supervisor',
        default=False,
        help='Indica si este contacto es un supervisor de departamento',
        store=True
    )
    
    department = fields.Many2many(
        'res.partner.department',
        string='Departamentos',
        help='Departamentos a los que pertenece el trabajador/supervisor',
        store=True,
    )

    # Campo computado para controlar la visibilidad/readonly
    is_worker_user = fields.Boolean(
        string='Es Usuario Comercial',
        compute='_compute_is_worker_user',
        help='Indica si el usuario actual es un comercial'
    )    

    @api.depends_context('uid')
    def _compute_is_worker_user(self):
        """Calcula si el usuario actual es un comercial"""
        current_user = self.env.user
        for partner in self:
            # Verificar si el usuario actual tiene partner y es worker
            if current_user.partner_id and current_user.partner_id.worker:
                partner.is_worker_user = True
            else:
                partner.is_worker_user = False
    
    def get_medical_partners(self):
        """Devuelve todos los contactos del departamento médico"""
        return self.search([('department.name', 'ilike', 'Médico')])
    
    def get_aesthetic_partners(self):
        """Devuelve todos los contactos del departamento estética"""
        return self.search([('department.name', 'ilike', 'Estética')])

    # 🔍 NUEVO MÉTODO: búsqueda sin restricciones ni filtros de visibilidad
    @api.model
    def unrestricted_search(self, domain, limit=None):
        """Devuelve registros de res.partner sin aplicar filtros de visibilidad personalizados."""
        return super(ResPartner, self.sudo()).search(domain, limit=limit)

    def _validate_duplicate_in_department(self, field_name, field_value, current_department, exclude_id=None):
        """Método auxiliar para validar duplicados globalmente (sin restricciones)."""
        if not field_value:
            return

        if field_name == 'vat':
            field_value = field_value.strip().upper()
        
        domain = [(field_name, '=', field_value)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        
        # 👇 Aquí usamos la búsqueda sin restricciones
        existing_record = self.unrestricted_search(domain, limit=1)

        if existing_record:
            field_labels = {
                'vat': 'NIF/CIF',
                'phone': 'teléfono',
                'mobile': 'móvil'
            }
            field_label = field_labels.get(field_name, field_name)
            creator = existing_record.create_uid
            existing_department = existing_record.department or 'Sin departamento'
            
            raise ValidationError(
                f"❌ ERROR: No se puede crear/modificar el contacto.\n\n"
                f"📋 El {field_label} '{field_value}' ya está registrado en el sistema por:\n"
                f"🏭 Departamento: {existing_department}\n\n"
                f"⚠️ No se pueden duplicar clientes."
            )

    @api.constrains('vat', 'phone', 'mobile', 'department')
    def _check_duplicate_contact_in_department(self):
        """Validar que no existan contactos duplicados globalmente."""
        for record in self:
            if record.department:
                if record.vat:
                    self._validate_duplicate_in_department('vat', record.vat, record.department, record.id)
                if record.phone:
                    self._validate_duplicate_in_department('phone', record.phone, record.department, record.id)
                if record.mobile:
                    self._validate_duplicate_in_department('mobile', record.mobile, record.department, record.id)

    @api.model
    def create(self, vals):
        current_user = self.env.user
        if current_user.partner_id and current_user.partner_id.worker and current_user.partner_id.department:
            current_departments = current_user.partner_id.department
            vals['department'] = [(6, 0, current_departments.ids)]
            vals['worker'] = False
            vals['supervisor'] = False
            if vals.get('vat'):
                self._validate_duplicate_in_department('vat', vals.get('vat'), current_departments)
            if vals.get('phone'):
                self._validate_duplicate_in_department('phone', vals.get('phone'), current_departments)
            if vals.get('mobile'):
                self._validate_duplicate_in_department('mobile', vals.get('mobile'), current_departments)
        return super(ResPartner, self).create(vals)

    def write(self, vals):
        """Bloquear la edición de campos worker, supervisor y department para usuarios worker"""
        current_user = self.env.user
        
        # Si el usuario actual es un worker, verificar que no intente modificar campos restringidos
        if current_user.partner_id and current_user.partner_id.worker:
            restricted_fields = ['worker', 'supervisor', 'department']
            attempted_restricted_fields = [field for field in restricted_fields if field in vals]
            
            if attempted_restricted_fields:
                raise ValidationError(
                    f"❌ ACCESO DENEGADO\n\n"
                    f"No tienes permisos para modificar los campos: {', '.join(attempted_restricted_fields)}.\n"
                    f"Solo los administradores y supervisores pueden modificar estos campos."
                )
        
        return super(ResPartner, self).write(vals)

    # -------------------------
    # 🔒 Filtros de visibilidad
    # -------------------------
    
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        current_user = self.env.user
        if (current_user.partner_id and current_user.partner_id.supervisor and 
            current_user.partner_id.department):
            department_users = self.env['res.users'].search([
                ('partner_id.department', 'in', current_user.partner_id.department.ids)
            ])
            department_user_ids = department_users.ids
            supervisor_filter = [
                '|',
                ('department', 'in', current_user.partner_id.department.ids),
                ('create_uid', 'in', department_user_ids)
            ]
            args = args + supervisor_filter
        elif current_user.partner_id and current_user.partner_id.worker and not current_user.partner_id.supervisor:
            worker_filter = [
                '|',
                ('id', '=', current_user.partner_id.id),
                ('create_uid', '=', current_user.id)
            ]
            args = args + worker_filter
        return super(ResPartner, self).search(args, offset, limit, order, count)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if domain is None:
            domain = []
        current_user = self.env.user
        if (current_user.partner_id and current_user.partner_id.supervisor and 
            current_user.partner_id.department):
            department_users = self.env['res.users'].search([
                ('partner_id.department', 'in', current_user.partner_id.department.ids)
            ])
            department_user_ids = department_users.ids
            supervisor_filter = [
                '|',
                ('department', 'in', current_user.partner_id.department.ids),
                ('create_uid', 'in', department_user_ids)
            ]
            domain = domain + supervisor_filter
        elif current_user.partner_id and current_user.partner_id.worker and not current_user.partner_id.supervisor:
            worker_filter = [
                '|',
                ('id', '=', current_user.partner_id.id),
                ('create_uid', '=', current_user.id)
            ]
            domain = domain + worker_filter
        return super(ResPartner, self).search_read(domain, fields, offset, limit, order)