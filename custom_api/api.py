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
import calendar
from frappe.auth import LoginManager
from frappe.desk.form.document_follow import follow_document
from frappe.permissions import has_permission
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)
import re
import requests
from frappe.model.workflow import apply_workflow
from collections import defaultdict
import pdfkit
from werkzeug.wrappers import Response
from frappe.core.doctype.sms_settings.sms_settings import send_via_gateway
from io import BytesIO
import random
from openpyxl import load_workbook
from erpnext.controllers.item_variant import create_variant
import math


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

@frappe.whitelist()
def getToken():
	return frappe.sessions.get_csrf_token()


@frappe.whitelist(allow_guest=True)
def currentSite():
	return frappe.local.site




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


def validate_lead(doc, method=None):
    if doc.company_name and"Binance" in doc.company_name:
        frappe.throw("Invalid Request")
        
@frappe.whitelist()
def send_email(emails, subject, content, attachments=None, cc=None):
	# Convert the JSON string to a Python list
	recipients = json.loads(emails)

	# Prepare the email arguments
	email_args = {
		"recipients": recipients,
		"sender": None,
		"subject": subject,
		"message": content,
		"now": True,
		"cc": cc,
		"attachments": attachments or []  # Attachments list, default to an empty list if not provided
	}
	# Enqueue the email for sending
	enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args)
	return email_args

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
def send_multiple_channel_notifications(notification_data):
    for notification in notification_data:
        if notification['type'] == 'email':
            for user in notification['receivers']:
                send_email(json.dumps([user]), notification['subject'], notification['message'])
                
        elif notification['type'] == 'sms':
            phone_numbers = []
            for user in notification['receivers']:
                phone_numbers.append("+972" + str(user))
            send_via_gateway({'message': notification['message'], 'receiver_list':[phone_numbers]})
        elif notification['type'] == 'system_notification':
            for user in notification['users']:
                send_notification(notification['subject'],json.dumps([user]),notification['doctype'],notification['docname'],'Alert',notification['message'])

@frappe.whitelist()
def set_user_defaults(key,value):
	frappe.defaults.set_user_default(key,value,frappe.session.user)
	frappe.db.commit()
	
@frappe.whitelist(allow_guest=True)
def get_logged_session():
	return frappe.session

@frappe.whitelist(allow_guest=True)
def get_company_details():
    # Be defensive: user_settings may be empty/malformed, and we should not crash the API.
    selected_profile = None
    try:
        raw = frappe.model.utils.user_settings.get("Company")
        if raw:
            selected_profile = (json.loads(raw) or {}).get("selectedProfile")
    except Exception:
        selected_profile = None

    company = (
        selected_profile
        or frappe.defaults.get_user_default("Company")
        or frappe.get_doc("Company", frappe.get_list("Company", fields=["name"])[0].name).name
    )
    return frappe.get_doc("Company", company)
    

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

@frappe.whitelist()
def create_employee_attendance(company=None):
	"""
	Process employee attendance with bulk data fetching and improved error handling.
	"""
	try:
		print("🔄 Starting employee attendance processing...")

		selected_profile = None
		try:
			raw = frappe.model.utils.user_settings.get("Company")
			if raw:
				selected_profile = (json.loads(raw) or {}).get("selectedProfile")
		except Exception:
			selected_profile = None
		if company is None:
			company = (
				selected_profile
				or frappe.defaults.get_user_default("Company")
				or frappe.get_doc("Company", frappe.get_list("Company", fields=["name"])[0].name).name
			)

		print("📥 Fetching employee data and unlinked checkins...")
		employees = frappe.get_list(
			"Employee",
			filters={'status': 'Active', 'company': company},
			fields=['name', 'first_name', 'last_name', 'employee_name'],
		)
		
		if not employees:
			print("❌ No employees found in the system")
			return


		# Fetch all unlinked checkins for all employees in one query
		employee_names = [emp.name for emp in employees]
		all_checkins = frappe.get_list(
			"Employee Checkin",
			filters={'employee': ['in', employee_names], 'attendance': ['=', '']},
			fields=['name', 'time', 'log_type', 'employee'],
			order_by='employee, time asc'
		)
		
		# Group checkins by employee
		checkins_by_employee = {}
		for checkin in all_checkins:
			if checkin.employee not in checkins_by_employee:
				checkins_by_employee[checkin.employee] = []
			checkins_by_employee[checkin.employee].append(checkin)
		
		print(f"👥 Found {len(employees)} employees")
		print(f"🔗 Found {len(all_checkins)} unlinked checkins")
		print(f"📊 {len(checkins_by_employee)} employees have unlinked checkins")
		print(f"🏢 Company: {company}")
		print("-" * 60)
		
		# Process each employee's attendance
		processed_count = 0
		total_issues = 0
		
		for employee in employees:
			employee_name = _build_employee_name(employee)
			employee_checkins = checkins_by_employee.get(employee.name, [])
			
			if not employee_checkins:
				print(f"⏭️  {employee_name}: No unlinked checkins found")
				continue
				
			print(f"\n👤 Processing: {employee_name} ({len(employee_checkins)} checkins)")
			
			# Process this employee's checkins with improved logic
			created_records, employee_issues = _process_employee_attendance(
				employee, employee_checkins, company
			)
			processed_count += created_records
			total_issues += employee_issues
			
		print("\n" + "=" * 60)
		print(f"✅ Processing completed!")
		print(f"📈 Total attendance records created: {processed_count}")
		print(f"⚠️  Total issues found: {total_issues}")
		
	except Exception as e:
		print(f"💥 Critical error in attendance processing: {str(e)}")
		frappe.log_error("Attendance Processing", f"Error in create_employee_attendance: {str(e)}")
		raise


def _build_employee_name(employee):
	"""Build employee full name from first and last name."""
	fullname = employee.first_name or ""
	if employee.last_name and employee.last_name.strip():
		fullname += " " + employee.last_name
	return fullname


def _get_checkin_day(checkin_time):
	"""Get the checkin day adjusted for timezone (UTC-5)."""
	return (checkin_time - timedelta(hours=5)).strftime('%Y/%m/%d')


def _format_timestamp(dt):
	"""Format timestamp for error messages."""
	return dt.strftime("%d/%m/%Y, %H:%M:%S")


