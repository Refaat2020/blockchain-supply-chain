import json
import hashlib
from datetime import datetime
from typing import Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from user_identity import UserIdentity


# ==================== ENUMS ====================

class RecordType(str, Enum):
    PRODUCED = "PRODUCED"
    TRANSFER = "TRANSFER"
    RECEIVED = "RECEIVED"
    DELIVERED = "DELIVERED"


# ==================== DATA MODELS ====================

class GoodsManifest(BaseModel):
    manifest_id: str = Field(
        ...,
        description="Unique identifier for this manifest",
        examples=["M001", "MNF-2024-001"]
    )
    good_type: str = Field(
        ...,
        description="Type/category of goods",
        examples=["Book", "Electronics", "Pharmaceutical"]
    )
    quantity: int = Field(
        ...,
        gt=0,
        description="Total quantity of goods in this manifest"
    )
    creator: str = Field(
        ...,
        description="Ethereum address of the manifest creator",
        pattern=r"^0x[a-fA-F0-9]{40}$"
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of manifest creation",
        examples=["2026-03-01T10:00:00Z"]
    )

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure timestamp is valid ISO 8601 format"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "manifest_id": "M001",
                "good_type": "Book",
                "quantity": 100,
                "creator": "0xABC1234567890123456789012345678901234567",
                "timestamp": "2026-03-01T10:00:00Z"
            }
        }
    )


class Record(BaseModel):
    record_id: str = Field(
        ...,
        description="Unique identifier for this record",
        examples=["R001", "REC-2024-001"]
    )
    record_type: RecordType = Field(
        ...,
        description="Type of operation"
    )
    manifest_id: str = Field(
        ...,
        description="Reference to the GoodsManifest this record operates on"
    )
    quantity: int = Field(
        ...,
        gt=0,
        description="Quantity involved in this operation"
    )
    user: str = Field(
        ...,
        description="Ethereum address of the user performing this operation",
        pattern=r"^0x[a-fA-F0-9]{40}$"
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of the operation",
        examples=["2026-03-02T08:30:00Z"]
    )

    # Optional fields for additional context
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional additional data (location, temperature, etc.)"
    )

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure timestamp is valid ISO 8601 format"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record_id": "R001",
                "record_type": "TRANSFER",
                "manifest_id": "M001",
                "quantity": 20,
                "user": "0xDEF4567890123456789012345678901234567890",
                "timestamp": "2026-03-02T08:30:00Z",
                "metadata": {
                    "from_location": "Warehouse A",
                    "to_location": "Distribution Center B"
                }
            }
        }
    )


class SignedRecord(BaseModel):
    record: Record = Field(
        ...,
        description="The original record data"
    )
    hash: str = Field(
        ...,
        description="SHA-256 hash of the canonical record JSON (hex with 0x prefix)",
        pattern=r"^0x[a-fA-F0-9]{64}$"
    )
    signature: str = Field(
        ...,
        description="ECDSA signature of the record hash (hex with 0x prefix)"
    )
    user_address: str = Field(
        ...,
        description="Ethereum address of the signer",
        pattern=r"^0x[a-fA-F0-9]{40}$"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record": {
                    "record_id": "R001",
                    "record_type": "TRANSFER",
                    "manifest_id": "M001",
                    "quantity": 20,
                    "user": "0xDEF4567890123456789012345678901234567890",
                    "timestamp": "2026-03-02T08:30:00Z"
                },
                "hash": "0x9ab23f1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "signature": "0x304502210098765...",
                "user_address": "0xDEF4567890123456789012345678901234567890"
            }
        }
    )


# ==================== UTILITY FUNCTIONS ====================

def compute_hash(data_dict: dict) -> str:
    canonical_json = json.dumps(
        data_dict, sort_keys=True, separators=(',', ':'))

    hash_bytes = hashlib.sha256(canonical_json.encode('utf-8')).digest()
    return '0x' + hash_bytes.hex()


def to_signed_record(record: Record, private_key: str) -> SignedRecord:
    user = UserIdentity(private_key=private_key)
    record_dict = record.model_dump(exclude_none=True)
    record_hash = compute_hash(record_dict)
    signature = user.sign_record(record_dict)
    return SignedRecord(
        record=record,
        hash=record_hash,
        signature=signature,
        user_address=user.address
    )


