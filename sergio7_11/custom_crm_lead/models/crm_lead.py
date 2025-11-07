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
        readonly=False,
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
                total_revenue += product.list_price
            lead.expected_revenue = total_revenue
    
    def _get_or_create_department_tag(self, department_name, color=1):
        Tag = self.env['crm.tag']
        tag = Tag.search([('name', '=', department_name)], limit=1)
        if not tag:
            tag = Tag.create({'name': department_name, 'color': color})
        return tag

    def _assign_department_tag(self):
        for lead in self:
            tags_to_add = self.env['crm.tag']

            user = lead.user_id or self.env.user
            partner = user.partner_id if user else False

            if partner and partner.department:
                dept_names = partner.department.mapped('name')
                for name in dept_names:
                    tag = self._get_or_create_department_tag(name)
                    tags_to_add |= tag

            if tags_to_add:
                lead.tag_ids |= tags_to_add

    @api.model
    def create(self, vals):
        """Al crear lead, asignar departamento y etiqueta automáticamente"""
        if 'user_id' not in vals:
            vals['user_id'] = self.env.user.id
            
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
            self.phone = (partner.phone or partner.mobile or '').strip()
        else:
            self.email_from = False
            self.phone = False
    
    @api.onchange('product_ids')
    def _onchange_product_ids(self):
        """Actualizar ingreso esperado cuando cambian los productos"""
        self._compute_expected_revenue_from_products()
        
    ################################################

    # Los campos email_from y phone ya existen en el modelo base
    email_from = fields.Char(readonly=True)
    phone = fields.Char(readonly=True) 

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Filtros personalizados de visibilidad por rol para oportunidades CRM.
        """
        current_user = self.env.user
        
        # 🆕 CRÍTICO: Evitar recursión en cálculos computados
        if (self.env.context.get('skip_custom_search') or 
            self.env.context.get('active_test') is False or
            self.env.context.get('computing_opportunity_count') or
            '_compute_' in str(self.env.context)):
            _logger.info(f"🔓 Contexto especial detectado en CRM search - sin restricciones")
            return super(CrmLead, self).search(args, offset=offset, limit=limit, order=order, count=count)

        _logger.info(f"===== CRM SEARCH llamado por usuario {current_user.name} (ID {current_user.id}) =====")
        
        # Admin ve todo
        if self.env.user._is_admin():
            _logger.info("Es admin REAL - Sin restricciones")
            return super(CrmLead, self).search(args, offset, limit, order, count)

        if not current_user.partner_id:
            _logger.warning(f"Usuario sin partner_id asociado")
            return super(CrmLead, self).search(args + [('id', '=', False)], offset, limit, order, count)

        partner = current_user.partner_id
        _logger.info(f"- Roles: worker={partner.worker}, supervisor={partner.supervisor}, external={partner.external}")

        # COMERCIAL
        if partner.worker:
            _logger.info(f"COMERCIAL CRM search - Usuario {partner.name}")
            worker_domain = [
                '|', 
                ('create_uid', '=', current_user.id),
                ('user_id', '=', current_user.id)
            ]
            _logger.info(f"Worker domain: {worker_domain}")
            return super(CrmLead, self).search(args + worker_domain, offset, limit, order, count)

        # SUPERVISOR
        if partner.supervisor:
            _logger.info(f"SUPERVISOR CRM search - Usuario {partner.name}")
            _logger.info(f"- Departamentos: {partner.department.mapped('name')} (IDs {partner.department.ids})")
            _logger.info(f"- Empresa: {partner.internal_company_id.name if partner.internal_company_id else None}")

            # 🆕 CRÍTICO: Usar skip_custom_search para evitar recursión
            # Obtener IDs de comerciales de su departamento/empresa
            comerciales_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Comerciales encontrados: {len(comerciales_ids)} - IDs: {comerciales_ids}")

            # Obtener usuarios de esos comerciales
            commercial_userids = []
            for comercial_id in comerciales_ids:
                user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', comercial_id)], limit=1)
                if user:
                    commercial_userids.append(user.id)
            _logger.info(f"- Usuarios comerciales: {commercial_userids}")

            # 🆕 OBTENER EXTERNOS QUE TIENE ASIGNADOS ESTE SUPERVISOR
            externos_supervisados_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('external', '=', True),
                ('supervisores_ids', 'in', [partner.id])
            ]).ids
            _logger.info(f"- Externos supervisados: {len(externos_supervisados_ids)} - IDs: {externos_supervisados_ids}")

            # 🆕 OBTENER USUARIOS DE LOS EXTERNOS SUPERVISADOS
            external_userids = []
            for externo_id in externos_supervisados_ids:
                user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', externo_id)], limit=1)
                if user:
                    external_userids.append(user.id)
            _logger.info(f"- Usuarios externos: {external_userids}")

            # 🆕 OBTENER COMERCIALES DE LOS EXTERNOS SUPERVISADOS Y SUS USUARIOS
            comerciales_de_externos_ids = []
            comerciales_de_externos_userids = []
            
            if externos_supervisados_ids:
                for externo in self.env['res.partner'].with_context(skip_custom_search=True).browse(externos_supervisados_ids):
                    comerciales_de_externos_ids.extend(externo.comerciales_asignados_ids.ids)
                
                comerciales_de_externos_ids = list(set(comerciales_de_externos_ids))
                _logger.info(f"- Comerciales de externos: {len(comerciales_de_externos_ids)} - IDs: {comerciales_de_externos_ids}")
                
                for comercial_id in comerciales_de_externos_ids:
                    user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', comercial_id)], limit=1)
                    if user:
                        comerciales_de_externos_userids.append(user.id)
                _logger.info(f"- Usuarios de comerciales de externos: {comerciales_de_externos_userids}")

            # Combinar todos los usuarios permitidos
            todos_user_ids = list(set([current_user.id] + commercial_userids + external_userids + comerciales_de_externos_userids))
            _logger.info(f"- Total usuarios visibles: {len(todos_user_ids)}")

            # 🆕 CONSTRUIR DOMINIO AMPLIADO PARA SUPERVISOR - ESTRUCTURA CORREGIDA
            supervisor_domain = [
                '|',  # OR principal
                '|',  # Segundo nivel OR
                # Opción 1: Oportunidades creadas por usuarios permitidos
                ('create_uid', 'in', todos_user_ids),
                # Opción 2: Oportunidades asignadas al supervisor
                ('user_id', '=', current_user.id),
                # Opción 3: Oportunidades creadas por el supervisor
                ('create_uid', '=', current_user.id)
            ]

            _logger.info(f"Aplicando dominio supervisor CRM ampliado")
            result = super(CrmLead, self).search(args + supervisor_domain, offset, limit, order, count)
            _logger.info(f"Resultado CRM: {result if count else len(result)} registros")
            return result

        # 🆕 EXTERNO - Ahora funciona como supervisor
        if partner.external:
            _logger.info(f"EXTERNO CRM search - Usuario {partner.name} (como supervisor externo)")
            _logger.info(f"- Departamentos: {partner.department.mapped('name')} (IDs {partner.department.ids})")
            _logger.info(f"- Empresa: {partner.internal_company_id.name if partner.internal_company_id else None}")

            # 🆕 CRÍTICO: Usar skip_custom_search para evitar recursión
            # Obtener IDs de comerciales de su departamento/empresa
            comerciales_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Comerciales de su equipo: {len(comerciales_ids)} - IDs: {comerciales_ids}")

            # Obtener usuarios de esos comerciales
            commercial_userids = []
            for comercial_id in comerciales_ids:
                user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', comercial_id)], limit=1)
                if user:
                    commercial_userids.append(user.id)
            _logger.info(f"- Usuarios comerciales: {commercial_userids}")

            # Combinar todos los usuarios permitidos
            todos_user_ids = list(set([current_user.id] + commercial_userids))
            _logger.info(f"- Total usuarios visibles: {len(todos_user_ids)}")

            # 🆕 CONSTRUIR DOMINIO PARA EXTERNO (como supervisor)
            external_domain = [
                '|',  # OR principal
                '|',  # Segundo nivel OR
                # Opción 1: Oportunidades creadas por usuarios permitidos
                ('create_uid', 'in', todos_user_ids),
                # Opción 2: Oportunidades asignadas al externo
                ('user_id', '=', current_user.id),
                # Opción 3: Oportunidades creadas por el externo
                ('create_uid', '=', current_user.id)
            ]

            _logger.info(f"🔍 Aplicando dominio externo CRM (como supervisor)")
            result = super(CrmLead, self).search(args + external_domain, offset, limit, order, count)
            _logger.info(f"✅ Resultado externo CRM: {result if count else len(result)} registros")
            return result

        # OTRO ROL
        _logger.info("Usuario sin rol específico en CRM")
        return super(CrmLead, self).search(args + [('create_uid', '=', current_user.id)], offset, limit, order, count)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Filtros personalizados de visibilidad por rol para CRM search_read.
        """
        if domain is None:
            domain = []

        current_user = self.env.user
        
        # 🆕 CRÍTICO: Evitar recursión en cálculos computados
        if (self.env.context.get('skip_custom_search') or 
            self.env.context.get('active_test') is False or
            self.env.context.get('computing_opportunity_count') or
            '_compute_' in str(self.env.context)):
            _logger.info(f"🔓 Contexto especial detectado en CRM search_read - sin restricciones")
            return super(CrmLead, self).search_read(domain, fields, offset, limit, order)

        _logger.info(f"CRM SEARCH_READ llamado por usuario {current_user.name}")

        # Admin ve todo
        if self.env.is_admin():
            _logger.info("Es admin - Sin restricciones")
            return super(CrmLead, self).search_read(domain, fields, offset, limit, order)

        if not current_user.partner_id:
            _logger.warning(f"Usuario sin partner_id asociado")
            return super(CrmLead, self).search_read(domain + [('id', '=', False)], fields, offset, limit, order)

        partner = current_user.partner_id
        _logger.info(f"- Roles: worker={partner.worker}, supervisor={partner.supervisor}, external={partner.external}")

        # COMERCIAL
        if partner.worker:
            _logger.info(f"COMERCIAL CRM search_read - Usuario {partner.name}")
            worker_domain = [
                '|', 
                ('create_uid', '=', current_user.id),
                ('user_id', '=', current_user.id)
            ]
            _logger.info(f"Worker domain: {worker_domain}")
            return super(CrmLead, self).search_read(domain + worker_domain, fields, offset, limit, order)

        # SUPERVISOR
        if partner.supervisor:
            _logger.info(f"SUPERVISOR CRM search_read - Usuario {partner.name}")
            
            # 🆕 CRÍTICO: Usar skip_custom_search para evitar recursión
            # Obtener IDs de comerciales
            comerciales_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Comerciales encontrados: {len(comerciales_ids)}")

            # Obtener usuarios de comerciales
            commercial_userids = []
            for comercial_id in comerciales_ids:
                user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', comercial_id)], limit=1)
                if user:
                    commercial_userids.append(user.id)

            # 🆕 OBTENER EXTERNOS QUE TIENE ASIGNADOS ESTE SUPERVISOR
            externos_supervisados_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('external', '=', True),
                ('supervisores_ids', 'in', [partner.id])
            ]).ids
            _logger.info(f"- Externos supervisados: {len(externos_supervisados_ids)}")

            # 🆕 OBTENER USUARIOS DE EXTERNOS
            external_userids = []
            for externo_id in externos_supervisados_ids:
                user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', externo_id)], limit=1)
                if user:
                    external_userids.append(user.id)

            # 🆕 OBTENER COMERCIALES DE EXTERNOS Y SUS USUARIOS
            comerciales_de_externos_userids = []
            if externos_supervisados_ids:
                for externo in self.env['res.partner'].with_context(skip_custom_search=True).browse(externos_supervisados_ids):
                    for comercial in externo.comerciales_asignados_ids:
                        user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', comercial.id)], limit=1)
                        if user:
                            comerciales_de_externos_userids.append(user.id)

            # Combinar todos los usuarios
            todos_user_ids = list(set([current_user.id] + commercial_userids + external_userids + comerciales_de_externos_userids))
            _logger.info(f"- Total usuarios visibles: {len(todos_user_ids)}")

            # 🆕 DOMINIO AMPLIADO PARA SUPERVISOR - ESTRUCTURA CORREGIDA
            supervisor_domain = [
                '|',  # OR principal
                '|',  # Segundo nivel OR
                # Opción 1: Oportunidades de usuarios permitidos
                ('create_uid', 'in', todos_user_ids),
                # Opción 2: Oportunidades asignadas al supervisor
                ('user_id', '=', current_user.id),
                # Opción 3: Oportunidades creadas por el supervisor
                ('create_uid', '=', current_user.id)
            ]

            _logger.info(f"Aplicando dominio supervisor CRM ampliado en search_read")
            return super(CrmLead, self).search_read(domain + supervisor_domain, fields, offset, limit, order)

        # EXTERNO
        if partner.external:
            _logger.info(f"EXTERNO CRM search_read - Usuario {partner.name}")
            
            # 🆕 CRÍTICO: Usar skip_custom_search para evitar recursión
            # Obtener IDs de comerciales de su equipo
            comerciales_ids = self.env['res.partner'].with_context(skip_custom_search=True).sudo().search([
                ('worker', '=', True),
                ('department', 'in', partner.department.ids),
                ('internal_company_id', '=', partner.internal_company_id.id)
            ]).ids
            _logger.info(f"- Comerciales de su equipo: {len(comerciales_ids)}")

            # Obtener usuarios de comerciales
            commercial_userids = []
            for comercial_id in comerciales_ids:
                user = self.env['res.users'].with_context(skip_custom_search=True).search([('partner_id', '=', comercial_id)], limit=1)
                if user:
                    commercial_userids.append(user.id)

            # Combinar usuarios
            todos_user_ids = list(set([current_user.id] + commercial_userids))
            _logger.info(f"- Total usuarios visibles: {len(todos_user_ids)}")

            # 🆕 DOMINIO PARA EXTERNO
            external_domain = [
                '|',  # OR principal
                '|',  # Segundo nivel OR
                # Opción 1: Oportunidades de usuarios permitidos
                ('create_uid', 'in', todos_user_ids),
                # Opción 2: Oportunidades asignadas al externo
                ('user_id', '=', current_user.id),
                # Opción 3: Oportunidades creadas por el externo
                ('create_uid', '=', current_user.id)
            ]
            
            _logger.info(f"🔍 Aplicando dominio externo CRM en search_read")
            return super(CrmLead, self).search_read(domain + external_domain, fields, offset, limit, order)

        # OTRO ROL
        _logger.info("Usuario sin rol específico en CRM")
        return super(CrmLead, self).search_read(domain + [('create_uid', '=', current_user.id)], fields, offset, limit, order)


# 🆕 ELIMINAR la clase ResPartner del módulo CRM
# Ya existe en custom_partner y causa recursión