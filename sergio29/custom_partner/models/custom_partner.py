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

    external = fields.Boolean(
        string='Externo',
        default=False,
        help='Indica si este contacto es un usuario externo',
        store=True
    )

    # RELACIÓN DE COMERCIAL > SUPERVISOR EXTERNO (Muchos comerciales a un externo)
    supervisor_externo_id = fields.Many2one(
        'res.partner',
        string='Supervisor Externo',
        domain="[('external', '=', True)]",
        help='Supervisor externo asignado a este comercial'
    )

    # RELACIÓN DE SUPERVISOR EXTERNO > COMERCIALES ASIGNADOS (Uno externo, muchos comerciales)
    comerciales_asignados_ids = fields.One2many(
        'res.partner',
        'supervisor_externo_id',
        string='Comerciales Asignados',
        help='Comerciales asignados a este supervisor externo'
    )

    department = fields.Many2many(
        'res.partner.department',
        string='Departamentos',
        help='Departamentos a los que pertenece el trabajador/supervisor',
        store=True
    )

    is_worker_user = fields.Boolean(
        string='Es Usuario Comercial',
        compute='_compute_is_worker_user',
        help='Indica si el usuario actual es un comercial'
    )

    is_external_user = fields.Boolean(
        string='Es Usuario Externo',
        compute='_compute_is_external_user',
        help='Indica si el usuario actual es un externo'
    )
    
    supervisores_ids = fields.Many2many(
        'res.partner',
        'supervisor_externo_rel',  # nombre tabla relacional
        'externo_id', 'supervisor_id',
        string='Supervisores asignados',
        domain="[('supervisor', '=', True)]",
        help='Supervisores asignados a este supervisor externo'
    )


    # -------------------------
    # CONSTRAINTS Y VALIDACIONES
    # -------------------------

    @api.constrains('worker', 'supervisor', 'external')
    def _check_single_role(self):
        for record in self:
            active_roles = [record.worker, record.supervisor, record.external]
            if sum(active_roles) > 1:
                raise ValidationError(
                    "❌ ERROR: Solo puede seleccionar un rol a la vez.\n"
                    "Un contacto no puede ser Comercial, Supervisor y Externo simultáneamente."
                )

    
    @api.constrains('external', 'supervisores_ids')
    def _check_supervisor_externo_obligatorio(self):
        for rec in self:
            if rec.external and not rec.supervisores_ids:
                raise ValidationError("Debes asignar al menos un supervisor a este supervisor externo.")






    # -------------------------
    # ONCHANGE METHODS
    # -------------------------

    @api.onchange('worker')
    def _onchange_worker(self):
        if self.worker:
            self.supervisor = False
            self.external = False
            self.department = False
            self.supervisor_externo_id = False

    @api.onchange('supervisor')
    def _onchange_supervisor(self):
        if self.supervisor:
            self.worker = False
            self.external = False
            self.department = False
            self.supervisor_externo_id = False

    @api.onchange('external')
    def _onchange_external(self):
        if self.external:
            self.worker = False
            self.supervisor = False
            self.department = False
            self.company_id = False
        else:
            self.comerciales_asignados_ids = [(5, 0, 0)]  # Limpiar comerciales asignados si deja de ser externo

    # -------------------------
    # COMPUTED METHODS
    # -------------------------

    @api.depends_context('uid')
    def _compute_is_worker_user(self):
        current_user = self.env.user
        for partner in self:
            partner.is_worker_user = bool(
                current_user.partner_id and
                current_user.partner_id.worker
            )

    @api.depends_context('uid')
    def _compute_is_external_user(self):
        current_user = self.env.user
        for partner in self:
            partner.is_external_user = bool(
                current_user.partner_id and
                current_user.partner_id.external
            )

    # -------------------------
    # BUSINESS METHODS
    # -------------------------

    def get_medical_partners(self):
        """Devuelve todos los contactos del departamento médico"""
        return self.search([('department.name', 'ilike', 'Médico')])

    def get_aesthetic_partners(self):
        """Devuelve todos los contactos del departamento estética"""
        return self.search([('department.name', 'ilike', 'Estética')])

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
        existing_record = self.unrestricted_search(domain, limit=1)
        if existing_record:
            field_labels = {
                'vat': 'NIF/CIF',
                'phone': 'teléfono',
                'mobile': 'móvil'
            }
            field_label = field_labels.get(field_name, field_name)
            existing_department = existing_record.department or 'Sin departamento'
            raise ValidationError(
                f"❌ ERROR: No se puede crear/modificar el contacto.\n\n"
                f"📋 El {field_label} '{field_value}' ya está registrado en el sistema por:\n"
                f"🏭 Departamento: {existing_department}\n\n"
                f"⚠️ No se pueden duplicar clientes."
            )

    @api.constrains('vat', 'phone', 'mobile', 'department')
    def _check_duplicate_contact_in_department(self):
        for record in self:
            if record.department:
                if record.vat:
                    self._validate_duplicate_in_department('vat', record.vat, record.department, record.id)
                if record.phone:
                    self._validate_duplicate_in_department('phone', record.phone, record.department, record.id)
                if record.mobile:
                    self._validate_duplicate_in_department('mobile', record.mobile, record.department, record.id)

    # -------------------------
    # CRUD METHODS
    # -------------------------

    @api.model
    def create(self, vals):
        current_user = self.env.user
        # Aplicar exclusividad de roles
        if vals.get('worker'):
            vals['supervisor'] = False
            vals['external'] = False
            vals['supervisor_externo_id'] = False
        elif vals.get('supervisor'):
            vals['worker'] = False
            vals['external'] = False
            vals['supervisor_externo_id'] = False
        elif vals.get('external'):
            vals['worker'] = False
            vals['supervisor'] = False
            vals['department'] = False
            vals['company_id'] = False
        # Asignar por defecto la compañía del usuario que crea el contacto
        if not vals.get('company_id'):
            vals['company_id'] = current_user.company_id.id
        # Si el usuario es comercial, aplicar restricciones
        if current_user.partner_id and current_user.partner_id.worker and current_user.partner_id.department:
            current_departments = current_user.partner_id.department
            vals['department'] = [(6, 0, current_departments.ids)]
            vals['worker'] = False
            vals['supervisor'] = False
            vals['external'] = False
        # Validar duplicados
        if vals.get('vat'):
            self._validate_duplicate_in_department('vat', vals.get('vat'), vals.get('department', False))
        if vals.get('phone'):
            self._validate_duplicate_in_department('phone', vals.get('phone'), vals.get('department', False))
        if vals.get('mobile'):
            self._validate_duplicate_in_department('mobile', vals.get('mobile'), vals.get('department', False))
        return super(ResPartner, self).create(vals)

    def write(self, vals):
        current_user = self.env.user
        # Si el usuario actual es comercial, bloquear edición de campos restringidos
        if current_user.partner_id and current_user.partner_id.worker:
            restricted_fields = ['worker', 'supervisor', 'department', 'external', 'supervisor_externo_id']
            attempted_restricted_fields = [field for field in restricted_fields if field in vals]
            if attempted_restricted_fields:
                raise ValidationError(
                    f"❌ ACCESO DENEGADO\n\n"
                    f"No tienes permisos para modificar los campos: {', '.join(attempted_restricted_fields)}.\n"
                    f"Solo los administradores y supervisores pueden modificar estos campos."
                )
        # Exclusividad de roles al editar
        if vals.get('worker'):
            vals['supervisor'] = False
            vals['external'] = False
            vals['supervisor_externo_id'] = False
        elif vals.get('supervisor'):
            vals['worker'] = False
            vals['external'] = False
            vals['supervisor_externo_id'] = False
        elif vals.get('external'):
            vals['worker'] = False
            vals['supervisor'] = False
            vals['department'] = False
            vals['company_id'] = False
        return super(ResPartner, self).write(vals)

    # -------------------------
    # FILTROS DE VISIBILIDAD
    # -------------------------

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        current_user = self.env.user
        if self.env.is_admin():
            return super().search(args, offset, limit, order, count)
        if current_user.partner_id and current_user.partner_id.supervisor:
            supervisor_domain = [
                '|',
                '|',
                    ('id', '=', current_user.partner_id.id),
                    '&',
                        ('worker', '=', True),
                        ('department', 'in', current_user.partner_id.department.ids),
                '&',
                    ('external', '=', True),
                    ('supervisores_ids', 'in', [current_user.partner_id.id]),
            ]
            return super().search(args + supervisor_domain, offset, limit, order, count)
        elif current_user.partner_id and current_user.partner_id.external:
            return super().search(args + [('id', '=', current_user.partner_id.id)], offset, limit, order, count)
        elif current_user.partner_id and current_user.partner_id.worker:
            worker_domain = [
                '|',
                ('id', '=', current_user.partner_id.id),
                ('supervisor_externo_id', '=', current_user.partner_id.supervisor_externo_id.id)
            ]
            return super().search(args + worker_domain, offset, limit, order, count)
        else:
            return super().search(args + [('id', '=', current_user.partner_id.id)], offset, limit, order, count)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if domain is None:
            domain = []
        current_user = self.env.user
        if self.env.is_admin():
            return super().search_read(domain, fields, offset, limit, order)
        if current_user.partner_id and current_user.partner_id.supervisor:
            supervisor_domain = [
                '|',
                '|',
                    ('id', '=', current_user.partner_id.id),
                    '&',
                        ('worker', '=', True),
                        ('department', 'in', current_user.partner_id.department.ids),
                '&',
                    ('external', '=', True),
                    ('supervisores_ids', 'in', [current_user.partner_id.id]),
            ]
            return super().search_read(domain + supervisor_domain, fields, offset, limit, order)
        elif current_user.partner_id and current_user.partner_id.external:
            return super().search_read(domain + [('id', '=', current_user.partner_id.id)], fields, offset, limit, order)
        elif current_user.partner_id and current_user.partner_id.worker:
            worker_domain = [
                '|',
                ('id', '=', current_user.partner_id.id),
                ('supervisor_externo_id', '=', current_user.partner_id.supervisor_externo_id.id)
            ]
            return super().search_read(domain + worker_domain, fields, offset, limit, order)
        else:
            return super().search_read(domain + [('id', '=', current_user.partner_id.id)], fields, offset, limit, order)