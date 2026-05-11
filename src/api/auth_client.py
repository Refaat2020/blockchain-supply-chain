import requests
import json
from typing import Optional, Tuple
from user_identity import UserIdentity


class AuthenticationClient:
    
    def __init__(self, scm_url: str = "http://localhost:8000"):
        """
        Initialize authentication client.
        
        Args:
            scm_url: Base URL of Supply Chain Manager API
        """
        self.scm_url = scm_url.rstrip('/')
        self.session = requests.Session()
        self.current_token: Optional[str] = None
        self.current_user: Optional[str] = None
    
    # ==================== AUTHENTICATION FLOW ====================
    
    def authenticate(
        self,
        user_address: str,
        private_key: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        print(f"\n🔐 Authenticating {user_address[:20]}...")
        
        try:
            # Step 1: Request challenge
            print(f"   Step 1: Requesting challenge...")
            challenge_response = requests.post(
                f"{self.scm_url}/auth/challenge",
                json={"user_address": user_address},
                timeout=10
            )
            
            if challenge_response.status_code != 200:
                error_msg = f"Failed to get challenge: {challenge_response.text}"
                print(f"   ❌ {error_msg}")
                return False, None, error_msg
            
            challenge_data = challenge_response.json()
            challenge = challenge_data["challenge"]
            
            print(f"   ✅ Challenge received: {challenge[:20]}...")
            print(f"   Expires: {challenge_data['expires_at']}")
            
            # Step 2: Sign challenge
            print(f"   Step 2: Signing challenge...")
            
            user = UserIdentity(private_key)
            
            # Verify address matches
            if user.address.lower() != user_address.lower():
                error_msg = f"Address mismatch! Key belongs to {user.address}, not {user_address}"
                print(f"   ❌ {error_msg}")
                return False, None, error_msg
            
            # Sign the challenge
            challenge_dict = {"challenge": challenge}
            signature = user.sign_record(challenge_dict)
            
            print(f"   ✅ Challenge signed: {signature[:40]}...")
            
            # Step 3: Submit signature
            print(f"   Step 3: Submitting signature...")
            
            verify_response = requests.post(
                f"{self.scm_url}/auth/verify",
                json={
                    "user_address": user_address,
                    "challenge": challenge,
                    "signature": signature
                },
                timeout=10
            )
            
            if verify_response.status_code != 200:
                error_msg = f"Verification failed: {verify_response.text}"
                print(f"   ❌ {error_msg}")
                return False, None, error_msg
            
            verify_data = verify_response.json()
            
            # Step 4: Store token
            token = verify_data["token"]
            self.current_token = token
            self.current_user = user_address
            
            # Set Authorization header for future requests
            self.session.headers.update({
                "Authorization": f"Bearer {token}"
            })
            
            print(f"   ✅ Authentication successful!")
            print(f"   Token expires: {verify_data['expires_at']}")
            
            return True, token, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            print(f"   ❌ {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"   ❌ {error_msg}")
            return False, None, error_msg
    
    # ==================== CONVENIENCE METHODS ====================
    
    def authenticate_with_identity(self, user: UserIdentity) -> Tuple[bool, Optional[str], Optional[str]]:
        return self.authenticate(user.address, user.private_key)
    
    def is_authenticated(self) -> bool:
        return self.current_token is not None
    
    def get_token(self) -> Optional[str]:
        return self.current_token
    
    def get_user_address(self) -> Optional[str]:
        return self.current_user
    
    def logout(self):
        self.current_token = None
        self.current_user = None
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]
        print("✅ Logged out")
    
    # ==================== PROTECTED API CALLS ====================
    
    def call_protected_endpoint(
        self,
        endpoint: str,
        method: str = "GET",
        **kwargs
    ) -> requests.Response:
        if not self.is_authenticated():
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        url = f"{self.scm_url}{endpoint}"
        
        if method.upper() == "GET":
            return self.session.get(url, **kwargs)
        elif method.upper() == "POST":
            return self.session.post(url, **kwargs)
        elif method.upper() == "PUT":
            return self.session.put(url, **kwargs)
        elif method.upper() == "DELETE":
            return self.session.delete(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
    
    def get_profile(self) -> dict:
        """Get authenticated user profile"""
        response = self.call_protected_endpoint("/protected/profile")
        response.raise_for_status()
        return response.json()
    
    def get_auth_stats(self) -> dict:
        """Get authentication statistics"""
        response = self.call_protected_endpoint("/protected/stats")
        response.raise_for_status()
        return response.json()


# ==================== TESTING & DEMO ====================

def demo_authentication():
    print("\n" + "=" * 70)
    print("🧪 AUTHENTICATION CLIENT DEMO")
    print("=" * 70)
    
    # Step 1: Create user
    print("\nStep 1: Creating user identity...")
    user = UserIdentity()
    print(f"✅ User created: {user.address}")
    
    # Step 2: Initialize client
    print("\nStep 2: Initializing authentication client...")
    client = AuthenticationClient("http://localhost:8000")
    
    # Step 3: Authenticate
    print("\nStep 3: Performing authentication...")
    success, token, error = client.authenticate_with_identity(user)
    
    if not success:
        print(f"\n❌ Authentication failed: {error}")
        print("   Make sure the server is running:")
        print("   python auth_server.py")
        return
    
    print(f"\n✅ Authentication successful!")
    print(f"   Token: {token[:50]}...")
    
    # Step 4: Call protected endpoint
    print("\nStep 4: Calling protected endpoint...")
    
    try:
        profile = client.get_profile()
        print(f"✅ Profile retrieved:")
        print(f"   User: {profile['user_address']}")
        print(f"   Message: {profile['message']}")
        
        # Get statistics
        print("\nStep 5: Getting authentication statistics...")
        stats = client.get_auth_stats()
        print(f"✅ Statistics:")
        print(f"   Active challenges: {stats['active_challenges']}")
        print(f"   Used challenges: {stats['used_challenges']}")
        print(f"   Token TTL: {stats['token_ttl_hours']} hours")
        
    except Exception as e:
        print(f"❌ Error calling protected endpoint: {e}")
    
    # Step 6: Test with invalid token
    print("\nStep 6: Testing with invalid token...")
    client.logout()
    
    try:
        client.get_profile()
        print("❌ Should have been rejected!")
    except ValueError as e:
        print(f"✅ Correctly rejected: {e}")
    
    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETED!")
    print("=" * 70)


def demo_multiple_users():
    print("\n" + "=" * 70)
    print("👥 MULTIPLE USERS DEMO")
    print("=" * 70)
    
    users = []
    clients = []
    
    # Create 3 users
    for i in range(1, 4):
        print(f"\n👤 User {i}:")
        user = UserIdentity()
        print(f"   Address: {user.address[:20]}...")
        
        client = AuthenticationClient("http://localhost:8000")
        success, token, error = client.authenticate_with_identity(user)
        
        if success:
            print(f"   ✅ Authenticated")
            users.append(user)
            clients.append(client)
        else:
            print(f"   ❌ Failed: {error}")
    
    # All users call protected endpoint
    print("\n" + "=" * 70)
    print("All users calling protected endpoint:")
    print("=" * 70)
    
    for i, client in enumerate(clients, 1):
        try:
            profile = client.get_profile()
            print(f"\nUser {i}: {profile['user_address'][:20]}...")
            print(f"   Status: {profile['message']}")
        except Exception as e:
            print(f"User {i} error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ MULTI-USER DEMO COMPLETED!")
    print("=" * 70)


# ==================== STANDALONE FUNCTION ====================

def authenticate(
    user_address: str,
    private_key: str,
    scm_url: str = "http://localhost:8000"
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Standalone authentication function.
    
    Args:
        user_address: Ethereum address
        private_key: Private key for signing
        scm_url: Supply Chain Manager URL
    
    Returns:
        Tuple of (success, token, error_message)
    
    Example:
        >>> success, token, error = authenticate(
        ...     "0xABC...",
        ...     "0xPRIVATE_KEY",
        ...     "http://localhost:8000"
        ... )
    """
    client = AuthenticationClient(scm_url)
    return client.authenticate(user_address, private_key)


# ==================== MAIN ====================

if __name__ == "__main__":
    import sys
    import time
    
    print("\n⚠️  Make sure the authentication server is running!")
    print("   Run: python auth_server.py")
    print("\nWaiting 3 seconds...")
    time.sleep(3)
    
    try:
        # Test server connection
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"\n✅ Server is running")
        
        # Run demos
        demo_authentication()
        
        print("\n" + "=" * 70)
        time.sleep(2)
        
        demo_multiple_users()
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to server")
        print("   Please start the server first:")
        print("   python auth_server.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
