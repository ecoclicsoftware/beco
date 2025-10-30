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
    
    @api.depends('user_id', 'user_id.partner_id.department')
    def _compute_commercial_department(self):
        for lead in self:
            if lead.user_id and lead.user_id.partner_id and lead.user_id.partner_id.department:
                dept_names = ', '.join(lead.user_id.partner_id.department.mapped('name'))
                lead.commercial_department = dept_names
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
        # Devuelve la etiqueta como recordset; crea si no existe
        Tag = self.env['crm.tag']
        tag = Tag.search([('name', '=', department_name)], limit=1)
        if not tag:
            tag = Tag.create({'name': department_name, 'color': color})
        return tag

    def _assign_department_tag(self):
        # Añade etiquetas vía unión de recordsets (evita TypeError)
        for lead in self:
            tags_to_add = self.env['crm.tag']

            # Vendedor elegido o usuario actual
            user = lead.user_id or self.env.user
            partner = user.partner_id if user else False

            if partner and partner.department:
                # Nombres de departamentos del partner (Many2many)
                dept_names = partner.department.mapped('name')
                for name in dept_names:
                    tag = self._get_or_create_department_tag(name)
                    tags_to_add |= tag

            # Une todas las etiquetas en una sola operación
            if tags_to_add:
                lead.tag_ids |= tags_to_add

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
        current_user = self.env.user
        if not current_user.has_group('base.group_system') and current_user.partner_id:

            # FILTRO SUPERVISOR
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                # Comerciales del departamento
                department_ids = current_user.partner_id.department.ids
                commercial_partners = self.env['res.partner'].search([
                    ('department', 'in', department_ids), 
                    ('worker', '=', True)
                ])
                commercial_userids = [
                    self.env['res.users'].search([('partner_id', '=', p.id)], limit=1).id
                    for p in commercial_partners if self.env['res.users'].search([('partner_id', '=', p.id)], limit=1)
                ]
                # Externos que tienen asignado como supervisor al usuario actual
                external_partners = self.env['res.partner'].search([
                    ('external', '=', True),
                    '|',
                    ('supervisor_externo_id', '=', current_user.partner_id.id),  # Si usas Many2one
                    ('supervisores_ids', 'in', [current_user.partner_id.id])    # Si usas Many2many
                ])
                external_userids = [
                    self.env['res.users'].search([('partner_id', '=', p.id)], limit=1).id
                    for p in external_partners if self.env['res.users'].search([('partner_id', '=', p.id)], limit=1)
                ]
                # Todos los usuarios permitidos para el supervisor
                user_ids = list(set([current_user.id] + commercial_userids + external_userids))
                supervisor_filter = [
                    '|', '|',
                    ('create_uid', 'in', user_ids),  # Oportunidades creadas por cualquier user permitido
                    ('user_id', '=', current_user.id),  # Asignadas al supervisor
                    ('create_uid', '=', current_user.id),  # Creadas por el supervisor
                ]
                args = (args or []) + supervisor_filter

            # FILTRO COMMERCIAL
            elif current_user.partner_id.worker:
                worker_filter = [
                    '|',
                    ('create_uid', '=', current_user.id),
                    ('user_id', '=', current_user.id),
                ]
                args = (args or []) + worker_filter

            # FILTRO EXTERNO
            elif current_user.partner_id.external:
                external_filter = [
                    '|',
                    ('create_uid', '=', current_user.id),
                    ('user_id', '=', current_user.id),
                ]
                args = (args or []) + external_filter

        return super(CrmLead, self).search(args, offset, limit, order, count)



    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        current_user = self.env.user
        if not current_user.has_group('base.group_system') and current_user.partner_id:

            # Mismo filtro de supervisor que arriba
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                department_ids = current_user.partner_id.department.ids
                commercial_partners = self.env['res.partner'].search([
                    ('department', 'in', department_ids), 
                    ('worker', '=', True)
                ])
                commercial_userids = [
                    self.env['res.users'].search([('partner_id', '=', p.id)], limit=1).id
                    for p in commercial_partners if self.env['res.users'].search([('partner_id', '=', p.id)], limit=1)
                ]
                external_partners = self.env['res.partner'].search([
                    ('external', '=', True),
                    '|',
                    ('supervisor_externo_id', '=', current_user.partner_id.id),
                    ('supervisores_ids', 'in', [current_user.partner_id.id])
                ])
                external_userids = [
                    self.env['res.users'].search([('partner_id', '=', p.id)], limit=1).id
                    for p in external_partners if self.env['res.users'].search([('partner_id', '=', p.id)], limit=1)
                ]
                user_ids = list(set([current_user.id] + commercial_userids + external_userids))
                supervisor_filter = [
                    '|', '|',
                    ('create_uid', 'in', user_ids),
                    ('user_id', '=', current_user.id),
                    ('create_uid', '=', current_user.id),
                ]
                domain = (domain or []) + supervisor_filter

            elif current_user.partner_id.worker:
                worker_filter = [
                    '|',
                    ('create_uid', '=', current_user.id),
                    ('user_id', '=', current_user.id),
                ]
                domain = (domain or []) + worker_filter

            elif current_user.partner_id.external:
                external_filter = [
                    '|',
                    ('create_uid', '=', current_user.id),
                    ('user_id', '=', current_user.id),
                ]
                domain = (domain or []) + external_filter

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
                    ('department', 'in', current_user.partner_id.department.ids),  # <-- corregido
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
            if current_user.partner_id.supervisor and current_user.partner_id.department:
                supervisor_filter = [
                    '|',
                    ('department', 'in', current_user.partner_id.department.ids),  # <-- corregido
                    ('create_uid', '=', current_user.id)
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