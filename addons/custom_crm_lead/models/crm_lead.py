from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def name_get(self):
        """Personalizar la visualización de productos para mostrar nombre - precio"""
        result = []
        for product in self:
            # Formatear el precio con separadores de miles y decimales
            price_formatted = "{:,.2f}".format(product.list_price).replace(",", "X").replace(".", ",").replace("X", ".")
            name = f"{product.name} - {price_formatted} €"
            result.append((product.id, name))
        return result


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    product_ids = fields.Many2many(
        'product.product',
        string='Productos',
        relation='crm_lead_product_rel'
    )
    commercial_department = fields.Char(
        string='Departamento Comercial',
        compute='_compute_commercial_department',
        store=True,
        help="Departamento del comercial asignado a esta oportunidad"
    )
    tag_ids = fields.Many2many(
        string='Etiquetas',
        help='Etiquetas relacionadas con esta oportunidad',
        readonly=True
    )
    
    # Campo para calcular el ingreso esperado desde los productos
    expected_revenue = fields.Float(
        string='Ingreso Esperado',
        compute='_compute_expected_revenue_from_products',
        store=True,
        readonly=False,  # Permitir edición manual si es necesario
        help="Ingreso esperado calculado automáticamente desde los productos seleccionados"
    )
    
    #FILTRO CRM DEPARTAMENTOS 
    
    @api.depends('user_id', 'user_id.department')
    def _compute_commercial_department(self):
        """Calcula y asigna el departamento del comercial automáticamente"""
        for lead in self:
            if lead.user_id and lead.user_id.department:
                lead.commercial_department = lead.user_id.department
            else:
                lead.commercial_department = False
    
    @api.depends('product_ids', 'product_ids.list_price')
    def _compute_expected_revenue_from_products(self):
        """Calcula el ingreso esperado sumando el precio de los productos seleccionados"""
        for lead in self:
            total_revenue = 0.0
            for product in lead.product_ids:
                # Sumar el precio de lista de cada producto
                total_revenue += product.list_price
            lead.expected_revenue = total_revenue
    
    def _get_or_create_department_tag(self, department_name, color=1):
        """Busca o crea una etiqueta para el departamento"""
        tag_model = self.env['crm.tag']
        tag = tag_model.search([('name', '=', department_name)], limit=1)
        
        if not tag:
            tag = tag_model.create({
                'name': department_name,
                'color': color
            })
        
        return tag
    
    def _assign_department_tag(self):
        """Asigna etiquetas de departamento basado en el comercial"""
        for lead in self:
            # Limpiar etiquetas de departamento existentes
            department_tags = self.env['crm.tag'].search([
                ('name', 'in', ['Médico', 'Estética', 'medico', 'estetica'])
            ])
            lead.tag_ids = [(3, tag.id) for tag in department_tags]

            # Obtener departamento del comercial asignado
            dept = (lead.user_id.department or getattr(lead.user_id.partner_id, 'department', False))
            if dept:
                dept_lower = dept.lower()
                if any(word in dept_lower for word in ['médic', 'medic']):
                    tag = self._get_or_create_department_tag('Médico', 1)
                    lead.tag_ids = [(4, tag.id)]
                elif any(word in dept_lower for word in ['estét', 'estet']):
                    tag = self._get_or_create_department_tag('Estética', 2)
                    lead.tag_ids = [(4, tag.id)]
    
    @api.model
    def create(self, vals):
        """Al crear lead, asignar departamento y etiqueta automáticamente"""
        # Si no hay user_id, usar usuario actual
        if 'user_id' not in vals:
            vals['user_id'] = self.env.user.id
            
        # Auto-completar email y teléfono si se proporciona partner_id
        if vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            if 'email_from' not in vals:
                vals['email_from'] = (partner.email or '').strip()
            if 'phone' not in vals:
                vals['phone'] = (partner.phone or partner.mobile or '').strip()
        
        lead = super().create(vals)
        lead._assign_department_tag()
        return lead
    
    def write(self, vals):
        """Al modificar lead, actualizar departamento y etiquetas"""
        # Si se está cambiando el partner, actualizar email y teléfono
        if 'partner_id' in vals:
            partner_id = vals['partner_id']
            if partner_id:
                partner = self.env['res.partner'].browse(partner_id)
                if 'email_from' not in vals:
                    vals['email_from'] = (partner.email or '').strip()
                if 'phone' not in vals:
                    vals['phone'] = (partner.phone or partner.mobile or '').strip()
            else:
                if 'email_from' not in vals:
                    vals['email_from'] = False
                if 'phone' not in vals:
                    vals['phone'] = False
        
        result = super().write(vals)
        
        # Actualizar etiquetas si cambió el comercial o el partner
        if 'user_id' in vals or 'partner_id' in vals:
            self._assign_department_tag()
            
        return result
    
    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Actualizar en tiempo real cuando se cambia comercial"""
        self._assign_department_tag()
        
    @api.onchange('partner_id')
    def _onchange_partner_autofill(self):
        """Auto-completar email y teléfono desde el partner"""
        partner = self.partner_id
        if partner:
            self.email_from = (partner.email or '').strip()
            # Prioriza teléfono fijo, si no hay usa móvil
            self.phone = (partner.phone or partner.mobile or '').strip()
        else:
            self.email_from = False
            self.phone = False
    
    @api.onchange('product_ids')
    def _onchange_product_ids(self):
        """Actualizar ingreso esperado cuando cambian los productos"""
        # Forzar el cálculo del ingreso esperado
        self._compute_expected_revenue_from_products()
        
     ################################################

    # Los campos email_from y phone ya existen en el modelo base, 
    # solo los heredamos para agregar readonly
    email_from = fields.Char(readonly=True)
    phone = fields.Char(readonly=True) 

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Filtrar leads/oportunidades según jerarquía: Admin > Supervisor > Trabajador"""
        current_user = self.env.user
        
        # Debug: Log para verificar qué está pasando
        _logger.info(f"CRM search called by user: {current_user.name}")
        _logger.info(f"User is admin: {current_user.has_group('base.group_system')}")
        _logger.info(f"User partner supervisor: {current_user.partner_id.supervisor if current_user.partner_id else 'No partner'}")
        _logger.info(f"User partner worker: {current_user.partner_id.worker if current_user.partner_id else 'No partner'}")
        _logger.info(f"User department: {current_user.partner_id.department if current_user.partner_id else 'No partner'}")
        
        # Si el usuario NO es administrador, aplicar filtros según rol
        if not current_user.has_group('base.group_system') and current_user.partner_id:
            
            # Si es supervisor, puede ver leads de su departamento Y leads asignados a él
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                _logger.info("Applying supervisor filter")
                # Buscar todos los usuarios trabajadores del mismo departamento
                department_partners = self.env['res.partner'].search([
                    ('department', '=', current_user.partner_id.department),
                    ('worker', '=', True)
                ])
                
                # Obtener los user_ids de estos partners
                department_user_ids = []
                for partner in department_partners:
                    user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
                    if user:
                        department_user_ids.append(user.id)
                
                # Incluir al supervisor también
                department_user_ids.append(current_user.id)
                
                # FILTRO CORREGIDO: Supervisor puede ver:
                # 1. Leads de su departamento (creados por cualquier usuario del depto)
                # 2. Leads asignados a él (user_id = supervisor)
                # 3. Leads que él creó (create_uid = supervisor)
                supervisor_filter = [
                    '|', '|',
                    ('create_uid', 'in', department_user_ids),  # Leads del departamento
                    ('user_id', '=', current_user.id),  # Leads asignados al supervisor
                    ('create_uid', '=', current_user.id)  # Leads que el supervisor creó
                ]
                if args is None:
                    args = []
                args = args + supervisor_filter
                _logger.info(f"Supervisor filter - department users: {department_user_ids}")
            
            # Si es trabajador (pero no supervisor), puede ver sus leads Y leads asignados a él
            elif current_user.partner_id.worker:
                _logger.info("Applying worker filter - own leads AND assigned leads")
                worker_filter = [
                    '|',  # Cambiado a OR para incluir ambas condiciones
                    ('create_uid', '=', current_user.id),  # Leads que él creó
                    ('user_id', '=', current_user.id)  # Leads asignados a él
                ]
                if args is None:
                    args = []
                args = args + worker_filter
        
        return super(CrmLead, self).search(args, offset, limit, order, count)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """También aplicar filtro en search_read para vistas"""
        current_user = self.env.user
        
        # Si el usuario NO es administrador, aplicar filtros según rol
        if not current_user.has_group('base.group_system') and current_user.partner_id:
            
            # Si es supervisor, puede ver leads de su departamento Y leads asignados a él
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                # Buscar todos los usuarios trabajadores del mismo departamento
                department_partners = self.env['res.partner'].search([
                    ('department', '=', current_user.partner_id.department),
                    ('worker', '=', True)
                ])
                
                # Obtener los user_ids de estos partners
                department_user_ids = []
                for partner in department_partners:
                    user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
                    if user:
                        department_user_ids.append(user.id)
                
                # Incluir al supervisor también
                department_user_ids.append(current_user.id)
                
                # FILTRO CORREGIDO: Supervisor puede ver:
                # 1. Leads de su departamento (creados por cualquier usuario del depto)
                # 2. Leads asignados a él (user_id = supervisor)
                # 3. Leads que él creó (create_uid = supervisor)
                supervisor_filter = [
                    '|', '|',
                    ('create_uid', 'in', department_user_ids),  # Leads del departamento
                    ('user_id', '=', current_user.id),  # Leads asignados al supervisor
                    ('create_uid', '=', current_user.id)  # Leads que el supervisor creó
                ]
                if domain is None:
                    domain = []
                domain = domain + supervisor_filter
            
            # Si es trabajador (pero no supervisor), puede ver sus leads Y leads asignados a él
            elif current_user.partner_id.worker:
                worker_filter = [
                    '|',  # Cambiado a OR para incluir ambas condiciones
                    ('create_uid', '=', current_user.id),  # Leads que él creó
                    ('user_id', '=', current_user.id)  # Leads asignados a él
                ]
                if domain is None:
                    domain = []
                domain = domain + worker_filter
        
        return super(CrmLead, self).search_read(domain, fields, offset, limit, order)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Filtrar contactos según jerarquía: Admin > Supervisor > Trabajador"""
        current_user = self.env.user
        
        # Debug: Log para verificar qué está pasando
        _logger.info(f"Partner name_search called by user: {current_user.name}")
        _logger.info(f"User partner supervisor: {current_user.partner_id.supervisor if current_user.partner_id else 'No partner'}")
        _logger.info(f"User partner worker: {current_user.partner_id.worker if current_user.partner_id else 'No partner'}")
        _logger.info(f"Context: {self._context}")
        
        # Si el usuario actual tiene un rol específico, aplicar filtro
        if current_user.partner_id:
            
            # Si es supervisor, puede ver contactos de su departamento
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                _logger.info("Applying supervisor contact filter")
                supervisor_filter = [
                    '|',
                    ('department', '=', current_user.partner_id.department),  # Su departamento
                    '&',
                    ('create_uid', '=', current_user.id),  # Contactos que él creó
                    ('worker', '=', False)  # Solo clientes, no trabajadores
                ]
                if args is None:
                    args = []
                args = args + supervisor_filter
            
            # Si es trabajador (pero no supervisor), solo ve sus contactos
            elif current_user.partner_id.worker:
                _logger.info("Applying worker contact filter")
                worker_filter = [
                    ('create_uid', '=', current_user.id),  # Solo contactos que él creó
                    ('worker', '=', False)  # Excluir trabajadores, solo clientes
                ]
                if args is None:
                    args = []
                args = args + worker_filter
        
        return super(ResPartner, self).name_search(name, args, operator, limit)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """También aplicar filtro en búsquedas directas de contactos"""
        current_user = self.env.user
        
        # Si el usuario actual tiene un rol específico, aplicar filtro
        if current_user.partner_id:
            
            # Si es supervisor, puede ver contactos de su departamento
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                supervisor_filter = [
                    '|',
                    ('department', '=', current_user.partner_id.department),  # Su departamento
                    ('create_uid', '=', current_user.id)  # Contactos que él creó
                ]
                if args is None:
                    args = []
                args = args + supervisor_filter
            
            # Si es trabajador (pero no supervisor), solo ve sus contactos
            elif current_user.partner_id.worker:
                worker_filter = [
                    '|',
                    ('id', '=', current_user.partner_id.id),  # Su propio registro
                    ('create_uid', '=', current_user.id)  # Solo contactos que él creó
                ]
                if args is None:
                    args = []
                args = args + worker_filter
        
        return super(ResPartner, self).search(args, offset, limit, order, count)