def verify_signed_record(signed_record: SignedRecord) -> bool:
    from user_identity import SignatureVerifier

    record_dict = signed_record.record.model_dump(exclude_none=True)
    computed_hash = compute_hash(record_dict)

    if computed_hash != signed_record.hash:
        print(
            f"❌ Hash mismatch! Computed: {computed_hash}, Stored: {signed_record.hash}")
        return False

    verifier = SignatureVerifier()
    is_valid_signature = verifier.verify_signature(
        record_dict,
        signed_record.signature,
        signed_record.user_address
    )

    if not is_valid_signature:
        print(f"❌ Invalid signature for address {signed_record.user_address}")
        return False

    return True


# ==================== DEMONSTRATION & TESTING ====================

def demo_manifest_creation():
    print("=" * 70)
    print("DEMO 1: GoodsManifest Creation")
    print("=" * 70)

    # Create a user to be the manifest creator
    creator = UserIdentity()

    manifest = GoodsManifest(
        manifest_id="M001",
        good_type="Organic Coffee Beans",
        quantity=1000,
        creator=creator.address,
        timestamp="2026-05-04T10:00:00Z"
    )

    print(f"\n📦 Created Manifest:")
    print(manifest.model_dump_json(indent=2))

    print(f"\n🔑 Manifest Hash: {compute_hash(manifest.model_dump())}")

    return manifest, creator


def demo_record_operations():
    print("\n" + "=" * 70)
    print("DEMO 2: Supply Chain Record Operations")
    print("=" * 70)

    user = UserIdentity()

    # PRODUCED record
    produced_record = Record(
        record_id="R001",
        record_type=RecordType.PRODUCED,
        manifest_id="M001",
        quantity=1000,
        user=user.address,
        timestamp="2026-05-04T10:00:00Z",
        metadata={"factory": "Factory A", "batch_number": "BA-001"}
    )

    print(f"\n✅ PRODUCED Record:")
    print(produced_record.model_dump_json(indent=2))

    # TRANSFER record
    transfer_record = Record(
        record_id="R002",
        record_type=RecordType.TRANSFER,
        manifest_id="M001",
        quantity=500,
        user=user.address,
        timestamp="2026-05-05T14:30:00Z",
        metadata={
            "from_location": "Factory A",
            "to_location": "Warehouse B",
            "carrier": "Transport Co."
        }
    )

    print(f"\n🚚 TRANSFER Record:")
    print(transfer_record.model_dump_json(indent=2))

    return produced_record, transfer_record, user


def demo_signing_and_verification():
    print("\n" + "=" * 70)
    print("DEMO 3: Record Signing & Verification")
    print("=" * 70)

    # Create user and record
    user = UserIdentity()

    record = Record(
        record_id="R003",
        record_type=RecordType.DELIVERED,
        manifest_id="M001",
        quantity=500,
        user=user.address,
        timestamp="2026-05-06T09:00:00Z"
    )

    print(f"\n📝 Original Record:")
    print(f"   Record ID: {record.record_id}")
    print(f"   Type: {record.record_type}")
    print(f"   User: {record.user}")

    # Sign the record
    signed_record = to_signed_record(record, user.private_key)

    print(f"\n✍️  Signed Record:")
    print(f"   Hash: {signed_record.hash[:20]}...")
    print(f"   Signature: {signed_record.signature[:40]}...")
    print(f"   Signer: {signed_record.user_address}")

    # Verify the signed record
    is_valid = verify_signed_record(signed_record)
    print(f"\n✅ Verification Result: {is_valid}")

    return signed_record, user


def demo_tamper_detection_on_signed_record(original_signed_record: SignedRecord):
    print("\n" + "=" * 70)
    print("DEMO 4: Tamper Detection on SignedRecord")
    print("=" * 70)

    print(f"\n📦 Original signed record:")
    print(f"   Quantity: {original_signed_record.record.quantity}")
    print(f"   Hash: {original_signed_record.hash[:20]}...")

    # Create tampered version
    tampered_record = original_signed_record.model_copy(deep=True)
    tampered_record.record.quantity = 100  # Changed from 500 to 100!

    print(f"\n🚨 Attacker modifies quantity to 100 but keeps original signature")

    # Try to verify tampered record
    is_valid = verify_signed_record(tampered_record)

    print(f"\n❌ Verification Result: {is_valid}")
    if not is_valid:
        print("   Tamper detected! Hash no longer matches the record.")