def _process_employee_attendance(employee, checkins, company_name):
	"""
	Process all checkins for a single employee and create attendance records.
	Returns: (created_count, issues_count)
	"""
	# Treat "today" in the same adjusted timezone used for day grouping (UTC-5)
	today = (frappe.utils.now_datetime() - timedelta(hours=5)).date()
	# Count checkin types for verbose output
	checkin_types = {}
	for checkin in checkins:
		checkin_types[checkin.log_type] = checkin_types.get(checkin.log_type, 0) + 1
	
	print(f"      📋 Checkin types: {', '.join([f'{k}({v})' for k, v in checkin_types.items()])}")
	
	# Initialize attendance tracking
	attendance_data = {}
	checkin_stack = []
	issues_count = 0
	
	# Process each checkin (simplified from original logic)
	for checkin in checkins:
		checkin_day = _get_checkin_day(checkin.time)
		
		# Initialize day structure if needed
		if checkin_day not in attendance_data:
			if checkin.log_type == 'IN':
				attendance_data[checkin_day] = {
					'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []
				}
		
		# Process based on log type (original logic simplified)
		if checkin.log_type == 'IN':
			if checkin_day in attendance_data and attendance_data[checkin_day]['check_in'] is not None:
				attendance_data[checkin_day]['issues'].append(f"{_format_timestamp(checkin.time)} - Double Check-IN same day")
				issues_count += 1
			elif checkin_day in attendance_data:
				attendance_data[checkin_day]['check_in'] = checkin
				checkin_stack.append(checkin)
			
		elif checkin.log_type == 'OUT':
			if not checkin_stack:
				# Check-out without check-in
				if checkin_day not in attendance_data:
					attendance_data[checkin_day] = {'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []}
				attendance_data[checkin_day]['issues'].append(f"{_format_timestamp(checkin.time)} - Check-out without check-in")
				issues_count += 1
			else:
				clock_in = checkin_stack.pop()
				clockin_day = _get_checkin_day(clock_in.time)
				
				# Check if shift spans more than 2 days
				day_diff = (checkin.time - timedelta(hours=5)).day - (clock_in.time - timedelta(hours=5)).day
				if day_diff > 1:
					attendance_data[clockin_day]['issues'].append(f"{_format_timestamp(clock_in.time)} - Employee checked in for more than 2 days")
					issues_count += 1
				else:
					attendance_data[clockin_day]['check_out'] = checkin
				
				# FIXED: Handle unclosed check-ins - assign to their correct days
				while checkin_stack:
					unclosed_checkin = checkin_stack.pop()
					unclosed_day = _get_checkin_day(unclosed_checkin.time)
					unclosed_date = (unclosed_checkin.time - timedelta(hours=5)).date()
					
					# Do not flag current-day open shifts; they may still be in progress
					if unclosed_date == today:
						continue
					
					if unclosed_day not in attendance_data:
						attendance_data[unclosed_day] = {'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []}
					
					attendance_data[unclosed_day]['issues'].append(f"{_format_timestamp(unclosed_checkin.time)} - Checkin without checkout")
					issues_count += 1
			
		elif checkin.log_type == 'Break-OUT':
			if checkin_day not in attendance_data:
				if checkin_stack:
					checkin_day = _get_checkin_day(checkin_stack[-1].time)
					attendance_data[checkin_day]['breaks'].append(checkin)
				else:
					attendance_data[checkin_day] = {'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []}
					attendance_data[checkin_day]['issues'].append(f"{_format_timestamp(checkin.time)} - Break-out without check-in")
					issues_count += 1
			else:
				attendance_data[checkin_day]['breaks'].append(checkin)
			
		elif checkin.log_type == 'Break-IN':
			if checkin_day not in attendance_data:
				if checkin_stack:
					checkin_day = _get_checkin_day(checkin_stack[-1].time)
				else:
					attendance_data[checkin_day] = {'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []}
					attendance_data[checkin_day]['issues'].append(f"{_format_timestamp(checkin.time)} - Break-in without check-in")
					issues_count += 1
					continue
			
			day_data = attendance_data[checkin_day]
			if day_data['breaks']:
				break_out = day_data['breaks'].pop(0)
				day_data['break_log'].append({'out': break_out, 'in': checkin})
			else:
				day_data['issues'].append(f"{_format_timestamp(checkin.time)} - Break in before break out")
				issues_count += 1
		else:
			# Unknown checkin type
			if checkin_day not in attendance_data:
				attendance_data[checkin_day] = {'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []}
			attendance_data[checkin_day]['issues'].append(f"{_format_timestamp(checkin.time)} - Unknown checkin type")
			issues_count += 1
	
	# FIXED: Handle any remaining unclosed check-ins - assign to correct days
	if checkin_stack:
		print(f"      ⚠️  {len(checkin_stack)} unclosed check-in(s) remaining")
		for unclosed_checkin in checkin_stack:
			unclosed_day = _get_checkin_day(unclosed_checkin.time)
			unclosed_date = (unclosed_checkin.time - timedelta(hours=5)).date()
			
			# Do not flag current-day open shifts; they may still be in progress
			if unclosed_date == today:
				continue
			
			if unclosed_day not in attendance_data:
				attendance_data[unclosed_day] = {'check_in': None, 'check_out': None, 'breaks': [], 'break_log': [], 'issues': []}
			
			attendance_data[unclosed_day]['issues'].append(f"{_format_timestamp(unclosed_checkin.time)} - Checkin without checkout (end of processing)")
			issues_count += 1
	
	# Create attendance records for valid days
	created_count = 0
	print(f"   📅 Processing {len(attendance_data)} days:")
	
	for day, day_data in attendance_data.items():
		day_issues = day_data['issues']
		has_checkout = day_data['check_out'] is not None
		has_checkin = day_data['check_in'] is not None
		
		if day_issues:
			print(f"      🗓️  {day}: ❌ SKIPPED - {len(day_issues)} issue(s)")
			for issue in day_issues:
				print(f"         ⚠️  {issue}")
		elif not has_checkin:
			print(f"      🗓️  {day}: ❌ SKIPPED - No check-in found")
			issues_count += 1
		elif not has_checkout:
			print(f"      🗓️  {day}: ❌ SKIPPED - No check-out found (incomplete day)")
			issues_count += 1
		else:
			# Valid day - create attendance using improved function
			try:
				check_in_time = day_data['check_in'].time.strftime("%H:%M")
				check_out_time = day_data['check_out'].time.strftime("%H:%M")
				break_count = len(day_data['break_log'])
				
				status, attendance_name = _create_attendance_record(day_data, company_name, employee)
				
				if status == "created":
					print(f"      🗓️  {day}: ✅ CREATED - {check_in_time} to {check_out_time}" +
						  (f" ({break_count} breaks)" if break_count > 0 else ""))
					created_count += 1
				elif status == "existing":
					print(f"      🗓️  {day}: 🔁 EXISTS - linked checkins to existing attendance ({attendance_name})")
				elif status == "skipped_inactive":
					print(f"      🗓️  {day}: ⛔ SKIPPED - employee is inactive")
					issues_count += 1
				else:
					# Any other non-fatal outcome
					print(f"      🗓️  {day}: ⚠️  SKIPPED - {status}")
					issues_count += 1
				
			except Exception as e:
				print(f"      🗓️  {day}: 💥 ERROR - Failed to create: {str(e)}")
				frappe.log_error("Attendance Creation", f"Error creating attendance for {_build_employee_name(employee)} on {day}: {str(e)}")
				issues_count += 1
	
	# Summary for this employee
	if created_count > 0:
		print(f"   ✅ {_build_employee_name(employee)}: {created_count} attendance record(s) created")
	if issues_count > 0:
		print(f"   ⚠️  {_build_employee_name(employee)}: {issues_count} issue(s) found")
	
	return created_count, issues_count


def _create_attendance_record(day_data, company_name, employee):
	"""
	Create attendance record with fixed time calculations.
	"""
	import calendar
	from datetime import date
	
	employee_id = day_data['check_in'].employee
	attendance_date = day_data['check_in'].time.date()

	# If attendance already exists for that employee/date, do NOT try to create another one.
	# Instead, just link the checkins to the existing attendance record.
	existing_attendance = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee_id,
			"attendance_date": attendance_date,
			"docstatus": ["!=", 2],  # ignore cancelled attendance
		},
		pluck="name",
		limit=1,
	)
	existing_attendance_name = existing_attendance[0] if existing_attendance else None

	# Collect all related checkin names for linking (used both for created/existing)
	checkin_names = [day_data['check_in'].name]
	for break_entry in day_data['break_log']:
		break_out = break_entry['out']
		break_in = break_entry['in']
		checkin_names.extend([break_out.name, break_in.name])
	checkin_names.append(day_data['check_out'].name)

	if existing_attendance_name:
		frappe.db.sql(
			"""
			UPDATE `tabEmployee Checkin`
			SET attendance = %s
			WHERE name IN ({})
			""".format(",".join(["%s"] * len(checkin_names))),
			[existing_attendance_name] + checkin_names,
		)
		frappe.db.commit()
		print(
			f"            🔁 Attendance already exists ('{existing_attendance_name}'); linked {len(checkin_names)} checkins"
		)
		return "existing", existing_attendance_name

	# Skip creating any HR transactions for inactive employees
	employee_status = frappe.db.get_value("Employee", employee_id, "status")
	if employee_status and employee_status != "Active":
		print(f"            ⛔ Employee '{employee_id}' is '{employee_status}' - skipping attendance creation")
		return "skipped_inactive", None
	
	# FIXED: Use total_seconds() instead of just seconds for correct time calculation
	time_diff = day_data['check_out'].time - day_data['check_in'].time
	working_hours = round(time_diff.total_seconds() / 3600, 2)
	
	# Calculate month range for overtime calculation
	check_in_date = day_data['check_in'].time
	this_month = date(check_in_date.year, check_in_date.month, 1)
	days_in_month = calendar.monthrange(check_in_date.year, check_in_date.month)[1]
	next_month = this_month + timedelta(days=days_in_month)
	
	# Get previous work in month
	previous_work = frappe.db.sql("""
		SELECT COALESCE(SUM(working_hours) - SUM(COALESCE(break_hours, 0)), 0) as net_working_hours
		FROM `tabAttendance` 
		WHERE employee = %s AND attendance_date BETWEEN %s AND %s
	""", [employee_id, this_month, next_month], as_dict=True)
	
	previous_net_hours = previous_work[0].net_working_hours if previous_work else 0
	
	# Create attendance document
	attendance_doc = frappe.get_doc({
		'doctype': 'Attendance',
		'attendance_date': attendance_date,
		'employee': employee_id,
		'company': company_name,
		'employee_name': employee.employee_name,
		'working_hours': working_hours,
		'status': 'Present',
		'in_time': day_data['check_in'].time,
		'out_time': day_data['check_out'].time,
	})
	
	# Process breaks and calculate total break hours
	total_break_hours = 0
	
	for break_entry in day_data['break_log']:
		break_out = break_entry['out']  # Break start
		break_in = break_entry['in']    # Break end
		
		# FIXED: Use total_seconds() for break duration calculation too
		break_duration = break_in.time - break_out.time
		break_hours = round(break_duration.total_seconds() / 3600, 2)
		
		if break_hours > 0:
			attendance_doc.append('breaks', {
				'break_out': break_out.time, 
				'break_in': break_in.time
			})
			total_break_hours += break_hours
	
	attendance_doc.break_hours = total_break_hours
	
	# Calculate overtime
	net_working_hours = previous_net_hours + working_hours - total_break_hours
	attendance_doc.overtime_hours = max(0, net_working_hours - 208)
	
	# Verbose output for debugging
	if total_break_hours > 0:
		print(f"            ⏰ Working: {working_hours}h, Breaks: {total_break_hours}h, Net: {working_hours - total_break_hours}h")
	else:
		print(f"            ⏰ Working: {working_hours}h (no breaks)")
	
	if attendance_doc.overtime_hours > 0:
		print(f"            ⏱️  Overtime: {attendance_doc.overtime_hours}h (monthly total: {net_working_hours}h)")
	
	# Save and submit
	try:
		attendance_doc.insert(ignore_permissions=True)
		attendance_doc.submit()
	except Exception as e:
		# Race-condition safety: another process may have created attendance after our "exists" check.
		# If it's a duplicate attendance error, fall back to linking checkins to the existing record.
		msg = str(e)
		if ("Duplicate Attendance" in msg) or ("already marked for the date" in msg):
			existing_attendance = frappe.get_all(
				"Attendance",
				filters={
					"employee": employee_id,
					"attendance_date": attendance_date,
					"docstatus": ["!=", 2],
				},
				pluck="name",
				limit=1,
			)
			existing_attendance_name = existing_attendance[0] if existing_attendance else None
			if existing_attendance_name:
				frappe.db.sql(
					"""
					UPDATE `tabEmployee Checkin`
					SET attendance = %s
					WHERE name IN ({})
					""".format(",".join(["%s"] * len(checkin_names))),
					[existing_attendance_name] + checkin_names,
				)
				frappe.db.commit()
				print(
					f"            🔁 Attendance already exists ('{existing_attendance_name}'); linked {len(checkin_names)} checkins"
				)
				return "existing", existing_attendance_name
		# Not a duplicate, bubble up to be logged by caller
		raise
	
	# Bulk update checkin records
	frappe.db.sql("""
		UPDATE `tabEmployee Checkin` 
		SET attendance = %s 
		WHERE name IN ({})
	""".format(','.join(['%s'] * len(checkin_names))), 
	[attendance_doc.name] + checkin_names)
	
	print(f"            📄 Attendance record '{attendance_doc.name}' created and linked to {len(checkin_names)} checkins")

	frappe.db.commit()
	return "created", attendance_doc.name


def create_and_link_attendance(attendances):
	"""
	Legacy function - kept for backward compatibility.
	"""
	company = frappe.get_list("Company", limit=1)
	company_name = company[0].name if company else None
	
	# Get employee data
	employee = attendances['check_in'].employee
	employee_data = frappe.get_doc("Employee", employee)
	
	return _create_attendance_record(attendances, company_name, employee_data)
	

def getAssignments(args=None):
	"""get assigned to"""
	if not args:
		args = frappe.local.form_dict

	return frappe.get_all(
		"ToDo",
		fields=["allocated_to as owner", "name"],
		filters={
			"reference_type": args.get("doctype"),
			"reference_name": args.get("name"),
			"status": ("!=", "Cancelled"),
		},
		limit=5,
	)

@frappe.whitelist()
def assign(args=None):
	"""add in someone's to do list
	args = {
			"assign_to": [],
			"doctype": ,
			"name": ,
			"description": ,
			"assignment_rule":,
			"skip_system_email"
	}

	"""
	if not args:
		args = frappe.local.form_dict

	users_with_duplicate_todo = []
	shared_with_users = []

	for assign_to in frappe.parse_json(args.get("assign_to")):
		filters = {
			"reference_type": args["doctype"],
			"reference_name": args["name"],
			"status": "Open",
			"allocated_to": assign_to,
		}


		from frappe.utils import nowdate

		if not args.get("description"):
			args["description"] = _("Assignment for {0} {1}").format(args["doctype"], args["name"])

		d = frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": assign_to,
				"reference_type": args["doctype"],
				"reference_name": args["name"],
				"description": args.get("description"),
				"priority": args.get("priority", "Medium"),
				"status": "Open",
				"date": args.get("date", nowdate()),
				"assigned_by": args.get("assigned_by", frappe.session.user),
				"assignment_rule": args.get("assignment_rule"),
			}
		).insert(ignore_permissions=True)

		# set assigned_to if field exists
		if frappe.get_meta(args["doctype"]).get_field("assigned_to"):
			frappe.db.set_value(args["doctype"], args["name"], "assigned_to", assign_to)

		doc = frappe.get_doc(args["doctype"], args["name"])

		# if assignee does not have permissions, share or inform
		if not frappe.has_permission(doc=doc, user=assign_to):
			if frappe.get_system_settings("disable_document_sharing"):
				msg = _("User {0} is not permitted to access this document.").format(frappe.bold(assign_to))
				msg += "<br>" + _(
					"As document sharing is disabled, please give them the required permissions before assigning."
				)
				frappe.throw(msg, title=_("Missing Permission"))
			else:
				frappe.share.add(doc.doctype, doc.name, assign_to)
				shared_with_users.append(assign_to)

		# make this document followed by assigned user
		if frappe.get_cached_value("User", assign_to, "follow_assigned_documents"):
			follow_document(args["doctype"], args["name"], assign_to)
	
		# notify
		if not args["skip_system_email"] == 1:
			notify_assignment(
				d.assigned_by,
				d.allocated_to,
				d.reference_type,
				d.reference_name,
				action="ASSIGN",
				description=args.get("description"),
			)

	if shared_with_users:
		user_list = "<br><br>" + "<br>".join(shared_with_users)
		frappe.msgprint(
			_("Shared with the following Users with Read access:{0}").format(user_list, alert=True)
		)

	if users_with_duplicate_todo:
		user_list = "<br><br>" + "<br>".join(users_with_duplicate_todo)
		frappe.msgprint(_("Already in the following Users ToDo list:{0}").format(user_list, alert=True))

	return getAssignments(args)


def notify_assignment(
	assigned_by, allocated_to, doc_type, doc_name, action="CLOSE", description=None
):
	"""
	Notify assignee that there is a change in assignment
	"""
	if not (assigned_by and allocated_to and doc_type and doc_name):
		return

	# return if self assigned or user disabled
	if assigned_by == allocated_to or not frappe.db.get_value("User", allocated_to, "enabled"):
		return

	# Search for email address in description -- i.e. assignee
	user_name = frappe.get_cached_value("User", frappe.session.user, "full_name")
	title = get_title(doc_type, doc_name)
	description_html = f"<div>{description}</div>" if description else None
	if action == "SHARE":
		subject = _("{0} Shared a {1} with you").format(
			frappe.bold(user_name),frappe.bold(doc_type)
		)
	else:
		user_name = frappe.bold(user_name)
		document_type = frappe.bold(doc_type)
		title = get_title_html(title)
		subject = _("{0} assigned a new task {1} {2} to you").format(user_name, document_type, title)

	notification_doc = {
		"type": "Assignment",
		"document_type": doc_type,
		"subject": subject,
		"document_name": doc_name,
		"from_user": frappe.session.user,
		"email_content": description_html,
	}

	enqueue_create_notification(allocated_to, notification_doc)
 
@frappe.whitelist(allow_guest=True)
def convert_docx_to_pdf():
	if 'docx_file' not in frappe.request.files:
		frappe.throw("No file uploaded")
	
	# Get the uploaded DOCX file
	docx_file = frappe.request.files['docx_file'].stream.read()

	# Save the uploaded DOCX file temporarily
	temp_doc_path = "/tmp/temp_doc.docx"
	with open(temp_doc_path, "wb") as f:
		f.write(docx_file)

	# Convert DOCX to PDF using pdfkit or another library
	try:
		temp_pdf_path = "/tmp/temp_doc.pdf"
		pdfkit.from_file(temp_doc_path, temp_pdf_path)

		# Read the generated PDF
		with open(temp_pdf_path, "rb") as pdf_file:
			pdf_content = pdf_file.read()

		response = Response(pdf_content, content_type='application/pdf')
		response.headers['Content-Disposition'] = 'attachment; filename="document.pdf"'
		return response
	except OSError as e:
		frappe.log_error(frappe.get_traceback(), "Docx to PDF conversion failed")
		return {"message": "Error converting document", "error": str(e)}, 500


def update_employee_timesheet_on_attendance_creation(doc, method):
	employee = doc.employee
	employee_doc = frappe.get_doc("Employee", employee)
	if employee_doc.status != "Active":
		return False
	
	working_hours = doc.working_hours
	in_time = doc.in_time
 
	attendance_month = in_time.month
	attendance_year = in_time.year

	timesheet_start_range = datetime(attendance_year, attendance_month, 1)
	timesheet_end_range = datetime(attendance_year, attendance_month, calendar.monthrange(attendance_year, attendance_month)[1])

	timesheets = frappe.get_list("Timesheet", fields="*", filters = {"employee": employee, "docstatus": 0, "start_date": ["between", (timesheet_start_range.date(),timesheet_end_range.date())]})
	
	if(len(timesheets) == 0):
		# create timesheet for this month
		timesheet = frappe.new_doc("Timesheet")
		timesheet.start_date = timesheet_start_range
		timesheet.end_date = timesheet_end_range
		timesheet.employee = doc.employee
		timesheet.append('time_logs',{'from_time':in_time, 'hours': working_hours, 'activity_type': 'Wage'})
	else:
		# append timesheet record for the day (multiply overtime hours with rate)
		timesheet = frappe.get_doc("Timesheet", timesheets[-1])
		for log in timesheet.time_logs:
			if log.from_time == in_time:
				return False
		timesheet.append('time_logs',{'from_time':in_time, 'hours': working_hours, 'activity_type': 'Wage'}) 
	timesheet.save()
 
 
@frappe.whitelist()
def get_list_with_children(doctype, filters=None, fields=None, order_by="modified desc", limit=None):
    """
    Fetch a list of documents with their children.
    Optimized version to reduce database queries from N+1 to a few bulk queries.

    Args:
        doctype (str): The DocType to query.
        filters (dict or list, optional): Filters to apply. Defaults to None.
        fields (list, optional): List of fields to fetch. Defaults to None.
        order_by (str, optional): Order by clause. Defaults to "modified desc".
        limit (int, optional): Limit the number of records to fetch. Defaults to None.
    Returns:
        list: List of documents with children.
    """
    try:
        # Ensure filters and fields are valid
        filters = filters or {}
        
        # Ensure `filters` is correctly deserialized
        if isinstance(filters, str):
            import json
            filters = json.loads(filters)

        # Get document names efficiently with pluck to get just the names
        doc_names = frappe.get_all(
            doctype, 
            filters=filters, 
            fields=["name"], 
            order_by=order_by, 
            limit=limit,
            pluck="name"
        )
        
        if not doc_names:
            return []

        # Get meta information for the doctype
        meta = frappe.get_meta(doctype)
        
        # Identify child table fields
        child_table_fields = []
        for field in meta.fields:
            if field.fieldtype == "Table":
                child_table_fields.append({
                    'fieldname': field.fieldname,
                    'child_doctype': field.options
                })

        # Bulk fetch parent records with all fields
        parent_records = frappe.get_all(
            doctype,
            filters={"name": ["in", doc_names]},
            fields="*"
        )
        
        # Create a mapping for maintaining order
        name_to_record = {record.name: record for record in parent_records}
        
        # Bulk fetch child records for each child table
        child_data = {}
        for child_field in child_table_fields:
            fieldname = child_field['fieldname']
            child_doctype = child_field['child_doctype']
            
            # Fetch all child records for all parents in one query
            child_records = frappe.get_all(
                child_doctype,
                filters={
                    "parent": ["in", doc_names],
                    "parenttype": doctype
                },
                fields="*",
                order_by="parent, idx"
            )
            
            # Group child records by parent
            child_data[fieldname] = {}
            for child_record in child_records:
                parent_name = child_record.parent
                if parent_name not in child_data[fieldname]:
                    child_data[fieldname][parent_name] = []
                child_data[fieldname][parent_name].append(child_record)

        # Construct document objects maintaining the original order and structure
        result_documents = []
        for doc_name in doc_names:
            if doc_name in name_to_record:
                parent_record = name_to_record[doc_name]
                
                # Create a new document object
                doc = frappe.new_doc(doctype)
                
                # Set parent fields
                for key, value in parent_record.items():
                    if hasattr(doc, key):
                        setattr(doc, key, value)
                
                # Set child table data
                for child_field in child_table_fields:
                    fieldname = child_field['fieldname']
                    if fieldname in child_data and doc_name in child_data[fieldname]:
                        # Clear existing child records
                        setattr(doc, fieldname, [])
                        
                        # Add child records
                        for child_record in child_data[fieldname][doc_name]:
                            child_doc = frappe.new_doc(child_field['child_doctype'])
                            for child_key, child_value in child_record.items():
                                if hasattr(child_doc, child_key):
                                    setattr(child_doc, child_key, child_value)
                            
                            # Append to parent
                            doc.append(fieldname, child_doc)
                
                # Set document as loaded to avoid additional queries
                doc._doc_before_save = None
                doc.flags.ignore_permissions = True
                
                result_documents.append(doc)

        return result_documents
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error in get_list_with_children"))
        frappe.throw(_("An error occurred while fetching records. Please check the logs for more details."))

@frappe.whitelist()
def get_multiple_lists_with_children(doctypes):
    """
    Fetch multiple lists of documents with their children in a single API call.

    Args:
        doctypes (list): Array of objects, each containing:
            - doctype (str): The DocType to query
            - entity (str, optional): Key name to use in response dict (defaults to doctype)
            - filters (dict or list, optional): Filters to apply
            - fields (list, optional): List of fields to fetch
            - order_by (str, optional): Order by clause

    Returns:
        dict: Dictionary with entity (or doctype) as key and list of documents as value,
              plus an "assignees" key containing unique set of all assignees
    """
    try:
        # Ensure doctypes is properly deserialized
        if isinstance(doctypes, str):
            import json
            doctypes = json.loads(doctypes)
        
        if not isinstance(doctypes, list):
            frappe.throw(_("doctypes parameter must be a list/array"))
        
        result = {}
        all_assignees = set()  # Use set to automatically handle uniqueness
        
        for query in doctypes:
            if not isinstance(query, dict):
                frappe.throw(_("Each query must be an object/dictionary"))
            
            doctype = query.get('doctype')
            if not doctype:
                frappe.throw(_("doctype is required for each query"))
            
            # Use entity as key if provided, otherwise fall back to doctype
            result_key = query.get('entity', doctype)
            
            filters = query.get('filters') or {}
            fields = query.get('fields') or ["name"]
            order_by = query.get('order_by') or "modified desc"
            
            # Ensure _assign field is included in fields if not already present
            if isinstance(fields, list) and "_assign" not in fields:
                fields = fields + ["_assign"]
            
            # Ensure filters is properly deserialized if it's a string
            if isinstance(filters, str):
                filters = json.loads(filters)
            
            # Handle _assign field filtering - convert to LIKE pattern
            if isinstance(filters, list):
                processed_filters = []
                for filter_item in filters:
                    if isinstance(filter_item, list) and len(filter_item) >= 3:
                        field, operator, value = filter_item[0], filter_item[1], filter_item[2]
                        if field == "_assign" and operator == "=":
                            # Convert _assign equality filter to LIKE pattern
                            processed_filters.append([field, "like", f"%{value}%"])
                        else:
                            processed_filters.append(filter_item)
                    else:
                        processed_filters.append(filter_item)
                filters = processed_filters
            elif isinstance(filters, dict):
                processed_filters = {}
                for field, value in filters.items():
                    if field == "_assign":
                        # Convert _assign equality filter to LIKE pattern
                        if isinstance(value, list) and len(value) >= 2 and value[0] == "=":
                            processed_filters[field] = ("like", f"%{value[1]}%")
                        else:
                            processed_filters[field] = ("like", f"%{value}%")
                    else:
                        processed_filters[field] = value
                filters = processed_filters
            
            # Fetch the documents for this doctype
            doc_names = frappe.get_list(doctype, filters=filters, fields=fields, order_by=order_by)
            
            # Retrieve full documents for the fetched names and ensure _assign is included
            documents = []
            for doc_data in doc_names:
                doc = frappe.get_doc(doctype, doc_data["name"])
                
                # Check if _assign field exists in the table
                try:
                    table_columns = frappe.db.get_table_columns(doctype)
                    has_assign_field = "_assign" in table_columns
                    frappe.logger().info(f"Table {doctype} has _assign field: {has_assign_field}")
                    frappe.logger().info(f"Table columns: {table_columns}")
                except Exception as e:
                    frappe.logger().info(f"Error checking table structure: {e}")
                    has_assign_field = False
                
                # Get _assign field directly from database to ensure it's included
                assign_value = None
                if has_assign_field:
                    try:
                        assign_value = frappe.db.get_value(doctype, doc_data["name"], "_assign")
                        frappe.logger().info(f"_assign value for {doc_data['name']}: {assign_value}")
                    except Exception as e:
                        frappe.logger().info(f"Error getting _assign value: {e}")
                
                # Also check if there are any ToDo records for this document (standard assignment approach)
                todo_assignments = frappe.get_all(
                    "ToDo",
                    filters={
                        "reference_type": doctype,
                        "reference_name": doc_data["name"],
                        "status": ("not in", ("Cancelled", "Closed")),
                        "allocated_to": ("is", "set"),
                    },
                    fields=["allocated_to"]
                )
                
                if assign_value:
                    try:
                        # Parse _assign if it's a JSON string
                        if isinstance(assign_value, str):
                            parsed_assign = json.loads(assign_value)
                        else:
                            parsed_assign = assign_value
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, keep original value
                        parsed_assign = assign_value
                elif todo_assignments:
                    # Use ToDo assignments if _assign field is empty
                    parsed_assign = [todo.allocated_to for todo in todo_assignments]
                    frappe.logger().info(f"Using ToDo assignments for {doc_data['name']}: {parsed_assign}")
                else:
                    # If _assign field is empty/None, set it to empty list
                    parsed_assign = []
                
                # Add assignees to the global set
                if isinstance(parsed_assign, list):
                    for assignee in parsed_assign:
                        if assignee:  # Only add non-empty assignees
                            all_assignees.add(assignee)
                elif parsed_assign:  # Single assignee
                    all_assignees.add(parsed_assign)
                
                # Convert document to dictionary to ensure all fields are serialized
                doc_dict = doc.as_dict()
                
                # Explicitly add _assign field to the dictionary
                doc_dict['_assign'] = parsed_assign
                frappe.logger().info(f"Final _assign value in response: {parsed_assign}")
                
                documents.append(doc_dict)
            
            # Store in result dictionary using entity key
            result[result_key] = documents
        
        # Add unique assignees to the result
        result["assignees"] = sorted(list(all_assignees))  # Convert set to sorted list
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error in get_multiple_lists_with_children"))
        frappe.throw(_("An error occurred while fetching records. Please check the logs for more details."))



@frappe.whitelist()
def vote(doctype, docname, fieldname, unique_field, values, is_delete):
    doc = frappe.get_doc(doctype, docname)
    
    table_data = [f.get(unique_field) for f in doc.get(fieldname)]

    for value in values:
        if value.get(unique_field) in table_data:
            for item in doc.get(fieldname):
                if item.get(unique_field) == value.get(unique_field):
                    if is_delete:
                        doc.remove(item)
                    else:
                        for key, val in value.items():
                            item.set(key, val)
        else:
            if not is_delete:
                doc.append(fieldname, value)
    
    doc.save()    


@frappe.whitelist()
def get_unseen_docs(entities):
    """
    API to return documents from the specified entities that have not been seen by the current user.
    """
    # Step 1: Parse the entities parameter if it's a JSON string.
    try:
        entities = json.loads(entities)
    except json.JSONDecodeError:
        frappe.throw(_("Invalid parameter: 'entities' should be a JSON string representing an array of strings."))

    if not isinstance(entities, list):
        frappe.throw(_("Invalid parameter: 'entities' should be a list of strings."))

    # Step 2: Get entities filtered by the provided parameter.
    entity_docs = frappe.get_all('Entity', filters={'entity': ['in', entities]}, fields=['model', 'filters'])
    
    # Step 3: Gather all documents from the doctypes marked as "Track Seen".
    unseen_docs = []
    for entity in entity_docs:
        model_doctype = entity.get('model')
        filters = frappe.parse_json(entity.get('filters', '{}'))  # Parse filters if available

        if model_doctype and frappe.get_meta(model_doctype).track_seen:
            # Get list of documents with the provided filters and include the 'doctype' field.
            docs = frappe.get_list(
                model_doctype,
                filters=filters,
                fields=['doctype', 'name', 'creation', 'modified'],  # Ensure 'doctype' is included
                order_by='creation asc'
            )
            unseen_docs.extend(docs)
            
    print(unseen_docs)
    # Step 4: Filter out docs that have been seen by the current user.
    current_user = frappe.session.user
    unseen_docs = [
        doc for doc in unseen_docs
        if 'doctype' in doc and not frappe.get_doc(doc['doctype'], doc['name']).is_seen_by(current_user)
    ]

    return unseen_docs



@frappe.whitelist()
def openai_chat(return_response=False):
    from openai import OpenAI
    site_settings = frappe.get_doc("Site Settings")

    if site_settings.openai_key != None:
        client = OpenAI(
			api_key=site_settings.openai_key
		)

    ai_exec = frappe.get_attr('ui_builder.api.ai_exec')
    try:
        # Get the JSON payload from the request
        data = frappe.local.form_dict
        
        # Validate required fields
        if not data.get('model') or not data.get('user'):
            frappe.throw(_("Both 'model' and 'user' are required fields."))
        
        model = data.get('model')
        message = data.get('user')
        # system = data.get('system')
		

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": ""},
                    {"role": "user", "content": message},
                ]
            )
            frappe.logger("frappe.web").debug(response.choices[0].message)
            if return_response:
                return response.choices[0].message.content
            return ai_exec(response.choices[0].message.content) 
        except Exception as e:
            return f"An error occurred: {e}"
    except Exception as e:
        frappe.throw(_("An error occurred: {0}").format(str(e)))
        
