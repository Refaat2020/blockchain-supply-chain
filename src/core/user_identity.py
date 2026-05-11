import json
import hashlib
from typing import Dict, Any, Tuple
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3


class UserIdentity:

    def __init__(self, private_key: str = None):
        if private_key:
            # Load existing private key
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            self.account = Account.from_key(private_key)
        else:
            # Generate new key pair
            self.account = Account.create()

        self.private_key = self.account.key.hex()
        self.public_key = self.account._key_obj.public_key.to_hex()
        self.address = self.account.address

    def export_keys(self) -> Dict[str, str]:
        return {
            "private_key": self.private_key,
            "public_key": self.public_key,
            "address": self.address
        }

    def sign_record(self, record_dict: Dict[str, Any]) -> str:

        # Canonicalize the record to deterministic JSON
        canonical_json = self._canonicalize_record(record_dict)

        # Hash the canonical JSON
        record_hash = hashlib.sha256(canonical_json.encode('utf-8')).digest()

        # Create Ethereum-style message (adds prefix)
        message = encode_defunct(record_hash)

        # Sign the message
        signed_message = self.account.sign_message(message)

        return signed_message.signature.hex()

    @staticmethod
    def _canonicalize_record(record_dict: Dict[str, Any]) -> str:
        return json.dumps(record_dict, sort_keys=True, separators=(',', ':'))

    def __repr__(self):
        return f"UserIdentity(address={self.address})"


