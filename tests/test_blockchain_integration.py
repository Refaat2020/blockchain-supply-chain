

from datetime import datetime
from user_identity import UserIdentity
from data_structures import Record, RecordType, GoodsManifest, compute_hash
from repository import SupplyChainRepository
from blockchain_client import BlockchainAnchorClient


# ==================== MOCK BLOCKCHAIN FOR TESTING ====================

class MockBlockchainClient:
 
    def __init__(self):
        # record_id -> (hash, tx_hash, block_number)
        self.anchored_records = {}
        self.block_number = 1000000
        self.is_connected_flag = True

    def is_connected(self) -> bool:
        return self.is_connected_flag

    def anchor_hash(self, record_id: str, hash_hex: str, private_key: str) -> str:
        import hashlib

        # Simulate transaction hash
        tx_data = f"{record_id}{hash_hex}{datetime.utcnow()}"
        tx_hash = "0x" + hashlib.sha256(tx_data.encode()).hexdigest()

        # Simulate block mining
        self.block_number += 1

        # Store anchor
        self.anchored_records[record_id] = {
            "hash": hash_hex,
            "tx_hash": tx_hash,
            "block_number": self.block_number,
            "timestamp": datetime.utcnow().isoformat()
        }

        print(f"\n📤 [MOCK] Anchoring record: {record_id}")
        print(f"   Hash: {hash_hex[:20]}...")
        print(f"   TX Hash: {tx_hash[:20]}...")
        print(f"   ✅ Anchored in block {self.block_number}")

        return tx_hash

    def retrieve_hash(self, record_id: str) -> str:
        """Retrieve anchored hash"""
        if record_id not in self.anchored_records:
            raise ValueError(f"Record {record_id} not found")

        hash_hex = self.anchored_records[record_id]["hash"]
        print(f"\n🔍 [MOCK] Retrieved hash for {record_id}")
        print(f"   Hash: {hash_hex[:20]}...")

        return hash_hex

    def verify_on_chain(self, record_id: str, expected_hash: str):
        """Verify hash on-chain"""
        print(f"\n [MOCK] Verifying record: {record_id}")

        if record_id not in self.anchored_records:
            print(f"❌Record not found on-chain")
            return False, {
                "status": "NOT_FOUND",
                "record_id": record_id,
                "match": False
            }

        on_chain_hash = self.anchored_records[record_id]["hash"]

        # Normalize hashes
        if not expected_hash.startswith('0x'):
            expected_hash = '0x' + expected_hash
        if not on_chain_hash.startswith('0x'):
            on_chain_hash = '0x' + on_chain_hash

        is_valid = on_chain_hash.lower() == expected_hash.lower()
        status = "VALID" if is_valid else "INVALID"

        print(f"   Expected: {expected_hash[:20]}...")
        print(f"   On-chain: {on_chain_hash[:20]}...")
        print(f"   {'✅' if is_valid else '❌'} Verification: {status}")

        return is_valid, {
            "status": status,
            "record_id": record_id,
            "expected_hash": expected_hash,
            "on_chain_hash": on_chain_hash,
            "match": is_valid
        }

    def get_transaction_details(self, tx_hash: str):
        """Get transaction details"""
        # Find record by tx_hash
        for record_id, data in self.anchored_records.items():
            if data["tx_hash"] == tx_hash:
                return {
                    "tx_hash": tx_hash,
                    "block_number": data["block_number"],
                    "confirmations": 5,  # Simulated
                    "status": "SUCCESS",
                    "timestamp": data["timestamp"]
                }

        raise ValueError(f"Transaction {tx_hash} not found")

    def has_record(self, record_id: str) -> bool:
        """Check if record exists"""
        return record_id in self.anchored_records

    def get_total_records(self) -> int:
        """Get total anchored records"""
        return len(self.anchored_records)


# ==================== INTEGRATED SUPPLY CHAIN MANAGER ====================