@frappe.whitelist()
def openai_chat_simple(data=None):
    from openai import OpenAI
    site_settings = frappe.get_doc("Site Settings")

    if site_settings.openai_key != None:
        client = OpenAI(
			api_key=site_settings.openai_key
		)
    try:
        # Get the JSON payload from the request
        if data == None:
            data = frappe.local.form_dict
        
        # Validate required fields
        if not data.get('model') or not data.get('user'):
            frappe.throw(_("Both 'model' and 'user' are required fields."))
        
        model = data.get('model')
        message = data.get('user')
        system = data.get('system')

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ]
            )
            #return response.choices[0].message.content
            frappe.logger("frappe.web").debug(response.choices[0].message.content)
            return response.choices[0].message 
        except Exception as e:
            return f"An error occurred: {e}"
    except Exception as e:
        frappe.throw(_("An error occurred: {0}").format(str(e)))
        
@frappe.whitelist()
def get_company_user_list(user):
    profile_context = frappe.get_doc("Profile Context")
    try:
        selected_profile = json.loads(frappe.model.utils.user_settings.get(profile_context.profile_doctype))['selectedProfile']
    except:
        return ""
    
    if frappe.session.user == "Administrator":
        return ""
    
    user_list = [d.user for d in frappe.get_list("User Permission", filters={'allow':'Company','for_value': selected_profile}, fields=['user'], ignore_permissions=True)]
    if len(user_list) == 0:
        return f"name = 'Null'"
    
    filter_string = f"name in{tuple(user_list)}".replace(',)', ')')
 
    return filter_string


