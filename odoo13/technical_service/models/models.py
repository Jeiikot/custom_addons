# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _


class technicalServiceStage(models.Model):
    """ Model for case stages. This models the main stages of a Technical Service Request management flow. """

    _name = 'technical_service.stage'
    _description = 'Technical Service Stage'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=20)
    done = fields.Boolean('Request Done')

class technicalServiceCategory(models.Model):
    _name = 'technical_service.category'
    _description = 'Technical Service Category'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)


class technicalServiceRequest(models.Model):
    _name = 'technical_service.request'

    _description = 'Technical Service Request'

    @api.returns('self')
    def _default_stage(self):
        return self.env['technical_service.stage'].search([], limit=1)

    name = fields.Char('Name', required=True, translate=True)
    description = fields.Text('Description')
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High')], string='Priority')

    request_date = fields.Date('Request Date', tracking=True, default=fields.Date.context_today,
                               help="Date requested for the technical service to happen")
    schedule_date = fields.Datetime('Scheduled Date', required=True,
        help="Date the Technical Service team plans the service.  It should not differ much from the Request Date. ")
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    category_id = fields.Many2one('technical_service.category', string='Service Category', required=True)
    user_id = fields.Many2one('res.users', string='Technician', tracking=True, required=True)
    stage_id = fields.Many2one('technical_service.stage', string='Stage', ondelete='restrict',
                               tracking=True, default=_default_stage, copy=False)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.end_date < record.start_date:
                raise exceptions.ValidationError(_("The start date must be less than the end date."))
