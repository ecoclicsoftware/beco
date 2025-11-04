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
        domain="[('worker', '=', True)]",
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
    
    # ---------------------------------
    # Individual default_get override
    # ---------------------------------
    
    @api.model
    def default_get(self, fields_list):
        """Forzar company_type a 'person' por defecto"""
        res = super(ResPartner, self).default_get(fields_list)
        res['company_type'] = 'person'
        return res


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
        """Validar que el externo tenga supervisores solo al confirmar guardado"""
        for rec in self:
            # NO validar si estamos en contexto de onchange o sin ID persistente
            if not rec.id:
                continue
                
            # Solo validar en registros external que YA FUERON guardados al menos una vez y que el usuario está intentando guardar cambios definitivos
            if rec.external and not rec.supervisores_ids:
                # Comprobar si este es un guardado real y no un cambio temporal
                if rec._origin.external == rec.external:
                    # El registro ya era externo antes, permitir edición temporal
                    continue
                else:
                    # Es un cambio nuevo a externo, validar
                    raise ValidationError(
                        "⚠️ Debes asignar al menos un supervisor antes de guardar este contacto externo."
                    )


            
            
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
    
    
    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        """
        Onchange que se ejecuta ANTES del warning estándar.
        Prepara el valor de internal_company_id para que se guarde cuando se acepte el warning.
        """
        if self.parent_id:
            parent = self.parent_id
            
            # Intentar obtener la compañía del parent
            company_to_assign = False
            
            # Opción 1: Si parent es una compañía (type='company'), usar su company_id
            if parent.is_company and parent.company_id:
                company_to_assign = parent.company_id
                _logger.info(f"✅ Onchange: Parent es compañía, usando company_id: {company_to_assign.name}")
            
            # Opción 2: Si parent tiene internal_company_id custom
            elif hasattr(parent, 'internal_company_id') and parent.internal_company_id:
                company_to_assign = parent.internal_company_id
                _logger.info(f"✅ Onchange: Parent tiene internal_company_id: {company_to_assign.name}")
            
            # Opción 3: Si parent tiene company_id estándar
            elif parent.company_id:
                company_to_assign = parent.company_id
                _logger.info(f"✅ Onchange: Parent tiene company_id estándar: {company_to_assign.name}")
            
            # Opción 4: Si el parent tiene un parent a su vez (es un contacto de una compañía)
            elif parent.parent_id:
                # Recursivamente buscar la compañía en el parent del parent
                grandparent = parent.parent_id
                if grandparent.is_company and grandparent.company_id:
                    company_to_assign = grandparent.company_id
                    _logger.info(f"✅ Onchange: Usando compañía del grandparent: {company_to_assign.name}")
                elif grandparent.company_id:
                    company_to_assign = grandparent.company_id
                    _logger.info(f"✅ Onchange: Usando company_id del grandparent: {company_to_assign.name}")
            
            # Opción 5: Buscar en todas las compañías permitidas del usuario
            if not company_to_assign:
                user_companies = self.env.user.company_ids
                if user_companies:
                    # Intentar encontrar la compañía que coincida con el nombre del parent
                    matching_company = user_companies.filtered(
                        lambda c: parent.name and c.name.lower() in parent.name.lower()
                    )
                    if matching_company:
                        company_to_assign = matching_company[0]
                        _logger.info(f"✅ Onchange: Usando compañía por coincidencia de nombre: {company_to_assign.name}")
                    else:
                        # Usar la primera compañía permitida al usuario que no sea la default
                        other_companies = user_companies - self.env.company
                        if other_companies:
                            company_to_assign = other_companies[0]
                            _logger.info(f"✅ Onchange: Usando primera compañía disponible: {company_to_assign.name}")
                        else:
                            company_to_assign = self.env.company
                            _logger.warning(f"⚠️ Onchange: Usando compañía por defecto del usuario: {company_to_assign.name}")
            
            self.internal_company_id = company_to_assign
            
        else:
            self.internal_company_id = False
            _logger.info("🧹 Onchange: Parent_id limpiado, limpiando internal_company_id")
        


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
        """
        Sobrescribir write para:
        1. FORZAR sincronización parent_id -> internal_company_id SIEMPRE
        2. Gestionar cambios de roles
        3. Sincronización bidireccional de relaciones
        """
        
        # ============================================================
        # SINCRONIZACIÓN AGRESIVA parent_id -> internal_company_id
        # ============================================================
        if 'parent_id' in vals:
            parent_id = vals.get('parent_id')
            
            _logger.info(f"🔍 WRITE: Detectado cambio en parent_id: {parent_id}")
            
            if parent_id:
                # Buscar el parent con sudo() para asegurar acceso
                parent = self.env['res.partner'].sudo().browse(parent_id)
                
                # Intentar múltiples fuentes para obtener la compañía
                company_to_assign = False
                
                # Opción 1: Si parent es una compañía (type='company'), usar su company_id
                if parent.is_company and parent.company_id:
                    company_to_assign = parent.company_id.id
                    _logger.info(f"✅ Parent es compañía, usando company_id: {company_to_assign}")
                
                # Opción 2: Si parent tiene internal_company_id custom
                elif hasattr(parent, 'internal_company_id') and parent.internal_company_id:
                    company_to_assign = parent.internal_company_id.id
                    _logger.info(f"✅ Parent tiene internal_company_id: {company_to_assign}")
                
                # Opción 3: Si parent tiene company_id estándar
                elif parent.company_id:
                    company_to_assign = parent.company_id.id
                    _logger.info(f"✅ Parent tiene company_id estándar: {company_to_assign}")
                
                # Opción 4: Buscar en las compañías permitidas del usuario
                else:
                    user_companies = self.env.user.company_ids
                    if user_companies:
                        # Intentar encontrar la compañía que coincida con el nombre del parent
                        matching_company = user_companies.filtered(
                            lambda c: parent.name and c.name.lower() in parent.name.lower()
                        )
                        if matching_company:
                            company_to_assign = matching_company[0].id
                            _logger.info(f"✅ Write: Usando compañía por coincidencia de nombre: {company_to_assign}")
                        else:
                            # Usar la primera compañía permitida al usuario que no sea la default
                            other_companies = user_companies - self.env.company
                            if other_companies:
                                company_to_assign = other_companies[0].id
                                _logger.info(f"✅ Write: Usando primera compañía disponible: {company_to_assign}")
                            else:
                                company_to_assign = self.env.company.id
                                _logger.warning(f"⚠️ Write: Usando compañía por defecto del usuario: {company_to_assign}")
                    else:
                        company_to_assign = self.env.company.id
                        _logger.warning(f"⚠️ Write: Usando compañía por defecto del usuario: {company_to_assign}")
                
                # FORZAR la asignación en vals
                vals['internal_company_id'] = company_to_assign
                _logger.info(f"🎯 FORZANDO internal_company_id en vals: {company_to_assign}")
                
            else:
                # Si se limpia parent_id, limpiar también internal_company_id
                vals['internal_company_id'] = False
                _logger.info("🧹 Parent_id limpiado, limpiando internal_company_id")
        
        # ============================================================
        # LÓGICA DE ROLES (tu código existente)
        # ============================================================
        if 'worker' in vals and not vals['worker']:
            vals['supervisor_externo_id'] = False
            for record in self:
                if record.supervisor_externo_id:
                    externo = record.supervisor_externo_id
                    if record in externo.comerciales_asignados_ids:
                        externo.write({'comerciales_asignados_ids': [(3, record.id)]})
        
        if 'supervisor' in vals and not vals['supervisor']:
            vals['department'] = [(5, 0, 0)]
        
        if 'external' in vals and not vals['external']:
            vals['supervisores_ids'] = [(5, 0, 0)]
            vals['comerciales_asignados_ids'] = [(5, 0, 0)]
        
        # ============================================================
        # EJECUTAR WRITE ORIGINAL
        # ============================================================
        result = super(ResPartner, self).write(vals)
        
        # ============================================================
        # POST-WRITE: VERIFICACIÓN Y CORRECCIÓN FORZADA
        # ============================================================
        # Si había parent_id en vals, verificar que se haya aplicado correctamente
        # ESTA PARTE ES REDUNDANTE Y PUEDE CAUSAR PROBLEMAS - ELIMINAR O COMENTAR
        # if 'parent_id' in vals and vals.get('internal_company_id'):
        #     for record in self:
        #         if record.internal_company_id.id != vals['internal_company_id']:
        #             # Si no se aplicó correctamente, forzar con UPDATE directo a BD
        #             _logger.error(f"❌ internal_company_id no se aplicó correctamente, forzando con SQL...")
        #             self.env.cr.execute("""
        #                 UPDATE res_partner 
        #                 SET internal_company_id = %s 
        #                 WHERE id = %s
        #             """, (vals['internal_company_id'], record.id))
        #             self.env.cr.commit()
        #             _logger.info(f"✅ Forzado por SQL: partner {record.id} -> company {vals['internal_company_id']}")
        
        # ============================================================
        # SINCRONIZACIÓN BIDIRECCIONAL (tu código existente)
        # ============================================================
        if 'supervisor_externo_id' in vals:
            for record in self:
                if record.supervisor_externo_id:
                    externo = record.supervisor_externo_id
                    if record not in externo.comerciales_asignados_ids:
                        externo.write({'comerciales_asignados_ids': [(4, record.id)]})
                
                if record._origin.supervisor_externo_id and \
                record._origin.supervisor_externo_id != record.supervisor_externo_id:
                    old_externo = record._origin.supervisor_externo_id
                    if record in old_externo.comerciales_asignados_ids:
                        old_externo.write({'comerciales_asignados_ids': [(3, record.id)]})
        
        if 'comerciales_asignados_ids' in vals:
            for record in self:
                if record.external:
                    for comercial in record.comerciales_asignados_ids:
                        if comercial.supervisor_externo_id != record:
                            comercial.write({'supervisor_externo_id': record.id})
                    
                    if record._origin.comerciales_asignados_ids:
                        removed_comerciales = record._origin.comerciales_asignados_ids - record.comerciales_asignados_ids
                        for comercial in removed_comerciales:
                            if comercial.supervisor_externo_id == record:
                                comercial.write({'supervisor_externo_id': False})
        
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
                    '&',  # C: Externos asignados
                        ('external', '=', True),
                        ('supervisores_ids', 'in', [current_user.partner_id.id]),
            ]
            return super().search(args + supervisor_domain, offset, limit, order, count)
        elif current_user.partner_id and current_user.partner_id.external:
            # Externo puede verse a sí mismo Y sus comerciales asignados (ahora con Many2many)
            external_domain = [
                '|',
                    ('id', '=', current_user.partner_id.id),
                    ('id', 'in', current_user.partner_id.comerciales_asignados_ids.ids)
            ]
            return super().search(args + external_domain, offset, limit, order, count)
        elif current_user.partner_id and current_user.partner_id.worker:
            # Comercial puede verse a sí mismo 
            worker_domain = [('id', '=', current_user.partner_id.id)]
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
                    '&',  # C: Externos asignados
                        ('external', '=', True),
                        ('supervisores_ids', 'in', [current_user.partner_id.id]),
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
            # Comercial puede verse a sí mismo Y otros comerciales con mismo supervisor externo
            worker_domain = [
                '|',
                    ('id', '=', current_user.partner_id.id),
                    '&',
                        ('worker', '=', True),
                        ('supervisor_externo_id', '=', current_user.partner_id.supervisor_externo_id.id)
            ]
            return super().search_read(domain + worker_domain, fields, offset, limit, order)
        else:
            return super().search_read(domain + [('id', '=', current_user.partner_id.id)], fields, offset, limit, order)