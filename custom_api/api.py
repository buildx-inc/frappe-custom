import json
import frappe
import frappe.client
from frappe.model.mapper import get_mapped_doc
import frappe.handler
from frappe.utils import get_site_name
from frappe import _
from frappe.desk.form.load import add_comments
from frappe.utils.background_jobs import enqueue
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from hrms.hr.doctype.employee_checkin.employee_checkin import update_attendance_in_checkins
from datetime import datetime, timedelta, date
from frappe.desk.form.document_follow import follow_document
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)
from datetime import datetime, date, timedelta
import re
import requests
from frappe.model.workflow import apply_workflow
from collections import defaultdict

@frappe.whitelist()
def current_site():
    return frappe.local.site_path

@frappe.whitelist()
def fetch_all_from_doctype(doctype, name = "", filters = None, fields = None):
    if name == "":
        orders = frappe.get_all(doctype, filters = filters)

        if(orders):
            response = []
            
            for order in orders:
                response.append(frappe.get_doc(doctype, order.name, filters = filters, fields = fields))
            return response
        else :
            return "no entries found"
    else:
        return frappe.get_doc(doctype, name, fields = fields)
    
    

@frappe.whitelist()
def getComments(doctype, docname):
    project_doc = frappe.get_doc(doctype, docname)
    docinfo = frappe._dict(user_info={})
    comments = add_comments(project_doc,docinfo)
    comment_data = []
    for comment in comments:
        comment_owner = frappe.get_doc("User",comment['owner'])
        comment['owner_role'] = comment_owner.role_profile_name
        comment_data.append(comment)
    return comment_data


@frappe.whitelist(allow_guest=True)
def get_metadata(doctype, with_child_tables = False):
    if with_child_tables:
        result = {}
        meta = frappe.get_meta(doctype)
        result['meta'] = meta
        result['tables'] = {}
        for field in meta._fields:
            if meta._fields[field].fieldtype == 'Table':
                result['tables'][meta._fields[field].fieldname] = frappe.get_meta(meta._fields[field].options)
        return result
    else:
        return frappe.get_meta(doctype)

@frappe.whitelist(allow_guest=True)
def get_multiple_metadata(doctypes):
    metadata = {}
    for index, doctype in enumerate(json.loads(doctypes)):
        try:
            metadata[doctype] =  frappe.get_meta(doctype)
        except frappe.DoesNotExistError as e:
            metadata[doctype] = {"error": str(e)}
    return metadata

@frappe.whitelist(allow_guest=True)
def dev():
    if frappe.conf.developer_mode:
        return 1
    else:
        return 0


@frappe.whitelist()
def send_email(emails, subject, content, attachments=None):
    # Convert the JSON string to a Python list
    recipients = json.loads(emails)

    # Prepare the email arguments
    email_args = {
        "recipients": recipients,
        "sender": None,
        "subject": subject,
        "message": content,
        "now": True,
        "attachments": attachments or []  # Attachments list, default to an empty list if not provided
    }
    # Enqueue the email for sending
    enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args)

@frappe.whitelist()
def send_notification(subject, users, doctype = None, doc_name = None, notification_type = None, email_content = None, attachment = None):
    users = json.loads(users)
    for user in users:
        notification_log = frappe.get_doc({
            "doctype": "Notification Log",
            "modified_by": frappe.session.user,
            "owner": frappe.session.user,
            "subject": subject,
            "for_user": user,
            "type": notification_type,
            "email_content": email_content,
            "document_type": doctype,
            "document_name": doc_name,
            "attached_file": attachment,
            "from_user": frappe.session.user,
        })
        notification_log.insert(ignore_permissions=True)

@frappe.whitelist()
def get_user_notifications(limit=20):
    notification_logs = frappe.db.get_list("Notification Log", fields=["*"], limit=limit, filters={"for_user": frappe.session.user }, order_by="modified desc")

    users = [log.from_user for log in notification_logs]
    users = [*set(users)]  # remove duplicates
    user_info = frappe._dict()

    for user in users:
        frappe.utils.add_user_info(user, user_info) 
    return {"notification_logs": notification_logs, "user_info": user_info}

@frappe.whitelist(allow_guest=True)
def get_logged_user():
    if frappe.session.user:
        user_doc = frappe.get_doc("User",frappe.session.user)
        # role_profiles = [role_profile.role_profile for role_profile in user_doc.role_profiles]
        val = frappe.db.get_values("User", {'name': frappe.session.user}, "*", as_dict=True)
        # val[0]["role_profiles"] = role_profiles
        val[0]["site"] = frappe.local.site_path
    return val
        
