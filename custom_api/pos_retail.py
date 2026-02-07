# Copyright (c) 2026, Buildx and contributors
# For license information, please see license.txt
#
# Retail POS API  –  custom_api.pos_retail
# =========================================
# Endpoints:
#   POST  /api/method/custom_api.pos_retail.sync
#   GET   /api/method/custom_api.pos_retail.items_search
#   GET   /api/method/custom_api.pos_retail.item_by_barcode
#   POST  /api/method/custom_api.pos_retail.price_quote

import json
import traceback
import frappe
from frappe import _
from frappe.utils import flt, cint, now_datetime, getdate, nowdate


# ---------------------------------------------------------------------------
# 1)  SYNC  –  idempotent offline-sync endpoint
# ---------------------------------------------------------------------------

@frappe.whitelist()
def sync(operations=None):
	"""
	POST /api/method/custom_api.pos_retail.sync
	Body: { "operations": [ { "id": "uuid", "kind": "sale", "payload": {...} } ] }

	Rules:
	- Each operation is identified by its `id` (client UUID).
	- If an operation with that id was already processed, return the cached result.
	- Supported kinds: sale, return, payment.
	"""
	if isinstance(operations, str):
		operations = json.loads(operations)

	if not operations:
		frappe.throw(_("No operations provided"), frappe.InvalidStatusError)

	results = []
	for op in operations:
		op_id = op.get("id")
		kind = op.get("kind")
		payload = op.get("payload") or {}

		if not op_id:
			results.append({"id": op_id, "ok": False, "error": "Missing operation id"})
			continue

		# ---- idempotency check ----
		existing = frappe.db.get_value(
			"POS Retail Sync Operation",
			{"operation_id": op_id},
			["name", "status", "result_doctype", "result_docname", "error_message"],
			as_dict=True,
		)
		if existing:
			if existing.status == "Success":
				results.append({
					"id": op_id,
					"ok": True,
					"doc": {"doctype": existing.result_doctype, "name": existing.result_docname},
				})
			else:
				results.append({"id": op_id, "ok": False, "error": existing.error_message})
			continue

		# ---- dispatch by kind ----
		try:
			if kind == "sale":
				doc = _handle_sale(payload)
			elif kind == "return":
				doc = _handle_return(payload)
			elif kind == "payment":
				doc = _handle_payment(payload)
			else:
				raise ValueError(f"Unknown operation kind: {kind}")

			# log success
			_log_sync_op(op_id, kind, payload, "Success", doc.doctype, doc.name)
			results.append({
				"id": op_id,
				"ok": True,
				"doc": {"doctype": doc.doctype, "name": doc.name},
			})

		except Exception as e:
			frappe.db.rollback()
			error_msg = str(e)
			frappe.log_error(
				title=f"POS Retail Sync Error: {op_id}",
				message=traceback.format_exc(),
			)
			_log_sync_op(op_id, kind, payload, "Failed", error_message=error_msg)
			results.append({"id": op_id, "ok": False, "error": error_msg})

	frappe.db.commit()
	return {"results": results}


