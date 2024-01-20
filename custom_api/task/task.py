import frappe
from frappe.utils.background_jobs import enqueue
    



@frappe.whitelist()
def daily_notifications():
    users = frappe.db.get_list("User", fields=["*"], limit=0, order_by="modified desc")
    tasks_by_user = {}
    for user in users:
        user_tasks = frappe.db.get_list("Task", fields=["name","subject"], limit=0, filters=[["status","not in", ["Completed", "Cancelled"]],["Task User", "User", "in", user.name]])
        if user_tasks:
           tasks_by_user[user.name] = {}
           tasks_by_user[user.name]['name'] = user.first_name
           tasks_by_user[user.name]['tasks'] = user_tasks
    email_args = {}
    for user in tasks_by_user:
        subject = "{0} Pending Tasks".format(len(tasks_by_user[user]))
        counter = 1
        user_email_summary = f"<h4>Hello {tasks_by_user[user]['name']},</h4><h4>You have the following unfinished tasks:<ul>"
        for user_task in tasks_by_user[user]['tasks']:
            user_email_summary += f"<li><a href='{frappe.utils.get_url()}/Task/{user_task.name}' target='_blank'>{counter}- {user_task.subject}</a></li>"
            counter += 1
        user_email_summary += "</ul>"
        email_args[user] = {
            "recipients": user,
            "sender": None,
            "subject" : subject,
            "message" : user_email_summary,
		    "now": True
        }
        enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args[user])

    
    
    return email_args