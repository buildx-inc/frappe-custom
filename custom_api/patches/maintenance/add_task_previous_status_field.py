import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    if frappe.db.exists("Custom Field", {"dt": "Task", "fieldname": "previous_status"}):
        return

    create_custom_fields(
        {
            "Task": [
                {
                    "fieldname": "previous_status",
                    "label": "Previous Status",
                    "fieldtype": "Data",
                    "insert_after": "status",
                    "read_only": 1,
                    "no_copy": 1,
                }
            ]
        },
        update=True,
    )
