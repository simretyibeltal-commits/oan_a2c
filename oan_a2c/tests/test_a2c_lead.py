import frappe
import unittest
from oan_a2c.api.v1.webhooks import lead_inbound


class TestA2CLead(unittest.TestCase):
	"""
	Tests for the A2C Lead DocType controller and the lead_inbound webhook.
	"""

	TEST_PHONE = "+251911000001"
	TEST_PHONE_2 = "+251911000002"

	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"A2C Lead",
			filters={"phone_number": ("in", [cls.TEST_PHONE, cls.TEST_PHONE_2])},
			pluck="name",
		):
			frappe.delete_doc("A2C Lead", name, ignore_permissions=True, force=True)
		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all(
			"A2C Lead",
			filters={"phone_number": ("in", [self.TEST_PHONE, self.TEST_PHONE_2])},
			pluck="name",
		):
			frappe.delete_doc("A2C Lead", name, ignore_permissions=True, force=True)
		frappe.db.commit()

	# ------------------------------------------------------------------
	# DocType controller tests
	# ------------------------------------------------------------------

	def test_1_create_lead_success(self):
		"""A valid lead should be created with an auto-generated LEAD-YYYY-##### name."""
		lead = frappe.new_doc("A2C Lead")
		lead.phone_number = self.TEST_PHONE
		lead.lead_source = "Missed Call"
		lead.status = "Open"
		lead.insert()

		self.assertTrue(lead.name.startswith("LEAD-"))
		self.assertEqual(lead.status, "Open")

	def test_2_duplicate_active_lead_blocked(self):
		"""Two active leads for the same phone number must be rejected."""
		lead = frappe.new_doc("A2C Lead")
		lead.phone_number = self.TEST_PHONE
		lead.lead_source = "Missed Call"
		lead.status = "Open"
		lead.insert()

		duplicate = frappe.new_doc("A2C Lead")
		duplicate.phone_number = self.TEST_PHONE
		duplicate.lead_source = "IVR"
		duplicate.status = "Open"

		with self.assertRaises(frappe.DuplicateEntryError):
			duplicate.insert()

	def test_3_converted_lead_allows_new_lead_same_phone(self):
		"""A new lead for the same phone is allowed when the prior lead is Converted."""
		lead = frappe.new_doc("A2C Lead")
		lead.phone_number = self.TEST_PHONE
		lead.lead_source = "Missed Call"
		lead.status = "Converted"
		lead.insert()

		new_lead = frappe.new_doc("A2C Lead")
		new_lead.phone_number = self.TEST_PHONE
		new_lead.lead_source = "Agent Entry"
		new_lead.status = "Open"
		new_lead.insert()

		self.assertTrue(new_lead.name.startswith("LEAD-"))

	# ------------------------------------------------------------------
	# Webhook tests
	# ------------------------------------------------------------------

	def test_4_webhook_creates_new_lead(self):
		"""A first-time inbound call should create a new Open lead."""
		response = lead_inbound(
			phone_number=self.TEST_PHONE,
			lead_source="Missed Call",
			external_ref_id="TELCO-001",
			timestamp="2026-05-19T10:00:00Z",
		)

		self.assertEqual(response["status"], "success")
		self.assertTrue(response["lead_id"].startswith("LEAD-"))

		lead = frappe.get_doc("A2C Lead", response["lead_id"])
		self.assertEqual(lead.phone_number, self.TEST_PHONE)
		self.assertEqual(lead.status, "Open")
		self.assertIn("TELCO-001", lead.call_notes)

	def test_5_webhook_idempotent_on_duplicate_call(self):
		"""A second call for the same active phone must update, not duplicate."""
		r1 = lead_inbound(
			phone_number=self.TEST_PHONE,
			lead_source="Missed Call",
			external_ref_id="TELCO-001",
			timestamp="2026-05-19T10:00:00Z",
		)
		lead_id = r1["lead_id"]

		r2 = lead_inbound(
			phone_number=self.TEST_PHONE,
			lead_source="IVR",
			external_ref_id="TELCO-002",
			timestamp="2026-05-19T10:05:00Z",
		)

		self.assertEqual(r2["lead_id"], lead_id)
		self.assertIn("Existing active lead updated", r2["message"])

		notes = frappe.db.get_value("A2C Lead", lead_id, "call_notes")
		self.assertIn("TELCO-001", notes)
		self.assertIn("TELCO-002", notes)

		count = frappe.db.count("A2C Lead", {"phone_number": self.TEST_PHONE})
		self.assertEqual(count, 1)

	def test_6_webhook_missing_phone_raises(self):
		"""Webhook must reject requests with no phone_number."""
		with self.assertRaises(Exception):
			lead_inbound(phone_number="")
