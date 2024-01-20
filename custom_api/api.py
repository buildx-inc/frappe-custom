import base64
import binascii
import json
from urllib.parse import urlencode, urlparse

import frappe
import frappe.client
import frappe.handler
from frappe import _
from frappe.utils.data import sbool
from frappe.utils.response import build_response
from frappe.desk.form.load import add_comments
from frappe.utils.background_jobs import enqueue
from frappe.desk.form.document_follow import follow_document
from frappe.desk.doctype.notification_log.notification_log import (
	enqueue_create_notification,
	get_title,
	get_title_html,
)
from frappe.share import add, get_users, set_permission
from datetime import datetime


@frappe.whitelist()
def get_takeaway_customer():
    return frappe.get_doc('Customer','TAKEAWAY')







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
def fetch_floor_data(name):
    floorData = {}
    floorDoc = frappe.get_doc("Restaurant Object", name)
    floorData["name"] = floorDoc.name
    floorData["description"] = floorDoc.description
    floorData["floor_plan"] = floorDoc.floor_plan
    if floorDoc.type == "Floor":
        floorRooms = frappe.get_all("Restaurant Object", filters = [["floor", "=", floorDoc.name]], fields = ["name","description"])
        floorData["rooms"] = {}
        for room in floorRooms:
            roomTables = frappe.get_all("Restaurant Object", filters = [["room", "=", room.name],["type","=","Table"]], fields = ["name","description","reserved","data_style","no_of_seats"])
            roomProductionCenters = frappe.get_all("Restaurant Object", filters = [["room", "=", room.name],["type","=","Production Center"]])
            floorData["rooms"][room.description] = {}
            floorData["rooms"][room.description]["name"] = room.name
            floorData["rooms"][room.description]["floor_plan"] = room.floor_plan
            floorData["rooms"][room.description]["tables"] = {}
            for table in roomTables:
                floorData["rooms"][room.description]["tables"][table.description] = {}
                floorData["rooms"][room.description]["tables"][table.description]["name"] = table.name
                tableOrders = frappe.get_all("Table Order", filters = [["table", "=", table.name],["status", "!=", "Invoiced"]])
                floorData["rooms"][room.description]["tables"][table.description]["numberOfOrders"] = len(tableOrders)
                floorData["rooms"][room.description]["tables"][table.description]["numberOfSeats"] = table.no_of_seats
                floorData["rooms"][room.description]["tables"][table.description]["dataStyle"] = table.data_style
                floorData["rooms"][room.description]["tables"][table.description]["reserved"] = table.reserved
                floorData["rooms"][room.description]["tables"][table.description]["tableDescription"] = table.description
            floorData["rooms"][room.description]["production_centers"] = {}
            for productionCenter in roomProductionCenters:
                productionCenter = frappe.get_doc("Restaurant Object",productionCenter)
                floorData["rooms"][room.description]["production_centers"][productionCenter.description] = productionCenter
        return floorData
    else:
        return "Error: Object is not a floor"

@frappe.whitelist()
def db_item_entries():
    # data = frappe.db.sql("SELECT item_code as code from `tabOrder Entry Item`")
    data = frappe.db.sql("SHOW COLUMNS FROM `tabOrder Entry Item`")

    return data

@frappe.whitelist()
def get_menu_items():
    def object_to_dict(obj):
        exclude_attributes = ["_meta", "_table_fieldnames","item_defaults","attributes","uoms"]
        
        obj_dict = {}
        for attr, value in vars(obj).items():
            if attr not in exclude_attributes:
                obj_dict[attr] = value
        return obj_dict

    menuItemData = {}
    menuItems = frappe.get_all("Item", filters={"item_type": "Menu"})
    
    for menuItem in menuItems:
        menuItemData[menuItem.name] = {}
        item = frappe.get_doc("Item", menuItem.name)
        menuItemData[menuItem.name] = object_to_dict(item)
        
        bins = frappe.get_list("Bin", filters={"item_code": menuItem.name})
        if len(bins) > 1:
            qty = 0
            for bin in bins:
                binItem = frappe.get_doc("Bin", bin.name)
                qty += binItem.projected_qty
            menuItemData[menuItem.name]["projected_qty"] = qty
        elif len(bins) == 1:
            binItem = frappe.get_doc("Bin", bins[0].name)
            menuItemData[menuItem.name]["projected_qty"] = binItem.projected_qty
        else:
            menuItemData[menuItem.name]["projected_qty"] = 0
    
    return menuItemData

