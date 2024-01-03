import frappe

def execute():
    doctype_doctype = frappe.get_doc("DocType","DocType")
    doctype_fields = [
        {'fieldname': 'alias', 'label': 'Alias', 'fieldtype': 'Data', 'options': None, 'reqd': 0},
        {'fieldname': 'enable_drive', 'label': 'Enable Drive', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'has_kanban', 'label': 'Has Kanban', 'fieldtype': 'Check', 'options': None, 'reqd': 0}]
    for field in doctype_fields:
        if field['fieldname'] not in [d.fieldname for d in doctype_doctype.fields]:
            doctype_doctype.append("fields",field)

    doctype_doctype.save(ignore_permissions=True)

    docfield_doctype = frappe.get_doc("DocType","DocField")
    docfield_fields = [
        {'fieldname': 'alias', 'label': 'Alias', 'fieldtype': 'Data', 'options': None, 'reqd': 0},
        {'fieldname': 'buildx_depends_on', 'label': 'Buildx Depends On', 'fieldtype': 'Data', 'options': None, 'reqd': 0},
        {'fieldname': 'calendar_color', 'label': 'Calendar Color', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'calendar_description', 'label': 'Calendar Description', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'calendar_end_date', 'label': 'Calendar End Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'calendar_start_date', 'label': 'Calendar Start Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'calendar_title', 'label': 'Calendar Title', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'conditional_default', 'label': 'Conditional Default', 'fieldtype': 'JSON', 'options': None, 'reqd': 0},
        {'fieldname': 'enable_actions', 'label': 'Enable Actions', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'filters', 'label': 'Filters', 'fieldtype': 'JSON', 'options': None, 'reqd': 0},
        {'fieldname': 'in_compact_list', 'label': 'In Compact List', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'in_edit', 'label': 'In Edit', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'in_list_compact', 'label': 'In List Compact', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'kanban_category', 'label': 'Kanban Category', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'kanban_date', 'label': 'Kanban Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'kanban_description', 'label': 'Kanban Description', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'kanban_group', 'label': 'Kanban Group', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'kanban_title', 'label': 'Kanban Title', 'fieldtype': 'Check', 'options': None, 'reqd': 0},
        {'fieldname': 'multiselect_key', 'label': 'Multiselect Key', 'fieldtype': 'Data', 'options': None, 'reqd': 0},
        {'fieldname': 'validation', 'label': 'valid', 'fieldtype': 'JSON', 'options': None, 'reqd': 0},
    ]
    for field in docfield_fields:
        if field['fieldname'] not in [d.fieldname for d in docfield_doctype.fields]:
            docfield_doctype.append("fields",field)

    docfield_doctype.save(ignore_permissions=True)

    user_doctype = frappe.get_doc("DocType","User")
    user_fields = [
        {'fieldname': 'company', 'label': 'Company', 'fieldtype': 'Link', 'options': 'Company', 'reqd': 0},
        {'fieldname': 'role_profile_name', 'label': 'Role Profile', 'fieldtype': 'Link', 'options': 'Role Profile', 'reqd': 0},
        {'fieldname': 'status', 'label': 'Status', 'fieldtype': 'Select', 'options': 'Active\nCancelled', 'reqd': 0}
    ]
    for field in user_fields:
        if field['fieldname'] not in [d.fieldname for d in user_doctype.fields]:
            user_doctype.append("fields",field)

    user_doctype.save(ignore_permissions=True)

    project_doctype = frappe.get_doc("DocType","Project")
    project_fields = [
        {'fieldname': 'project_location', 'label': 'Location', 'fieldtype': 'Data', 'options': None, 'reqd': 0},
        {'fieldname': 'sub_contractor', 'label': 'Sub Contractor', 'fieldtype': 'Table', 'options': 'Project Sub Contractor', 'reqd': 0},
        {'fieldname': 'main_contractor', 'label': 'Main Contractor', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0},
        {'fieldname': 'third_party_consultant', 'label': 'Third Party Consultant', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0},
        {'fieldname': 'consultant', 'label': 'Consultant', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0},
        {'fieldname': 'system_area', 'label': 'System Area', 'fieldtype': 'Float', 'options': None, 'reqd': 0},
        {'fieldname': 'project_manager', 'label': 'Project Manager', 'fieldtype': 'Link', 'options': 'User', 'reqd': 0},
        {'fieldname': 'project_manager_name', 'label': 'Project Manager', 'fieldtype': 'Data', 'options': None, 'reqd': 0},
        {'fieldname': 'project_management_company', 'label': 'Project Management Company', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0},
        {'fieldname': 'authority', 'label': 'Authority', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0},
        {'fieldname': 'total_area', 'label': 'Total Area', 'fieldtype': 'Float', 'options': None, 'reqd': 0},
        {'fieldname': 'entities', 'label': 'Entities', 'fieldtype': 'Heading', 'options': None, 'reqd': 0},
        {'fieldname': 'developer', 'label': 'Developer', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0},
        {'fieldname': 'parent_project', 'label': 'Parent Project', 'fieldtype': 'Link', 'options': 'Project', 'reqd': 0},
        {'fieldname': 'customer', 'label': 'Client', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 1}
    ]
    for field in project_fields:
        if field['fieldname'] not in [d.fieldname for d in project_doctype.fields]:
            project_doctype.append("fields",field)

    project_doctype.save(ignore_permissions=True)

    task_doctype = frappe.get_doc("DocType","Task")
    task_fields = [
        {'fieldname': 'notes', 'label': 'Notes', 'fieldtype': 'Text', 'options': None, 'reqd': 0},
        {'fieldname': 'exp_start_date', 'label': 'Deadline', 'fieldtype': 'Date', 'options': None, 'reqd': 0},
        {'fieldname': 'users', 'label': 'Users', 'fieldtype': 'Table', 'options': 'Task User', 'reqd': 0}
    ]
    
    for field in task_fields:
        if field['fieldname'] not in [d.fieldname for d in task_doctype.fields]:
            task_doctype.append("fields",field)
    task_doctype.save(ignore_permissions=True)
