def donor_application_after_insert(doc, method):
    doc.docstatus = 1
    doc.save(ignore_permissions=True)

def email_status_check(doc, method):
    for recipient in doc.recipients:
        if recipient.status != 'Sent':
            apply_workflow = frappe.get_attr("frappe.model.workflow.apply_workflow")
            try:
                individual_donor = frappe.get_doc("Individual Donor", recipient.recipient)
                apply_workflow(individual_donor, "Email Error")
            except:
                pass
            try:
                donor_organization = frappe.get_doc("Donor Organization", recipient.recipient)
                apply_workflow(donor_organization, "Email Error")
            except:
                pass
