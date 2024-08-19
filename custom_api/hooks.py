from . import __version__ as app_version

app_name = "custom_api"
app_title = "Custom Api"
app_publisher = "Buildx"
app_description = "Custom Api collection for core Buildx logic"
app_email = "info@buildx.ps"
app_license = "MIT"

# api_path = "custom_api.api.convert_docx_to_pdf"

doc_events = {
    "Attendance": {
        "on_create": "custom_api.api.update_employee_timesheet_on_attendance_creation",
    }
}

scheduler_events = {
    "daily": [
        "custom_api.api.create_employee_attendance"
    ]
}