@frappe.whitelist()
def get_addons_items():
    def object_to_dict(obj):
        exclude_attributes = ["_meta", "_table_fieldnames","item_defaults","attributes","uoms"]
        
        obj_dict = {}
        for attr, value in vars(obj).items():
            if attr not in exclude_attributes:
                obj_dict[attr] = value
        return obj_dict

    menuItemData = {}
    menuItems = frappe.get_all("Item", filters={"item_type": "Addons"})
    
    for menuItem in menuItems:
        menuItemData[menuItem.name] = {}
        item = frappe.get_doc("Item", menuItem.name)
        menuItemData[menuItem.name] = object_to_dict(item)
        
        bin = frappe.get_list("Bin", filters={"item_code": menuItem.name})
        if len(bin) > 0:
            binItem = frappe.get_doc("Bin", bin[0].name)
            menuItemData[menuItem.name]["projected_qty"] = binItem.projected_qty
        else:
            menuItemData[menuItem.name]["projected_qty"] = 0
    
    return menuItemData

@frappe.whitelist()
def reserve_table(tableName, customerName):
    table = frappe.get_doc("Restaurant Object", tableName)
    if table.type == "Table":
        if table.reserved == 0:
            table.reserved = 1
            table.save(ignore_permissions=True)
            order = frappe.get_doc({
                "doctype": "Table Order",
                "table": tableName,
                "customer": customerName
            })
            order.insert()
            frappe.db.commit()
            return "Success!"
        else:
            return "Error: Table already reserved"
    else:
        return "Error: Object is not a table"
    return "Error: Reservation failed"

@frappe.whitelist()
def cancel_reservation(tableName):
    table = frappe.get_doc("Restaurant Object", tableName)
    if table.type == "Table":
        if table.reserved == 1:
            table.reserved = 0
            table.save(ignore_permissions=True)
        else:
            return "Error: Table is not reserved"
    else:
        return "Error: Object is not a table"
    return "Error: Unidentified error"
@frappe.whitelist()
def item_entries(status = ""):
    subtable_fields = frappe.db.sql("SHOW COLUMNS FROM `tabOrder Entry Item`")

    field_names = [field[0] for field in subtable_fields]
    field_names_str = ", ".join(field_names)
    if status == "":
        query = f"SELECT {field_names_str} FROM `tabOrder Entry Item`"
    else:
        query = f"SELECT {field_names_str} FROM `tabOrder Entry Item` WHERE `status` = {status}"
    items = frappe.db.sql(query, as_dict=True)
    for item in items:
        query = f"SELECT `projected_qty` FROM `tabBin` WHERE `item_code` = '{item.item_code}'"
        projected_qty = frappe.db.sql(query, as_dict=True)
        if len(projected_qty) > 0:
            item["projected_qty"] = projected_qty[0]["projected_qty"]
    return items

@frappe.whitelist()
def move_table_orders(orders, destinationTable):
    orders = json.loads(orders)
    if len(orders) > 0:
        for order in orders:
            tableOrder = frappe.get_doc("Table Order", order)
            tableOrder.table = destinationTable
            tableOrder.save(ignore_permissions=True)
        return "Success"
    else:
        return "Error: No orders specified"

@frappe.whitelist(allow_guest=True)
def get_metadata(doctype):
    metadata = {}
    metadata["fields"] = frappe.get_meta(doctype).fields
    metadata["module"] = frappe.get_meta(doctype).module
    metadata["is_submitable"] = frappe.get_meta(doctype).is_submittable
    return metadata

