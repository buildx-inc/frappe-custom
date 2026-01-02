import frappe
from frappe.model.document import Document


class SyncEvent(Document):
	"""Receiver-side audit record for CDC events."""

	pass

