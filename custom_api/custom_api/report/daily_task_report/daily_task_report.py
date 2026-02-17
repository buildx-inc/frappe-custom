import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

ACTIVE_STATUSES = ("Open", "Working", "Pending Review", "Overdue")
PRIORITY_RANK = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
BUCKET_RANK = {"Upcoming (2 Days)": 0, "Overdue": 1, "Other Active Tasks": 2}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    rows, summary = get_report_rows(filters)
    columns = get_columns()
    chart = get_chart(rows)
    return columns, rows, None, chart, summary


def get_report_rows(filters=None):
    filters = frappe._dict(filters or {})
    report_date = getdate(filters.get("report_date") or today())
    upcoming_until = add_days(report_date, 2)
    rows = get_task_rows(filters)

    for row in rows:
        due_date = get_relevant_due_date(row)
        row.due_date = due_date
        row.bucket = get_bucket_label(due_date, report_date, upcoming_until)
        row.bucket_rank = BUCKET_RANK.get(row.bucket, 99)
        row.priority_rank = PRIORITY_RANK.get(row.priority, 99)
        row.days_to_due = (due_date - report_date).days if due_date else None
        row.assignees = row.assignees or ""
        row.previous_status = row.previous_status if "previous_status" in row else None

    # Keep modified desc as the last tiebreaker after bucket/priority/due ordering.
    rows.sort(key=lambda x: x.modified, reverse=True)
    rows.sort(key=lambda x: x.due_date or add_days(report_date, 36500))
    rows.sort(key=lambda x: x.priority_rank)
    rows.sort(key=lambda x: x.bucket_rank)

    return rows, get_summary(rows)


def get_rows_grouped_by_bucket(rows):
    grouped = {"Upcoming (2 Days)": [], "Overdue": [], "Other Active Tasks": []}
    for row in rows:
        grouped.setdefault(row.bucket, []).append(row)
    return grouped


def get_bucket_counter(rows):
    counter = {"Upcoming (2 Days)": 0, "Overdue": 0, "Other Active Tasks": 0}
    for row in rows:
        counter[row.bucket] = counter.get(row.bucket, 0) + 1
    return counter


def get_top_highlights(rows, limit=8):
    highlight = []
    for row in rows:
        is_critical = row.priority in ("Urgent", "High")
        is_attention_bucket = row.bucket in ("Overdue", "Upcoming (2 Days)")
        if is_critical or is_attention_bucket:
            highlight.append(row)
        if len(highlight) >= limit:
            break
    return highlight


def get_task_rows(filters):
    where_sql = [
        "t.status in %(active_statuses)s",
    ]
    query_filters = {
        "active_statuses": ACTIVE_STATUSES,
    }

    if filters.get("project"):
        where_sql.append("t.project = %(project)s")
        query_filters["project"] = filters.get("project")

    if filters.get("priority"):
        where_sql.append("t.priority = %(priority)s")
        query_filters["priority"] = filters.get("priority")

    if filters.get("user"):
        where_sql.append(
            """(
                exists (
                    select 1
                    from `tabUser List` ulf
                    where ulf.parent = t.name
                      and ulf.parenttype = 'Task'
                      and ulf.parentfield = 'users'
                      and ulf.user = %(user)s
                )
                or ifnull(t._assign, '') like concat('%%', %(user)s, '%%')
                or exists (
                    select 1
                    from `tabToDo` td
                    where td.reference_type = 'Task'
                      and td.reference_name = t.name
                      and td.allocated_to = %(user)s
                      and td.status not in ('Cancelled', 'Closed')
                )
            )"""
        )
        query_filters["user"] = filters.get("user")

    previous_status_column = "null as previous_status"
    if frappe.db.has_column("Task", "previous_status"):
        previous_status_column = "t.previous_status as previous_status"

    return frappe.db.sql(
        f"""
        select
            t.name,
            t.subject,
            t.project,
            t.status,
            t.priority,
            t.exp_end_date,
            t.review_date,
            {previous_status_column},
            t.modified,
            ta.assignees
        from `tabTask` t
        left join (
            select
                parent,
                group_concat(coalesce(nullif(full_name, ''), user) order by idx asc separator ', ') as assignees
            from `tabUser List`
            where parenttype = 'Task'
              and parentfield = 'users'
            group by parent
        ) ta on ta.parent = t.name
        where {' and '.join(where_sql)}
        """,
        query_filters,
        as_dict=True,
    )


def get_relevant_due_date(row):
    if row.status == "Pending Review" and row.review_date:
        return getdate(row.review_date)
    if row.exp_end_date:
        return getdate(row.exp_end_date)
    return None


def get_bucket_label(due_date, report_date, upcoming_until):
    if due_date and report_date <= due_date <= upcoming_until:
        return "Upcoming (2 Days)"
    if due_date and due_date < report_date:
        return "Overdue"
    return "Other Active Tasks"


def get_summary(rows):
    counter = get_bucket_counter(rows)
    critical_count = sum(1 for row in rows if row.priority in ("Urgent", "High"))

    return [
        {"value": len(rows), "label": _("Total Active Tasks"), "datatype": "Int"},
        {"value": critical_count, "label": _("Critical Priority (Urgent/High)"), "datatype": "Int"},
        {"value": counter["Upcoming (2 Days)"], "label": _("Upcoming (2 Days)"), "datatype": "Int"},
        {"value": counter["Overdue"], "label": _("Overdue"), "datatype": "Int"},
        {"value": counter["Other Active Tasks"], "label": _("Other Active Tasks"), "datatype": "Int"},
    ]


def get_chart(rows):
    counter = get_bucket_counter(rows)
    labels = ["Upcoming (2 Days)", "Overdue", "Other Active Tasks"]
    total_values = [counter.get(label, 0) for label in labels]
    critical_values = [
        sum(1 for row in rows if row.bucket == label and row.priority in ("Urgent", "High"))
        for label in labels
    ]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Total Tasks"), "values": total_values},
                {"name": _("Urgent/High"), "values": critical_values},
            ],
        },
        "type": "bar",
        "height": 280,
        "barOptions": {"stacked": 0},
    }


def get_columns():
    return [
        {"label": _("Bucket"), "fieldname": "bucket", "fieldtype": "Data", "width": 170},
        {"label": _("Task"), "fieldname": "name", "fieldtype": "Link", "options": "Task", "width": 160},
        {"label": _("Subject"), "fieldname": "subject", "fieldtype": "Data", "width": 250},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 95},
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 120},
        {"label": _("Days To Due"), "fieldname": "days_to_due", "fieldtype": "Int", "width": 110},
        {"label": _("Previous Status"), "fieldname": "previous_status", "fieldtype": "Data", "width": 130},
        {"label": _("Assignees"), "fieldname": "assignees", "fieldtype": "Data", "width": 220},
    ]