@frappe.whitelist()
def ai_wrapper_test(template, **kwargs):
	site_settings = frappe.get_doc("Site Settings")
	log_doc = frappe.new_doc("OpenAi Prompt Log")
	log_doc.prompt_name = template
	log_doc.variables = json.dumps(kwargs)
	
	template_doc = frappe.get_doc("OpenAI Prompt Template", template)
	base_prompt = template_doc.base_prompt
	for variable in template_doc.variables:
		placeholder = '{' + variable.variable_name + '}'
		if variable.variable_name in kwargs:
			if variable.fieldtype == 'JSON':
				kwargs[variable.variable_name] = json.dumps(kwargs[variable.variable_name])
			base_prompt = base_prompt.replace(placeholder, kwargs[variable.variable_name])
		else:
			if variable.default_value is not None:
				base_prompt = base_prompt.replace(placeholder, variable.default_value)
	
	chat_result = openai_chat_simple(data={'model': site_settings.default_model, 'system': '', 'user': base_prompt})
	log_doc.openai_response = chat_result
	
	ai_exec = frappe.get_attr('ui_builder.api.ai_exec')
	execution_result = ai_exec(chat_result)   
	log_doc.api_response = execution_result 
	
	log_doc.save()


  
@frappe.whitelist(allow_guest=True)
def fetch_users():
    profile_context = frappe.get_doc("Profile Context")
    try:
        selected_profile = json.loads(frappe.model.utils.user_settings.get(profile_context.profile_doctype))['selectedProfile']
    except:
        return frappe.db.get_all("User",fields='*')
    
    additional_context = profile_context.profile_members_doctype
    
    # Check if additional_context is None or empty
    if not additional_context:
        return frappe.db.get_all("User",fields='*')
        
    context_doctype = frappe.get_doc("DocType", additional_context, ignore_permissions=True)
    filter_field = None
    for field in context_doctype.fields:
        if field.options == profile_context.profile_doctype:
            filter_field = field.fieldname
    
    if filter_field == None:
        return frappe.db.get_all("User",fields='*')
        
    user_data = []
    user_list = frappe.get_list("User", fields='*', ignore_permissions=True)
    for user in user_list:
        additional_context_data = frappe.db.get_all(additional_context, filters={'user': user.name, filter_field: selected_profile},fields='*',limit=1)
        if len(additional_context_data) > 0:
            user_data.append(additional_context_data[0].update(user))
       
    return user_data    
    
    
