import requests

class LicenseResult(tuple):
    def __new__(cls, is_valid: bool, message: str, is_network_error: bool = False):
        return super().__new__(cls, (is_valid, message))
        
    def __init__(self, is_valid: bool, message: str, is_network_error: bool = False):
        self.is_valid = is_valid
        self.message = message
        self.is_network_error = is_network_error

class LicenseManager:
    PRODUCT_ID = "hi4y_jBWc8yT9l7qNujIOg=="
    API_URL = "https://api.gumroad.com/v2/licenses/verify"
    DECREMENT_URL = "https://api.gumroad.com/v2/licenses/decrement_uses_count"

    @classmethod
    def verify_license(cls, license_key: str, increment_uses_count: bool = True) -> LicenseResult:
        """
        Verifies the license key using Gumroad API.
        If increment_uses_count is True, checks if uses <= 2.
        Returns a LicenseResult tuple: (is_valid: bool, message: str) with .is_network_error flag.
        """
        if not license_key or not license_key.strip():
            return LicenseResult(False, "Please enter a valid license key.", False)

        try:
            response = requests.post(cls.API_URL, data={
                "product_id": cls.PRODUCT_ID,
                "license_key": license_key.strip(),
                "increment_uses_count": "true" if increment_uses_count else "false"
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    purchase = data.get("purchase", {})
                    # Ensure it has not been refunded
                    if purchase.get("refunded"):
                        return LicenseResult(False, "This license key has been refunded and is no longer valid.", False)
                    if purchase.get("chargebacked"):
                        return LicenseResult(False, "This license key has been charged back and is no longer valid.", False)
                    
                    if increment_uses_count:
                        uses = data.get("uses", 0)
                        if uses > 2:
                            # Revert the increment immediately if they exceed 2 devices
                            cls.decrement_license(license_key)
                            return LicenseResult(False, "Activation limit reached. A single license can only be used on up to 2 devices. Please deactivate an old device first.", False)

                    return LicenseResult(True, "Activation successful!", False)
            
            # API returns 404 for invalid keys
            return LicenseResult(False, "Invalid license key. Please check and try again.", False)

        except requests.exceptions.RequestException:
            return LicenseResult(False, "Could not connect to the activation server. Please check your internet connection.", True)
        except Exception as e:
            return LicenseResult(False, f"An unexpected error occurred: {str(e)}", False)

    @classmethod
    def decrement_license(cls, license_key: str) -> bool:
        """
        Decrements the uses count on Gumroad to free up a device seat.
        """
        if not license_key or not license_key.strip():
            return False
            
        try:
            response = requests.put(cls.DECREMENT_URL, data={
                "product_id": cls.PRODUCT_ID,
                "license_key": license_key.strip()
            }, timeout=10)
            if response.status_code == 200:
                return response.json().get("success", False)
        except Exception:
            pass
        return False
