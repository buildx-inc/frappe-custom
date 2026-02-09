# Copyright (c) 2026, Buildx and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MultiPayment(Document):
    
    def on_submit(self):
        company_abbr = frappe.db.get_value("Company", self.company, "abbr")
        if self.reference_doc != None and self.reference_doc != "":
            reference_doc = frappe.get_doc(self.reference_doctype, self.reference_doc)
            outstanding_amount = reference_doc.outstanding_amount
            if reference_doc.doctype == "Sales Order": #receivable
                payment_type = "Receive"
                party_type = "Customer"
                party = reference_doc.customer

            elif reference_doc.doctype == "Sales Invoice": #receivable
                payment_type = "Receive"
                party_type = "Customer"
                party = reference_doc.customer
            elif reference_doc.doctype == "Purchase Order": #payable
                payment_type = "Pay"
                party_type = "Supplier"
                party = reference_doc.supplier
            elif reference_doc.doctype == "Purchase Invoice": #payable
                payment_type = "Pay"
                party_type = "Supplier"
                party = reference_doc.supplier
        else:
            reference_doc = None
            party_type = self.party_type
            party = self.party
            payment_type = self.payment_type
            
        for pe in self.payment_entries:
            #create payment entry for each payment entry
            if pe.payment_entry != None and pe.payment_entry != "":
                continue
            if pe.account == None or pe.account == "":
                if payment_type == "Pay":
                    account = f"Cheques in hand - {company_abbr}"
                else:
                    account = "Cheques Payable ({pe.bank}) - {company_abbr}"
            else:
                account = pe.account
            pe_doc = frappe.new_doc("Payment Entry")
            pe_doc.payment_type = payment_type
            if payment_type == "Pay":
                pe_doc.paid_from = account
            else:
                pe_doc.paid_to = account
                
            if pe.mode_of_payment == "Cheque":
                pe_doc.reference_no = pe.cheque_no
                pe_doc.reference_date = pe.cheque_clearance_date
                
            pe_doc.party_type = party_type
            pe_doc.party = party
            if reference_doc != None:
                pe_doc.append("references",{
                    'reference_doctype': self.reference_doctype,
                    'reference_name': self.reference_doc,
                    'allocated_amount': pe.amount
                })
            if pe.mode_of_payment == "Cheque" and pe.linked_cheque != None and pe.linked_cheque != "":
                pe_doc.linked_cheque = pe.linked_cheque
            pe_doc.paid_amount = pe.amount
            pe_doc.received_amount = pe.amount
            pe_doc.mode_of_payment = pe.mode_of_payment
            pe_doc.posting_date = pe.posting_date
            pe_doc.currency = pe.currency
            pe_doc.save()
            pe.payment_entry = pe_doc.name
            pe_doc.submit()


     