def item_before_insert(doc, method):
    if doc.variant_of:
        parent_item = frappe.get_doc("Item", doc.variant_of)
        doc.valuation_rate = parent_item.valuation_rate
        doc.standard_rate = parent_item.standard_rate
        doc.image = parent_item.image
        doc.warehouse_sections = parent_item.warehouse_sections
        
def website_item_before_insert(doc, method):
    parent_item = frappe.get_doc('Item', doc.item_code)
    doc.image = parent_item.image
    
def sales_invoice_before_insert(doc,method=None):
    total = doc.total
    doc.base_total = total
    doc.base_net_total = total
    doc.net_total = total
    doc.base_grand_total = total
    doc.base_rounded_total = total
    doc.grand_total = total
    doc.rounded_total = total
    # doc.outstanding_amount = total
    doc.amount_eligible_for_commission = total
    doc.is_return = int(doc.is_return)
    doc.is_pos = int(doc.is_pos)
    doc.is_consolidated = int(doc.is_consolidated)
    for item in doc.items:
        rate = item.rate
        amount = item.amount
        item.price_list_rate = rate
        item.base_price_list_rate = rate
        item.base_rate = rate
        item.stock_uom_rate = rate
        item.net_rate = rate
        item.base_net_rate = rate
        item.base_amount = amount
        item.net_amount = amount
        item.base_net_amount = amount
        
@frappe.whitelist()
def get_sales_by_item(from_date, to_date):
    sales_data = {}
    items = frappe.db.get_all("Item", fields='*' , filters={'item_group': ['!=', 'Raw Material']})
    total_sales = 0
    for item in items:
        item_sales = frappe.db.get_all('POS Invoice Item', filters={'item_code':item.name, 'creation':['between',(from_date,to_date)]}, fields='*')
        for item_sale in item_sales:
            total_sales += item_sale.base_amount
            if item_sale.item_code not in sales_data.keys():
                sales_data[item_sale.item_code] = {
                    'revenue': 0,
                    'orders' : 0,
                    'percentage': 0
                }
            sales_data[item_sale.item_code]['revenue'] += item_sale.base_amount
            sales_data[item_sale.item_code]['orders'] += item_sale.qty
            sales_data[item_sale.item_code]['item_group'] = item_sale.item_group
            sales_data[item_sale.item_code]['image'] = item.image
            
    return sales_data  

@frappe.whitelist()
def verify():
    company = frappe.get_doc("Company", frappe.get_list("Company")[0])
    if frappe.session.user != "Administrator":
        if frappe.local.request_ip == company.domain:
            return True
        else:
            return False
        
    company.domain = frappe.get_request_header('X-Forwarded-For')
    company.save()
    return "IP set successfully"
    
    
