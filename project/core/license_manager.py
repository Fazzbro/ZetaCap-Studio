import requests

class LicenseManager:
    PRODUCT_ID = "hi4y_jBWc8yT9l7qNujIOg=="
    API_URL = "https://api.gumroad.com/v2/licenses/verify"

    @classmethod
    def verify_license(cls, license_key: str) -> tuple[bool, str]:
        """
        Verifies the license key using Gumroad API.
        Returns a tuple: (is_valid: bool, message: str)
        """
        if not license_key or not license_key.strip():
            return False, "Please enter a valid license key."

        try:
            response = requests.post(cls.API_URL, data={
                "product_id": cls.PRODUCT_ID,
                "license_key": license_key.strip()
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    purchase = data.get("purchase", {})
                    # Ensure it has not been refunded
                    if purchase.get("refunded"):
                        return False, "This license key has been refunded and is no longer valid."
                    if purchase.get("chargebacked"):
                        return False, "This license key has been charged back and is no longer valid."
                    
                    return True, "Activation successful!"
            
            # API returns 404 for invalid keys
            return False, "Invalid license key. Please check and try again."

        except requests.exceptions.RequestException:
            return False, "Could not connect to the activation server. Please check your internet connection."
        except Exception as e:
            return False, f"An unexpected error occurred: {str(e)}"
