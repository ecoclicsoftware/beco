import logging
_logger = logging.getLogger(__name__)

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
    
    supervisor_externo_id = fields.Many2one(
        'res.partner',
        string='Supervisor Externo',
        domain="[('external', '=', True)]",
        help='Supervisor externo asignado a este comercial'
    )


    comerciales_asignados_ids = fields.Many2many(
        'res.partner',
        'supervisor_externo_comercial_rel',  # nombre de la tabla relacional
        'externo_id', 
        'comercial_id',
        string='Comerciales Asignados',
        # domain="[('worker', '=', True)]",
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
    
    internal_company_id = fields.Many2one(
        'res.company',
        string='Compañía Asignada',
        ondelete='restrict',
        help='Compañía de Odoo asignada a este contacto',
        store=True
    )


    # -------------------------
    # CONSTRAINTS Y VALIDACIONES
    # -------------------------

    @api.constrains('worker', 'supervisor', 'external')
    def _check_single_role(self):
        """Validar que solo tenga un rol activo, pero permitir transiciones"""
        for record in self:
            # Solo validar si el registro ya está en la base de datos
            if record.id:
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
            
            
    @api.constrains('external', 'comerciales_asignados_ids')
    def _check_comerciales_externo(self):
        """Validar que los comerciales asignados a un externo sean válidos"""
        for rec in self:
            if rec.external and rec.comerciales_asignados_ids:
                # Verificar que los asignados sean realmente comerciales
                no_workers = rec.comerciales_asignados_ids.filtered(lambda c: not c.worker)
                if no_workers:
                    raise ValidationError(
                        f"Solo se pueden asignar comerciales. Los siguientes contactos no son comerciales: "
                        f"{', '.join(no_workers.mapped('name'))}"
                    )
    
    
    @api.constrains('external', 'comerciales_asignados_ids')
    def _check_comerciales_mismo_departamento(self):
        for rec in self:
            if rec.external and rec.comerciales_asignados_ids:
                departamentos_externo = rec.department
                comerciales_departamento_diferente = rec.comerciales_asignados_ids.filtered(
                    lambda c: not c.department or not any(dept in departamentos_externo for dept in c.department)
                )
                if comerciales_departamento_diferente:
                    raise ValidationError(
                        f"❌ ERROR: Solo puedes asignar comerciales del mismo departamento.\n"
                        f"Los comerciales {comerciales_departamento_diferente.mapped('name')} "
                        f"no pertenecen a tu departamento."
                    )
                    

    @api.constrains('external', 'comerciales_asignados_ids')
    def _check_comerciales_mismo_departamento_externo(self):
        """Validar que los comerciales asignados a un externo sean de su mismo departamento"""
        for rec in self:
            if rec.external and rec.comerciales_asignados_ids:
                # El externo no tiene departamento, así que verificamos los departamentos de los supervisores
                departamentos_supervisores = rec.supervisores_ids.mapped('department')
                if not departamentos_supervisores:
                    raise ValidationError(
                        "El externo debe tener al menos un supervisor con departamento asignado "
                        "para poder asignar comerciales."
                    )
                
                # Verificar que cada comercial tenga al menos un departamento en común con los supervisores
                for comercial in rec.comerciales_asignados_ids:
                    if not comercial.department:
                        raise ValidationError(
                            f"El comercial {comercial.name} no tiene departamento asignado."
                        )
                    
                    departamentos_comercial = comercial.department
                    departamentos_supervisores_flat = [dept for sublist in departamentos_supervisores for dept in sublist]
                    
                    if not any(dept in departamentos_supervisores_flat for dept in departamentos_comercial):
                        raise ValidationError(
                            f"El comercial {comercial.name} no pertenece a los departamentos "
                            f"de los supervisores asignados al externo."
                        )

    @api.constrains('worker', 'supervisor_externo_id')
    def _check_comercial_tiene_departamento(self):
        """Validar que el comercial tenga departamento si tiene supervisor externo"""
        for rec in self:
            if rec.worker and rec.supervisor_externo_id and not rec.department:
                raise ValidationError(
                    "El comercial debe tener departamento asignado para poder tener un supervisor externo."
                )

    # -------------------------
    # ONCHANGE METHODS
    # -------------------------

    # @api.onchange('worker')
    # def _onchange_worker(self):
    #     if self.worker:
    #         self.supervisor = False
    #         self.external = False
    #         self.department = False
    #         self.supervisor_externo_id = False

    # @api.onchange('supervisor')
    # def _onchange_supervisor(self):
    #     if self.supervisor:
    #         self.worker = False
    #         self.external = False
    #         self.department = False
    #         self.supervisor_externo_id = False

    # @api.onchange('external')
    # def _onchange_external(self):
    #     if self.external:
    #         self.worker = False
    #         self.supervisor = False
    #         self.department = False
    #         self.company_id = False
    #     else:
    #         self.comerciales_asignados_ids = [(5, 0, 0)]  # Limpiar comerciales asignados si deja de ser externo

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
            
    def _compute_meeting_count(self):
        """
        Sobrescribe el método para evitar errores de acceso durante el cálculo.
        Usamos sudo() para bypassear las reglas de acceso temporalmente solo para este
        cálculo, ya que el campo es de solo lectura y no expone datos sensibles.
        """
        try:
            # Llama a la lógica original con sudo() para evitar que las reglas de acceso
            # del usuario actual interfieran con la obtención de IDs.
            partners_sudo = self.sudo()
            super(ResPartner, partners_sudo)._compute_meeting_count()
        except Exception as e:
            _logger.error(f"Error computing meeting_count, falling back to 0. Error: {e}")
            # Si algo falla incluso con sudo, asignamos 0 a todos para no bloquear la UI.
            self.meeting_count = 0



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
    # DEBUGGING METHODS
    # -------------------------
    
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Override para debuggear qué campos se están enviando"""
        result = super(ResPartner, self).fields_get(allfields, attributes)
        _logger.info(f"🔍 FIELDS_GET llamado")
        return result

    @api.model
    def create(self, vals):
        _logger.info(f"🎯 CREATE llamado con vals: {vals}")
        return super(ResPartner, self).create(vals)



    # -------------------------
    # CRUD METHODS
    # -------------------------

    @api.model
    def create(self, vals):
        current_user = self.env.user
        
        # Validar exclusividad de roles
        role_fields = ['worker', 'supervisor', 'external']
        active_roles = [field for field in role_fields if vals.get(field)]
        if len(active_roles) > 1:
            raise ValidationError("Solo puede seleccionar un rol a la vez.")
        
        # Limpiar campos según el rol seleccionado
        if vals.get('worker'):
            vals.update({
                'supervisor': False,
                'external': False,
                'supervisores_ids': [(5, 0, 0)],
            })
        elif vals.get('supervisor'):
            vals.update({
                'worker': False,
                'external': False,
                'supervisor_externo_id': False,
            })
        elif vals.get('external'):
            vals.update({
                'worker': False,
                'supervisor': False,
                'department': [(5, 0, 0)],
                'company_id': False,
            })
        
        # Asignar compañía por defecto si no especificada, excepto para externos
        if not vals.get('external') and not vals.get('company_id'):
            vals['company_id'] = current_user.company_id.id

        # Lógica para SUPERVISOR creando un COMERCIAL
        if current_user.partner_id.supervisor and vals.get('worker'):
            if not vals.get('department'):
                if current_user.partner_id.department:
                    # Asigna los departamentos del supervisor al nuevo comercial
                    vals['department'] = [(6, 0, current_user.partner_id.department.ids)]
                else:
                    raise ValidationError("No puedes crear un comercial porque, como supervisor, no tienes un departamento asignado.")

        # Lógica para COMERCIAL creando un CONTACTO (sin rol)
        elif current_user.partner_id.worker:
            # Un comercial no puede crear otros usuarios con roles
            if vals.get('worker') or vals.get('supervisor') or vals.get('external'):
                raise ValidationError("No tienes permisos para crear usuarios con roles (Comercial, Supervisor, Externo).")
            # Asigna su propio departamento al nuevo contacto si no se especifica uno
            if current_user.partner_id.department and not vals.get('department'):
                vals['department'] = [(6, 0, current_user.partner_id.department.ids)]
        
        # Validar duplicados (mantenemos tu lógica)
        duplicate_fields = ['vat', 'phone', 'mobile']
        for field in duplicate_fields:
            if vals.get(field):
                self._validate_duplicate_in_department(field, vals.get(field), vals.get('department', False))

        return super(ResPartner, self).create(vals)


    def write(self, vals):
        current_user = self.env.user
        _logger.info(f"✏️ EJECUTANDO WRITE para {self.mapped('name')}")
        _logger.info(f"📦 Valores a escribir: {vals}")
        
        # Log del estado actual antes de escribir
        for record in self:
            _logger.info(f"📊 Estado actual ANTES de {record.name}:")
            _logger.info(f"   - ID: {record.id}")
            _logger.info(f"   - worker: {record.worker}")
            _logger.info(f"   - supervisor: {record.supervisor}")  
            _logger.info(f"   - external: {record.external}")
            _logger.info(f"   - comerciales_asignados_ids: {record.comerciales_asignados_ids.ids}")
            _logger.info(f"   - comerciales_asignados_names: {record.comerciales_asignados_ids.mapped('name')}")
            _logger.info(f"   - supervisores_ids: {record.supervisores_ids.ids}")
            _logger.info(f"   - department: {record.department.ids}")
            _logger.info(f"   - company_id: {record.company_id.id}")
        
        # Si estamos intentando asignar comerciales, log específico
        if 'comerciales_asignados_ids' in vals:
            _logger.info(f"🎯 INTENTANDO ASIGNAR COMERCIALES: {vals['comerciales_asignados_ids']}")
        
        # Si el usuario actual es comercial, bloquear edición de campos restringidos
        if current_user.partner_id and current_user.partner_id.worker:
            restricted_fields = ['worker', 'supervisor', 'department', 'external', 'supervisor_externo_id', 'supervisores_ids', 'comerciales_asignados_ids']
            attempted_restricted_fields = [field for field in restricted_fields if field in vals]
            if attempted_restricted_fields:
                _logger.error(f"🚫 ACCESO DENEGADO: Comercial intentando modificar {attempted_restricted_fields}")
                raise ValidationError(
                    f"❌ ACCESO DENEGADO\n\n"
                    f"No tienes permisos para modificar los campos: {', '.join(attempted_restricted_fields)}.\n"
                    f"Solo los administradores y supervisores pueden modificar estos campos."
                )
        
        # Exclusividad de roles al editar - usar approach diferente
        records_to_clear = self.env['res.partner']
        
        for record in self:
            # Si se está cambiando a worker
            if vals.get('worker') and not record.worker:
                _logger.info(f"🔄 {record.name} cambiando a WORKER")
                records_to_clear += record
            
            # Si se está cambiando a supervisor  
            elif vals.get('supervisor') and not record.supervisor:
                _logger.info(f"🔄 {record.name} cambiando a SUPERVISOR")
                records_to_clear += record
                
            # Si se está cambiando a external
            elif vals.get('external') and not record.external:
                _logger.info(f"🔄 {record.name} cambiando a EXTERNAL")
                records_to_clear += record
        
        if records_to_clear:
            _logger.info(f"🚨 REGISTROS QUE CAMBIAN DE ROL: {records_to_clear.mapped('name')}")
        
        # Aplicar cambios de roles en una sola operación para evitar problemas de caché
        if records_to_clear:
            # Primero limpiar relaciones para los registros que cambian de rol
            clear_vals = {}
            
            if vals.get('worker'):
                clear_vals.update({
                    'supervisor': False,
                    'external': False,
                    'supervisores_ids': [(5, 0, 0)],
                    'comerciales_asignados_ids': [(5, 0, 0)],
                })
                _logger.info(f"🔄 Limpiando campos para cambio a WORKER: {clear_vals}")
            elif vals.get('supervisor'):
                clear_vals.update({
                    'worker': False,
                    'external': False,
                    'supervisor_externo_id': False,
                    'comerciales_asignados_ids': [(5, 0, 0)],
                })
                _logger.info(f"🔄 Limpiando campos para cambio a SUPERVISOR: {clear_vals}")
            elif vals.get('external'):
                clear_vals.update({
                    'worker': False,
                    'supervisor': False,
                    'department': [(5, 0, 0)],
                    'company_id': False,
                    'supervisor_externo_id': False,
                })
                _logger.info(f"🔄 Limpiando campos para cambio a EXTERNAL: {clear_vals}")
            
            # Aplicar limpieza primero
            if clear_vals:
                # Hacer una copia de vals sin los campos de rol para evitar conflictos
                temp_vals = vals.copy()
                role_fields = ['worker', 'supervisor', 'external']
                for field in role_fields:
                    if field in temp_vals:
                        del temp_vals[field]
                
                _logger.info(f"🔄 Aplicando limpieza primero con: {clear_vals}")
                # Primero aplicar la limpieza
                records_to_clear.write(clear_vals)
                
                # Luego aplicar el resto de valores
                if temp_vals:
                    _logger.info(f"🔄 Aplicando valores temporales: {temp_vals}")
                    super(ResPartner, records_to_clear).write(temp_vals)
                
                # Finalmente aplicar el cambio de rol
                role_vals = {k: v for k, v in vals.items() if k in role_fields}
                if role_vals:
                    _logger.info(f"🔄 Aplicando cambio de rol final: {role_vals}")
                    super(ResPartner, records_to_clear).write(role_vals)
                
                _logger.info("✅ PROCESO DE CAMBIO DE ROL COMPLETADO")
                return True
        
        # Para registros que no cambian de rol, escribir normalmente
        _logger.info("🔄 Ejecutando WRITE normal (sin cambio de rol)")
        result = super(ResPartner, self).write(vals)
        
        # Log del estado DESPUÉS de escribir
        for record in self:
            _logger.info(f"📊 Estado actual DESPUÉS de {record.name}:")
            _logger.info(f"   - worker: {record.worker}")
            _logger.info(f"   - supervisor: {record.supervisor}")  
            _logger.info(f"   - external: {record.external}")
            _logger.info(f"   - comerciales_asignados_ids: {record.comerciales_asignados_ids.ids}")
            _logger.info(f"   - comerciales_asignados_names: {record.comerciales_asignados_ids.mapped('name')}")
            _logger.info(f"   - supervisores_ids: {record.supervisores_ids.ids}")
            _logger.info(f"   - department: {record.department.ids}")
        
        _logger.info(f"✅ WRITE COMPLETADO para {self.mapped('name')}")
        return result


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
                '|',  # (A) O (B)
                    ('id', '=', current_user.partner_id.id),  # A: Sí mismo
                '|',  # (B) O (C)
                    '&',  # B: Comerciales de sus departamentos
                        ('worker', '=', True),
                        ('department', 'in', current_user.partner_id.department.ids),
                '|',  # (C) O (D)
                    '&',  # C: Externos asignados
                        ('external', '=', True),
                        ('supervisores_ids', 'in', [current_user.partner_id.id]),
                    '&',  # D: Contactos creados por sus externos
                        ('create_uid.partner_id.external', '=', True),
                        ('create_uid.partner_id.supervisores_ids', 'in', [current_user.partner_id.id])
            ]
            return super().search(args + supervisor_domain, offset, limit, order, count)
        
        elif current_user.partner_id and current_user.partner_id.external:
            # Externo puede verse a sí mismo Y sus comerciales asignados
            external_domain = [
                '|',
                    ('id', '=', current_user.partner_id.id),
                    ('id', 'in', current_user.partner_id.comerciales_asignados_ids.ids)
            ]
            return super().search(args + external_domain, offset, limit, order, count)
        
        elif current_user.partner_id and current_user.partner_id.worker:
            # Comercial puede verse a sí mismo Y los contactos que él creó
            worker_domain = [
                '|',
                    ('id', '=', current_user.partner_id.id),
                    ('create_uid', '=', current_user.id)
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
                '|',  # (A) O (B)
                    ('id', '=', current_user.partner_id.id),  # A: Sí mismo
                '|',  # (B) O (C)
                    '&',  # B: Comerciales de sus departamentos
                        ('worker', '=', True),
                        ('department', 'in', current_user.partner_id.department.ids),
                '|',  # (C) O (D)
                    '&',  # C: Externos asignados
                        ('external', '=', True),
                        ('supervisores_ids', 'in', [current_user.partner_id.id]),
                    '&',  # D: Contactos creados por sus externos
                        ('create_uid.partner_id.external', '=', True),
                        ('create_uid.partner_id.supervisores_ids', 'in', [current_user.partner_id.id])
            ]
            return super().search_read(domain + supervisor_domain, fields, offset, limit, order)
        
        elif current_user.partner_id and current_user.partner_id.external:
            # Externo puede verse a sí mismo Y sus comerciales asignados
            external_domain = [
                '|',
                    ('id', '=', current_user.partner_id.id),
                    ('id', 'in', current_user.partner_id.comerciales_asignados_ids.ids)
            ]
            return super().search_read(domain + external_domain, fields, offset, limit, order)
        
        elif current_user.partner_id and current_user.partner_id.worker:
            # Comercial puede verse a sí mismo Y los contactos que él creó
            worker_domain = [
                '|',
                    ('id', '=', current_user.partner_id.id),
                    ('create_uid', '=', current_user.id)
            ]
            return super().search_read(domain + worker_domain, fields, offset, limit, order)
        
        else:
            return super().search_read(domain + [('id', '=', current_user.partner_id.id)], fields, offset, limit, order)