@frappe.whitelist()
def employee_attendance(date=None, employee=None, company=None):
    """
    Get employee attendance data for the specified month.
    If no date is provided, uses current month.
    
    Args:
        date: Date string in format 'YYYY-MM-DD' or datetime object
        
    Returns:
        Dict containing attendance data for all employees for the month
    """
    if company is None:
        # Be defensive: user_settings may be empty/malformed, and we should not crash the API.
        selected_profile = None
        try:
            raw = frappe.model.utils.user_settings.get("Company")
            if raw:
                selected_profile = (json.loads(raw) or {}).get("selectedProfile")
        except Exception:
            selected_profile = None

        company = (
            selected_profile
            or frappe.defaults.get_user_default("Company")
            or frappe.get_doc("Company", frappe.get_list("Company", fields=["name"])[0].name).name
        )
    # `company` should remain the input (string company name). Use a separate variable for the Doc.
    company_doc = frappe.get_doc("Company", company)

    print(f"[VERBOSE] Starting employee_attendance function with date parameter: {date}")
    
    # Parse input date and determine month/year to process
    if date is None:
        target_date = datetime.now() - timedelta(hours=5)  # Timezone offset
        print(f"[VERBOSE] No date provided, using current date with timezone offset: {target_date}")
    else:
        if isinstance(date, str):
            target_date = datetime.strptime(date, "%Y-%m-%d")
            print(f"[VERBOSE] Parsed string date: {date} -> {target_date}")
        else:
            target_date = date
            print(f"[VERBOSE] Using provided datetime object: {target_date}")
    
    current_day = target_date.day
    current_month = target_date.month
    current_year = target_date.year
    
    print(f"[VERBOSE] Processing data for: Day={current_day}, Month={current_month}, Year={current_year}")
    
    # Calculate month boundaries
    month_start = datetime(current_year, current_month, 1, 5)  # Start at 5 AM on 1st
    if current_month == 12:
        month_end = datetime(current_year + 1, 1, 1, 5)  # End at 5 AM on 1st of next year
    else:
        month_end = datetime(current_year, current_month + 1, 1, 5)  # End at 5 AM on 1st of next month
    
    print(f"[VERBOSE] Month boundaries: Start={month_start}, End={month_end}")
    
    # Configuration
    overtime_after = 208
    total_salaries = 0
    total_advances = 0
    
    print(f"[VERBOSE] Configuration: overtime_after={overtime_after} hours")
    
    # Get all active employees
    print(f"[VERBOSE] Fetching all active employees...")
    if employee:
        employee_list = frappe.get_all("Employee", filters={'name': employee}, fields=['name', 'first_name', 'last_name', 'hourly_rate', 'designation'])
    else:  
        employee_list = frappe.get_all(
            "Employee",
            fields=['name', 'first_name', 'last_name', 'hourly_rate', 'designation'],
            # NOTE: The filter key must be the fieldname "company", not the `Company` Doc object.
            filters={'status': 'Active', 'company': company_doc.name}
        )
    
    print(f"[VERBOSE] Found {len(employee_list)} active employees")
    
    if not employee_list:
        print(f"[VERBOSE] No active employees found, returning empty result")
        return {
            'total_salaries': 0,
            'total_advances': 0,
            'net_salaries': 0,
            'employee_attendance': {}
        }
    
    # Get all employee names for bulk queries
    employee_names = [emp.name for emp in employee_list]
    print(f"[VERBOSE] Employee names for bulk queries: {employee_names}")
    
    # Bulk fetch all checkin data for the month
    print(f"[VERBOSE] Fetching all employee checkin data for the month...")
    all_checkins = frappe.get_list(
        "Employee Checkin",
        filters=[
            ['Employee Checkin', 'employee', 'in', employee_names],
            ['Employee Checkin', 'time', '>=', month_start],
            ['Employee Checkin', 'time', '<', month_end]
        ],
        fields=['employee', 'name', 'time', 'log_type'],
        order_by='employee, time asc'
    )
    
    print(f"[VERBOSE] Found {len(all_checkins)} checkin records")
    
    # Bulk fetch all advance data for the month
    print(f"[VERBOSE] Fetching all employee advance data for the month...")
    all_advances = frappe.get_list(
        "Employee Advance",
        filters=[
            ['Employee Advance', 'employee', 'in', employee_names],
            ['Employee Advance', 'posting_date', '>=', month_start],
            ['Employee Advance', 'posting_date', '<', month_end]
        ],
        fields=['employee', 'advance_amount', 'posting_date', 'purpose']
    )
    
    print(f"[VERBOSE] Found {len(all_advances)} advance records")
    
    # Fetch petty cash advances from Journal Entries for the month
    print(f"[VERBOSE] Fetching petty cash advances from Journal Entries for the month...")
    je_petty_cash_rows = frappe.get_all(
        "Journal Entry",
        fields=[
            "name",
            "posting_date",
            "`tabJournal Entry Account`.party as party",
            "`tabJournal Entry Account`.debit_in_account_currency as debit",
            "`tabJournal Entry Account`.credit_in_account_currency as credit",
        ],
        filters=[
            ["Journal Entry Account", "account", "=", f"Payroll Payable - {company_doc.abbr}"],
            ["Journal Entry", "title", "like", "%Petty Cash%"],
            ["Journal Entry", "posting_date", ">=", month_start.date()],
            ["Journal Entry", "posting_date", "<", month_end.date()],
            ["Journal Entry Account", "party", "in", employee_names],
        ],
        order_by="posting_date desc",
    )
    print(f"[VERBOSE] Found {len(je_petty_cash_rows)} petty cash JE rows")
    # Aggregate JE advances per employee
    je_advances_by_employee = {}
    for row in je_petty_cash_rows:
        party = row.get("party")
        if not party:
            continue
        debit = row.get("debit") or 0
        credit = row.get("credit") or 0
        amount = (debit - credit) or 0
        if amount <= 0:
            continue
        if party not in je_advances_by_employee:
            je_advances_by_employee[party] = 0
        je_advances_by_employee[party] += amount
    print(f"[VERBOSE] Aggregated JE advances for {len(je_advances_by_employee)} employees")
    
    # Group data by employee
    print(f"[VERBOSE] Grouping checkin and advance data by employee...")
    checkins_by_employee = {}
    advances_by_employee = {}
    
    for checkin in all_checkins:
        if checkin.employee not in checkins_by_employee:
            checkins_by_employee[checkin.employee] = []
        checkins_by_employee[checkin.employee].append(checkin)
    
    for advance in all_advances:
        if advance.employee not in advances_by_employee:
            advances_by_employee[advance.employee] = []
        advances_by_employee[advance.employee].append(advance)
    
    print(f"[VERBOSE] Grouped data: {len(checkins_by_employee)} employees with checkins, {len(advances_by_employee)} employees with advances")
    
    attendance_data = {}
    checkin_stack = []
    # Process each employee
    print(f"[VERBOSE] Starting to process each employee...")
    for employee in employee_list:
        # Build employee full name
        employee_fullname = employee.first_name or ""
        if employee.last_name:
            employee_fullname += " " + employee.last_name
        
        print(f"[VERBOSE] Processing employee: {employee_fullname} ({employee.name})")
        
        # Initialize employee data
        attendance_data[employee_fullname] = {
            'attendance': {},
            'working_hours': 0,
            'designation': employee.designation,
            'break_hours': 0,
            'advance': 0,
            'net_working_hours': 0,
            'todays_work_hours': 0,
            'overtime_hours': 0,
            'hourly_rate': employee.hourly_rate or 0,
            'salary': 0,
            'salary_after_advances': 0,
            'status': "Off",
            'overtime': False
        }
        
        # Process advances
        employee_advances = advances_by_employee.get(employee.name, [])
        print(f"[VERBOSE]   Found {len(employee_advances)} advance records for {employee_fullname}")
        for advance in employee_advances:
            attendance_data[employee_fullname]['advance'] += advance.advance_amount or 0
        
        if employee_advances:
            print(f"[VERBOSE]   Total advances for {employee_fullname}: {attendance_data[employee_fullname]['advance']}")
        
        # Add petty cash JE advances
        je_advance_amount = je_advances_by_employee.get(employee.name, 0)
        if je_advance_amount:
            attendance_data[employee_fullname]['advance'] += je_advance_amount
            print(f"[VERBOSE]   Added petty cash JE advances for {employee_fullname}: {je_advance_amount}")
        
        # Process checkins
        checkin_list = checkins_by_employee.get(employee.name, [])
        print(f"[VERBOSE]   Found {len(checkin_list)} checkin records for {employee_fullname}")
        checkin_stack = []
        
        # Seed stack with an open check-in before the month window (handles cross-month shifts)
        prev_open_checkin = None
        prev_checkin = frappe.get_list(
            "Employee Checkin",
            filters=[
                ['Employee Checkin', 'employee', '=', employee.name],
                ['Employee Checkin', 'time', '<', month_start],
            ],
            fields=['employee', 'name', 'time', 'log_type'],
            order_by='time desc',
            limit=1
        )
        if prev_checkin and prev_checkin[0].log_type == 'IN':
            prev_open_checkin = prev_checkin[0]
            effective_prev_time = max(prev_open_checkin.time, month_start)
            prev_day_key = str((effective_prev_time - timedelta(hours=5)).day)
            if prev_day_key not in attendance_data[employee_fullname]['attendance']:
                attendance_data[employee_fullname]['attendance'][prev_day_key] = {
                    'in_time': None,
                    'out_time': None,
                    'check_in': None,
                    'check_out': None,
                    'breaks': [],
                    'break_log': [],
                    'issues': [],
                    'shifts': 0,
                    'work_time': 0,
                    'break_time': 0
                }
            attendance_data[employee_fullname]['attendance'][prev_day_key]['in_time'] = effective_prev_time
            attendance_data[employee_fullname]['attendance'][prev_day_key]['check_in'] = prev_open_checkin
            attendance_data[employee_fullname]['status'] = "Working"
            checkin_stack.append(prev_open_checkin)
        
        for checkin in checkin_list:
            checkin_day = (checkin.time - timedelta(hours=5)).day
            day_key = str(checkin_day)
            print(f"[VERBOSE]     Processing {checkin.log_type} at {checkin.time} for day {checkin_day}")
            
            # Initialize day data if not exists
            if day_key not in attendance_data[employee_fullname]['attendance']:
                attendance_data[employee_fullname]['attendance'][day_key] = {
                    'in_time': None,
                    'out_time': None,
                    'check_in': None,
                    'check_out': None,
                    'breaks': [],
                    'break_log': [],
                    'issues': [],
                    'shifts': 0,
                    'work_time': 0,
                    'break_time': 0
                }
            
            day_data = attendance_data[employee_fullname]['attendance'][day_key]
            
            # Process different checkin types
            if checkin.log_type == 'IN':
                if day_data['in_time'] is not None and day_data['out_time'] is None:
                    # Existing shift for the day is still open -> true double check-in
                    day_data['issues'].append(f"{checkin.time.strftime('%d/%m/%Y, %H:%M:%S')} - Double Check-in same day")
                else:
                    # Previous shift (if any) is closed; start a new shift on the same day
                    day_data['in_time'] = checkin.time
                    day_data['check_in'] = checkin
                    day_data['out_time'] = None
                    day_data['check_out'] = None
                    day_data['breaks'] = []
                    day_data['break_log'] = []
                    attendance_data[employee_fullname]['status'] = "Working"
                    checkin_stack.append(checkin)
                    day_data['shifts'] += 1
                
            elif checkin.log_type == 'OUT':
                day_data['out_time'] = checkin.time
                day_data['check_out'] = checkin
                attendance_data[employee_fullname]['status'] = "Off"
                
                if not checkin_stack:
                    day_data['issues'].append(f"{checkin.time.strftime('%d/%m/%Y, %H:%M:%S')} - Check-out without check-in")
                else:
                    clock_in = checkin_stack.pop()
                    effective_clock_in_time = clock_in.time
                    if effective_clock_in_time < month_start:
                        effective_clock_in_time = month_start
                    clockin_day = (effective_clock_in_time - timedelta(hours=5)).day
                    clockin_day_key = str(clockin_day)
                    
                    if clockin_day_key not in attendance_data[employee_fullname]['attendance']:
                        attendance_data[employee_fullname]['attendance'][clockin_day_key] = {
                            'in_time': None,
                            'out_time': None,
                            'check_in': None,
                            'check_out': None,
                            'breaks': [],
                            'break_log': [],
                            'issues': [],
                            'shifts': 0,
                            'work_time': 0,
                            'break_time': 0
                        }
                    
                    if attendance_data[employee_fullname]['attendance'][clockin_day_key]['in_time'] is None:
                        attendance_data[employee_fullname]['attendance'][clockin_day_key]['in_time'] = effective_clock_in_time
                        attendance_data[employee_fullname]['attendance'][clockin_day_key]['check_in'] = clock_in
                    
                    if checkin_day == clockin_day:
                        # Same day shift
                        work_time = checkin.time - effective_clock_in_time
                        work_hours = round(work_time.total_seconds() / 3600, 2)
                        day_data['work_time'] += work_hours
                        attendance_data[employee_fullname]['working_hours'] += work_hours
                    elif (checkin_day - clockin_day) > 1:
                        day_data['issues'].append(f"{clock_in.time.strftime('%d/%m/%Y, %H:%M:%S')} - Employee checked in for more than 2 days")
                    else:
                        # Shift carries over to next day
                        # End first day at 4:59 AM on the actual checkout date to avoid month boundary errors
                        first_day_end = checkin.time.replace(hour=4, minute=59, second=0, microsecond=0)
                        work_time1 = first_day_end - effective_clock_in_time
                        work_hours1 = round(work_time1.total_seconds() / 3600, 2)
                        
                        if clockin_day_key in attendance_data[employee_fullname]['attendance']:
                            attendance_data[employee_fullname]['attendance'][clockin_day_key]['work_time'] += work_hours1
                            attendance_data[employee_fullname]['attendance'][clockin_day_key]['out_time'] = first_day_end
                        
                        # Start second day at 5:00 AM on the same actual checkout date
                        second_day_start = checkin.time.replace(hour=5, minute=0, second=0, microsecond=0)
                        work_time2 = checkin.time - second_day_start
                        work_hours2 = round(work_time2.total_seconds() / 3600, 2)
                        
                        day_data['in_time'] = second_day_start
                        day_data['work_time'] += work_hours2
                        
                        attendance_data[employee_fullname]['working_hours'] += work_hours1 + work_hours2
                
                # Clear any remaining unclosed checkins
                while checkin_stack:
                    unclosed_checkin = checkin_stack.pop()
                    unclosed_day = (unclosed_checkin.time - timedelta(hours=5)).day
                    unclosed_day_key = str(unclosed_day)
                    if unclosed_day_key in attendance_data[employee_fullname]['attendance']:
                        attendance_data[employee_fullname]['attendance'][unclosed_day_key]['issues'].append(
                            f"{unclosed_checkin.time.strftime('%d/%m/%Y, %H:%M:%S')} - Checkin without checkout"
                        )
                        
            elif checkin.log_type == 'Break-OUT':
                day_data['breaks'].append(checkin)
                attendance_data[employee_fullname]['status'] = "On Break"
                
            elif checkin.log_type == 'Break-IN':
                if day_data['breaks']:
                    attendance_data[employee_fullname]['status'] = "Working"
                    break_start = day_data['breaks'][0]
                    break_time = checkin.time - break_start.time
                    break_hours = round(break_time.total_seconds() / 3600, 2)
                    
                    day_data['break_time'] += break_hours
                    attendance_data[employee_fullname]['break_hours'] += break_hours
                    day_data['break_log'].append({'out': break_start, 'in': checkin})
                    day_data['breaks'].pop(0)
                else:
                    day_data['issues'].append(f"{checkin.time.strftime('%d/%m/%Y, %H:%M:%S')} - Break in before break out")
            else:
                day_data['issues'].append(f"{checkin.time.strftime('%d/%m/%Y, %H:%M:%S')} - Unknown checkin type")
        
        # Handle any remaining unclosed checkins - report as issues only if NOT from today
        today = (frappe.utils.now_datetime() - timedelta(hours=5)).date()
        while checkin_stack:
            unclosed_checkin = checkin_stack.pop()
            unclosed_day = (unclosed_checkin.time - timedelta(hours=5)).day
            unclosed_day_key = str(unclosed_day)
            unclosed_checkin_date = (unclosed_checkin.time - timedelta(hours=5)).date()
            
            print(f"[DEBUG] Processing unclosed checkin for {employee_fullname}: day={unclosed_day}, day_key={unclosed_day_key}, time={unclosed_checkin.time}")
            print(f"[DEBUG] Today's date: {today}, Checkin date: {unclosed_checkin_date}")
            
            # Try to find a checkout right after the month window to close cross-month shifts
            resolved_with_future_checkout = False
            future_checkout = frappe.get_list(
                "Employee Checkin",
                filters=[
                    ['Employee Checkin', 'employee', '=', employee.name],
                    ['Employee Checkin', 'time', '>', unclosed_checkin.time],
                    ['Employee Checkin', 'time', '<=', month_end + timedelta(days=1)]
                ],
                fields=['employee', 'name', 'time', 'log_type'],
                order_by='time asc',
                limit=1
            )
            
            if (
                future_checkout
                and future_checkout[0].log_type == 'OUT'
                and unclosed_day_key in attendance_data[employee_fullname]['attendance']
            ):
                # Treat this as a cross-month shift; cap hours at month_end boundary
                effective_out_time = min(future_checkout[0].time, month_end)
                effective_in_time = max(unclosed_checkin.time, month_start)
                work_hours = round((effective_out_time - effective_in_time).total_seconds() / 3600, 2)
                
                day_data = attendance_data[employee_fullname]['attendance'][unclosed_day_key]
                day_data['out_time'] = effective_out_time
                day_data['check_out'] = future_checkout[0]
                day_data['work_time'] += work_hours
                attendance_data[employee_fullname]['working_hours'] += work_hours
                attendance_data[employee_fullname]['status'] = "Off"
                
                resolved_with_future_checkout = True
                print(f"[DEBUG] Resolved cross-month shift using checkout at {future_checkout[0].time} (counted until {effective_out_time})")
            
            # Only report as issue if it's NOT from today (previous days only) and we could not resolve it
            if (not resolved_with_future_checkout) and unclosed_checkin_date != today and unclosed_day_key in attendance_data[employee_fullname]['attendance']:
                attendance_data[employee_fullname]['attendance'][unclosed_day_key]['issues'].append(
                    f"{unclosed_checkin.time.strftime('%d/%m/%Y, %H:%M:%S')} - Checkin without checkout"
                )
                print(f"[DEBUG] Added issue for unclosed checkin from previous day: {unclosed_checkin.time}")
            else:
                if unclosed_checkin_date == today:
                    print(f"[DEBUG] Skipping issue for today's unclosed checkin (still working): {unclosed_checkin.time}")
                else:
                    print(f"[DEBUG] ERROR: day_key {unclosed_day_key} not found in attendance data for {employee_fullname}")

        # Calculate current day work hours only if it's actually today and employee is currently working
        is_current_date = (target_date.date() == datetime.now().date())
        if is_current_date and str(current_day) in attendance_data[employee_fullname]['attendance']:
            current_day_data = attendance_data[employee_fullname]['attendance'][str(current_day)]
            try:
                if attendance_data[employee_fullname]['status'] == "Working" and current_day_data.get('in_time'):
                    current_time = datetime.now()
                    todays_work_hours = round((current_time - current_day_data['in_time']).total_seconds() / 3600, 2)
                    attendance_data[employee_fullname]['working_hours'] += todays_work_hours
                    attendance_data[employee_fullname]['todays_work_hours'] = todays_work_hours
                elif attendance_data[employee_fullname]['status'] == "On Break" and current_day_data.get('breaks'):
                    if current_day_data.get('in_time'):
                        break_start_time = current_day_data['breaks'][0].time
                        todays_work_hours = round((break_start_time - current_day_data['in_time']).total_seconds() / 3600, 2)
                        attendance_data[employee_fullname]['working_hours'] += todays_work_hours
                        attendance_data[employee_fullname]['todays_work_hours'] = todays_work_hours
                elif attendance_data[employee_fullname]['status'] == "Off":
                    attendance_data[employee_fullname]['todays_work_hours'] = current_day_data.get('work_time', 0)
            except Exception as e:
                frappe.log_error(f"Error calculating today's hours for {employee_fullname}: {str(e)}")
        
        # Calculate final totals
        emp_data = attendance_data[employee_fullname]
        emp_data['net_working_hours'] = round(emp_data['working_hours'] - emp_data['break_hours'], 2)
        emp_data['working_hours'] = round(emp_data['working_hours'], 2)
        emp_data['break_hours'] = round(emp_data['break_hours'], 2)
        
        print(f"[VERBOSE]   {employee_fullname} totals: Working={emp_data['working_hours']}h, Breaks={emp_data['break_hours']}h, Net={emp_data['net_working_hours']}h")
        
        # Handle overtime
        if emp_data['net_working_hours'] > overtime_after:
            emp_data['overtime'] = True
            emp_data['overtime_hours'] = round(emp_data['net_working_hours'] - overtime_after, 2)
            original_net_hours = emp_data['net_working_hours']
            emp_data['net_working_hours'] = overtime_after + ((emp_data['net_working_hours'] - overtime_after) * 1.5)
            print(f"[VERBOSE]   {employee_fullname} has OVERTIME: {emp_data['overtime_hours']}h (adjusted net hours: {original_net_hours} -> {emp_data['net_working_hours']})")
        
        # Calculate salary
        emp_data['salary'] = round(emp_data['hourly_rate'] * emp_data['net_working_hours'], 2)
        emp_data['salary_after_advances'] = round(emp_data['salary'] - emp_data['advance'], 2)
        
        print(f"[VERBOSE]   {employee_fullname} salary calculation: {emp_data['hourly_rate']}/h * {emp_data['net_working_hours']}h = ${emp_data['salary']} (after advances: ${emp_data['salary_after_advances']})")
        
        total_salaries += emp_data['salary']
        total_advances += emp_data['advance']
    
    print(f"[VERBOSE] All employees processed!")
    print(f"[VERBOSE] FINAL TOTALS:")
    print(f"[VERBOSE]   Total Salaries: ${round(total_salaries, 2)}")
    print(f"[VERBOSE]   Total Advances: ${round(total_advances, 2)}")
    print(f"[VERBOSE]   Net Salaries: ${round(total_salaries - total_advances, 2)}")
    print(f"[VERBOSE]   Month/Year: {current_month}/{current_year}")
    print(f"[VERBOSE]   Processed Date: {target_date.strftime('%Y-%m-%d')}")
    print(f"[VERBOSE] Function completed successfully!")
    
    return {
        'total_salaries': round(total_salaries, 2),
        'total_advances': round(total_advances, 2),
        'net_salaries': round(total_salaries - total_advances, 2),
        'employee_attendance': attendance_data,
        'month': current_month,
        'year': current_year,
        'processed_date': target_date.strftime('%Y-%m-%d')
    }