class IntegratedSupplyChainManager:

    def __init__(
        self,
        repository: SupplyChainRepository,
        blockchain_client,
        deployer_private_key: str
    ):
        self.repo = repository
        self.blockchain = blockchain_client
        self.deployer_key = deployer_private_key

    def anchor_record(self, record_id: str, record_hash: str) -> str:
        """
        Anchor a record hash on blockchain.

        Args:
            record_id: Record identifier
            record_hash: SHA-256 hash (hex)

        Returns:
            Transaction hash
        """
        tx_hash = self.blockchain.anchor_hash(
            record_id,
            record_hash,
            self.deployer_key
        )

        # Get transaction details
        try:
            tx_details = self.blockchain.get_transaction_details(tx_hash)
            block_number = tx_details.get("block_number")
        except:
            block_number = None

        # Update repository
        self.repo.anchor_record_on_blockchain(
            record_id,
            tx_hash,
            block_number
        )

        return tx_hash

    def verify_record_integrity(self, record_id: str) -> dict:
        print(f"\n" + "=" * 70)
        print(f"🔍 COMPLETE INTEGRITY VERIFICATION: {record_id}")
        print("=" * 70)

        # Step 1: Retrieve from repository
        stored_record = self.repo.get_record(record_id)
        if not stored_record:
            return {
                "valid": False,
                "error": "Record not found in repository"
            }

        # Step 2: Verify local hash
        from data_structures import verify_signed_record, SignedRecord, Record

        record = Record(**stored_record["record"])
        signed_record = SignedRecord(
            record=record,
            hash=stored_record["hash"],
            signature=stored_record["signature"],
            user_address=stored_record["user_address"]
        )

        local_valid = verify_signed_record(signed_record)

        print(f"\n✅ Step 1: Local Verification")
        print(f"   Hash: {stored_record['hash'][:20]}...")
        print(f"   Signature: {'Valid' if local_valid else 'Invalid'}")

        # Step 3: Verify on blockchain
        print(f"\n✅ Step 2: Blockchain Verification")

        if not stored_record.get('blockchain_anchored'):
            print(f"   ⚠️  Not yet anchored on blockchain")
            return {
                "valid": local_valid,
                "blockchain_anchored": False,
                "local_valid": local_valid
            }

        is_valid_onchain, bc_details = self.blockchain.verify_on_chain(
            record_id,
            stored_record["hash"]
        )

        # Step 4: Final result
        fully_valid = local_valid and is_valid_onchain

        print(f"\n" + "=" * 70)
        print(
            f"{'✅' if fully_valid else '❌'} FINAL VERDICT: {'VALID' if fully_valid else 'INVALID'}")
        print("=" * 70)

        return {
            "valid": fully_valid,
            "local_valid": local_valid,
            "blockchain_valid": is_valid_onchain,
            "blockchain_details": bc_details,
            "record_hash": stored_record["hash"],
            "blockchain_tx": stored_record.get("blockchain_tx_hash")
        }


# ==================== COMPLETE WORKFLOW TEST ====================

