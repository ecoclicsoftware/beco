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
        domain="[('worker', '=', True), ('department', 'in', department), ('internal_company_id', '=', internal_company_id)]",  # 🆕 DOMINIO COMPLETO
        help='Comerciales asignados a este supervisor externo (solo de su mismo departamento y empresa)'
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
    
    comercial_asignado_id = fields.Many2one(
        'res.partner',
        string='Comercial Asignado',
        domain="[('worker', '=', True), ('department', 'in', department), ('internal_company_id', '=', internal_company_id)]",
        help='Comercial responsable de este cliente',
        tracking=True,
        ondelete='restrict'
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
               
                
    @api.constrains('comercial_asignado_id', 'department', 'internal_company_id')
    def _check_comercial_asignado_same_department_company(self):
        """Validar que el comercial asignado sea del mismo departamento y empresa"""
        for record in self:
            if record.comercial_asignado_id:
                comercial = record.comercial_asignado_id
                
                # Verificar que sea comercial
                if not comercial.worker:
                    raise ValidationError(
                        f"Solo puedes asignar usuarios con rol 'Comercial'. "
                        f"{comercial.name} no es un comercial."
                    )
                
                # Verificar misma empresa
                if record.internal_company_id and comercial.internal_company_id:
                    if record.internal_company_id != comercial.internal_company_id:
                        raise ValidationError(
                            f"El comercial asignado debe ser de la misma empresa.\n"
                            f"Cliente: {record.internal_company_id.name}\n"
                            f"Comercial: {comercial.internal_company_id.name}"
                        )
                
                # Verificar mismo departamento (al menos uno en común)
                if record.department and comercial.department:
                    departamentos_comunes = record.department & comercial.department
                    if not departamentos_comunes:
                        raise ValidationError(
                            f"El comercial asignado debe pertenecer al menos a uno de los departamentos del cliente.\n"
                            f"Departamentos del cliente: {record.department.mapped('name')}\n"
                            f"Departamentos del comercial: {comercial.department.mapped('name')}"
                        )
    @api.constrains('company_type', 'is_company')
    def _check_company_type_individual(self):
        """Forzar que todos los contactos sean individuos"""
        for record in self:
            if record.company_type != 'person' or record.is_company:
                raise ValidationError(
                    "❌ ERROR: Solo se permiten contactos de tipo 'Individuo'.\n"
                    "No se pueden crear contactos de tipo 'Empresa' en este sistema."
                )
    
    @api.constrains('external', 'comerciales_asignados_ids')
    def _check_comerciales_mismo_departamento_externo(self):
        """Validar que los comerciales asignados a un externo sean de su mismo departamento y empresa"""
        for rec in self:
            if rec.external and rec.comerciales_asignados_ids:
                # Verificar que cada comercial tenga al menos un departamento en común y misma empresa
                for comercial in rec.comerciales_asignados_ids:
                    if not comercial.department:
                        raise ValidationError(
                            f"El comercial {comercial.name} no tiene departamento asignado."
                        )
                    
                    if not comercial.internal_company_id:
                        raise ValidationError(
                            f"El comercial {comercial.name} no tiene empresa asignada."
                        )
                    
                    # Verificar mismo departamento
                    departamentos_comunes = rec.department & comercial.department
                    if not departamentos_comunes:
                        raise ValidationError(
                            f"El comercial {comercial.name} no pertenece a los departamentos "
                            f"del externo {rec.name}."
                        )
                    
                    # Verificar misma empresa
                    if rec.internal_company_id != comercial.internal_company_id:
                        raise ValidationError(
                            f"El comercial {comercial.name} no pertenece a la misma empresa "
                            f"que el externo {rec.name}."
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
        # FORZAR TIPO INDIVIDUO
        # -------------------------
        vals['company_type'] = 'person'
        vals['is_company'] = False
        _logger.info(f"✅ Forzando company_type='person' e is_company=False")
        
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
            _logger.info(f"   - comerciales_asignados_ids: {partner.comerciales_asignados_ids.ids}")
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
        
        # 🆕 EXTERNO creando COMERCIAL - AUTO-ASIGNACIÓN
        elif current_user.partner_id.external and vals.get('worker'):
            _logger.info(f"🔄 EXTERNO creando COMERCIAL - Procesando auto-asignación")
            
            # Verificar que el externo tenga supervisores asignados
            creator_partner = self.env['res.partner'].sudo().browse(current_user.partner_id.id)
            if not creator_partner.supervisores_ids:
                raise ValidationError(
                    "No puedes crear un comercial porque no tienes supervisores asignados. "
                    "Contacta con un administrador."
                )
            
            # 🆕 ASIGNAR AUTOMÁTICAMENTE DEPARTAMENTO Y EMPRESA DEL EXTERNO
            if not vals.get('department') and creator_partner.department:
                vals['department'] = [(6, 0, creator_partner.department.ids)]
                _logger.info(f"✅ Asignando departamentos del externo: {creator_partner.department.ids}")
            
            if not vals.get('internal_company_id') and creator_partner.internal_company_id:
                vals['internal_company_id'] = creator_partner.internal_company_id.id
                _logger.info(f"✅ Asignando empresa del externo: {vals['internal_company_id']}")
            
            # 🆕 VERIFICAR QUE EL COMERCIAL TENGA DEPARTAMENTO Y EMPRESA
            if not vals.get('department'):
                raise ValidationError(
                    "El comercial debe tener departamento asignado. "
                    "Como externo, debes tener departamento para crear comerciales."
                )
            
            if not vals.get('internal_company_id'):
                raise ValidationError(
                    "El comercial debe tener empresa asignada. "
                    "Como externo, debes tener empresa para crear comerciales."
                )
        
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
        # AUTO-ASIGNACIÓN DE COMERCIAL A CLIENTES
        # -------------------------
        # Si el creador es un comercial y está creando un cliente (sin roles)
        if (current_user.partner_id and 
            current_user.partner_id.worker and 
            not vals.get('worker') and 
            not vals.get('supervisor') and 
            not vals.get('external')):
            
            # Auto-asignar al comercial que lo crea
            if not vals.get('comercial_asignado_id'):
                vals['comercial_asignado_id'] = current_user.partner_id.id
                _logger.info(
                    f"✅ Auto-asignando comercial '{current_user.partner_id.name}' "
                    f"(ID: {current_user.partner_id.id}) al cliente"
                )
        
        # -------------------------
        # 🆕 AUTO-ASIGNACIÓN DEL COMERCIAL AL EXTERNO
        # -------------------------
        # Si el creador es un externo y está creando un comercial
        if (current_user.partner_id and 
            current_user.partner_id.external and 
            vals.get('worker')):
            
            _logger.info(f"🎯 EXTERNO creando COMERCIAL - Preparando auto-asignación")
            
            # Crear el registro primero
            _logger.info(f"📦 Valores FINALES antes de crear: {vals}")
            new_comercial = super(ResPartner, self).create(vals)
            
            # Auto-asignar el nuevo comercial al externo que lo creó
            try:
                _logger.info(f"🔄 Auto-asignando comercial {new_comercial.name} (ID: {new_comercial.id}) al externo {current_user.partner_id.name}")
                
                # Usar sudo() para evitar problemas de permisos
                externo_partner = self.env['res.partner'].sudo().browse(current_user.partner_id.id)
                
                # Agregar el nuevo comercial a la lista de comerciales asignados del externo
                externo_partner.write({
                    'comerciales_asignados_ids': [(4, new_comercial.id)]
                })
                
                _logger.info(f"✅ Auto-asignación EXITOSA:")
                _logger.info(f"   - Comercial: {new_comercial.name} (ID: {new_comercial.id})")
                _logger.info(f"   - Externo: {externo_partner.name} (ID: {externo_partner.id})")
                _logger.info(f"   - Comerciales asignados ahora: {externo_partner.comerciales_asignados_ids.ids}")
                
            except Exception as e:
                _logger.error(f"❌ ERROR en auto-asignación: {e}")
                # No hacemos rollback porque el comercial ya se creó exitosamente
                # Solo logueamos el error
            
            return new_comercial
        
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
        
        # 🆕 BLOQUEAR CAMBIO A COMPAÑÍA - PERO NO LANZAR ERROR, SOLO FORZAR
        if 'company_type' in vals and vals['company_type'] != 'person':
            _logger.warning(f"🚫 Intento de cambiar company_type a {vals['company_type']} - Forzando a 'person'")
            vals['company_type'] = 'person'
        
        if 'is_company' in vals and vals['is_company']:
            _logger.warning(f"🚫 Intento de cambiar is_company a True - Forzando a False")
            vals['is_company'] = False
        
        # Log del estado actual antes de escribir
        for record in self:
            _logger.info(f"📊 Estado actual ANTES de {record.name}:")
            _logger.info(f"   - ID: {record.id}")
            _logger.info(f"   - worker: {record.worker}")
            _logger.info(f"   - supervisor: {record.supervisor}")  
            _logger.info(f"   - external: {record.external}")
            _logger.info(f"   - comercial_asignado_id: {record.comercial_asignado_id.id if record.comercial_asignado_id else 'VACÍO'}")
            _logger.info(f"   - comerciales_asignados_ids: {record.comerciales_asignados_ids.ids}")
            _logger.info(f"   - supervisores_ids: {record.supervisores_ids.ids}")
            _logger.info(f"   - department: {record.department.ids}")
        
        # Si estamos intentando asignar comerciales, log específico
        if 'comerciales_asignados_ids' in vals:
            _logger.info(f"🎯 INTENTANDO ASIGNAR COMERCIALES: {vals['comerciales_asignados_ids']}")
        
        if 'comercial_asignado_id' in vals:
            _logger.info(f"🎯 INTENTANDO ASIGNAR COMERCIAL: {vals['comercial_asignado_id']}")
        
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
        
        # Detectar cambios de rol REALES (de False a True)
        records_to_clear = self.env['res.partner']
        
        for record in self:
            # SOLO limpiar si hay un cambio REAL de rol (de False a True)
            if vals.get('worker') == True and not record.worker:
                _logger.info(f"🔄 {record.name} cambiando a WORKER (era False, ahora True)")
                records_to_clear += record
            
            elif vals.get('supervisor') == True and not record.supervisor:
                _logger.info(f"🔄 {record.name} cambiando a SUPERVISOR (era False, ahora True)")
                records_to_clear += record
                
            elif vals.get('external') == True and not record.external:
                _logger.info(f"🔄 {record.name} cambiando a EXTERNAL (era False, ahora True)")
                records_to_clear += record
        
        if records_to_clear:
            _logger.info(f"🚨 REGISTROS QUE CAMBIAN DE ROL: {records_to_clear.mapped('name')}")
        
        # Solo aplicar limpieza si HAY registros que realmente cambian de rol
        if records_to_clear:
            clear_vals = {}
            
            if vals.get('worker') == True:
                clear_vals.update({
                    'supervisor': False,
                    'external': False,
                    'supervisores_ids': [(5, 0, 0)],
                    'comerciales_asignados_ids': [(5, 0, 0)],
                    'comercial_asignado_id': False,  # Limpiar comercial asignado al cambiar a worker
                })
                _logger.info(f"🔄 Limpiando campos para cambio a WORKER: {clear_vals}")
            elif vals.get('supervisor') == True:
                clear_vals.update({
                    'worker': False,
                    'external': False,
                    'supervisor_externo_id': False,
                    'comerciales_asignados_ids': [(5, 0, 0)],
                    'comercial_asignado_id': False,  # Limpiar comercial asignado al cambiar a supervisor
                })
                _logger.info(f"🔄 Limpiando campos para cambio a SUPERVISOR: {clear_vals}")
            elif vals.get('external') == True:
                clear_vals.update({
                    'worker': False,
                    'supervisor': False,
                    'department': [(5, 0, 0)],
                    'company_id': False,
                    'supervisor_externo_id': False,
                    'comercial_asignado_id': False,  # Limpiar comercial asignado al cambiar a external
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
                super(ResPartner, records_to_clear).write(clear_vals)
                
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
                
                # Si hay registros restantes que NO cambiaron de rol, escribirles normalmente
                remaining_records = self - records_to_clear
                if remaining_records:
                    _logger.info(f"🔄 Escribiendo registros restantes sin cambio de rol: {remaining_records.mapped('name')}")
                    super(ResPartner, remaining_records).write(vals)
                
                # Log del estado DESPUÉS
                for record in self:
                    _logger.info(f"📊 Estado actual DESPUÉS de {record.name}:")
                    _logger.info(f"   - worker: {record.worker}")
                    _logger.info(f"   - supervisor: {record.supervisor}")  
                    _logger.info(f"   - external: {record.external}")
                    _logger.info(f"   - comercial_asignado_id: {record.comercial_asignado_id.id if record.comercial_asignado_id else 'VACÍO'}")
                    _logger.info(f"   - comerciales_asignados_ids: {record.comerciales_asignados_ids.ids}")
                    _logger.info(f"   - supervisores_ids: {record.supervisores_ids.ids}")
                
                _logger.info(f"✅ WRITE COMPLETADO para {self.mapped('name')}")
                return True
        
        # Para registros que NO cambian de rol, escribir normalmente
        _logger.info("🔄 Ejecutando WRITE normal (sin cambio de rol)")
        result = super(ResPartner, self).write(vals)
        
        # 🆕 DEBUG: Verificar si el campo se guardó realmente
        self.env.cr.flush()  # Forzar flush a la base de datos
        for record in self:
            # Leer directamente de la base de datos
            self.env.cr.execute("""
                SELECT id, name, comercial_asignado_id 
                FROM res_partner 
                WHERE id = %s
            """, (record.id,))
            db_row = self.env.cr.fetchone()
            _logger.info(f"🔍 VERIFICACIÓN EN BD para {record.name} (ID {record.id}):")
            _logger.info(f"   - En caché ORM: comercial_asignado_id = {record.comercial_asignado_id.id if record.comercial_asignado_id else 'NULL'}")
            _logger.info(f"   - En BD PostgreSQL: comercial_asignado_id = {db_row[2] if db_row else 'NO ENCONTRADO'}")

        # Log del estado DESPUÉS
        for record in self:
            _logger.info(f"📊 Estado actual DESPUÉS de {record.name}:")
            _logger.info(f"   - worker: {record.worker}")
            _logger.info(f"   - supervisor: {record.supervisor}")  
            _logger.info(f"   - external: {record.external}")
            _logger.info(f"   - comercial_asignado_id: {record.comercial_asignado_id.id if record.comercial_asignado_id else 'VACÍO'}")
            _logger.info(f"   - comerciales_asignados_ids: {record.comerciales_asignados_ids.ids}")
            _logger.info(f"   - supervisores_ids: {record.supervisores_ids.ids}")
            _logger.info(f"   - department: {record.department.ids}")

        _logger.info(f"✅ WRITE COMPLETADO para {self.mapped('name')}")
        return result



    # -------------------------
    # FILTROS DE VISIBILIDAD
    # -------------------------

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Filtros personalizados de visibilidad por rol.
        """
        current_user = self.env.user
        
        # 🆕 CRÍTICO: Evitar recursión en cálculos computados y operaciones del sistema
        if (self.env.context.get('skip_custom_search') or 
            self.env.context.get('active_test') is False or
            self.env.context.get('computing_opportunity_count') or
            '_compute_' in str(self.env.context)):
            _logger.info(f"🔓 Contexto especial detectado - búsqueda sin restricciones")
            return super(ResPartner, self).search(args, offset=offset, limit=limit, order=order, count=count)

        # IMPORTANTE: Verificar si ya estamos en un contexto de bypass
        if self.env.context.get('skip_custom_search'):
            _logger.info(f"🔓 Bypass activado - búsqueda sin restricciones")
            return super(ResPartner, self).search(args, offset=offset, limit=limit, order=order, count=count)

        _logger.info(f"===== SEARCH llamado por usuario {current_user.name} (ID {current_user.id}) =====")
        _logger.info(f"- Partner ID: {current_user.partner_id.id if current_user.partner_id else None}")
        
        # Admin ve todo
        if self.env.user._is_admin():
            _logger.info("Es admin REAL - Sin restricciones")
            return super(ResPartner, self).search(args, offset, limit, order, count)

        if not current_user.partner_id:
            _logger.warning(f"Usuario sin partner_id asociado")
            return super(ResPartner, self).search(args + [('id', '=', False)], offset, limit, order, count)

        partner = current_user.partner_id
        _logger.info(f"- Roles: worker={partner.worker}, supervisor={partner.supervisor}, external={partner.external}")

        # COMERCIAL
        if partner.worker:
            _logger.info(f"COMERCIAL search - Usuario {partner.name} (ID {partner.id})")
            
            # 🆕 LIMPIAR args que restringen por ID
            clean_args = []
            for item in args:
                if isinstance(item, tuple) and len(item) == 3:
                    field, operator, value = item
                    if field == 'id' and operator == 'in':
                        _logger.info(f"🚫 Ignorando restricción externa: {item}")
                        continue
                clean_args.append(item)
            
            worker_domain = [
                '|',
                ('id', '=', partner.id),
                ('comercial_asignado_id', '=', partner.id)
            ]
            
            _logger.info(f"Args originales: {args}")
            _logger.info(f"Args limpiados: {clean_args}")
            _logger.info(f"Worker domain: {worker_domain}")
            
            # Llamar a super() con args limpiados y sudo para bypassear record rules
            result = super(ResPartner, self.sudo()).search(clean_args + worker_domain, offset=offset, limit=limit, order=order, count=count)
            
            _logger.info(f"Resultado comercial: {result if count else len(result)} registros")
            if not count:
                _logger.info(f"- IDs encontrados: {result.ids}")
            return result

        # SUPERVISOR
        if partner.supervisor:
            _logger.info(f"SUPERVISOR search - Usuario {partner.name}")
            _logger.info(f"- Departamentos: {partner.department.mapped('name')} (IDs {partner.department.ids})")
            _logger.info(f"- Empresa: {partner.internal_company_id.name if partner.internal_company_id else None}")

            # Obtener IDs de comerciales (CON CONTEXTO SKIP)
            comerciales_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Comerciales encontrados: {len(comerciales_ids)} - IDs: {comerciales_ids}")

            # Obtener IDs de clientes creados por comerciales (CON CONTEXTO SKIP)
            clientes_por_comerciales = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('create_uid.partner_id', 'in', comerciales_ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids

            # Obtener clientes creados por el supervisor mismo (CON CONTEXTO SKIP)
            clientes_por_supervisor = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('create_uid', '=', current_user.id),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Clientes creados por este supervisor: {len(clientes_por_supervisor)}")

            # 🆕 OBTENER EXTERNOS QUE TIENE ASIGNADOS ESTE SUPERVISOR
            externos_supervisados_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('external', '=', True),
                ('supervisores_ids', 'in', [partner.id])
            ]).ids
            _logger.info(f"- Externos supervisados: {len(externos_supervisados_ids)} - IDs: {externos_supervisados_ids}")

            # 🆕 OBTENER COMERCIALES DE LOS EXTERNOS SUPERVISADOS
            comerciales_de_externos = []
            clientes_de_externos = []
            
            if externos_supervisados_ids:
                # Comerciales asignados a los externos supervisados
                for externo in self.env['res.partner'].browse(externos_supervisados_ids):
                    comerciales_de_externos.extend(externo.comerciales_asignados_ids.ids)
                
                comerciales_de_externos = list(set(comerciales_de_externos))
                _logger.info(f"- Comerciales de externos supervisados: {len(comerciales_de_externos)} - IDs: {comerciales_de_externos}")
                
                # Clientes de los comerciales de los externos supervisados
                if comerciales_de_externos:
                    clientes_de_externos = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                        ('worker', '=', False),
                        ('supervisor', '=', False),
                        ('external', '=', False),
                        ('create_uid.partner_id', 'in', comerciales_de_externos)
                    ]).ids
                    _logger.info(f"- Clientes de comerciales de externos: {len(clientes_de_externos)}")

            # Combinar todos los tipos de clientes
            todos_clientes_ids = list(set(clientes_por_comerciales + clientes_por_supervisor + clientes_de_externos))
            _logger.info(f"- Total clientes visibles: {len(todos_clientes_ids)}")

            # 🆕 CONSTRUIR DOMINIO AMPLIADO PARA SUPERVISOR - ESTRUCTURA CORREGIDA
            supervisor_domain = [
                '|',  # OR principal
                '|',  # Segundo nivel OR
                '|',  # Tercer nivel OR  
                '|',  # Cuarto nivel OR
                '|',  # Quinto nivel OR
                # Opción 1: El propio supervisor
                ('id', '=', partner.id),
                # Opción 2: Comerciales de su departamento/empresa
                '&', '&',
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id),
                # Opción 3: Clientes de su equipo
                '&', '&', '&',
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('id', 'in', todos_clientes_ids if todos_clientes_ids else [False]),
                # Opción 4: Externos que supervisa
                '&',
                ('external', '=', True),
                ('id', 'in', externos_supervisados_ids),
                # Opción 5: Comerciales de los externos que supervisa
                '&',
                ('worker', '=', True),
                ('id', 'in', comerciales_de_externos if comerciales_de_externos else [False]),
                # Opción 6: Clientes de los comerciales de los externos que supervisa
                '&', '&', '&',
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('id', 'in', clientes_de_externos if clientes_de_externos else [False])
            ]

            _logger.info(f"Aplicando dominio supervisor ampliado")
            result = super(ResPartner, self).search(args + supervisor_domain, offset, limit, order, count)
            _logger.info(f"Resultado: {result if count else len(result)} registros")
            return result

        # EXTERNO
        if partner.external:
            _logger.info(f"EXTERNO search - Usuario {partner.name}")
            
            # 🆕 OBTENER CLIENTES DE LOS COMERCIALES ASIGNADOS (solo de misma empresa)
            comerciales_asignados_ids = partner.comerciales_asignados_ids.ids
            _logger.info(f"- Comerciales asignados: {comerciales_asignados_ids}")
            
            if comerciales_asignados_ids:
                # Obtener IDs de clientes creados por los comerciales asignados (CON CONTEXTO SKIP)
                clientes_de_comerciales = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                    ('worker', '=', False),
                    ('supervisor', '=', False),
                    ('external', '=', False),
                    ('create_uid.partner_id', 'in', comerciales_asignados_ids),
                    ('internal_company_id', '=', partner.internal_company_id.id)  # 🆕 Solo clientes de misma empresa
                ]).ids
                _logger.info(f"- Clientes de comerciales asignados: {len(clientes_de_comerciales)} - IDs: {clientes_de_comerciales}")
            else:
                clientes_de_comerciales = []
                _logger.info(f"- No hay comerciales asignados")
            
            # 🆕 DOMINIO PARA EXTERNOS AMPLIADO - CORREGIDO
            external_domain = [
                '|',  # Primer OR
                '|',  # Segundo OR
                ('id', '=', partner.id),  # Opción 1: El propio externo
                ('id', 'in', comerciales_asignados_ids),  # Opción 2: Comerciales asignados
                '&', '&', '&', '&',  # Opción 3: Clientes de comerciales (todos estos deben ser True)
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('internal_company_id', '=', partner.internal_company_id.id),
                ('id', 'in', clientes_de_comerciales if clientes_de_comerciales else [False])
            ]
            
            _logger.info(f"🔍 Aplicando dominio externo ampliado:")
            _logger.info(f"   - Externo propio: {partner.id}")
            _logger.info(f"   - Comerciales asignados: {len(comerciales_asignados_ids)}")
            _logger.info(f"   - Clientes de comerciales: {len(clientes_de_comerciales)}")
            
            result = super(ResPartner, self).search(args + external_domain, offset, limit, order, count)
            _logger.info(f"✅ Resultado externo: {result if count else len(result)} registros")
            if not count:
                _logger.info(f"- IDs encontrados: {result.ids}")
            return result

        # OTRO ROL
        _logger.info("Usuario sin rol específico")
        return super(ResPartner, self).search(args + [('id', '=', partner.id)], offset, limit, order, count)




    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Filtros personalizados de visibilidad por rol.
        """
        if domain is None:
            domain = []

        current_user = self.env.user
        
        # 🆕 CRÍTICO: Evitar recursión en cálculos computados
        if (self.env.context.get('skip_custom_search') or 
            self.env.context.get('active_test') is False or
            self.env.context.get('computing_opportunity_count') or
            '_compute_' in str(self.env.context)):
            _logger.info(f"🔓 Contexto especial detectado en search_read - sin restricciones")
            return super(ResPartner, self).search_read(domain, fields, offset, limit, order)

        _logger.info(f"SEARCH_READ llamado por usuario {current_user.name}")

        # Admin ve todo
        if self.env.is_admin():
            _logger.info("Es admin - Sin restricciones")
            return super(ResPartner, self).search_read(domain, fields, offset, limit, order)

        if not current_user.partner_id:
            _logger.warning(f"Usuario sin partner_id asociado")
            return super(ResPartner, self).search_read(domain + [('id', '=', False)], fields, offset, limit, order)

        partner = current_user.partner_id
        _logger.info(f"- Roles: worker={partner.worker}, supervisor={partner.supervisor}, external={partner.external}")

        # COMERCIAL
        if partner.worker:
            _logger.info(f"COMERCIAL search_read - Usuario {partner.name}")
            worker_domain = [
                '|', 
                ('id', '=', partner.id),
                ('comercial_asignado_id', '=', partner.id)
            ]
            _logger.info(f"Worker domain: {worker_domain}")
            return super(ResPartner, self).search_read(domain + worker_domain, fields, offset, limit, order)

        # SUPERVISOR
        if partner.supervisor:
            _logger.info(f"SUPERVISOR search_read - Usuario {partner.name}")
            
            # Obtener IDs de comerciales
            comerciales_ids = self.env['res.partner'].sudo().search([
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Comerciales encontrados: {len(comerciales_ids)}")

            # Obtener IDs de clientes creados por comerciales
            clientes_por_comerciales = self.env['res.partner'].sudo().search([
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('create_uid.partner_id', 'in', comerciales_ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids

            # Obtener clientes creados por el supervisor mismo
            clientes_por_supervisor = self.env['res.partner'].sudo().search([
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('create_uid', '=', current_user.id),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids

            # 🆕 OBTENER EXTERNOS QUE TIENE ASIGNADOS ESTE SUPERVISOR
            externos_supervisados_ids = self.env['res.partner'].sudo().search([
                ('external', '=', True),
                ('supervisores_ids', 'in', [partner.id])
            ]).ids
            _logger.info(f"- Externos supervisados: {len(externos_supervisados_ids)}")

            # 🆕 OBTENER COMERCIALES DE LOS EXTERNOS SUPERVISADOS
            comerciales_de_externos = []
            clientes_de_externos = []
            
            if externos_supervisados_ids:
                # Comerciales asignados a los externos supervisados
                for externo in self.env['res.partner'].browse(externos_supervisados_ids):
                    comerciales_de_externos.extend(externo.comerciales_asignados_ids.ids)
                
                comerciales_de_externos = list(set(comerciales_de_externos))
                _logger.info(f"- Comerciales de externos supervisados: {len(comerciales_de_externos)}")
                
                # Clientes de los comerciales de los externos supervisados
                if comerciales_de_externos:
                    clientes_de_externos = self.env['res.partner'].sudo().search([
                        ('worker', '=', False),
                        ('supervisor', '=', False),
                        ('external', '=', False),
                        ('create_uid.partner_id', 'in', comerciales_de_externos)
                    ]).ids
                    _logger.info(f"- Clientes de comerciales de externos: {len(clientes_de_externos)}")

            # Combinar todos los tipos de clientes
            todos_clientes_ids = list(set(clientes_por_comerciales + clientes_por_supervisor + clientes_de_externos))
            _logger.info(f"- Total clientes visibles: {len(todos_clientes_ids)}")

            # 🆕 CONSTRUIR DOMINIO AMPLIADO PARA SUPERVISOR - ESTRUCTURA CORREGIDA
            supervisor_domain = [
                '|',  # OR principal
                '|',  # Segundo nivel OR
                '|',  # Tercer nivel OR  
                '|',  # Cuarto nivel OR
                '|',  # Quinto nivel OR
                # Opción 1: El propio supervisor
                ('id', '=', partner.id),
                # Opción 2: Comerciales de su departamento/empresa
                '&', '&',
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id),
                # Opción 3: Clientes de su equipo
                '&', '&', '&',
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('id', 'in', todos_clientes_ids if todos_clientes_ids else [False]),
                # Opción 4: Externos que supervisa
                '&',
                ('external', '=', True),
                ('id', 'in', externos_supervisados_ids),
                # Opción 5: Comerciales de los externos que supervisa
                '&',
                ('worker', '=', True),
                ('id', 'in', comerciales_de_externos if comerciales_de_externos else [False]),
                # Opción 6: Clientes de los comerciales de los externos que supervisa
                '&', '&', '&',
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('id', 'in', clientes_de_externos if clientes_de_externos else [False])
            ]

            _logger.info(f"Aplicando dominio supervisor ampliado en search_read")
            return super(ResPartner, self).search_read(domain + supervisor_domain, fields, offset, limit, order)

        # EXTERNO
        if partner.external:
            _logger.info(f"EXTERNO search_read - Usuario {partner.name}")
            
            # 🆕 OBTENER CLIENTES DE LOS COMERCIALES ASIGNADOS (solo de misma empresa)
            comerciales_asignados_ids = partner.comerciales_asignados_ids.ids
            _logger.info(f"- Comerciales asignados: {comerciales_asignados_ids}")
            
            if comerciales_asignados_ids:
                # Obtener IDs de clientes creados por los comerciales asignados
                clientes_de_comerciales = self.env['res.partner'].sudo().search([
                    ('worker', '=', False),
                    ('supervisor', '=', False),
                    ('external', '=', False),
                    ('create_uid.partner_id', 'in', comerciales_asignados_ids),
                    ('internal_company_id', '=', partner.internal_company_id.id)  # 🆕 Solo clientes de misma empresa
                ]).ids
                _logger.info(f"- Clientes de comerciales asignados: {len(clientes_de_comerciales)}")
            else:
                clientes_de_comerciales = []
            
            # 🆕 DOMINIO PARA EXTERNOS AMPLIADO - CORREGIDO
            external_domain = [
                '|',  # Primer OR
                '|',  # Segundo OR  
                ('id', '=', partner.id),  # Opción 1: El propio externo
                ('id', 'in', comerciales_asignados_ids),  # Opción 2: Comerciales asignados
                '&', '&', '&', '&',  # Opción 3: Clientes de comerciales (todos estos deben ser True)
                ('worker', '=', False),
                ('supervisor', '=', False),
                ('external', '=', False),
                ('internal_company_id', '=', partner.internal_company_id.id),
                ('id', 'in', clientes_de_comerciales if clientes_de_comerciales else [False])
            ]
            
            _logger.info(f"🔍 Aplicando dominio externo ampliado en search_read")
            _logger.info(f"   - Externo: {partner.id}")
            _logger.info(f"   - Comerciales asignados: {len(comerciales_asignados_ids)}")
            _logger.info(f"   - Clientes de comerciales: {len(clientes_de_comerciales)}")
            
            return super(ResPartner, self).search_read(domain + external_domain, fields, offset, limit, order)

        # OTRO ROL
        _logger.info("Usuario sin rol específico")
        return super(ResPartner, self).search_read(domain + [('id', '=', partner.id)], fields, offset, limit, order)