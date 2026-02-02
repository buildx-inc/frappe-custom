from __future__ import annotations

import frappe
from frappe import _


def _compute_amount(qty, rate):
    try:
        return float(qty or 0) * float(rate or 0)
    except Exception:
        return 0


def _validate_tender(tender_doc):
    if not tender_doc.get("customer"):
        frappe.throw(_("Tender must have a Customer before conversion."))

    items = tender_doc.get("items") or []
    if not items:
        frappe.throw(_("Tender must have at least one item."))


@frappe.whitelist()
def recompute_tender_totals(tender_name: str) -> dict:
    """Recompute Tender item amounts + competitor totals.

    Updates in-place:
    - Tender Item.amount = qty * rate
    - Tender Competitor Price.amount = qty * rate
    - Tender Competitor.total_amount = sum(amount) for its prices

    Returns:
      {"tender": <name>, "competitors": {<competitor_name>: <total>, ...}}

    Notes:
    - Competitor matching uses string equality between:
      - Tender Competitor.competitor_name
      - Tender Competitor Price.competitor
    """

    if not tender_name:
        frappe.throw(_("tender_name is required"))

    tender = frappe.get_doc("Tender", tender_name)

    # 1) item amounts
    for row in tender.get("items") or []:
        row.amount = _compute_amount(row.get("qty"), row.get("rate"))

    # 2) competitor price amounts + aggregation
    totals = {}
    for row in tender.get("competitor_prices") or []:
        row.amount = _compute_amount(row.get("qty"), row.get("rate"))
        comp = (row.get("competitor") or "").strip()
        if not comp:
            continue
        totals[comp] = float(totals.get(comp, 0) or 0) + float(row.amount or 0)

    # 3) write totals into competitors table
    for row in tender.get("competitors") or []:
        name = (row.get("competitor_name") or "").strip()
        if not name:
            continue
        row.total_amount = totals.get(name, 0)

    tender.save(ignore_permissions=True)

    return {"tender": tender.name, "competitors": totals}


@frappe.whitelist()
def create_quotation_from_tender(tender_name: str) -> str:
    """Create an ERPNext Quotation from a Tender.

    Returns:
      quotation.name

    Notes:
    - Requires Tender.customer.
    - Uses Tender.items rows: item_code, qty, rate.
    """

    if not tender_name:
        frappe.throw(_("tender_name is required"))

    tender = frappe.get_doc("Tender", tender_name)
    _validate_tender(tender)

    # Ensure computed totals are up-to-date before generating documents.
    try:
        recompute_tender_totals(tender.name)
        tender = frappe.get_doc("Tender", tender.name)
    except Exception:
        # Do not block quotation creation if totals computation fails.
        pass

    qtn = frappe.new_doc("Quotation")
    qtn.quotation_to = "Customer"
    qtn.party_name = tender.customer

    # Dates
    if tender.get("tender_date"):
        qtn.transaction_date = tender.tender_date

    # Company
    if tender.get("company"):
        qtn.company = tender.company

    # Items
    for row in tender.get("items") or []:
        if not row.get("item_code"):
            continue
        qty = row.get("qty") or 0
        rate = row.get("rate")
        if rate in (None, ""):
            frappe.throw(_("Tender item rate is required for item {0}").format(row.get("item_code")))

        qtn.append(
            "items",
            {
                "item_code": row.get("item_code"),
                "qty": qty,
                "uom": row.get("uom"),
                "rate": rate,
                "amount": _compute_amount(qty, rate),
            },
        )

    # Keep a reference in title/remarks
    qtn.title = tender.get("tender_title") or tender.name
    qtn.terms = (tender.get("notes") or "")

    qtn.insert(ignore_permissions=True)

    # Optional: submit? usually quotation stays draft.
    # qtn.submit()

    # Store linkage if fields exist on Tender (future-proof)
    if hasattr(tender, "quotation"):
        tender.quotation = qtn.name
        tender.save(ignore_permissions=True)

    return qtn.name


@frappe.whitelist()
def create_sales_order_from_quotation(quotation_name: str) -> str:
    """Create Sales Order from an existing Quotation.

    Returns:
      sales_order.name
    """

    if not quotation_name:
        frappe.throw(_("quotation_name is required"))

    # ERPNext factory method
    try:
        from erpnext.selling.doctype.quotation.quotation import make_sales_order
    except Exception as e:
        frappe.throw(_("ERPNext make_sales_order not available: {0}").format(str(e)))

    so = make_sales_order(quotation_name)
    so.insert(ignore_permissions=True)

    return so.name


@frappe.whitelist()
def convert_tender_to_sales_order(tender_name: str) -> dict:
    """Convenience: Tender -> Quotation -> Sales Order.

    Returns:
      { quotation, sales_order }
    """

    quotation = create_quotation_from_tender(tender_name)
    sales_order = create_sales_order_from_quotation(quotation)

    # Store linkage if fields exist on Tender (future-proof)
    tender = frappe.get_doc("Tender", tender_name)
    if hasattr(tender, "sales_order"):
        tender.sales_order = sales_order
        tender.save(ignore_permissions=True)

    return {"quotation": quotation, "sales_order": sales_order}