@frappe.whitelist()
def get_doctype_permissions(doctype: str, name: str | None = None):
    """
    Return the current session user's permissions on a DocType (and optionally a specific doc).
    """	
    
    PERM_TYPES = [
		"read", "write", "create", "delete",
		"submit", "cancel", "amend",
		"print", "email", "report", "share",
		"import", "export", "set_user_permissions",
	]
    
    user = frappe.session.user

    # Validate doctype exists
    frappe.get_meta(doctype)  # will throw if invalid

    doc = None
    if name:
        try:
            doc = frappe.get_doc(doctype, name)
        except Exception:
            doc = None

    perms = {}
    for p in PERM_TYPES:
        perms[p] = bool(
            has_permission(
                doctype=doctype,
                ptype=p,
                doc=doc,
                user=user,
            )
        )

    return {
        "user": user,
        "doctype": doctype,
        "docname": name,
        "permissions": perms,
    }


@frappe.whitelist()
def get_linked_docs_with_metadata(doctype, name):
    """
    Aggregate related docs for a document and split into submitted vs other.

    Returns an object with two keys:
    - submitted_docs: {
        doctype: {
          link_fieldnames: ["..."],
          link_fields_meta: [{fieldname, fieldtype, label, options, option_label}],
          allow_on_submit: 0/1,
          reqd: 0/1,
          is_submittable: 0/1,
          docs: [{docname, title, link_fieldnames, allow_on_submit}]
        }
      }
    - other_related_docs: same structure as submitted_docs
    """
    # Validate permission
    frappe.has_permission(doctype, doc=name)

    # Import here to avoid circulars at import time
    from frappe.desk.form import linked_with as linked_with_mod

    # 1) All related docs (direct references)
    all_related = linked_with_mod.get(doctype, name) or {}

    # 2) All submitted linked docs (nested traversal)
    submitted_payload = linked_with_mod.get_submitted_linked_docs(doctype, name) or {}
    submitted_rows = submitted_payload.get("docs", []) or []

    # For quick membership test
    submitted_set = {(row.get("doctype"), row.get("name")) for row in submitted_rows if row.get("doctype") and row.get("name")}

    # Linked field mapping (how each doctype links back to our source doctype)
    linked_map = linked_with_mod.get_linked_doctypes(doctype)

    def _get_title(dt, dn):
        try:
            return get_title(dt, dn)
        except Exception:
            return None

    def _collect_table_fields_pointing_to_child(parent_dt, child_dt):
        """When our current document is a child doctype and parent_dt has a Table field with options=child_dt,
        return those Table DocFields' metadata from the parent doctype."""
        meta = frappe.get_meta(parent_dt)
        results = []
        for df in meta.fields:
            if df.fieldtype in frappe.model.table_fields and df.options == child_dt:
                results.append(df)
        return results

    def _link_field_meta_for(parent_dt):
        """Return tuple: (fieldname_labels, allow_on_submit_any, reqd_any, fields_meta).

        Handles Link, Dynamic Link, child table link fields and get_parent(Table) relationship.
        For child link fields returns names like "ChildDT.fieldname".
        """
        info = linked_map.get(parent_dt) or {}
        fieldname_labels = []
        allow_any = 0
        reqd_any = 0
        fields_meta = []

        def _option_label_for(df):
            # For Link/Table types, options usually holds a DocType name
            try:
                if getattr(df, "options", None) and df.fieldtype in ("Link", "Table", "Table MultiSelect"):
                    # If options is a DocType, return its name (label)
                    frappe.get_meta(df.options)
                    return df.options
            except Exception:
                pass
            return getattr(df, "options", None)

        def _append_df_meta(df, qualified_fieldname):
            nonlocal allow_any, reqd_any
            fieldname_labels.append(qualified_fieldname)
            allow_any = 1 if (allow_any or int(getattr(df, "allow_on_submit", 0) or 0)) else 0
            reqd_any = 1 if (reqd_any or int(getattr(df, "reqd", 0) or 0)) else 0
            fields_meta.append({
                "fieldname": qualified_fieldname,
                "fieldtype": getattr(df, "fieldtype", None),
                "label": getattr(df, "label", None),
                "options": getattr(df, "options", None),
                "option_label": _option_label_for(df),
            })

        # Direct link/dynamic link fields on the parent doctype
        if info.get("fieldname") and not info.get("child_doctype"):
            fn = info.get("fieldname")
            fn_list = fn if isinstance(fn, list) else [fn]
            meta = frappe.get_meta(parent_dt)
            for fname in fn_list:
                df = meta.get_field(fname)
                if df:
                    _append_df_meta(df, fname)

        # Link lives on a child row used inside parent_dt
        if info.get("child_doctype") and info.get("fieldname"):
            child_dt = info.get("child_doctype")
            fn = info.get("fieldname")
            fn_list = fn if isinstance(fn, list) else [fn]
            child_meta = frappe.get_meta(child_dt)
            for fname in fn_list:
                df = child_meta.get_field(fname)
                if df:
                    _append_df_meta(df, f"{child_dt}.{fname}")

        # Parent has a Table field with options == our source doctype (get_parent case)
        if info.get("get_parent"):
            # Our current source doctype may be a child table
            for df in _collect_table_fields_pointing_to_child(parent_dt, doctype):
                _append_df_meta(df, df.fieldname)

        return fieldname_labels, allow_any, reqd_any, fields_meta

    def _aggregate(dt_to_rows):
        agg = {}
        for dt, rows in (dt_to_rows or {}).items():
            if not rows:
                continue
            fieldnames, allow_any, reqd_any, fields_meta = _link_field_meta_for(dt)
            is_submittable = 1 if frappe.get_meta(dt).is_submittable else 0
            docs_list = []
            for r in rows:
                dn = r.get("name")
                docs_list.append({
                    "docname": dn,
                    "title": _get_title(dt, dn),
                    "link_fieldnames": fieldnames,
                    "allow_on_submit": int(allow_any),
                })
            agg[dt] = {
                "link_fieldnames": fieldnames,
                "link_fields_meta": fields_meta,
                "allow_on_submit": int(allow_any),
                "reqd": int(reqd_any),
                "is_submittable": is_submittable,
                "docs": docs_list,
            }
        return agg

    # Build submitted intersection limited to "directly related" list
    submitted_intersection = {}
    for dt, rows in (all_related or {}).items():
        only_submitted = [r for r in rows if (dt, r.get("name")) in submitted_set]
        if only_submitted:
            submitted_intersection[dt] = only_submitted

    # Build other related (not in submitted)
    other_related = {}
    for dt, rows in (all_related or {}).items():
        non_submitted = [r for r in rows if (dt, r.get("name")) not in submitted_set]
        if non_submitted:
            other_related[dt] = non_submitted

    return {
        "submitted_docs": _aggregate(submitted_intersection),
        "other_related_docs": _aggregate(other_related),
    }