@frappe.whitelist()
def get_user_defaults(key):
    default_list = frappe.get_list("DefaultValue",filters={"defkey":key,"parent":frappe.session.user},ignore_permissions=True)
    if len(default_list) != 0:
        default_values = []
        for default_value in default_list:
            doc = frappe.get_doc("DefaultValue",default_value['name'])
            default_values.append(doc.defvalue)
        return default_values
    else:
        return {}

@frappe.whitelist()
def set_user_defaults(key,value):
    frappe.defaults.set_user_default(key,value,frappe.session.user)
    frappe.db.commit()
    
@frappe.whitelist(allow_guest=True)
def get_logged_session():
    return frappe.session

@frappe.whitelist(allow_guest=True)
def save_doc(doc ,children=[]):
    for child in children:
        if isinstance(child,list):
            child_list = []
            for n_child in child:
                n_child_doc = frappe.get_doc(n_child['data'])
                n_child_doc.save(ignore_permissions=True)
                child_list.append(n_child_doc.name)
            doc[child['field']] = child_list
        else:
            child_doc = frappe.get_doc(child['data'])
            child_doc.save(ignore_permissions=True)
            doc[child['field']] = child_doc.name
    new_doc = frappe.get_doc(doc)
    new_doc.save(ignore_permissions=True)
    

@frappe.whitelist(allow_guest=True)
def file_upload(file_name, folder, doctype, docname):
    file = frappe.new_doc("File")
    file.file_name = file_name
    file.attached_to_doctype = doctype
    file.attached_to_name = docname
    file.is_folder = 1
    file.folder = folder
    file.insert(ignore_if_duplicate=True)
    return file
    
    
@frappe.whitelist()
def get_exchange_rate_data(from_date,to_date):
    response = requests.get("https://wcur.pma.ps/ar/webtools/currency/export")
    regex = r"[a-zA-Z0-9]{32}"
    matches = re.findall(regex, response.text)
    key, val = matches[0], matches[1]
    data = {
        "from": from_date,
        "to": to_date,
        key: val,
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': response.headers["Set-Cookie"]
    }
    
    response = requests.post("https://wcur.pma.ps/ar/webtools/currency/export", headers=headers, data= data)
    return response.text
    
def log(message, logging_enabled = True):
    if not logging_enabled:
        return
    else:
        print(message)


