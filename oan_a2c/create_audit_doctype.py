import frappe

def run():
    if not frappe.db.exists("DocType", "A2C Lead Audit Event"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "A2C Lead Audit Event",
            "module": "OpenAgriNet Access to Credit",
            "custom": 0,
            "istable": 0,
            "naming_rule": "Expression",
            "autoname": "format:AUDIT-{YYYY}-{#####}",
            "fields": [
                {
                    "fieldname": "lead",
                    "fieldtype": "Link",
                    "options": "A2C Lead",
                    "label": "Lead",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "event_type",
                    "fieldtype": "Select",
                    "label": "Event Type",
                    "options": "Created\nContacted\nAssigned\nStatus Changed\nVisit Scheduled\nCredit Info Added\nCommented",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "event_title",
                    "fieldtype": "Data",
                    "label": "Event Title",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "event_description",
                    "fieldtype": "Text",
                    "label": "Event Description"
                }
            ],
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1
                },
                {
                    "role": "Development Agent",
                    "read": 1,
                    "write": 0,
                    "create": 0,
                    "delete": 0
                },
                {
                    "role": "Bank Agent",
                    "read": 1,
                    "write": 0,
                    "create": 0,
                    "delete": 0
                }
            ],
            "sort_field": "creation",
            "sort_order": "DESC"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("A2C Lead Audit Event DocType created successfully!")
    else:
        print("DocType already exists.")
