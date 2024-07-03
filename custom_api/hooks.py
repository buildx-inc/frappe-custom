from . import __version__ as app_version

app_name = "custom_api"
app_title = "Custom Api"
app_publisher = "Buildx"
app_description = "Custom Api collection for core Buildx logic"
app_email = "info@buildx.ps"
app_license = "MIT"

scheduler_events = {
    "daily": [
        "custom_api.api.create_employee_attendance"
    ]
}