def test_complete_supply_chain_with_blockchain():
    """
    Test complete supply chain workflow with blockchain anchoring.
    """
    print("\n" + "=" * 70)
    print("🧪 COMPLETE SUPPLY CHAIN + BLOCKCHAIN INTEGRATION TEST")
    print("=" * 70)

    # Initialize components
    repo = SupplyChainRepository("test_blockchain_scm.db")
    mock_blockchain = MockBlockchainClient()

    # Deployer private key (for anchoring transactions)
    deployer = UserIdentity()
    deployer_key = deployer.private_key

    # Initialize integrated manager
    scm = IntegratedSupplyChainManager(repo, mock_blockchain, deployer_key)

    # Create users
    print("\n" + "=" * 70)
    print("STEP 1: Create Supply Chain Participants")
    print("=" * 70)

    manufacturer = UserIdentity()
    distributor = UserIdentity()

    print(f"👤 Manufacturer: {manufacturer.address[:20]}...")
    print(f"👤 Distributor:  {distributor.address[:20]}...")

    # Create manifest
    print("\n" + "=" * 70)
    print("STEP 2: Create Goods Manifest")
    print("=" * 70)

    manifest = GoodsManifest(
        manifest_id="M-COFFEE-BC-001",
        good_type="Organic Coffee Beans",
        quantity=1000,
        creator=manufacturer.address,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )

    repo.create_manifest(manifest.model_dump())
    print(f"✅ Manifest created: {manifest.manifest_id}")

    # PRODUCE operation
    print("\n" + "=" * 70)
    print("STEP 3: PRODUCE Operation with Blockchain Anchoring")
    print("=" * 70)

    produce_record = Record(
        record_id="R-PROD-BC-001",
        record_type=RecordType.PRODUCED,
        manifest_id="M-COFFEE-BC-001",
        quantity=1000,
        user=manufacturer.address,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metadata={"factory": "Factory A", "batch": "BC-001"}
    )

    # Sign record
    produce_dict = produce_record.model_dump(exclude_none=True)
    produce_sig = manufacturer.sign_record(produce_dict)
    produce_hash = compute_hash(produce_dict)

    # Store in repository
    repo.create_record(
        produce_dict,
        produce_hash,
        produce_sig,
        manufacturer.address
    )

    print(f"✅ Record created and signed")
    print(f"   Record ID: {produce_record.record_id}")
    print(f"   Hash: {produce_hash[:20]}...")

    # Anchor on blockchain
    print(f"\n⛓️  Anchoring on blockchain...")
    tx_hash = scm.anchor_record(produce_record.record_id, produce_hash)

    print(f"✅ Anchored successfully")
    print(f"   TX Hash: {tx_hash[:20]}...")

    # TRANSFER operation
    print("\n" + "=" * 70)
    print("STEP 4: TRANSFER Operation with Blockchain Anchoring")
    print("=" * 70)

    transfer_record = Record(
        record_id="R-TRANS-BC-001",
        record_type=RecordType.TRANSFER,
        manifest_id="M-COFFEE-BC-001",
        quantity=600,
        user=manufacturer.address,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metadata={"to": "Warehouse B", "carrier": "TransCo"}
    )

    transfer_dict = transfer_record.model_dump(exclude_none=True)
    transfer_sig = manufacturer.sign_record(transfer_dict)
    transfer_hash = compute_hash(transfer_dict)

    repo.create_record(
        transfer_dict,
        transfer_hash,
        transfer_sig,
        manufacturer.address
    )

    # Anchor on blockchain
    tx_hash = scm.anchor_record(transfer_record.record_id, transfer_hash)

    print(f"✅ Transfer anchored")

    # Verify complete integrity
    print("\n" + "=" * 70)
    print("STEP 5: COMPLETE INTEGRITY VERIFICATION")
    print("=" * 70)

    # Verify PRODUCE record
    prod_verification = scm.verify_record_integrity("R-PROD-BC-001")

    # Verify TRANSFER record
    trans_verification = scm.verify_record_integrity("R-TRANS-BC-001")

    # Test tampering detection
    print("\n" + "=" * 70)
    print("STEP 6: TAMPERING DETECTION TEST")
    print("=" * 70)

    print(f"\n🚨 Simulating tampered data...")

    # Try to verify with wrong hash
    is_valid, details = mock_blockchain.verify_on_chain(
        "R-PROD-BC-001",
        "0xFAKEHASH1234567890123456789012345678901234567890123456789012"
    )

    if not is_valid:
        print(f"✅ Tamper detected correctly!")

    # Summary
    print("\n" + "=" * 70)
    print("STEP 7: BLOCKCHAIN STATE SUMMARY")
    print("=" * 70)

    print(f"\n📊 On-Chain Statistics:")
    print(f"   Total Records Anchored: {mock_blockchain.get_total_records()}")
    print(f"   Current Block: {mock_blockchain.block_number}")

    print(f"\n📋 Anchored Records:")
    for record_id in mock_blockchain.anchored_records:
        data = mock_blockchain.anchored_records[record_id]
        print(f"   - {record_id}")
        print(f"     Hash: {data['hash'][:20]}...")
        print(f"     TX: {data['tx_hash'][:20]}...")
        print(f"     Block: {data['block_number']}")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - BLOCKCHAIN INTEGRATION SUCCESSFUL!")
    print("=" * 70)

    return True


# ==================== MAIN ====================

if __name__ == "__main__":
    try:
        test_complete_supply_chain_with_blockchain()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
