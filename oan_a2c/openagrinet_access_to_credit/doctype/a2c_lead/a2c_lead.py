import frappe
from frappe import _
from frappe.model.document import Document


class A2CLead(Document):
	def before_save(self):
		self._enforce_phone_uniqueness()

	def _enforce_phone_uniqueness(self):
		"""
		Enforce uniqueness of phone_number among active (non-terminal) leads only.

		A converted or closed lead must not block a new lead for the same farmer
		re-entering the funnel in a later season. Frappe's built-in 'unique'
		constraint is too coarse for this conditional requirement.
		"""
		if not self.phone_number:
			return

		active_statuses = ("Open", "Contacted")
		existing = frappe.db.get_value(
			"A2C Lead",
			{
				"phone_number": self.phone_number,
				"status": ("in", active_statuses),
				"name": ("!=", self.name or ""),
			},
			"name",
		)
		if existing:
			frappe.throw(
				_(
					"An active lead ({0}) already exists for phone number {1}. "
					"Duplicate leads are blocked to maintain clean funnel data."
				).format(existing, self.phone_number),
				frappe.DuplicateEntryError,
			)
