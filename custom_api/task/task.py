import frappe
from frappe.utils.background_jobs import enqueue
    



@frappe.whitelist()
def daily_notifications():
    users = frappe.db.get_list("User", fields=["*"], limit=0, order_by="modified desc")
    tasks_by_user = {}
    for user in users:
        user_tasks = frappe.db.get_list("Task", fields=["name"], limit=0, filters=[["status","not in", ["Completed", "Cancelled"]],["Task User", "User", "in", user.name]])
        if user_tasks:
           tasks_by_user[user.name] = user_tasks
    email_args = {}
    for user in tasks_by_user:
        subject = "{0} Pending Tasks".format(len(tasks_by_user[user]))
        counter = 1
        user_email_summary = ""
        for user_task in tasks_by_user[user]:
            user_email_summary += "{0}- {1} \n".format(counter, user_task.name)
            counter += 1
        email_args[user] = {
            "recipients": user,
            "sender": None,
            "subject" : subject,
            "message" : user_email_summary,
		    "now": True
        }
        enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args[user])

    
    
    return email_args