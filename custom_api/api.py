import json
import frappe
import frappe.client
from frappe.model.mapper import get_mapped_doc
import frappe.handler
from frappe.utils import get_site_name
from frappe import _
from frappe.desk.form.load import add_comments
from frappe.utils.background_jobs import enqueue
from frappe.desk.form.document_follow import follow_document
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)
from datetime import datetime
from frappe.model.workflow import apply_workflow



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


@frappe.whitelist(allow_guest=True)
def get_metadata(doctype):
    metadata = {}
    metadata["fields"] = frappe.get_meta(doctype).fields
    metadata["module"] = frappe.get_meta(doctype).module
    metadata["is_submitable"] = frappe.get_meta(doctype).is_submittable
    return frappe.get_meta(doctype)

@frappe.whitelist()
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
        role_profiles = [role_profile.role_profile for role_profile in user_doc.role_profiles]
        val = frappe.db.get_values("User", {'name': frappe.session.user}, "*", as_dict=True)
        val[0]["role_profiles"] = role_profiles
        val[0]["site"] = frappe.local.site_path
    return val
        
    
    
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
    