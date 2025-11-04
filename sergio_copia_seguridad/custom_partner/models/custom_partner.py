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



    # -------------------------
    # CRUD METHODS
    # -------------------------

    @api.model
    def create(self, vals):
        _logger.info(f"🎯 CREATE llamado con vals: {vals}")
        current_user = self.env.user
        
        # -------------------------
        # DEBUG: ¿QUIÉN ESTÁ LOGUEADO?
        # -------------------------
        _logger.info(f"═══════════════════════════════════════")
        _logger.info(f"👤 Usuario actual (res.users):")
        _logger.info(f"   - ID: {current_user.id}")
        _logger.info(f"   - Login: {current_user.login}")
        _logger.info(f"   - Name: {current_user.name}")
        _logger.info(f"   - Partner ID: {current_user.partner_id.id if current_user.partner_id else 'None'}")
        _logger.info(f"   - Partner Name: {current_user.partner_id.name if current_user.partner_id else 'None'}")
        
        if current_user.partner_id:
            # Forzar lectura desde BD sin caché
            partner = self.env['res.partner'].sudo().browse(current_user.partner_id.id)
            
            _logger.info(f"📋 Datos del Partner asociado (desde BD):")
            _logger.info(f"   - ID: {partner.id}")
            _logger.info(f"   - Name: {partner.name}")
            _logger.info(f"   - worker: {partner.worker}")
            _logger.info(f"   - supervisor: {partner.supervisor}")
            _logger.info(f"   - external: {partner.external}")
            _logger.info(f"   - internal_company_id: {partner.internal_company_id.name if partner.internal_company_id else 'None'}")
            _logger.info(f"   - department IDs: {partner.department.ids}")
            _logger.info(f"   - department Names: {partner.department.mapped('name')}")
        else:
            _logger.info(f"⚠️ El usuario NO tiene partner_id asociado")
        _logger.info(f"═══════════════════════════════════════")
        
        # -------------------------
        # VALIDACIÓN DE ROLES
        # -------------------------
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
        
        # -------------------------
        # ASIGNACIÓN DE COMPANY_ID POR DEFECTO
        # -------------------------
        if not vals.get('external') and not vals.get('company_id'):
            vals['company_id'] = current_user.company_id.id
        
        # -------------------------
        # LÓGICA SEGÚN ROL DEL CREADOR
        # -------------------------
        
        # SUPERVISOR creando COMERCIAL
        if current_user.partner_id.supervisor and vals.get('worker'):
            if not vals.get('department'):
                if current_user.partner_id.department:
                    vals['department'] = [(6, 0, current_user.partner_id.department.ids)]
                else:
                    raise ValidationError(
                        "No puedes crear un comercial porque, como supervisor, "
                        "no tienes un departamento asignado."
                    )
        
        # COMERCIAL creando CONTACTO
        elif current_user.partner_id.worker:
            # Un comercial NO puede crear usuarios con roles
            if vals.get('worker') or vals.get('supervisor') or vals.get('external'):
                raise ValidationError(
                    "No tienes permisos para crear usuarios con roles "
                    "(Comercial, Supervisor, Externo)."
                )
            
            # Asignar departamento del comercial al nuevo contacto si no se especifica
            if current_user.partner_id.department and not vals.get('department'):
                vals['department'] = [(6, 0, current_user.partner_id.department.ids)]
        
        # -------------------------
        # HERENCIA AUTOMÁTICA DE EMPRESA Y DEPARTAMENTOS
        # -------------------------
        if current_user.partner_id:
            # Forzar lectura desde BD sin caché
            creator_partner = self.env['res.partner'].sudo().browse(current_user.partner_id.id)
            
            _logger.info(f"🔄 Aplicando herencia automática...")
            _logger.info(f"   - Valores actuales en vals:")
            _logger.info(f"     * internal_company_id: {vals.get('internal_company_id')}")
            _logger.info(f"     * department: {vals.get('department')}")
            
            # Heredar internal_company_id si no se especificó O está vacío
            if not vals.get('internal_company_id') and creator_partner.internal_company_id:
                vals['internal_company_id'] = creator_partner.internal_company_id.id
                _logger.info(
                    f"✅ Heredando empresa '{creator_partner.internal_company_id.name}' "
                    f"(ID: {creator_partner.internal_company_id.id}) al nuevo contacto"
                )
            else:
                if vals.get('internal_company_id'):
                    _logger.info(f"ℹ️ internal_company_id ya tiene valor: {vals.get('internal_company_id')}")
                elif not creator_partner.internal_company_id:
                    _logger.warning(f"⚠️ El creador NO tiene empresa asignada")
            
            # Heredar department si no se especificó O está vacío y el creador no es externo
            # Verificar si department está vacío: None, False, [], o [[6, False, []]]
            department_empty = (
                not vals.get('department') or 
                vals.get('department') == [[6, False, []]] or
                vals.get('department') == [(6, 0, [])]
            )
            
            _logger.info(f"   - department_empty: {department_empty}")
            
            if department_empty and creator_partner.department and not vals.get('external'):
                vals['department'] = [(6, 0, creator_partner.department.ids)]
                _logger.info(
                    f"✅ Heredando departamentos {creator_partner.department.mapped('name')} "
                    f"(IDs: {creator_partner.department.ids}) al nuevo contacto"
                )
            else:
                if not department_empty:
                    _logger.info(f"ℹ️ department ya tiene valor: {vals.get('department')}")
                elif not creator_partner.department:
                    _logger.warning(f"⚠️ El creador NO tiene departamentos asignados")
                elif vals.get('external'):
                    _logger.info(f"ℹ️ El nuevo contacto es externo (no hereda departamentos)")

        
        # -------------------------
        # VALIDACIÓN DE DUPLICADOS
        # -------------------------
        duplicate_fields = ['vat', 'phone', 'mobile']
        for field in duplicate_fields:
            if vals.get(field):
                self._validate_duplicate_in_department(field, vals.get(field), vals.get('department'), False)
        
        _logger.info(f"📦 Valores FINALES antes de crear: {vals}")
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
            # Obtener IDs de comerciales de los departamentos del supervisor
            comerciales_ids = self.env['res.partner'].sudo().search([
                ('worker', '=', True),
                ('department', 'in', current_user.partner_id.department.ids),
                ('internal_company_id', '=', current_user.partner_id.internal_company_id.id)
            ]).ids
            
            # Obtener IDs de clientes (contactos sin rol) creados por esos comerciales
            clientes_ids = self.env['res.partner'].sudo().search([
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('create_uid.partner_id', 'in', comerciales_ids),
                ('internal_company_id', '=', current_user.partner_id.internal_company_id.id)
            ]).ids
            
            supervisor_domain = [
                '|', '|', '|', '|',  # 5 condiciones principales con 4 operadores OR
                ('id', '=', current_user.partner_id.id),  # 1. Sí mismo
                '&', '&',  # 2. Comerciales de sus departamentos Y misma empresa
                    ('worker', '=', True),
                    ('department', 'in', current_user.partner_id.department.ids),
                    ('internal_company_id', '=', current_user.partner_id.internal_company_id.id),
                '&',  # 3. Externos asignados
                    ('external', '=', True),
                    ('supervisores_ids', 'in', [current_user.partner_id.id]),
                '&', '&', '&',  # 4. Contactos sin rol creados por sus comerciales
                    ('worker', '=', False),
                    ('supervisor', '=', False),
                    ('external', '=', False),
                    ('id', 'in', clientes_ids),
                '&',  # 5. Contactos creados por externos asignados
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
            # Obtener IDs de comerciales de los departamentos del supervisor
            comerciales_ids = self.env['res.partner'].sudo().search([
                ('worker', '=', True),
                ('department', 'in', current_user.partner_id.department.ids),
                ('internal_company_id', '=', current_user.partner_id.internal_company_id.id)
            ]).ids
            
            # Obtener IDs de clientes (contactos sin rol) creados por esos comerciales
            clientes_ids = self.env['res.partner'].sudo().search([
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('create_uid.partner_id', 'in', comerciales_ids),
                ('internal_company_id', '=', current_user.partner_id.internal_company_id.id)
            ]).ids
            
            supervisor_domain = [
                '|', '|', '|', '|',  # 5 condiciones principales con 4 operadores OR
                ('id', '=', current_user.partner_id.id),  # 1. Sí mismo
                '&', '&',  # 2. Comerciales de sus departamentos Y misma empresa
                    ('worker', '=', True),
                    ('department', 'in', current_user.partner_id.department.ids),
                    ('internal_company_id', '=', current_user.partner_id.internal_company_id.id),
                '&',  # 3. Externos asignados
                    ('external', '=', True),
                    ('supervisores_ids', 'in', [current_user.partner_id.id]),
                '&', '&', '&',  # 4. Contactos sin rol creados por sus comerciales
                    ('worker', '=', False),
                    ('supervisor', '=', False),
                    ('external', '=', False),
                    ('id', 'in', clientes_ids),
                '&',  # 5. Contactos creados por externos asignados
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