def _log_sync_op(operation_id, kind, payload, status,
                 result_doctype=None, result_docname=None, error_message=None):
	"""Insert a POS Retail Sync Operation record."""
	doc = frappe.get_doc({
		"doctype": "POS Retail Sync Operation",
		"operation_id": operation_id,
		"kind": kind,
		"payload": json.dumps(payload, default=str) if payload else "",
		"status": status,
		"result_doctype": result_doctype,
		"result_docname": result_docname,
		"error_message": error_message,
		"cashier": frappe.session.user,
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.commit()


# ---------------------------------------------------------------------------
#  Sale handler  –  creates & submits a Sales Invoice
# ---------------------------------------------------------------------------

def _handle_sale(payload):
	"""
	payload expects:
	{
		"customer": "Walk-in Customer",
		"pos_profile": "Retail POS",           # optional, auto-detected if omitted
		"items": [
			{ "item_code": "ITEM-001", "qty": 2, "rate": 10.0 }
		],
		"payments": [
			{ "mode_of_payment": "Cash", "amount": 20.0 }
		],
		"posting_date": "2026-02-07",           # optional, defaults to today
		"additional_discount_percentage": 0,    # optional
		"discount_amount": 0                    # optional
	}
	"""
	pos_profile_name = payload.get("pos_profile")
	pos_profile = None
	if pos_profile_name:
		pos_profile = frappe.get_cached_doc("POS Profile", pos_profile_name)

	customer = payload.get("customer")
	if not customer and pos_profile:
		customer = pos_profile.customer

	if not customer:
		customer = _get_default_customer()

	items = payload.get("items", [])
	if not items:
		frappe.throw(_("No items in sale payload"))

	company = payload.get("company")
	if not company and pos_profile:
		company = pos_profile.company
	if not company:
		company = frappe.defaults.get_defaults().get("company")

	sinv = frappe.new_doc("Sales Invoice")
	sinv.is_pos = 1
	sinv.pos_profile = pos_profile_name or ""
	sinv.customer = customer
	sinv.company = company
	sinv.posting_date = payload.get("posting_date") or nowdate()
	sinv.set_posting_time = 1
	sinv.posting_time = payload.get("posting_time") or frappe.utils.nowtime()
	sinv.update_stock = 1
	sinv.set_warehouse = payload.get("warehouse") or (pos_profile.warehouse if pos_profile else "")

	# optional discounts
	if payload.get("additional_discount_percentage"):
		sinv.additional_discount_percentage = flt(payload["additional_discount_percentage"])
	if payload.get("discount_amount"):
		sinv.discount_amount = flt(payload["discount_amount"])

	# items
	for item in items:
		sinv.append("items", {
			"item_code": item["item_code"],
			"qty": flt(item.get("qty", 1)),
			"rate": flt(item.get("rate", 0)),
			"warehouse": item.get("warehouse") or sinv.set_warehouse,
			"serial_no": item.get("serial_no", ""),
			"batch_no": item.get("batch_no", ""),
			"uom": item.get("uom", ""),
		})

	# payments
	payments = payload.get("payments", [])
	for pmt in payments:
		sinv.append("payments", {
			"mode_of_payment": pmt["mode_of_payment"],
			"amount": flt(pmt["amount"]),
		})

	sinv.flags.ignore_permissions = True
	sinv.insert()
	sinv.submit()

	return sinv


# ---------------------------------------------------------------------------
#  Return handler  –  creates a return invoice against an existing SINV
# ---------------------------------------------------------------------------

def _handle_return(payload):
	"""
	payload expects:
	{
		"against_invoice": "SINV-0001",
		"items": [
			{ "item_code": "ITEM-001", "qty": 1 }     # qty should be positive; we negate it
		],
		"payments": [
			{ "mode_of_payment": "Cash", "amount": -10.0 }
		]
	}
	"""
	against = payload.get("against_invoice")
	if not against:
		frappe.throw(_("against_invoice is required for return"))

	source = frappe.get_doc("Sales Invoice", against)

	ret = frappe.copy_doc(source)
	ret.is_return = 1
	ret.return_against = against
	ret.is_pos = 1
	ret.update_stock = 1

	# zero out items, then add return lines
	ret.items = []
	for item in payload.get("items", []):
		# find original item row for defaults
		orig_item = next(
			(r for r in source.items if r.item_code == item["item_code"]), None
		)
		ret.append("items", {
			"item_code": item["item_code"],
			"qty": -abs(flt(item.get("qty", 1))),
			"rate": flt(item.get("rate")) if item.get("rate") else (orig_item.rate if orig_item else 0),
			"warehouse": item.get("warehouse") or (orig_item.warehouse if orig_item else ""),
			"serial_no": item.get("serial_no", ""),
			"batch_no": item.get("batch_no", ""),
		})

	# payments
	ret.payments = []
	for pmt in payload.get("payments", []):
		ret.append("payments", {
			"mode_of_payment": pmt["mode_of_payment"],
			"amount": flt(pmt["amount"]),
		})

	ret.flags.ignore_permissions = True
	ret.insert()
	ret.submit()

	return ret


# ---------------------------------------------------------------------------
#  Payment handler  –  standalone Payment Entry
# ---------------------------------------------------------------------------

def _handle_payment(payload):
	"""
	payload expects:
	{
		"against_invoice": "SINV-0001",
		"mode_of_payment": "Cash",
		"amount": 50.0,
		"reference_no": "",         # optional, for bank transfers
		"reference_date": ""        # optional
	}
	"""
	against = payload.get("against_invoice")
	if not against:
		frappe.throw(_("against_invoice is required for payment"))

	sinv = frappe.get_doc("Sales Invoice", against)

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.party_type = "Customer"
	pe.party = sinv.customer
	pe.company = sinv.company
	pe.posting_date = payload.get("posting_date") or nowdate()
	pe.mode_of_payment = payload.get("mode_of_payment", "Cash")
	pe.paid_amount = flt(payload.get("amount"))
	pe.received_amount = flt(payload.get("amount"))
	pe.reference_no = payload.get("reference_no") or sinv.name
	pe.reference_date = payload.get("reference_date") or nowdate()

	# get accounts from mode of payment
	mop = frappe.get_cached_doc("Mode of Payment", pe.mode_of_payment)
	mop_account = None
	for acc in mop.accounts:
		if acc.company == sinv.company:
			mop_account = acc.default_account
			break

	if mop_account:
		pe.paid_to = mop_account

	pe.append("references", {
		"reference_doctype": "Sales Invoice",
		"reference_name": sinv.name,
		"total_amount": sinv.grand_total,
		"outstanding_amount": sinv.outstanding_amount,
		"allocated_amount": flt(payload.get("amount")),
	})

	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()

	return pe


# ---------------------------------------------------------------------------
# 2)  ITEMS SEARCH
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["GET"])
def items_search(text="", pos_profile=None, limit=20):
	"""
	GET /api/method/custom_api.pos_retail.items_search?text=apple&limit=20
	Returns minimal item fields needed for the POS frontend.
	"""
	limit = cint(limit) or 20
	text = (text or "").strip()

	filters = {"disabled": 0, "has_variants": 0, "is_sales_item": 1}
	or_filters = {}

	if text:
		or_filters = {
			"item_code": ["like", f"%{text}%"],
			"item_name": ["like", f"%{text}%"],
			"description": ["like", f"%{text}%"],
		}

	# if pos_profile is given, filter by item groups allowed
	item_group_filter = _get_item_group_filter(pos_profile)
	if item_group_filter:
		filters["item_group"] = ["in", item_group_filter]

	items = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters if text else None,
		fields=[
			"name", "item_code", "item_name", "item_group",
			"stock_uom", "image", "description",
			"standard_rate", "has_batch_no", "has_serial_no",
		],
		limit_page_length=limit,
		order_by="item_name asc",
	)

	# attach barcodes + price
	_enrich_items(items, pos_profile)

	return items


