import frappe

def run():
    try:
        frappe.rename_doc('DocType', 'Consent Data Field', 'A2C Consent Data', force=True)
        frappe.db.commit()
        print("Renamed successfully!")
    except Exception as e:
        print(f"Error: {e}")
