import frappe
import unittest
import jwt
import datetime
from frappe.utils import get_url
from oan_a2c.api.auth import login, forgot_password, reset_password
from oan_a2c.api.middleware import validate_jwt_request

class TestAuthAPI(unittest.TestCase):
    """
    Unit Tests for Identity and Access Management (IAM) endpoints.
    Ensures strict adherence to our NSPF and No-Hack mandates.
    """
    
    @classmethod
    def setUpClass(cls):
        # Create a test agent user
        cls.test_email = "test_agent@coopbank.com"
        cls.test_password = "SuperSecurePassword123!"
        
        if not frappe.db.exists("User", cls.test_email):
            user = frappe.new_doc("User")
            user.email = cls.test_email
            user.first_name = "Test Agent"
            user.insert(ignore_permissions=True)
            
            from frappe.core.doctype.user.user import update_password
            update_password(new_password=cls.test_password, user=cls.test_email)
            
        # Ensure we have a mock encryption key if tests are running in an isolated CI/CD env
        if not frappe.conf.get("encryption_key"):
            frappe.conf.encryption_key = "ci_cd_test_encryption_key_for_jwt"

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def setUp(self):
        # Reset local context before each test
        frappe.local.response = {}
        frappe.set_user("Administrator")
        
        # Patch get_request_header for testing middleware
        self.original_get_request_header = getattr(frappe, "get_request_header", None)
        frappe.get_request_header = self.mock_get_request_header
        
        self.mock_headers = {}

    def tearDown(self):
        if self.original_get_request_header:
            frappe.get_request_header = self.original_get_request_header

    def mock_get_request_header(self, key):
        return self.mock_headers.get(key)

    def test_1_login_success(self):
        # Act
        response = login(self.test_email, self.test_password)
        
        # Assert
        self.assertEqual(response.get("message").get("status"), "success")
        self.assertIn("token", response.get("message"))
        
        token = response["message"]["token"]
        payload = jwt.decode(token, frappe.conf.encryption_key, algorithms=["HS256"])
        
        self.assertEqual(payload["sub"], self.test_email)
        self.assertEqual(payload["iss"], "oan_a2c_identity_gateway")

    def test_2_login_failure(self):
        # Act
        response = login(self.test_email, "WrongPassword999")
        
        # Assert
        self.assertEqual(frappe.local.response.get("http_status_code"), 401)
        self.assertEqual(response.get("exception"), "frappe.exceptions.AuthenticationError")

    def test_3_middleware_valid_jwt(self):
        # Arrange
        payload = {
            "sub": self.test_email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, frappe.conf.encryption_key, algorithm="HS256")
        
        frappe.local.request = frappe._dict({
            "path": "/api/method/oan_a2c.api.v1.get_leads"
        })
        self.mock_headers["Authorization"] = f"Bearer {token}"
        
        # Act
        validate_jwt_request()
        
        # Assert
        # The middleware should successfully set the user context
        self.assertEqual(frappe.session.user, self.test_email)

    def test_4_middleware_missing_header(self):
        # Arrange
        frappe.local.request = frappe._dict({
            "path": "/api/method/oan_a2c.api.v1.get_leads"
        })
        self.mock_headers = {}
        
        # Act & Assert
        with self.assertRaises(frappe.AuthenticationError):
            validate_jwt_request()

    def test_5_middleware_expired_jwt(self):
        # Arrange
        payload = {
            "sub": self.test_email,
            "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=1) # Expired 1 hour ago
        }
        token = jwt.encode(payload, frappe.conf.encryption_key, algorithm="HS256")
        
        frappe.local.request = frappe._dict({
            "path": "/api/method/oan_a2c.api.v1.get_leads"
        })
        self.mock_headers["Authorization"] = f"Bearer {token}"
        
        # Act & Assert
        with self.assertRaises(frappe.AuthenticationError):
            validate_jwt_request()
            
    def test_6_forgot_password(self):
        response = forgot_password(self.test_email)
        self.assertEqual(response.get("message").get("status"), "success")
