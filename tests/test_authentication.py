from datetime import datetime, timedelta
from user_identity import UserIdentity
from auth_server import AuthenticationManager


def test_authentication_flow():
    """Test complete authentication flow"""
    print("\n" + "=" * 70)
    print("🧪 AUTHENTICATION FLOW TEST")
    print("=" * 70)

    # Initialize manager
    auth_manager = AuthenticationManager()

    # Create users
    print("\n" + "=" * 70)
    print("STEP 1: Create Users")
    print("=" * 70)

    user1 = UserIdentity()
    user2 = UserIdentity()

    print(f"👤 User 1: {user1.address[:20]}...")
    print(f"👤 User 2: {user2.address[:20]}...")

    # Test 1: Generate challenge
    print("\n" + "=" * 70)
    print("TEST 1: Generate Challenge")
    print("=" * 70)

    challenge_resp = auth_manager.generate_challenge(user1.address)
    print(f"✅ Challenge generated:")
    print(f"   Challenge: {challenge_resp.challenge[:40]}...")
    print(f"   Expires: {challenge_resp.expires_at}")

    # Test 2: Sign challenge
    print("\n" + "=" * 70)
    print("TEST 2: Sign Challenge")
    print("=" * 70)

    challenge_dict = {"challenge": challenge_resp.challenge}
    signature = user1.sign_record(challenge_dict)

    print(f"✅ Challenge signed:")
    print(f"   Signature: {signature[:40]}...")

    # Test 3: Verify challenge and get token
    print("\n" + "=" * 70)
    print("TEST 3: Verify Signature & Get Token")
    print("=" * 70)

    success, token = auth_manager.verify_challenge(
        user1.address,
        challenge_resp.challenge,
        signature
    )

    if success:
        print(f"✅ Authentication successful!")
        print(f"   Token: {token[:50]}...")
    else:
        print(f"❌ Authentication failed!")
        return False

    # Test 4: Verify token
    print("\n" + "=" * 70)
    print("TEST 4: Verify JWT Token")
    print("=" * 70)

    verified_address = auth_manager.verify_token(token)

    if verified_address == user1.address:
        print(f"✅ Token verified successfully!")
        print(f"   Address: {verified_address}")
    else:
        print(f"❌ Token verification failed!")
        return False

    # Test 5: Replay attack prevention
    print("\n" + "=" * 70)
    print("TEST 5: Replay Attack Prevention")
    print("=" * 70)

    print("🚨 Attempting to reuse same challenge...")

    success_replay, token_replay = auth_manager.verify_challenge(
        user1.address,
        challenge_resp.challenge,  # Same challenge
        signature  # Same signature
    )

    if not success_replay:
        print(f"✅ Replay attack correctly prevented!")
    else:
        print(f"❌ SECURITY ISSUE: Replay attack succeeded!")
        return False

    # Test 6: Wrong signature
    print("\n" + "=" * 70)
    print("TEST 6: Wrong Signature Detection")
    print("=" * 70)

    # Generate new challenge for user2
    challenge_resp2 = auth_manager.generate_challenge(user2.address)

    # User 2 signs their challenge
    signature2 = user2.sign_record({"challenge": challenge_resp2.challenge})

    # Try to use User2's signature for User1's address
    print("🚨 Attempting to use User 2's signature for User 1...")
    success_wrong, token_wrong = auth_manager.verify_challenge(
        user1.address,  # User 1's address
        challenge_resp2.challenge,
        signature2  # User 2's signature
    )

    if not success_wrong:
        print(f"✅ Wrong signature correctly rejected!")
    else:
        print(f"❌ SECURITY ISSUE: Wrong signature accepted!")
        return False

    # Test 7: Expired challenge
    print("\n" + "=" * 70)
    print("TEST 7: Expired Challenge Detection")
    print("=" * 70)

    # Create short-lived challenge
    short_auth = AuthenticationManager(challenge_ttl=1)  # 1 second
    challenge_resp3 = short_auth.generate_challenge(user1.address)

    print("⏰ Waiting for challenge to expire...")
    import time
    time.sleep(2)

    signature3 = user1.sign_record({"challenge": challenge_resp3.challenge})

    success_expired, token_expired = short_auth.verify_challenge(
        user1.address,
        challenge_resp3.challenge,
        signature3
    )

    if not success_expired:
        print(f"✅ Expired challenge correctly rejected!")
    else:
        print(f"❌ SECURITY ISSUE: Expired challenge accepted!")
        return False

    # Test 8: Multiple users
    print("\n" + "=" * 70)
    print("TEST 8: Multiple Users Authentication")
    print("=" * 70)

    users = [UserIdentity() for _ in range(3)]
    tokens = []

    for i, user in enumerate(users, 1):
        print(f"\n👤 User {i}: {user.address[:20]}...")

        # Get challenge
        challenge = auth_manager.generate_challenge(user.address)

        # Sign
        sig = user.sign_record({"challenge": challenge.challenge})

        # Verify
        success, token = auth_manager.verify_challenge(
            user.address,
            challenge.challenge,
            sig
        )

        if success:
            tokens.append(token)
            print(f"   ✅ Authenticated")
        else:
            print(f"   ❌ Failed")
            return False

    # Verify all tokens
    print(f"\n🔍 Verifying all {len(tokens)} tokens...")
    for i, (user, token) in enumerate(zip(users, tokens), 1):
        verified = auth_manager.verify_token(token)
        if verified == user.address:
            print(f"   User {i}: ✅ Valid")
        else:
            print(f"   User {i}: ❌ Invalid")
            return False

    # Test 9: Statistics
    print("\n" + "=" * 70)
    print("TEST 9: Authentication Statistics")
    print("=" * 70)

    stats = auth_manager.get_statistics()
    print(f"📊 Statistics:")
    print(f"   Active challenges: {stats['active_challenges']}")
    print(f"   Used challenges: {stats['used_challenges']}")
    print(f"   JWT algorithm: {stats['jwt_algorithm']}")
    print(f"   Challenge TTL: {stats['challenge_ttl_seconds']}s")
    print(f"   Token TTL: {stats['token_ttl_hours']}h")

    # Final result
    print("\n" + "=" * 70)
    print("✅ ALL AUTHENTICATION TESTS PASSED!")
    print("=" * 70)

    print("\n📋 Security Features Verified:")
    print("   ✅ Challenge-response protocol")
    print("   ✅ ECDSA signature verification")
    print("   ✅ JWT token generation")
    print("   ✅ Token validation")
    print("   ✅ Replay attack prevention")
    print("   ✅ Signature forgery prevention")
    print("   ✅ Challenge expiration")
    print("   ✅ Multi-user support")

    return True


if __name__ == "__main__":
    try:
        test_authentication_flow()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