@frappe.whitelist()
def dev():
    if frappe.conf.developer_mode:
        return("You are in developer mode.")
    else:
        return("You are not in developer mode.")

@frappe.whitelist()
def create_room(description):
    new_doc = frappe.get_doc({
        "doctype": "Restaurant Object",
        "type": "Room",
        "description": description
    })
    new_doc.insert()
    frappe.db.commit()
    return frappe.get_doc("Restaurant Object", new_doc.name)

@frappe.whitelist()
def create_table(room,description,no_of_seats=4,minimum_seating=1,shape="Square",color="#5b1e34"):
    new_doc = frappe.get_doc({
        "doctype": "Restaurant Object",
        "type": "Table",
        "description": description,
        "room": room,
        "no_of_seats": no_of_seats,
        "minimum_seating": minimum_seating,
        "shape": shape,
        "color": color
    })
    new_doc.insert()
    frappe.db.commit()
    return frappe.get_doc("Restaurant Object", new_doc.name)
@frappe.whitelist()
def delete_empty_orders():
    orders = frappe.get_list("Table Order", filters={"status":"Attending"})
    for order in orders:
        order_doc = frappe.get_doc("Table Order",order["name"])
        if (frappe.utils.now_datetime() - order_doc.creation).total_seconds() > 600: #order time is more than 10 minutes
            if len(order_doc.entry_items) == 0:
                frappe.delete_doc("Table Order", order["name"])
            else:
                delete_order = True
                for entry_item in order_doc.entry_items:
                    if entry_item.status != "Attending":
                        delete_order = False
                if delete_order:
                    frappe.delete_doc("Table Order", order["name"])

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
	        "assignment_rule":
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
        return frappe.db.get_values("User", {'name': frappe.session.user}, "*", as_dict=True)

def project_on_create(doc, method):
    user_emails = [user.email for user in doc.users]
    attachment = {}
    if doc.doctype == "Project":
        if doc.owner != doc.project_manager and doc.project_manager not in user_emails:
            user_emails.append(doc.project_manager)
    share_doc = frappe.get_attr("frappe.share.add")
    for user in user_emails:
        share_doc(doc.doctype, doc.name, user, 1,1,0,1)
    
    frappe.db.commit()

    if doc.doctype == "Task":
        if doc.exp_start_date != None and doc.exp_start_date != "":
            dtstamp = datetime.now().strftime('%Y%m%dT%H%M%S')
            task_start = datetime.strptime(doc.exp_start_date + " 8", "%Y-%m-%d %H")
            task_start = task_start.strftime('%Y%m%dT%H%M%S')
            task_end = datetime.strptime(doc.exp_start_date + " 17", "%Y-%m-%d %H")
            task_end = task_end.strftime('%Y%m%dT%H%M%S')
            ical_data = f"""BEGIN:VCALENDAR
            VERSION:2.0
            PRODID:-//Buildx ERP//Task//EN
            BEGIN:VEVENT
            UID:2201-2020-AFB51
            TZID:{frappe.utils.get_time_zone()}
            CALSCALE:GREGORIAN
            DTSTAMP:{dtstamp}
            DTSTART:{task_start}
            DTEND:{task_end}
            SUMMARY:{doc.subject}
            DESCRIPTION:{doc.description}
            ORGANIZER:Buildx CMS
            END:VEVENT
            END:VCALENDAR
            """
            attachment = {'fname':'invite.ics', 'fcontent':ical_data}
    #notify
    send_notification("New " + doc.doctype + " " + doc.name, json.dumps(user_emails), notification_type="Assignment", doctype = doc.doctype,doc_name = doc.name)
    if doc.doctype == "Task":
        send_email(json.dumps(user_emails),f"New {doc.doctype} - {doc.subject}", f"You have been assigned a new {doc.doctype} - <a href='{frappe.utils.get_url()}/{doc.doctype}/{doc.name}' target='_blank'> {doc.name} </a><p>{doc.description}</p>", attachments = [attachment])
    if doc.doctype == "Project":
        send_email(json.dumps(user_emails),f"New {doc.doctype} - {doc.project_name}", f"You have been assigned a new {doc.doctype} - <a href='{frappe.utils.get_url()}/{doc.doctype}/{doc.name}' target='_blank'> {doc.name} </a><p>{doc.project_description}</p>")             
