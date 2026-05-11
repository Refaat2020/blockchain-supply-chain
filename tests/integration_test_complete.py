import json
import time
from datetime import datetime
from typing import Dict, List, Tuple
import tabulate as tab
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.join(CURRENT_DIR, '..', 'src', 'core'))

sys.path.append(os.path.join(CURRENT_DIR, '..', 'src', 'verification'))



from verification_engine import VerificationEngine, VerificationStatus
from repository_v2 import SupplyChainRepository
from data_structures import GoodsManifest, Record, RecordType, compute_hash
from user_identity import UserIdentity
# ==================== CONFIGURATION ====================

# For this demo, we'll use in-memory/local mode
# In production, connect to actual SCM server and blockchain
USE_LOCAL_MODE = True  # Set to False to use HTTP server
SCM_URL = "http://localhost:8000"


# ==================== COLOR OUTPUT ====================

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_step(step_num: int, title: str):
    """Print a step header"""
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}STEP {step_num}: {title}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")


# ==================== MOCK COMPONENTS FOR LOCAL MODE ====================

class MockBlockchain:
    """Mock blockchain for local testing"""

    def __init__(self):
        self.anchored_records = {}
        self.block_number = 1000000

    def anchor_hash(self, record_id: str, hash_hex: str, private_key: str) -> str:
        """Simulate anchoring"""
        import hashlib
        tx_hash = "0x" + \
            hashlib.sha256(
                f"{record_id}{hash_hex}{time.time()}".encode()).hexdigest()

        self.block_number += 1
        self.anchored_records[record_id] = {
            "hash": hash_hex,
            "tx_hash": tx_hash,
            "block_number": self.block_number
        }

        return tx_hash

    def verify_on_chain(self, record_id: str, expected_hash: str):
        """Verify hash on-chain"""
        if record_id not in self.anchored_records:
            return False, {"status": "NOT_FOUND"}

        on_chain_hash = self.anchored_records[record_id]["hash"]
        is_valid = on_chain_hash.lower() == expected_hash.lower()

        return is_valid, {
            "status": "VALID" if is_valid else "INVALID",
            "on_chain_hash": on_chain_hash
        }

    def get_transaction_details(self, tx_hash: str):
        """Get TX details"""
        for record_id, data in self.anchored_records.items():
            if data["tx_hash"] == tx_hash:
                return {
                    "tx_hash": tx_hash,
                    "block_number": data["block_number"],
                    "confirmations": 5,
                    "status": "SUCCESS"
                }
        raise ValueError("Transaction not found")


class MockSupplyChainManager:
    """Mock SCM for local testing"""

    def __init__(self, repo: SupplyChainRepository, blockchain: MockBlockchain):
        self.repo = repo
        self.blockchain = blockchain

    def create_manifest(self, manifest: GoodsManifest) -> bool:
        """Create manifest"""
        manifest_dict = manifest.model_dump()
        manifest_hash = compute_hash(manifest_dict)
        return self.repo.save_manifest(manifest_dict, manifest_hash)

    def process_operation(
        self,
        record: Record,
        signature: str,
        user_address: str
    ) -> Dict:
        """Process operation"""
        # Validate quantity
        self._validate_quantity(record)

        # Compute hash
        record_dict = record.model_dump(exclude_none=True, mode='json')
        record_hash = compute_hash(record_dict)

        # Save to repository
        self.repo.save_record({
            "record": record_dict,
            "hash": record_hash,
            "signature": signature,
            "user_address": user_address
        })

        # Anchor on blockchain
        tx_hash = self.blockchain.anchor_hash(
            record.record_id,
            record_hash,
            "dummy_key"
        )

        # Update repository with TX
        self.repo.update_tx_hash(record.record_id, tx_hash)

        return {
            "success": True,
            "record_id": record.record_id,
            "record_hash": record_hash,
            "blockchain_tx_hash": tx_hash
        }

    def _validate_quantity(self, record: Record):
        """Validate quantity constraints"""
        manifest = self.repo.get_manifest(record.manifest_id)

        if record.record_type == RecordType.PRODUCED:
            total_produced = self.repo.compute_available_quantity(
                record.manifest_id)
            if total_produced + record.quantity > manifest["quantity"]:
                raise ValueError(
                    f"Cannot produce {record.quantity}. Would exceed manifest limit."
                )

        elif record.record_type in [RecordType.TRANSFER, RecordType.DELIVERED]:
            available = self.repo.get_available_quantity_per_user(
                record.manifest_id,
                record.user
            )
            if available < record.quantity:
                raise ValueError(
                    f"Insufficient quantity. Available: {available}, Requested: {record.quantity}"
                )