def create_employee_attendance(doc, method):
    frappe.msgprint("Creating Employee Attendance")
    employee_list = frappe.get_list("Employee",fields=['name','first_name','last_name','hourly_rate','designation'])
    attendance_data = {}
    for employee in employee_list:
        employee_fullname = employee.first_name
        
        if employee.last_name != '' and employee.last_name != None:
            employee_fullname = employee_fullname + " " + employee.last_name
            
        checkin_stack = []
        filters = {'employee': employee.name}
        filters['attendance'] = ['=','']
        
        attendance_data[employee_fullname] = {}
        checkin_list = frappe.get_list(doctype="Employee Checkin",filters=filters,fields=['name', 'time', 'log_type', 'employee'], order_by='time asc')
        attendance_data[employee_fullname]['attendance'] = {}
        attendance_data[employee_fullname]['working_hours'] = 0
        attendance_data[employee_fullname]['break_hours'] = 0
        attendance_data[employee_fullname]['status'] = "Off"
        
        for checkin in checkin_list:
            checkin_day = (checkin.time - timedelta(hours=5)).strftime('%Y/%m/%d')

            if str(checkin_day) not in attendance_data[employee_fullname]['attendance'].keys():
                if checkin.log_type == 'IN':
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
            if checkin.log_type == 'IN':
                attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = checkin
                attendance_data[employee_fullname]['status'] = "Working"
                checkin_stack.append(checkin)
            elif checkin.log_type == 'OUT':
                attendance_data[employee_fullname]['status'] = "Off"
                if len(checkin_stack) == 0:
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Check-out without check-in")
                else:
                    clock_in = checkin_stack.pop()
                    clockin_day = (clock_in.time - timedelta(hours=5)).strftime('%Y/%m/%d') 
                     
                    if ((checkin.time - timedelta(hours=5)).day - (clock_in.time - timedelta(hours=5)).day) > 1:
                        attendance_data[employee_fullname]['attendance'][str(clockin_day)]['issues'].append(clock_in.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Employee checked in for more than 2 days")    
                    else: #shift carry over till the next day                    
                        attendance_data[employee_fullname]['attendance'][str(clockin_day)]['check_out'] = checkin    
                    while len(checkin_stack) > 0:
                        clock_in = checkin_stack.pop()
                        attendance_data[employee_fullname]['attendance'][str(clockin_day)]['issues'].append(clock_in.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Checkin without checkout")
            elif checkin.log_type == 'Break-OUT':
                if str(checkin_day) not in attendance_data[employee_fullname]['attendance'].keys():
                    if len(checkin_stack) != 0:
                        checkin_day = (checkin_stack[-1].time - timedelta(hours=5)).strftime('%Y/%m/%d')
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'].append(checkin)
                        attendance_data[employee_fullname]['status'] = "On Break"
                    else:
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break-out without check-in")
                else:
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'].append(checkin)
                    attendance_data[employee_fullname]['status'] = "On Break"
            elif checkin.log_type == 'Break-IN':
                if str(checkin_day) not in attendance_data[employee_fullname]['attendance'].keys():
                    if len(checkin_stack) != 0:
                        checkin_day = (checkin_stack[-1].time - timedelta(hours=5)).strftime('%Y/%m/%d')
                        if len(attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks']) != 0:
                            attendance_data[employee_fullname]['status'] = "Working"
                            attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'].append({'out':attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0], 'in':checkin})
                            del attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0]
                        else:
                            attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break in before break out")
                    else:
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break-in without check-in")
   
                else:
                    if len(attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks']) != 0:
                        attendance_data[employee_fullname]['status'] = "Working"
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'].append({'out':attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0], 'in':checkin})
                        del attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0]
                    else:
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break in before break out")
            else:
                attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Unknown checkin type")

        #per employee after calculations
        for day in attendance_data[employee_fullname]['attendance']:
            if len(attendance_data[employee_fullname]['attendance'][day]['issues']) == 0 and attendance_data[employee_fullname]['attendance'][day]['check_out'] != None:
                create_and_link_attendance(attendance_data[employee_fullname]['attendance'][day])


def create_and_link_attendance(attendances):
    company = frappe.get_list("Company")[0].name
    employee = attendances['check_in'].employee
    working_hours = round((attendances['check_out'].time - attendances['check_in'].time).seconds/36)/100

    attendance_doc = frappe.get_doc({
         'doctype' : 'Attendance',
         'attendance_date' : attendances['check_in'].time.date(),
         'employee' : employee,
         'company' : company,
         'employee_name':  frappe.get_doc("Employee",employee).employee_name,
         'working_hours': working_hours,
         'status': 'Present',
         'in_time': attendances['check_in'].time,
         'out_time': attendances['check_out'].time,
    })
    attendance_doc.save()
    checkin_log = [frappe.get_doc('Employee Checkin',attendances['check_in'].name)]
    total_break_hours = 0
    for break_entry in attendances['break_log']:
        break_out = break_entry['in']
        break_in = break_entry['out']
        checkin_log.append(frappe.get_doc('Employee Checkin',break_out.name))
        checkin_log.append(frappe.get_doc('Employee Checkin',break_in.name))
        if break_out.time > break_in.time:
            break_hours = round((break_out.time - break_in.time).seconds/36)/100
            attendance_doc.append('breaks',{'break_out':break_out.time, 'break_in': break_in.time})
        else:
            break_hours = round((break_in.time - break_out.time).seconds/36)/100
            attendance_doc.append('breaks',{'break_out':break_in.time, 'break_in': break_out.time})
        total_break_hours += break_hours
    attendance_doc.break_hours = total_break_hours
    checkin_log.append(frappe.get_doc('Employee Checkin',attendances['check_out'].name))
    for checkin in checkin_log:
        checkin.attendance = attendance_doc.name
        checkin.save()
        checkin.submit()
        
    attendance_doc.save()
    attendance_doc.submit()
    frappe.db.commit()
    

def purchase_invoice_before_submit(doc,method):
    if doc.paid_amount != 0:
        payment_entry = get_payment_entry(doc.doctype, doc.name)
    
        paid_amount = doc.paid_amount
        doc.paid_amount = 0
    
        payment_entry.total_allocated_amount = paid_amount
        payment_entry.total_allocated_amount = paid_amount
        payment_entry.base_total_allocated_amount = paid_amount
        payment_entry.base_party_amount = paid_amount
        payment_entry.base_paid_amount = paid_amount
        payment_entry.received_amount = paid_amount
        payment_entry.base_received_amount = paid_amount
        
        if len(doc.references) > 0:
            payment_entry.references[0].allocated_amount = paid_amount
            
        payment_entry.save()
        payment_entry.submit()
