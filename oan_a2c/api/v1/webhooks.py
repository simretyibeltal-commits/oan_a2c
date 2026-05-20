import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def lead_inbound(phone_number, lead_source="Missed Call", external_ref_id=None, timestamp=None):
	"""
	Automated lead intake from external telco systems (IVR / missed call gateways).

	Authentication: standard Frappe token auth (Authorization: token <key>:<secret>).
	The JWT middleware in oan_a2c.api.middleware skips non-JWT endpoints automatically
	because this endpoint uses Frappe's native API key/secret scheme — no Bearer token needed.

	Idempotency contract (spec §4.4):
	  - If an Open or Contacted lead already exists for this phone number, we do NOT
	    create a duplicate. Instead we append the new event to call_notes and return 200.
	  - This makes the webhook safe for telco systems that may fire multiple retries.

	Scalability note: single frappe.db.get_value() lookup hitting the phone_number
	search index + status filter. No loops, no get_all inside loops. O(1) per call.
	"""
	frappe.has_permission("A2C Lead", "create", throw=True)

	if not phone_number:
		frappe.throw(_("phone_number is required"), frappe.MandatoryError)

	active_statuses = ("Open", "Contacted")

	existing_name = frappe.db.get_value(
		"A2C Lead",
		{"phone_number": phone_number, "status": ("in", active_statuses)},
		"name",
	)

	if existing_name:
		# Idempotent update — append new event info to call_notes, do not duplicate
		existing_doc = frappe.get_doc("A2C Lead", existing_name)

		event_note = _build_event_note(lead_source, external_ref_id, timestamp)
		if existing_doc.call_notes:
			existing_doc.call_notes = existing_doc.call_notes + "\n\n" + event_note
		else:
			existing_doc.call_notes = event_note

		existing_doc.save(ignore_permissions=False)

		return {
			"status": "success",
			"lead_id": existing_name,
			"message": "Existing active lead updated with new event.",
		}

	# No active lead exists — create a fresh one
	new_lead = frappe.new_doc("A2C Lead")
	new_lead.phone_number = phone_number
	new_lead.lead_source = lead_source
	new_lead.status = "Open"
	new_lead.call_notes = _build_event_note(lead_source, external_ref_id, timestamp)
	new_lead.insert(ignore_permissions=False)

	return {
		"status": "success",
		"lead_id": new_lead.name,
		"message": "Lead captured successfully.",
	}


def _build_event_note(lead_source, external_ref_id, timestamp):
	"""Formats a single inbound event into a human-readable audit line."""
	parts = [f"Source: {lead_source}"]
	if external_ref_id:
		parts.append(f"Ref ID: {external_ref_id}")
	if timestamp:
		parts.append(f"Timestamp: {timestamp}")
	return " | ".join(parts)