class SignatureVerifier:

    @staticmethod
    def verify_signature(
        record_dict: Dict[str, Any],
        signature: str,
        expected_address: str
    ) -> bool:
        try:
            # Ensure signature has '0x' prefix
            if not signature.startswith('0x'):
                signature = '0x' + signature

            # Canonicalize the record (same as signing process)
            canonical_json = UserIdentity._canonicalize_record(record_dict)

            # Hash the canonical JSON
            record_hash = hashlib.sha256(
                canonical_json.encode('utf-8')).digest()

            # Create the same Ethereum-style message
            message = encode_defunct(record_hash)

            # Recover the address from the signature
            recovered_address = Account.recover_message(
                message, signature=signature)

            # Compare addresses (case-insensitive)
            return recovered_address.lower() == expected_address.lower()

        except Exception as e:
            print(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def recover_signer_address(record_dict: Dict[str, Any], signature: str) -> str:
        # Ensure signature has '0x' prefix
        if not signature.startswith('0x'):
            signature = '0x' + signature

        # Canonicalize and hash
        canonical_json = UserIdentity._canonicalize_record(record_dict)
        record_hash = hashlib.sha256(canonical_json.encode('utf-8')).digest()
        message = encode_defunct(record_hash)

        # Recover address
        return Account.recover_message(message, signature=signature)


def generate_user_keypair() -> Tuple[str, str, str]:
    user = UserIdentity()
    return user.private_key, user.public_key, user.address


# ==================== DEMONSTRATION & TESTING ====================

def demo_key_generation():
    print("=" * 70)
    print("DEMO 1: Key Pair Generation")
    print("=" * 70)

    # Generate 3 users
    users = []
    for i in range(1, 4):
        user = UserIdentity()
        users.append(user)
        print(f"\n👤 User {i}:")
        print(f"  Address:     {user.address}")
        print(f"  Private Key: {user.private_key[:20]}... (truncated)")
        print(f"  Public Key:  {user.public_key[:40]}... (truncated)")

    return users


def demo_signing_and_verification(users):
    print("\n" + "=" * 70)
    print("DEMO 2: Signing and Verification")
    print("=" * 70)

    # Create a sample supply chain record
    record = {
        "batch_id": "BATCH-001",
        "product": "Organic Coffee Beans",
        "quantity": 1000,
        "origin": "Ethiopia",
        "timestamp": "2024-05-04T10:30:00Z",
        "temperature": 22.5
    }

    print(f"\n📦 Record to sign:")
    print(json.dumps(record, indent=2))

    # User 1 signs the record
    user1 = users[0]
    signature = user1.sign_record(record)

    print(f"\n✍️  User 1 signed the record:")
    print(f"  Signature: {signature[:40]}... (truncated)")

    # Verify with correct address
    verifier = SignatureVerifier()
    is_valid = verifier.verify_signature(record, signature, user1.address)

    print(f"\n✅ Verification with User 1's address: {is_valid}")

    # Try to verify with wrong address (User 2's address)
    is_valid_wrong = verifier.verify_signature(
        record, signature, users[1].address)
    print(f"❌ Verification with User 2's address: {is_valid_wrong}")

    # Recover the signer
    recovered_address = verifier.recover_signer_address(record, signature)
    print(f"\n🔍 Recovered signer address: {recovered_address}")
    print(
        f"   Matches User 1? {recovered_address.lower() == user1.address.lower()}")

    return signature


def demo_tamper_detection(users, original_signature):
    print("\n" + "=" * 70)
    print("DEMO 3: Tamper Detection")
    print("=" * 70)

    # Original record
    original_record = {
        "batch_id": "BATCH-001",
        "product": "Organic Coffee Beans",
        "quantity": 1000,
        "origin": "Ethiopia",
        "timestamp": "2024-05-04T10:30:00Z",
        "temperature": 22.5
    }

    # Tampered record (quantity changed)
    tampered_record = original_record.copy()
    tampered_record["quantity"] = 500  # Changed!

    print("\n📦 Original record signed by User 1")
    print(f"   Quantity: {original_record['quantity']}")

    print("\n🚨 Attacker tries to change quantity to 500")
    print(f"   Using the same signature from User 1...")

    verifier = SignatureVerifier()

    # Try to verify tampered record with original signature
    is_valid_tampered = verifier.verify_signature(
        tampered_record,
        original_signature,
        users[0].address
    )

    print(f"\n❌ Verification result: {is_valid_tampered}")
    print("   Tamper detected! Signature does not match modified data.")


def demo_canonical_serialization():
    print("\n" + "=" * 70)
    print("DEMO 4: Canonical Serialization (Order Independence)")
    print("=" * 70)

    # Same record, different key orders
    record1 = {"b": 2, "a": 1, "c": 3}
    record2 = {"a": 1, "c": 3, "b": 2}
    record3 = {"c": 3, "a": 1, "b": 2}

    user = UserIdentity()

    sig1 = user.sign_record(record1)
    sig2 = user.sign_record(record2)
    sig3 = user.sign_record(record3)

    print(f"\n📝 Record 1 key order: {list(record1.keys())}")
    print(f"   Signature: {sig1[:40]}...")

    print(f"\n📝 Record 2 key order: {list(record2.keys())}")
    print(f"   Signature: {sig2[:40]}...")

    print(f"\n📝 Record 3 key order: {list(record3.keys())}")
    print(f"   Signature: {sig3[:40]}...")

    print(f"\n✅ All signatures identical? {sig1 == sig2 == sig3}")
    print("   Canonical serialization ensures deterministic signing!")


def demo_load_existing_keys():
    """Demo: Load user from existing private key"""
    print("\n" + "=" * 70)
    print("DEMO 5: Load Existing Keys")
    print("=" * 70)

    # Generate a user
    original_user = UserIdentity()
    print(f"\n👤 Original User:")
    print(f"   Address: {original_user.address}")

    # Export keys
    keys = original_user.export_keys()

    # Simulate saving and loading (e.g., from database)
    print(f"\n💾 Keys exported and saved...")

    # Load the same user from private key
    loaded_user = UserIdentity(private_key=keys["private_key"])
    print(f"\n👤 Loaded User:")
    print(f"   Address: {loaded_user.address}")

    print(
        f"\n✅ Addresses match? {original_user.address == loaded_user.address}")

    # Both can produce the same signature
    record = {"test": "data"}
    sig1 = original_user.sign_record(record)
    sig2 = loaded_user.sign_record(record)

    print(f"✅ Signatures match? {sig1 == sig2}")


# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    print("\n🔐 SUPPLY CHAIN USER IDENTITY & CRYPTOGRAPHY SYSTEM")
    print("=" * 70)

    # Run all demos
    users = demo_key_generation()
    signature = demo_signing_and_verification(users)
    demo_tamper_detection(users, signature)
    demo_canonical_serialization()
    demo_load_existing_keys()

    print("\n" + "=" * 70)
    print("✅ All demonstrations completed successfully!")
    print("=" * 70)
