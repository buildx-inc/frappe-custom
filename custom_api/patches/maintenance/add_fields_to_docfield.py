import frappe

def execute():
    frappe.flags.developer_mode = 1

    doctype_doctype = frappe.get_doc("DocType","DocType")
    doctype_fields = [
        {'fieldname': 'alias', 'label': 'Alias', 'fieldtype': 'Data', 'options': 'None', 'reqd': 0, 'idx': 3},
        {'fieldname': 'enable_drive', 'label': 'Enable Drive', 'fieldtype': 'Check', 'options': 'None', 'reqd': 0, 'idx': 17},
        {'fieldname': 'allow_email', 'label': 'Allow Email', 'fieldtype': 'Check', 'options': 'None', 'reqd': 0, 'idx': 86},
        {'fieldname': 'has_kanban', 'label': 'Has Kanban', 'fieldtype': 'Check', 'options': 'None', 'reqd': 0, 'idx': 19}]
    for field in doctype_fields:
        if field['fieldname'] not in [d.fieldname for d in doctype_doctype.fields]:
            doctype_doctype.fields.insert(field['idx'],field)

    doctype_doctype.save(ignore_permissions=True)

    docfield_doctype = frappe.get_doc("DocType","DocField")
    
    docfield_fields = [
        {'fieldname': 'alias', 'label': 'Alias', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 9},
        {'fieldname': 'buildx_depends_on', 'label': 'Buildx Depends On', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 44},
        {'fieldname': 'external_link', 'label': 'External Link', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 20},
        {'fieldname': 'select_label', 'label': 'Select Label', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 9},
        {'fieldname': 'option_label', 'label': 'Option Label', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 10},
        {'fieldname': 'calendar_color', 'label': 'Calendar Color', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 61},
        {'fieldname': 'calendar_description', 'label': 'Calendar Description', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 62},
        {'fieldname': 'calendar_end_date', 'label': 'Calendar End Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 65},
        {'fieldname': 'calendar_start_date', 'label': 'Calendar Start Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 63},
        {'fieldname': 'calendar_title', 'label': 'Calendar Title', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 60},
        {'fieldname': 'conditional_default', 'label': 'Conditional Default', 'fieldtype': 'JSON', 'options': None, 'reqd': 0, 'idx': 30},
        {'fieldname': 'enable_actions', 'label': 'Enable Actions', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 20},
        {'fieldname': 'filters', 'label': 'Filters', 'fieldtype': 'JSON', 'options': None, 'reqd': 0, 'idx': 57},
        {'fieldname': 'in_compact_list', 'label': 'In Compact List', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 55},
        {'fieldname': 'in_view', 'label': 'In View', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 53},
        {'fieldname': 'in_edit', 'label': 'In Edit', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 54},
        {'fieldname': 'in_list_compact', 'label': 'In List Compact', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 49},
        {'fieldname': 'kanban_category', 'label': 'Kanban Category', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 24},
        {'fieldname': 'kanban_date', 'label': 'Kanban Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 25},
        {'fieldname': 'kanban_description', 'label': 'Kanban Description', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 23},
        {'fieldname': 'kanban_group', 'label': 'Kanban Group', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 21},
        {'fieldname': 'kanban_title', 'label': 'Kanban Title', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 22},
        {'fieldname': 'kanban_user', 'label': 'Kanban User', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 23},
        {'fieldname': 'kanban_tags', 'label': 'Kanban Tags', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 26},
        {'fieldname': 'multiselect', 'label': 'Is Multiselect', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 6},
        {'fieldname': 'multiselect_id', 'label': 'Multiselect Id', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 7},
        {'fieldname': 'multiselect_key', 'label': 'Multiselect Key', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 8},
        {'fieldname': 'validation', 'label': 'valid', 'fieldtype': 'JSON', 'options': None, 'reqd': 0, 'idx': 56},
        {'fieldname': 'radio_group', 'label': 'Radio Group', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 4},
        {'fieldname': 'card_view', 'label': 'Card View', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 5}
        
    ]
    
    for field in docfield_fields:
        if field['fieldname'] not in [d.fieldname for d in docfield_doctype.fields]:
            docfield_doctype.field.insert(field['idx'],field)

    docfield_doctype.save(ignore_permissions=True)

    user_doctype = frappe.get_doc("DocType","User")
    user_fields = [
        {'fieldname': 'company', 'label': 'Company', 'fieldtype': 'Link', 'options': 'Company', 'reqd': 0, 'idx': 4},
        {'fieldname': 'role_profile_name', 'label': 'Role Profile', 'fieldtype': 'Link', 'options': 'Role Profile', 'reqd': 0, 'idx': 17},
        {'fieldname': 'status', 'label': 'Status', 'fieldtype': 'Select', 'options': 'Active\nCancelled', 'reqd': 0, 'idx': 5}
    ]
    for field in user_fields:
        if field['fieldname'] not in [d.fieldname for d in user_doctype.fields]:
            user_doctype.fields.insert(field['idx'],field)

    user_doctype.save(ignore_permissions=True)

    project_doctype = frappe.get_doc("DocType","Project")
    project_fields = [
        {'fieldname': 'project_location', 'label': 'Location', 'fieldtype': 'Data', 'options': 'None', 'reqd': 0, 'idx': 13},
        {'fieldname': 'sub_contractor', 'label': 'Sub Contractor', 'fieldtype': 'Table', 'options': 'Project Sub Contractor', 'reqd': 0, 'idx': 41},
        {'fieldname': 'main_contractor', 'label': 'Main Contractor', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 40},
        {'fieldname': 'third_party_consultant', 'label': 'Third Party Consultant', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 37},
        {'fieldname': 'consultant', 'label': 'Consultant', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 36},
        {'fieldname': 'system_area', 'label': 'System Area', 'fieldtype': 'Float', 'options': 'None', 'reqd': 0, 'idx': 16},
        {'fieldname': 'project_manager', 'label': 'Project Manager', 'fieldtype': 'Link', 'options': 'User', 'reqd': 1, 'idx': 8},
        {'fieldname': 'project_manager_name', 'label': 'Project Manager', 'fieldtype': 'Data', 'options': 'None', 'reqd': 0, 'idx': 9},
        {'fieldname': 'project_management_company', 'label': 'Project Management Company', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 39},
        {'fieldname': 'authority', 'label': 'Authority', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 38},
        {'fieldname': 'total_area', 'label': 'Total Area', 'fieldtype': 'Float', 'options': 'None', 'reqd': 0, 'idx': 15},
        {'fieldname': 'entities', 'label': 'Entities', 'fieldtype': 'Heading', 'options': 'None', 'reqd': 0, 'idx': 34},
        {'fieldname': 'developer', 'label': 'Developer', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 35},
        {'fieldname': 'parent_project', 'label': 'Parent Project', 'fieldtype': 'Link', 'options': 'Project', 'reqd': 0, 'idx': 5},
        {'fieldname': 'customer', 'label': 'Client', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 1, 'idx': 6}
    ]
    for field in project_fields:
        if field['fieldname'] not in [d.fieldname for d in project_doctype.fields]:
            project_doctype.fields.insert(field['idx'],field)

    project_doctype.save(ignore_permissions=True)

    task_doctype = frappe.get_doc("DocType","Task")
    task_fields = [
        {'fieldname': 'notes', 'label': 'Notes', 'fieldtype': 'Text', 'options': 'None', 'reqd': 0, 'idx': 30},
        {'fieldname': 'exp_start_date', 'label': 'Deadline', 'fieldtype': 'Date', 'options': 'None', 'reqd': 0, 'idx': 17},
        {'fieldname': 'users', 'label': 'Users', 'fieldtype': 'Table', 'options': 'Task User', 'reqd': 0, 'idx': 26}
    ]
    
    for field in task_fields:
        if field['fieldname'] not in [d.fieldname for d in task_doctype.fields]:
            task_doctype.fields.insert(field['idx'],field)
    task_doctype.save(ignore_permissions=True)

    frappe.flags.developer_mode = 0