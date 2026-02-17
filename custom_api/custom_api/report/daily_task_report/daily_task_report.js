frappe.query_reports["Daily Task Report"] = {
	"filters": [
		{
			"fieldname": "report_date",
			"label": __("Report Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "user",
			"label": __("User"),
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project"
		},
		{
			"fieldname": "priority",
			"label": __("Priority"),
			"fieldtype": "Select",
			"options": ["", "Low", "Medium", "High", "Urgent"]
		},
	],
	"onload": function (report) {
		report.page.add_inner_button(__("Download Daily PDF"), function () {
			const filters = report.get_values() || {};
			const query = new URLSearchParams({
				filters: JSON.stringify(filters),
			}).toString();
			window.open(`/api/method/custom_api.api.download_daily_task_report_pdf?${query}`);
		});
	},
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) {
			return value;
		}

		if (column.fieldname === "bucket") {
			if (data.bucket === "Overdue") {
				return `<span style="color: #d9534f; font-weight: 700">${value}</span>`;
			}
			if (data.bucket === "Upcoming (2 Days)") {
				return `<span style="color: #f0ad4e; font-weight: 700">${value}</span>`;
			}
			return value;
		}

		if (column.fieldname === "priority") {
			if (data.priority === "Urgent") return `<span style="color:#b91c1c;font-weight:700">${value}</span>`;
			if (data.priority === "High") return `<span style="color:#c2410c;font-weight:700">${value}</span>`;
			return value;
		}

		if (column.fieldname === "days_to_due" && data.days_to_due !== null && data.days_to_due !== undefined) {
			if (data.days_to_due < 0) return `<span style="color:#b91c1c;font-weight:700">${value}</span>`;
			if (data.days_to_due <= 2) return `<span style="color:#c2410c;font-weight:700">${value}</span>`;
			return value;
		}

		return value;
	},
};
