import frappe
from frappe import _


def _ensure_request_helpers():
	if not hasattr(frappe, "get_request"):
		def _get_request():
			return getattr(frappe.local, "request", None)

		frappe.get_request = _get_request  # type: ignore[attr-defined]


_ensure_request_helpers()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	"""Receive CDC events from edge sites."""
	request_obj = frappe.get_request()
	data = getattr(frappe.local, "form_dict", None)
	if not data and request_obj:
		try:
			data = request_obj.get_json(silent=True)
		except Exception:
			data = None

	if not data:
		frappe.throw(_("Missing JSON payload"))

	event_id = data.get("event_id")
	if not event_id:
		frappe.throw(_("Missing event_id"))

	_validate_api_key()

	if frappe.db.exists("Sync Event", {"event_id": event_id}):
		return {"status": "ok", "reason": "duplicate"}

	raw_doc = frappe._dict(data.get("doc") or {})
	for key in ("__run_link_triggers", "__unsaved"):
		raw_doc.pop(key, None)

	frappe.flags.ignore_cdc = True
	try:
		_sync_event(data, raw_doc)
	finally:
		frappe.flags.ignore_cdc = False

	frappe.publish_realtime(
		"sync:processed",
		{"site_id": data.get("site_id"), "event_id": event_id},
	)
	return {"status": "ok"}


def _sync_event(data, raw_doc):
	doc = frappe.get_doc(
		{
			"doctype": "Sync Event",
			"event_id": data.get("event_id"),
			"site_id": data.get("site_id"),
			"doctype_name": data.get("doctype"),
			"docname": data.get("docname"),
			"operation": data.get("operation"),
			"payload": frappe.as_json(raw_doc),
		}
	)
	doc.insert(ignore_permissions=True)
	_apply_change(raw_doc, data)


def _apply_change(doc_dict, data):
	doc = frappe.get_doc(doc_dict)
	doctype = doc.doctype
	docname = doc.name
	operation = data.get("operation")

	if not doctype or not docname:
		frappe.throw(_("Missing target doctype or docname"))

	try:
		if operation == "on_trash":
			if frappe.db.exists(doctype, docname):
				frappe.delete_doc(doctype, docname, ignore_permissions=True, force=True)
			return

		if not frappe.db.exists(doctype, docname):
			doc.insert(ignore_permissions=True)
			return

		existing = frappe.get_doc(doctype, docname)
		for key, value in doc_dict.items():
			if key in {"name", "doctype"}:
				continue
			try:
				setattr(existing, key, value)
			except Exception:
				continue

		existing.save(ignore_permissions=True)

	except Exception:
		frappe.log_error(frappe.get_traceback(), "sync.receive.apply_error")
		raise


def _validate_api_key():
	expected = None

	try:
		settings = frappe.get_cached_doc("Sync Settings")
		expected = settings.get_password("cloud_api_key") if getattr(settings, "cloud_api_key", None) else None
	except (frappe.DoesNotExistError, ImportError):
		settings = None

	if not expected:
		expected = frappe.conf.get("cloud_sync_api_key")

	if not expected:
		frappe.throw(_("Cloud sync API key is not configured on this site."))

	request_obj = frappe.get_request()
	request_headers = getattr(request_obj, "headers", {}) or {}
	auth_header = request_headers.get("Authorization", "")
	custom_header = request_headers.get("X-Frappe-Sync-Key")

	if custom_header:
		token = custom_header.strip()
	else:
		if not auth_header.startswith("Bearer "):
			frappe.throw(_("Missing sync token"), frappe.PermissionError)
		token = auth_header.split("Bearer ", 1)[1].strip()

	if token != expected:
		frappe.throw(_("Invalid API key"), frappe.PermissionError)