#create folder
    create_folder = frappe.get_attr("frappe.core.api.file.create_new_folder")
    create_folder(doc.name, "Home/Attachments")
    frappe.db.commit()
    frappe.publish_realtime("Project_Add", {"doctype": doc.doctype, "name": doc.name})

def project_on_update(doc, method):
    get_users = frappe.get_attr("frappe.share.get_users")
    old_value = [old_user.user for old_user in get_users(doc.doctype, doc.name)]
    new_value = [new_user.email for new_user in doc.users]
    attachment = {}
    if(doc.doctype == "Project"):
        new_value.append(doc.project_manager)
    added_users = list(set(new_value) - set(old_value))
    removed_users = list(set(old_value) - set(new_value))
    share_doc = frappe.get_attr("frappe.share.add")
    if added_users:
        new_users = []
        for user in added_users:
            new_users.append(user)
            share_doc(doc.doctype, doc.name, user, read = 1, write = 1, share = 1)
            if doc.doctype == "Task":
                if doc.exp_start_date != None and doc.exp_start_date != "":
                    dtstamp = datetime.now().strftime('%Y%m%dT%H%M%S')
                    task_start = datetime.strptime(doc.exp_start_date + " 8", "%Y-%m-%d %H")
                    task_start = task_start.strftime('%Y%m%dT%H%M%S')
                    task_end = datetime.strptime(doc.exp_start_date + " 17", "%Y-%m-%d %H")
                    task_end = task_end.strftime('%Y%m%dT%H%M%S')
                    ical_data = f"""BEGIN:VCALENDAR
                    VERSION:2.0
                    PRODID:-//Buildx ERP//Task//EN
                    BEGIN:VEVENT
                    UID:2201-2020-AFB51
                    TZID:{frappe.utils.get_time_zone()}
                    CALSCALE:GREGORIANgh
                    DTSTAMP:{dtstamp}
                    DTSTART:{task_start}
                    DTEND:{task_end}
                    SUMMARY:{doc.subject}
                    DESCRIPTION:{doc.description}
                    ORGANIZER:Buildx CMS
                    END:VEVENT
                    END:VCALENDAR
                    """
                    attachment = {'fname':'invite.ics', 'fcontent':ical_data}
        send_notification("New " + doc.doctype + " " + doc.name, json.dumps(new_users), doctype = doc.doctype,doc_name = doc.name,notification_type="Assignment")
        if doc.doctype == "Task":
            send_email(json.dumps(new_users),f"New {doc.doctype} - {doc.subject}", f"You have been assigned a new {doc.doctype} - <a href='{frappe.utils.get_url()}/{doc.doctype}/{doc.name}' target='_blank'> {doc.name} </a><p>{doc.description}</p>", attachments = [attachment])
        if doc.doctype == "Project":
            send_email(json.dumps(new_users),f"New {doc.doctype} - {doc.project_name}", f"You have been assigned a new {doc.doctype} - <a href='{frappe.utils.get_url()}/{doc.doctype}/{doc.name}' target='_blank'> {doc.name} </a><p>{doc.project_description}</p>", attachments = [attachment])             
    set_doc_permission = frappe.get_attr("frappe.share.set_permission")
    if removed_users:
        for user in removed_users:
             set_doc_permission(doc.doctype, doc.name, user, "read", 0)
    frappe.db.commit()
    frappe.publish_realtime("Project_Update", {"doctype": doc.doctype, "name": doc.name})
    
    
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
    