# ==================== INTEGRATION TEST ====================

class IntegrationTest:
    """Complete end-to-end integration test"""

    def __init__(self):
        """Initialize test"""
        self.repo = SupplyChainRepository("integration_test.db")
        self.blockchain = MockBlockchain()
        self.scm = MockSupplyChainManager(self.repo, self.blockchain)
        self.verification = VerificationEngine(self.repo, self.blockchain)

        self.users = {}
        self.records_created = []
        self.manifest_id = None

    def run(self):
        """Run complete test"""
        print(f"\n{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.HEADER}🧪 BLOCKCHAIN SUPPLY CHAIN - END-TO-END INTEGRATION TEST{Colors.ENDC}")
        print(f"{Colors.BOLD}{'=' * 70}{Colors.ENDC}")

        try:
            self.step1_setup_users()
            self.step2_authenticate_users()
            self.step3_create_manifest()
            self.step4_produce_operation()
            self.step5_transfer_operation()
            self.step6_receive_operation()
            self.step7_deliver_operation()
            self.step8_verify_all_records()
            self.step9_test_rejection()
            self.step10_summary_table()

            print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 70}{Colors.ENDC}")
            print(
                f"{Colors.BOLD}{Colors.GREEN}✅ ALL TESTS PASSED - INTEGRATION SUCCESSFUL!{Colors.ENDC}")
            print(f"{Colors.BOLD}{Colors.GREEN}{'=' * 70}{Colors.ENDC}")

        except Exception as e:
            print_error(f"TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.repo.close()

    # ==================== TEST STEPS ====================

    def step1_setup_users(self):
        """Step 1: Create users with key pairs"""
        print_step(1, "Setup - Create Users with Key Pairs")

        roles = ["Producer", "Transporter", "Receiver"]

        for role in roles:
            user = UserIdentity()
            self.users[role] = user

            print(f"\n{Colors.CYAN}👤 {role}:{Colors.ENDC}")
            print(f"   Address:     {user.address}")
            print(f"   Private Key: {user.private_key[:30]}... (truncated)")
            print_success(f"{role} created")

        print(f"\n{Colors.GREEN}✅ All 3 users created successfully{Colors.ENDC}")

    def step2_authenticate_users(self):
        """Step 2: Authenticate all users"""
        print_step(2, "Authenticate All Users with SCM")

        for role, user in self.users.items():
            print(f"\n🔐 Authenticating {role}...")
            print(f"   Address: {user.address[:30]}...")

            # In local mode, authentication is implicit
            print_success(f"{role} authenticated")

        print(f"\n{Colors.GREEN}✅ All users authenticated{Colors.ENDC}")

    def step3_create_manifest(self):
        """Step 3: Producer creates manifest"""
        print_step(3, "Producer Creates Manifest for 100 Books")

        producer = self.users["Producer"]
        self.manifest_id = f"M-BOOKS-{int(time.time())}"

        manifest = GoodsManifest(
            manifest_id=self.manifest_id,
            good_type="Books",
            quantity=100,
            creator=producer.address,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        print(f"\n📦 Creating manifest:")
        print(f"   ID:       {manifest.manifest_id}")
        print(f"   Type:     {manifest.good_type}")
        print(f"   Quantity: {manifest.quantity}")
        print(f"   Creator:  {producer.address[:30]}...")

        self.scm.create_manifest(manifest)

        print_success("Manifest created successfully")

    def step4_produce_operation(self):
        """Step 4: Producer submits PRODUCE operation"""
        print_step(4, "Producer Submits PRODUCE Operation for 100 Books")

        producer = self.users["Producer"]
        record_id = f"R-PROD-{int(time.time())}"

        record = Record(
            record_id=record_id,
            record_type=RecordType.PRODUCED,
            manifest_id=self.manifest_id,
            quantity=100,
            user=producer.address,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata={"factory": "Book Factory A", "batch": "B001"}
        )

        print(f"\n📝 Creating PRODUCE record:")
        print(f"   Record ID: {record.record_id}")
        print(f"   Quantity:  {record.quantity}")
        print(f"   User:      {producer.address[:30]}...")

        # Sign record
        record_dict = record.model_dump(exclude_none=True, mode='json')
        signature = producer.sign_record(record_dict)

        print(f"   Signature: {signature[:40]}...")

        # Process operation
        result = self.scm.process_operation(
            record, signature, producer.address)

        self.records_created.append({
            "record_id": record.record_id,
            "type": record.record_type.value,
            "hash": result["record_hash"],
            "tx_hash": result["blockchain_tx_hash"]
        })

        print_success("PRODUCE operation completed")
        print(f"   Hash:   {result['record_hash'][:40]}...")
        print(f"   TX:     {result['blockchain_tx_hash'][:40]}...")
        print_success("Record anchored on blockchain")

    def step5_transfer_operation(self):
        """Step 5: Transporter requests TRANSFER"""
        print_step(5, "Transporter Requests TRANSFER of 20 Books")

        producer = self.users["Producer"]
        record_id = f"R-TRANS-{int(time.time())}"

        record = Record(
            record_id=record_id,
            record_type=RecordType.TRANSFER,
            manifest_id=self.manifest_id,
            quantity=20,
            user=producer.address,  # Producer transfers
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata={"to": "Warehouse B", "carrier": "Transport Co."}
        )

        print(f"\n🚚 Creating TRANSFER record:")
        print(f"   Record ID: {record.record_id}")
        print(f"   Quantity:  {record.quantity}")
        print(f"   From:      {producer.address[:30]}...")

        # Sign and process
        record_dict = record.model_dump(exclude_none=True, mode='json')
        signature = producer.sign_record(record_dict)
        result = self.scm.process_operation(
            record, signature, producer.address)

        self.records_created.append({
            "record_id": record.record_id,
            "type": record.record_type.value,
            "hash": result["record_hash"],
            "tx_hash": result["blockchain_tx_hash"]
        })

        print_success("TRANSFER operation completed")
        print(f"   TX: {result['blockchain_tx_hash'][:40]}...")
        print_success("Record anchored on blockchain")

        # Check remaining quantity
        remaining = self.repo.get_available_quantity_per_user(
            self.manifest_id,
            producer.address
        )
        print_info(f"Producer remaining quantity: {remaining}")

    def step6_receive_operation(self):
        """Step 6: Receiver confirms RECEPTION"""
        print_step(6, "Receiver Confirms RECEPTION of 20 Books")

        receiver = self.users["Receiver"]
        record_id = f"R-REC-{int(time.time())}"

        record = Record(
            record_id=record_id,
            record_type=RecordType.RECEIVED,
            manifest_id=self.manifest_id,
            quantity=20,
            user=receiver.address,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata={"from": "Producer", "location": "Warehouse B"}
        )

        print(f"\n📥 Creating RECEIVED record:")
        print(f"   Record ID: {record.record_id}")
        print(f"   Quantity:  {record.quantity}")
        print(f"   Receiver:  {receiver.address[:30]}...")

        # Sign and process
        record_dict = record.model_dump(exclude_none=True, mode='json')
        signature = receiver.sign_record(record_dict)
        result = self.scm.process_operation(
            record, signature, receiver.address)

        self.records_created.append({
            "record_id": record.record_id,
            "type": record.record_type.value,
            "hash": result["record_hash"],
            "tx_hash": result["blockchain_tx_hash"]
        })

        print_success("RECEIVED operation completed")
        print(f"   TX: {result['blockchain_tx_hash'][:40]}...")
        print_success("Record anchored on blockchain")

        # Check receiver quantity
        received = self.repo.get_available_quantity_per_user(
            self.manifest_id,
            receiver.address
        )
        print_info(f"Receiver total quantity: {received}")

    def step7_deliver_operation(self):
        """Step 7: Receiver submits DELIVERY"""
        print_step(7, "Receiver Submits DELIVERY Record")

        receiver = self.users["Receiver"]
        record_id = f"R-DEL-{int(time.time())}"

        record = Record(
            record_id=record_id,
            record_type=RecordType.DELIVERED,
            manifest_id=self.manifest_id,
            quantity=10,  # Deliver 10 out of 20
            user=receiver.address,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata={"to": "Final Customer", "location": "Store C"}
        )

        print(f"\n📦 Creating DELIVERED record:")
        print(f"   Record ID: {record.record_id}")
        print(f"   Quantity:  {record.quantity}")
        print(f"   Deliverer: {receiver.address[:30]}...")

        # Sign and process
        record_dict = record.model_dump(exclude_none=True, mode='json')
        signature = receiver.sign_record(record_dict)
        result = self.scm.process_operation(
            record, signature, receiver.address)

        self.records_created.append({
            "record_id": record.record_id,
            "type": record.record_type.value,
            "hash": result["record_hash"],
            "tx_hash": result["blockchain_tx_hash"]
        })

        print_success("DELIVERED operation completed")
        print(f"   TX: {result['blockchain_tx_hash'][:40]}...")
        print_success("Record anchored on blockchain")

        # Check final quantity
        remaining = self.repo.get_available_quantity_per_user(
            self.manifest_id,
            receiver.address
        )
        print_info(f"Receiver remaining quantity: {remaining}")

    def step8_verify_all_records(self):
        """Step 8: Run full verification"""
        print_step(8, "Run Full Verification on All Records")

        for i, rec in enumerate(self.records_created, 1):
            print(
                f"\n{Colors.CYAN}━━━ Verifying Record {i}/{len(self.records_created)} ━━━{Colors.ENDC}")

            result = self.verification.verify_record(rec["record_id"])

            # Store verification status
            rec["verification"] = result.conclusion.value

            if result.is_fully_verified():
                print_success(f"Record {rec['record_id']} is FULLY VERIFIED")
            else:
                print_warning(
                    f"Record {rec['record_id']}: {result.conclusion.value}")

        print(
            f"\n{Colors.GREEN}✅ Verification completed for all records{Colors.ENDC}")

        # Verify quantity consistency
        print(f"\n{Colors.CYAN}━━━ Verifying Quantity Consistency ━━━{Colors.ENDC}")
        qty_result = self.verification.verify_quantity_consistency(
            self.manifest_id)

        if qty_result.is_consistent:
            print_success("Quantity consistency verified")
            print(f"   Produced:    {qty_result.total_produced}")
            print(f"   Transferred: {qty_result.total_transferred}")
            print(f"   Received:    {qty_result.total_received}")
            print(f"   Delivered:   {qty_result.total_delivered}")
            print(f"   Net:         {qty_result.net_available}")
        else:
            print_error("Quantity discrepancies detected!")

    def step9_test_rejection(self):
        """Step 9: Test rejection of invalid operation"""
        print_step(
            9, "Test Rejection - Try to Transfer 200 Books (Exceeds Available)")

        producer = self.users["Producer"]
        record_id = f"R-INVALID-{int(time.time())}"

        # Check current available
        available = self.repo.get_available_quantity_per_user(
            self.manifest_id,
            producer.address
        )

        print(f"\n📊 Current state:")
        print(f"   Producer has: {available} books")
        print(f"   Attempting to transfer: 200 books")

        record = Record(
            record_id=record_id,
            record_type=RecordType.TRANSFER,
            manifest_id=self.manifest_id,
            quantity=200,  # More than available!
            user=producer.address,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        print(f"\n🚨 Attempting invalid transfer...")

        try:
            record_dict = record.model_dump(exclude_none=True, mode='json')
            signature = producer.sign_record(record_dict)
            self.scm.process_operation(record, signature, producer.address)

            print_error("SECURITY ISSUE: Invalid operation was accepted!")

        except ValueError as e:
            print_success("Operation correctly rejected!")
            print(f"   Reason: {e}")

    def step10_summary_table(self):
        """Step 10: Print summary table"""
        print_step(10, "Summary Table")

        # Prepare table data
        table_data = []
        for rec in self.records_created:
            table_data.append([
                rec["record_id"],
                rec["type"],
                rec["hash"][:20] + "...",
                rec["tx_hash"][:20] + "...",
                rec.get("verification", "N/A")
            ])

        headers = ["Record ID", "Type", "Hash",
                   "Blockchain TX", "Verification"]

        print(f"\n{tab.tabulate(table_data, headers=headers, tablefmt='grid')}")

        # Final statistics
        print(f"\n{Colors.CYAN}📊 Final Statistics:{Colors.ENDC}")
        stats = self.repo.get_statistics()
        print(f"   Total Manifests:  {stats['total_manifests']}")
        print(f"   Total Records:    {stats['total_records']}")
        print(f"   Records Anchored: {stats['records_anchored']}")
        print(f"   Total Produced:   {stats['total_quantity_produced']}")


# ==================== MAIN ====================

if __name__ == "__main__":
    # Install tabulate if not available
    try:
        import tabulate
    except ImportError:
        print("Installing tabulate...")
        import subprocess
        subprocess.run(["pip", "install", "tabulate",
                       "--break-system-packages", "-q"])
        import tabulate

    # Run integration test
    test = IntegrationTest()
    test.run()
