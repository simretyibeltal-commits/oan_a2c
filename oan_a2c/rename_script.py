import frappe

def run():
    frappe.rename_doc('DocType', 'Consent Request', 'A2C Consent Request', force=True)
    frappe.rename_doc('DocType', 'Consent Data Field', 'A2C Consent Data', force=True)
    frappe.db.commit()
    print("Renamed successfully!")