# ---------------------------------------------------------------------------
# 3)  ITEM BY BARCODE
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["GET"])
def item_by_barcode(barcode=None, pos_profile=None):
	"""
	GET /api/method/custom_api.pos_retail.item_by_barcode?barcode=12345
	Returns the item matching the barcode, or 404.
	"""
	if not barcode:
		frappe.throw(_("barcode is required"), frappe.MandatoryError)

	barcode_doc = frappe.db.get_value(
		"Item Barcode",
		{"barcode": barcode},
		["parent", "barcode", "uom"],
		as_dict=True,
	)

	if not barcode_doc:
		frappe.throw(
			_("No item found for barcode {0}").format(barcode),
			frappe.DoesNotExistError,
		)

	item = frappe.get_all(
		"Item",
		filters={"name": barcode_doc.parent, "disabled": 0},
		fields=[
			"name", "item_code", "item_name", "item_group",
			"stock_uom", "image", "description",
			"standard_rate", "has_batch_no", "has_serial_no",
		],
		limit_page_length=1,
	)

	if not item:
		frappe.throw(
			_("Item {0} is disabled or not found").format(barcode_doc.parent),
			frappe.DoesNotExistError,
		)

	item = item[0]
	item["barcode"] = barcode
	item["barcode_uom"] = barcode_doc.uom or item["stock_uom"]

	_enrich_items([item], pos_profile)

	return item


