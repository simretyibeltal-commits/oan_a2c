import frappe
from frappe import _
import jwt
import datetime
from frappe.auth import LoginManager
from frappe.core.doctype.user.user import reset_password as reset_password_core
from frappe.core.doctype.user.user import update_password

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    """
    Authenticates a user and returns a stateless JWT.
    Wraps Frappe's core LoginManager to ensure standard validations.
    """
    try:
        login_manager = LoginManager()
        login_manager.authenticate(usr, pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["http_status_code"] = 401
        return {
            "exception": "frappe.exceptions.AuthenticationError",
            "message": _("Incorrect email or password.")
        }

    # Gather user context
    user = frappe.get_doc("User", usr)
    roles = [d.role for d in user.roles]

    secret = frappe.conf.get("encryption_key")
    if not secret:
        frappe.throw(_("System configuration error: missing encryption_key"))

    # Generate Short-Lived JWT Payload (1 hour)
    payload = {
        "sub": usr,
        "iss": "oan_a2c_identity_gateway",
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "roles": roles
    }
    
    token = jwt.encode(payload, secret, algorithm="HS256")

    # Logout the standard Frappe session we just accidentally created by calling post_login.
    # We want a purely stateless session.
    frappe.local.login_manager.logout()

    return {
        "message": {
            "status": "success",
            "token": token,
            "user": {
                "email": usr,
                "full_name": user.full_name,
                "roles": roles
            }
        }
    }

@frappe.whitelist(allow_guest=True)
def forgot_password(email):
    """
    Triggers Frappe's native secure password recovery flow via email.
    """
    try:
        reset_password_core(email)
    except Exception:
        # Standard security practice: do not leak if email exists or not
        pass
        
    return {
        "message": {
            "status": "success",
            "message": _("Password reset instructions have been sent to your registered email.")
        }
    }

@frappe.whitelist(allow_guest=True)
def reset_password(email, key, new_password):
    """
    Decoupled bridge for setting a new password using the email key.
    """
    # Fetch user using the specific reset key (which expires automatically per core logic)
    user = frappe.db.get_value("User", {"email": email, "reset_password_key": key}, "name")
    
    if not user:
        frappe.local.response["http_status_code"] = 401
        return {
            "exception": "frappe.exceptions.AuthenticationError",
            "message": _("Invalid or expired reset token.")
        }
        
    try:
        # update_password inherently validates password strength and nullifies the key
        update_password(new_password=new_password, logout_all_sessions=True, key=key)
        return {
            "message": {
                "status": "success",
                "message": _("Your password has been successfully updated. You may now login.")
            }
        }
    except Exception as e:
        frappe.local.response["http_status_code"] = 400
        return {
            "exception": "ValidationError",
            "message": str(e)
        }
