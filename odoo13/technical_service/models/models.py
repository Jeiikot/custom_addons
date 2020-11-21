# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _
from odoo.tools import date_utils
import pytz

import datetime


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
    worked_hours = fields.Float(string='Worked Hours',
        compute='_compute_worked_hours', store=True, readonly=True)

    normal_hours = fields.Float('Normal Hours', readonly=True)
    hours_nigth = fields.Float('Hours at Nigth', readonly=True)
    sunday_hours = fields.Float('Sunday Hours', readonly=True)

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

    @api.onchange('schedule_date')
    def _onchange_start_date(self):
        # set auto-changing field
        self.start_date = self.schedule_date

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.end_date < record.start_date:
                raise exceptions.ValidationError(_("The start date must be less than the end date."))

    @api.constrains('stage_id', 'end_date')
    def _check_done(self):
        for record in self:
            if not record.end_date and record.stage_id.done == True:
                raise exceptions.ValidationError(_("The stage cannot be completed if there is no end date."))

    @api.depends('start_date', 'end_date')
    def _compute_worked_hours(self):
        user_tz = self.env.user.tz or pytz.utc
        local = pytz.timezone(user_tz)
        for record in self:
            if record.end_date and record.start_date:
                delta = record.end_date - record.start_date
                record.worked_hours = delta.total_seconds() / 3600.0
                # Convert Fields.Datetime to Datetime
                start_date, end_date = self.convert_to_datetime(record.start_date, record.end_date, local)
                # Get Worked Hours
                dict_worked_hours = self.get_worked_hours(start_date, end_date)
                """
                    Hours worked Monday through Saturday from 7:00 a.m. at 8:00 p.m.
                                                &
                    Hours worked Monday through Saturday from 8:00 p.m. to 7:00 a.m.
                                                &
                                    Hours worked on Sunday
                """
                record.normal_hours, record.hours_nigth, record.sunday_hours = self.check_worked_hours(
                    dict_worked_hours,
                    week_days=[0, 1, 2, 3, 4, 5],
                    start_hour=7,
                    end_hour=20
                )
            else:
                record.worked_hours = False


    def get_worked_hours(self, start_date, end_date):
        start_day = int(start_date.weekday())
        start_hour = int(start_date.hour)
        end_day = int(end_date.weekday())
        end_hour = int(end_date.hour)
        """
                                    The dictionary of hours worked is composed: 
                            days of the week as keys and a list of hours worked as values.                    
                                    dict = {days of the week: [hours worked]}
        """
        count = 1
        dict_hours = dict()
        for day in range(0, 7):
            list_hours = list()
            for hour in range(0, 24):
                temp_datetime = datetime.timedelta(days=day, hours=hour)
                if (temp_datetime >= datetime.timedelta(days=start_day, hours=start_hour)) \
                        and (temp_datetime < datetime.timedelta(days=end_day, hours=end_hour)):
                    list_hours.append(
                        date_utils.start_of(start_date, "hour") + datetime.timedelta(hours=count)
                    )
                    count += 1
            if day == start_day:
                list_hours.insert(0, start_date)
            if day == end_day:
                list_hours.append(end_date)
            if list_hours:
                dict_hours[day] = list_hours

        return dict_hours

    def convert_to_datetime(self, from_date, to_date, local):
        start_date = datetime.datetime.strptime(
            fields.Datetime.to_string(from_date.astimezone(local)),
            '%Y-%m-%d %H:%M:%S')
        end_date = datetime.datetime.strptime(
            fields.Datetime.to_string(to_date.astimezone(local)),
            '%Y-%m-%d %H:%M:%S')
        return start_date, end_date

    def check_worked_hours(self, dict_worked_hours, week_days, start_hour, end_hour):
        global old_datetime
        count_normal_hours = 0
        count_night_hours = 0
        count_sunday_hours = 0
        for index_day, day in enumerate(dict_worked_hours.keys()):
            for index, element in enumerate(dict_worked_hours[day]):
                if (index == 0) and (index_day == 0): continue
                current_datetime = datetime.timedelta(
                    days=element.weekday(),
                    hours=element.hour,
                    minutes=element.minute
                )
                if index != 0:
                    old_datetime = datetime.timedelta(
                        days=dict_worked_hours[day][index - 1].weekday(),
                        hours=dict_worked_hours[day][index - 1].hour,
                        minutes=dict_worked_hours[day][index - 1].minute
                    )
                else:
                    pass
                # Normal hours and Nigth Hours
                # 7 AM <= x & x <= 8 PM include datetime current and next
                # 8 PM <= x & x <= 7 AM include datetime current and next
                if day in week_days:
                    if (datetime.timedelta(days=day, hours=start_hour, minutes=0) <= old_datetime) \
                            and (old_datetime <= datetime.timedelta(days=day, hours=end_hour, minutes=0)) \
                        and (datetime.timedelta(days=day, hours=start_hour, minutes=0) <= current_datetime) \
                            and (current_datetime <= datetime.timedelta(days=day, hours=end_hour, minutes=0)):
                        delta = current_datetime - old_datetime
                        count_normal_hours += delta.total_seconds() / 3600
                    else:
                        delta = current_datetime - old_datetime
                        count_night_hours += delta.total_seconds() / 3600
                else:
                    delta = current_datetime - old_datetime
                    count_sunday_hours += delta.total_seconds() / 3600
                old_datetime = current_datetime
        return count_normal_hours, count_night_hours, count_sunday_hours