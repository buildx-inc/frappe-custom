import frappe

def execute():
    frappe.flags.developer_mode = 1

    doctype_doctype = frappe.get_doc("DocType","DocType")
    doctype_fields = [
        {'doctype':'DocField','fieldname': 'alias', 'label': 'Alias', 'fieldtype': 'Data', 'options': 'None', 'reqd': 0, 'idx': 3},
        {'doctype':'DocField','fieldname': 'enable_drive', 'label': 'Enable Drive', 'fieldtype': 'Check', 'options': 'None', 'reqd': 0, 'idx': 17},
        {'doctype':'DocField','fieldname': 'allow_email', 'label': 'Allow Email', 'fieldtype': 'Check', 'options': 'None', 'reqd': 0, 'idx': 86},
        {'doctype':'DocField','fieldname': 'has_kanban', 'label': 'Has Kanban', 'fieldtype': 'Check', 'options': 'None', 'reqd': 0, 'idx': 19}]
    
    current_fields = []

    for doctype_field in doctype_doctype.fields:
        current_fields.append(doctype_field.fieldname)

    for field in doctype_fields:
        if field['fieldname'] not in current_fields:
            field_doc = frappe.get_doc(field)
            doctype_doctype.fields.insert(field['idx'],field_doc)

    doctype_doctype.save(ignore_permissions=True)

    docfield_doctype = frappe.get_doc("DocType","DocField")

    docfield_fields = [
        {'doctype':'DocField','fieldname': 'alias', 'label': 'Alias', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 9},
        {'doctype':'DocField','fieldname': 'buildx_depends_on', 'label': 'Buildx Depends On', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 44},
        {'doctype':'DocField','fieldname': 'external_link', 'label': 'External Link', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 20},
        {'doctype':'DocField','fieldname': 'select_label', 'label': 'Select Label', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 9},
        {'doctype':'DocField','fieldname': 'option_label', 'label': 'Option Label', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 10},
        {'doctype':'DocField','fieldname': 'calendar_color', 'label': 'Calendar Color', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 61},
        {'doctype':'DocField','fieldname': 'calendar_description', 'label': 'Calendar Description', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 62},
        {'doctype':'DocField','fieldname': 'calendar_end_date', 'label': 'Calendar End Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 65},
        {'doctype':'DocField','fieldname': 'calendar_start_date', 'label': 'Calendar Start Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 63},
        {'doctype':'DocField','fieldname': 'calendar_title', 'label': 'Calendar Title', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 60},
        {'doctype':'DocField','fieldname': 'conditional_default', 'label': 'Conditional Default', 'fieldtype': 'JSON', 'options': None, 'reqd': 0, 'idx': 30},
        {'doctype':'DocField','fieldname': 'enable_actions', 'label': 'Enable Actions', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 20},
        {'doctype':'DocField','fieldname': 'filters', 'label': 'Filters', 'fieldtype': 'JSON', 'options': None, 'reqd': 0, 'idx': 57},
        {'doctype':'DocField','fieldname': 'in_compact_list', 'label': 'In Compact List', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 55},
        {'doctype':'DocField','fieldname': 'in_view', 'label': 'In View', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 53},
        {'doctype':'DocField','fieldname': 'in_edit', 'label': 'In Edit', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 54},
        {'doctype':'DocField','fieldname': 'in_list_compact', 'label': 'In List Compact', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 49},
        {'doctype':'DocField','fieldname': 'kanban_category', 'label': 'Kanban Category', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 24},
        {'doctype':'DocField','fieldname': 'kanban_date', 'label': 'Kanban Date', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 25},
        {'doctype':'DocField','fieldname': 'kanban_description', 'label': 'Kanban Description', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 23},
        {'doctype':'DocField','fieldname': 'kanban_group', 'label': 'Kanban Group', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 21},
        {'doctype':'DocField','fieldname': 'kanban_title', 'label': 'Kanban Title', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 22},
        {'doctype':'DocField','fieldname': 'kanban_user', 'label': 'Kanban User', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 23},
        {'doctype':'DocField','fieldname': 'kanban_tags', 'label': 'Kanban Tags', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 26},
        {'doctype':'DocField','fieldname': 'multiselect', 'label': 'Is Multiselect', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 6},
        {'doctype':'DocField','fieldname': 'multiselect_id', 'label': 'Multiselect Id', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 7},
        {'doctype':'DocField','fieldname': 'multiselect_key', 'label': 'Multiselect Key', 'fieldtype': 'Data', 'options': None, 'reqd': 0, 'idx': 8},
        {'doctype':'DocField','fieldname': 'validation', 'label': 'valid', 'fieldtype': 'JSON', 'options': None, 'reqd': 0, 'idx': 56},
        {'doctype':'DocField','fieldname': 'radio_group', 'label': 'Radio Group', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 4},
        {'doctype':'DocField','fieldname': 'card_view', 'label': 'Card View', 'fieldtype': 'Check', 'options': None, 'reqd': 0, 'idx': 5}
        
    ]
    current_fields = []

    for docfield_field in docfield_doctype.fields:
        current_fields.append(docfield_field.fieldname)

    for field in docfield_fields:
        if field['fieldname'] not in current_fields:
            print("adding " + field['fieldname'] + " to DocField")
            field_doc = frappe.get_doc(field)
            docfield_doctype.fields.insert(field['idx'],field_doc)
        else:
            print("field:" + field['fieldname'] + " exists in DocField")


    docfield_doctype.save(ignore_permissions=True)

    user_doctype = frappe.get_doc("DocType","User")
    user_fields = [
        {'doctype':'DocField','fieldname': 'company', 'label': 'Company', 'fieldtype': 'Link', 'options': 'Company', 'reqd': 0, 'idx': 4},
        {'doctype':'DocField','fieldname': 'role_profile_name', 'label': 'Role Profile', 'fieldtype': 'Link', 'options': 'Role Profile', 'reqd': 0, 'idx': 17},
        {'doctype':'DocField','fieldname': 'status', 'label': 'Status', 'fieldtype': 'Select', 'options': 'Active\nCancelled', 'reqd': 0, 'idx': 5}
    ]
    
    
    current_fields = []

    for user_field in user_doctype.fields:
        current_fields.append(user_field.fieldname)

    for field in user_fields:
        if field['fieldname'] not in current_fields:
            field_doc = frappe.get_doc(field)
            user_doctype.fields.insert(field['idx'],field_doc)

    user_doctype.save(ignore_permissions=True)

    # project_doctype = frappe.get_doc("DocType","Project")
    # project_fields = [
    #     {'doctype':'DocField','fieldname': 'project_location', 'label': 'Location', 'fieldtype': 'Data', 'options': 'None', 'reqd': 0, 'idx': 13},
    #     {'doctype':'DocField','fieldname': 'sub_contractor', 'label': 'Sub Contractor', 'fieldtype': 'Table', 'options': 'Project Sub Contractor', 'reqd': 0, 'idx': 41},
    #     {'doctype':'DocField','fieldname': 'main_contractor', 'label': 'Main Contractor', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 40},
    #     {'doctype':'DocField','fieldname': 'third_party_consultant', 'label': 'Third Party Consultant', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 37},
    #     {'doctype':'DocField','fieldname': 'consultant', 'label': 'Consultant', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 36},
    #     {'doctype':'DocField','fieldname': 'system_area', 'label': 'System Area', 'fieldtype': 'Float', 'options': 'None', 'reqd': 0, 'idx': 16},
    #     {'doctype':'DocField','fieldname': 'project_manager', 'label': 'Project Manager', 'fieldtype': 'Link', 'options': 'User', 'reqd': 1, 'idx': 8},
    #     {'doctype':'DocField','fieldname': 'project_manager_name', 'label': 'Project Manager', 'fieldtype': 'Data', 'options': 'None', 'reqd': 0, 'idx': 9},
    #     {'doctype':'DocField','fieldname': 'project_management_company', 'label': 'Project Management Company', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 39},
    #     {'doctype':'DocField','fieldname': 'authority', 'label': 'Authority', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 38},
    #     {'doctype':'DocField','fieldname': 'total_area', 'label': 'Total Area', 'fieldtype': 'Float', 'options': 'None', 'reqd': 0, 'idx': 15},
    #     {'doctype':'DocField','fieldname': 'entities', 'label': 'Entities', 'fieldtype': 'Heading', 'options': 'None', 'reqd': 0, 'idx': 34},
    #     {'doctype':'DocField','fieldname': 'developer', 'label': 'Developer', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 0, 'idx': 35},
    #     {'doctype':'DocField','fieldname': 'parent_project', 'label': 'Parent Project', 'fieldtype': 'Link', 'options': 'Project', 'reqd': 0, 'idx': 5},
    #     {'doctype':'DocField','fieldname': 'customer', 'label': 'Client', 'fieldtype': 'Link', 'options': 'Supplier', 'reqd': 1, 'idx': 6}
    # ]
    
    
    # current_fields = []

    # for project_field in project_doctype.fields:
    #     current_fields.append(project_field.fieldname)

    # for field in project_fields:
    #     if field['fieldname'] not in current_fields:
    #         field_doc = frappe.get_doc(field)
    #         project_doctype.fields.insert(field['idx'],field_doc)

    # project_doctype.save(ignore_permissions=True)

    # task_doctype = frappe.get_doc("DocType","Task")
    # task_fields = [
    #     {'doctype':'DocField','fieldname': 'notes', 'label': 'Notes', 'fieldtype': 'Text', 'options': 'None', 'reqd': 0, 'idx': 30},
    #     {'doctype':'DocField','fieldname': 'exp_start_date', 'label': 'Deadline', 'fieldtype': 'Date', 'options': 'None', 'reqd': 0, 'idx': 17},
    #     {'doctype':'DocField','fieldname': 'users', 'label': 'Users', 'fieldtype': 'Table', 'options': 'Task User', 'reqd': 0, 'idx': 26}
    # ]
    
    
    # current_fields = []

    # for task_field in task_doctype.fields:
    #     current_fields.append(task_field.fieldname)

    # for field in task_fields:
    #     if field['fieldname'] not in current_fields:
    #         field_doc = frappe.get_doc(field)
    #         task_doctype.fields.insert(field['idx'],field_doc)

    # task_doctype.save(ignore_permissions=True)

    frappe.flags.developer_mode = 0