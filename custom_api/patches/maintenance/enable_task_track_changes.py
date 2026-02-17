import frappe


def execute():
    current_value = frappe.db.get_value("DocType", "Task", "track_changes")
    if int(current_value or 0) == 1:
        return

    frappe.db.set_value("DocType", "Task", "track_changes", 1, update_modified=False)
    frappe.clear_cache(doctype="Task")