def demo_hash_determinism():
    print("\n" + "=" * 70)
    print("DEMO 5: Hash Determinism (Canonical JSON)")
    print("=" * 70)

    # Same data, different orders
    data1 = {"manifest_id": "M001", "quantity": 100, "good_type": "Book"}
    data2 = {"good_type": "Book", "manifest_id": "M001", "quantity": 100}
    data3 = {"quantity": 100, "good_type": "Book", "manifest_id": "M001"}

    hash1 = compute_hash(data1)
    hash2 = compute_hash(data2)
    hash3 = compute_hash(data3)

    print(f"\n📝 Data 1 key order: {list(data1.keys())}")
    print(f"   Hash: {hash1}")

    print(f"\n📝 Data 2 key order: {list(data2.keys())}")
    print(f"   Hash: {hash2}")

    print(f"\n📝 Data 3 key order: {list(data3.keys())}")
    print(f"   Hash: {hash3}")

    print(f"\n✅ All hashes identical? {hash1 == hash2 == hash3}")


def demo_full_workflow():
    print("\n" + "=" * 70)
    print("DEMO 6: Complete Supply Chain Workflow")
    print("=" * 70)

    # Step 1: Create manufacturer
    manufacturer = UserIdentity()
    print(f"\n👤 Manufacturer: {manufacturer.address[:20]}...")

    # Step 2: Create manifest
    manifest = GoodsManifest(
        manifest_id="M-COFFEE-001",
        good_type="Organic Coffee Beans",
        quantity=1000,
        creator=manufacturer.address,
        timestamp="2026-05-04T08:00:00Z"
    )
    print(f"\n📦 Manifest Created: {manifest.manifest_id}")
    print(f"   Type: {manifest.good_type}")
    print(f"   Quantity: {manifest.quantity}")

    # Step 3: Manufacturer produces goods
    produced = Record(
        record_id="R-PROD-001",
        record_type=RecordType.PRODUCED,
        manifest_id=manifest.manifest_id,
        quantity=1000,
        user=manufacturer.address,
        timestamp="2026-05-04T08:30:00Z"
    )
    signed_produced = to_signed_record(produced, manufacturer.private_key)
    print(f"\n✅ PRODUCED - Signed by manufacturer")
    print(f"   Hash: {signed_produced.hash[:20]}...")

    # Step 4: Distributor receives goods
    distributor = UserIdentity()
    print(f"\n👤 Distributor: {distributor.address[:20]}...")

    transfer = Record(
        record_id="R-TRANS-001",
        record_type=RecordType.TRANSFER,
        manifest_id=manifest.manifest_id,
        quantity=1000,
        user=distributor.address,
        timestamp="2026-05-05T10:00:00Z",
        metadata={"from": "Factory", "to": "Warehouse"}
    )
    signed_transfer = to_signed_record(transfer, distributor.private_key)
    print(f"\n🚚 TRANSFER - Signed by distributor")
    print(f"   Hash: {signed_transfer.hash[:20]}...")

    # Step 5: Retailer receives
    retailer = UserIdentity()
    print(f"\n👤 Retailer: {retailer.address[:20]}...")

    received = Record(
        record_id="R-REC-001",
        record_type=RecordType.RECEIVED,
        manifest_id=manifest.manifest_id,
        quantity=500,
        user=retailer.address,
        timestamp="2026-05-06T14:00:00Z"
    )
    signed_received = to_signed_record(received, retailer.private_key)
    print(f"\n📥 RECEIVED - Signed by retailer")
    print(f"   Hash: {signed_received.hash[:20]}...")

    # Verify all records
    print(f"\n🔍 Verifying all signed records...")
    all_valid = (
        verify_signed_record(signed_produced) and
        verify_signed_record(signed_transfer) and
        verify_signed_record(signed_received)
    )
    print(f"✅ All records valid: {all_valid}")

    return [signed_produced, signed_transfer, signed_received]


# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    print("\n📄 SUPPLY CHAIN DATA STRUCTURES & CRYPTOGRAPHIC RECORDS")
    print("=" * 70)

    # Run all demos
    demo_manifest_creation()
    demo_record_operations()
    signed_rec, user = demo_signing_and_verification()
    demo_tamper_detection_on_signed_record(signed_rec)
    demo_hash_determinism()
    signed_records = demo_full_workflow()

    print("\n" + "=" * 70)
    print("✅ All demonstrations completed successfully!")
    print(f"📊 Total signed records created: {len(signed_records)}")
    print("=" * 70)