# ---------------------------------------------------------------------------
# 4)  PRICE QUOTE  –  cart totals / tax preview
# ---------------------------------------------------------------------------

@frappe.whitelist()
def price_quote(items=None, customer=None, pos_profile=None, company=None):
	"""
	POST /api/method/custom_api.pos_retail.price_quote
	Body: {
		"items": [ { "item_code": "X", "qty": 2, "rate": 10 } ],
		"customer": "Walk-in Customer",
		"pos_profile": "Retail POS"
	}
	Returns: { "items": [...], "total": ..., "taxes": [...], "grand_total": ... }
	"""
	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("items list is required"))

	if not company:
		if pos_profile:
			company = frappe.db.get_value("POS Profile", pos_profile, "company")
		if not company:
			company = frappe.defaults.get_defaults().get("company")

	if not customer:
		if pos_profile:
			customer = frappe.db.get_value("POS Profile", pos_profile, "customer")
		if not customer:
			customer = _get_default_customer()

	# build a draft Sales Invoice to leverage ERPNext tax calculation
	sinv = frappe.new_doc("Sales Invoice")
	sinv.is_pos = 1
	sinv.pos_profile = pos_profile or ""
	sinv.customer = customer
	sinv.company = company
	sinv.posting_date = nowdate()
	sinv.set_posting_time = 1
	sinv.update_stock = 0  # draft – no stock impact
	sinv.currency = frappe.get_cached_value("Company", company, "default_currency")

	for item in items:
		sinv.append("items", {
			"item_code": item["item_code"],
			"qty": flt(item.get("qty", 1)),
			"rate": flt(item.get("rate", 0)),
		})

	sinv.flags.ignore_permissions = True
	sinv.set_missing_values()
	sinv.calculate_taxes_and_totals()

	# build response
	result_items = []
	for row in sinv.items:
		result_items.append({
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"net_amount": row.net_amount,
		})

	taxes = []
	for tax_row in sinv.taxes:
		taxes.append({
			"description": tax_row.description,
			"rate": tax_row.rate,
			"tax_amount": tax_row.tax_amount,
			"total": tax_row.total,
		})

	return {
		"items": result_items,
		"total": sinv.total,
		"net_total": sinv.net_total,
		"taxes": taxes,
		"grand_total": sinv.grand_total,
		"rounding_adjustment": sinv.rounding_adjustment or 0,
		"rounded_total": sinv.rounded_total or sinv.grand_total,
		"currency": sinv.currency,
	}


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _get_default_customer():
	"""Return the default POS / walk-in customer."""
	customer = frappe.db.get_single_value("Selling Settings", "customer_name") or ""
	if not customer:
		# try finding a standard walk-in customer
		customer = frappe.db.get_value("Customer", {"name": ["like", "%Walk%In%"]}, "name") or ""
	return customer


def _get_item_group_filter(pos_profile):
	"""Return list of allowed item groups from POS Profile, or None."""
	if not pos_profile:
		return None
	groups = frappe.get_all(
		"POS Item Group",
		filters={"parent": pos_profile, "parenttype": "POS Profile"},
		fields=["item_group"],
		pluck="item_group",
	)
	return groups or None


def _enrich_items(items, pos_profile=None):
	"""Attach price_list_rate and barcodes to item dicts in-place."""
	if not items:
		return

	price_list = None
	if pos_profile:
		price_list = frappe.db.get_value("POS Profile", pos_profile, "selling_price_list")
	if not price_list:
		price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")

	for item in items:
		item_code = item.get("item_code") or item.get("name")

		# price
		if price_list:
			price = frappe.db.get_value(
				"Item Price",
				{"item_code": item_code, "price_list": price_list, "selling": 1},
				"price_list_rate",
			)
			item["price_list_rate"] = flt(price)
		else:
			item["price_list_rate"] = flt(item.get("standard_rate", 0))

		# barcodes
		barcodes = frappe.get_all(
			"Item Barcode",
			filters={"parent": item_code},
			fields=["barcode", "uom"],
		)
		item["barcodes"] = barcodes
