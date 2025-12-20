"""
Helper script to create a test user for RAG evaluation
"""
import requests

BASE_URL = "http://127.0.0.1:8000"
SIGNUP_URL = f"{BASE_URL}/auth/signup"

# Test user credentials - change these if needed
TEST_USER = {
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "Test User",
    "farm_size": "medium",  # Must be: 'small', 'medium', or 'large'
    "primary_crops": ["wheat", "rice"]
}

def create_test_user():
    """Create a test user via the signup endpoint."""
    print("🌾 Creating test user for RAG evaluation...")
    print(f"   Email: {TEST_USER['email']}")
    
    try:
        response = requests.post(
            SIGNUP_URL,
            json=TEST_USER,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✓ Test user created successfully!")
            print(f"\n📝 Use these credentials in run_evaluation.py:")
            print(f"   TEST_EMAIL = \"{TEST_USER['email']}\"")
            print(f"   TEST_PASSWORD = \"{TEST_USER['password']}\"")
            return True
        elif response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "already registered" in error_detail:
                print("ℹ️  Test user already exists. You can use it for evaluation.")
                print(f"\n📝 Credentials:")
                print(f"   Email: {TEST_USER['email']}")
                print(f"   Password: {TEST_USER['password']}")
                return True
            else:
                print(f"✗ Error: {error_detail}")
                return False
        else:
            print(f"✗ Failed to create user: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        print("   Make sure the backend server is running on http://127.0.0.1:8000")
        return False

if __name__ == "__main__":
    create_test_user()
