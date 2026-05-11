

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

# Import our modules
from data_structures import Record, compute_hash
from user_identity import SignatureVerifier
from repository_v2 import SupplyChainRepository


# ==================== VERIFICATION RESULT ENUMS ====================

class VerificationStatus(str, Enum):
    """Verification status values"""
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"
    PENDING = "PENDING"


class Conclusion(str, Enum):
    """Overall verification conclusion"""
    VERIFIED = "Record is cryptographically verified"
    FAILED = "Record verification failed"
    PARTIAL = "Record partially verified - blockchain pending"
    NOT_FOUND = "Record not found"
    ERROR = "Verification error"


# ==================== VERIFICATION RESULT MODELS ====================

class VerificationResult:
    """Complete verification result"""
    
    def __init__(
        self,
        record_id: str,
        hash_integrity: VerificationStatus,
        signature: VerificationStatus,
        blockchain_proof: VerificationStatus,
        timestamp: Optional[str],
        conclusion: Conclusion,
        details: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None
    ):
        self.record_id = record_id
        self.hash_integrity = hash_integrity
        self.signature = signature
        self.blockchain_proof = blockchain_proof
        self.timestamp = timestamp
        self.conclusion = conclusion
        self.details = details or {}
        self.errors = errors or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "record_id": self.record_id,
            "hash_integrity": self.hash_integrity.value,
            "signature": self.signature.value,
            "blockchain_proof": self.blockchain_proof.value,
            "timestamp": self.timestamp,
            "conclusion": self.conclusion.value
        }
        
        if self.details:
            result["details"] = self.details
        
        if self.errors:
            result["errors"] = self.errors
        
        return result
    
    def is_fully_verified(self) -> bool:
        """Check if record is fully verified"""
        return (
            self.hash_integrity == VerificationStatus.VALID and
            self.signature == VerificationStatus.VALID and
            self.blockchain_proof == VerificationStatus.VALID
        )
    
    def __str__(self) -> str:
        """String representation"""
        return json.dumps(self.to_dict(), indent=2)


class QuantityVerificationResult:
    """Quantity consistency verification result"""
    
    def __init__(
        self,
        manifest_id: str,
        is_consistent: bool,
        total_produced: int,
        total_transferred: int,
        total_received: int,
        total_delivered: int,
        net_available: int,
        discrepancies: List[str]
    ):
        self.manifest_id = manifest_id
        self.is_consistent = is_consistent
        self.total_produced = total_produced
        self.total_transferred = total_transferred
        self.total_received = total_received
        self.total_delivered = total_delivered
        self.net_available = net_available
        self.discrepancies = discrepancies
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "manifest_id": self.manifest_id,
            "is_consistent": self.is_consistent,
            "quantities": {
                "produced": self.total_produced,
                "transferred": self.total_transferred,
                "received": self.total_received,
                "delivered": self.total_delivered,
                "net_available": self.net_available
            },
            "discrepancies": self.discrepancies,
            "conclusion": "Quantities are consistent" if self.is_consistent else "Quantity discrepancies detected"
        }
    
    def __str__(self) -> str:
        """String representation"""
        return json.dumps(self.to_dict(), indent=2)


# ==================== VERIFICATION ENGINE ====================

class VerificationEngine:
    """
    Complete verification engine for supply chain records.
    
    Performs:
    1. Hash integrity verification
    2. Digital signature verification
    3. Blockchain proof verification
    4. Quantity consistency checks
    """
    
    def __init__(
        self,
        repository: SupplyChainRepository,
        blockchain_client=None
    ):
        """
        Initialize verification engine.
        
        Args:
            repository: Supply chain repository
            blockchain_client: Optional blockchain client for on-chain verification
        """
        self.repo = repository
        self.blockchain = blockchain_client
        self.signature_verifier = SignatureVerifier()
    
    # ==================== RECORD VERIFICATION ====================
    
    def verify_record(self, record_id: str) -> VerificationResult:
        """
        Complete verification of a supply chain record.
        
        Args:
            record_id: Record identifier to verify
        
        Returns:
            VerificationResult with all verification steps
        
        Example:
            >>> engine = VerificationEngine(repo, blockchain)
            >>> result = engine.verify_record("R-PROD-001")
            >>> print(result.conclusion)
        """
        print(f"\n{'=' * 70}")
        print(f"🔍 VERIFYING RECORD: {record_id}")
        print(f"{'=' * 70}")
        
        errors = []
        details = {}
        
        # Step 1: Retrieve record from repository
        print(f"\n📥 Step 1: Retrieving record from repository...")
        
        stored_record = self.repo.get_record(record_id)
        
        if not stored_record:
            print(f"   ❌ Record not found")
            return VerificationResult(
                record_id=record_id,
                hash_integrity=VerificationStatus.NOT_FOUND,
                signature=VerificationStatus.NOT_FOUND,
                blockchain_proof=VerificationStatus.NOT_FOUND,
                timestamp=None,
                conclusion=Conclusion.NOT_FOUND,
                errors=["Record not found in repository"]
            )
        
        print(f"   ✅ Record retrieved")
        details["record_type"] = stored_record["record"]["record_type"]
        details["manifest_id"] = stored_record["record"]["manifest_id"]
        details["quantity"] = stored_record["record"]["quantity"]
        details["user_address"] = stored_record["user_address"]
        
        # Step 2: Hash integrity verification
        print(f"\n🔐 Step 2: Verifying hash integrity...")
        
        hash_status = self._verify_hash_integrity(stored_record, details, errors)
        
        # Step 3: Digital signature verification
        print(f"\n✍️  Step 3: Verifying digital signature...")
        
        signature_status = self._verify_signature(stored_record, details, errors)
        
        # Step 4: Blockchain proof verification
        print(f"\n⛓️  Step 4: Verifying blockchain proof...")
        
        blockchain_status, timestamp = self._verify_blockchain_proof(
            stored_record, 
            details, 
            errors
        )
        
        # Step 5: Determine conclusion
        conclusion = self._determine_conclusion(
            hash_status,
            signature_status,
            blockchain_status
        )
        
        # Final result
        print(f"\n{'=' * 70}")
        print(f"📋 VERIFICATION RESULT")
        print(f"{'=' * 70}")
        print(f"   Hash Integrity:    {hash_status.value}")
        print(f"   Signature:         {signature_status.value}")
        print(f"   Blockchain Proof:  {blockchain_status.value}")
        print(f"   Timestamp:         {timestamp or 'N/A'}")
        print(f"   Conclusion:        {conclusion.value}")
        
        return VerificationResult(
            record_id=record_id,
            hash_integrity=hash_status,
            signature=signature_status,
            blockchain_proof=blockchain_status,
            timestamp=timestamp,
            conclusion=conclusion,
            details=details,
            errors=errors
        )
    
    def _verify_hash_integrity(
        self,
        stored_record: Dict,
        details: Dict,
        errors: List[str]
    ) -> VerificationStatus:
        """Verify hash integrity"""
        try:
            # Recompute hash from record data
            record_dict = stored_record["record"]
            recomputed_hash = compute_hash(record_dict)
            
            stored_hash = stored_record["hash"]
            
            details["stored_hash"] = stored_hash
            details["recomputed_hash"] = recomputed_hash
            
            print(f"   Stored hash:     {stored_hash[:40]}...")
            print(f"   Recomputed hash: {recomputed_hash[:40]}...")
            
            # Compare hashes
            if recomputed_hash == stored_hash:
                print(f"   ✅ Hash integrity verified")
                return VerificationStatus.VALID
            else:
                print(f"   ❌ Hash mismatch detected!")
                errors.append("Hash integrity check failed - data may have been tampered")
                return VerificationStatus.INVALID
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            errors.append(f"Hash verification error: {str(e)}")
            return VerificationStatus.ERROR
    
    def _verify_signature(
        self,
        stored_record: Dict,
        details: Dict,
        errors: List[str]
    ) -> VerificationStatus:
        """Verify digital signature"""
        try:
            record_dict = stored_record["record"]
            signature = stored_record["signature"]
            user_address = stored_record["user_address"]
            
            details["signature"] = signature[:40] + "..."
            
            print(f"   Signature: {signature[:40]}...")
            print(f"   Signer:    {user_address}")
            
            # Verify signature
            is_valid = self.signature_verifier.verify_signature(
                record_dict,
                signature,
                user_address
            )
            
            if is_valid:
                print(f"   ✅ Signature verified")
                return VerificationStatus.VALID
            else:
                print(f"   ❌ Invalid signature!")
                errors.append("Digital signature verification failed")
                return VerificationStatus.INVALID
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            errors.append(f"Signature verification error: {str(e)}")
            return VerificationStatus.ERROR
    
    def _verify_blockchain_proof(
        self,
        stored_record: Dict,
        details: Dict,
        errors: List[str]
    ) -> Tuple[VerificationStatus, Optional[str]]:
        """Verify blockchain proof"""
        try:
            tx_hash = stored_record.get("tx_hash")
            
            if not tx_hash:
                print(f"   ⚠️  No blockchain anchor found")
                errors.append("Record not yet anchored on blockchain")
                return VerificationStatus.PENDING, None
            
            details["tx_hash"] = tx_hash
            print(f"   TX Hash: {tx_hash[:40]}...")
            
            # If no blockchain client, can't verify on-chain
            if not self.blockchain:
                print(f"   ⚠️  Blockchain client not available")
                return VerificationStatus.PENDING, f"TX: {tx_hash[:20]}..."
            
            # Verify on blockchain
            record_id = stored_record["record"]["record_id"]
            expected_hash = stored_record["hash"]
            
            is_valid, bc_details = self.blockchain.verify_on_chain(
                record_id,
                expected_hash
            )
            
            if is_valid:
                # Get transaction details
                try:
                    tx_details = self.blockchain.get_transaction_details(tx_hash)
                    block_number = tx_details.get("block_number")
                    confirmations = tx_details.get("confirmations", 0)
                    
                    timestamp = f"Block #{block_number} ({confirmations} confirmations)"
                    
                    details["block_number"] = block_number
                    details["confirmations"] = confirmations
                    
                    print(f"   ✅ Blockchain proof verified")
                    print(f"   Block: {block_number}")
                    print(f"   Confirmations: {confirmations}")
                    
                    return VerificationStatus.VALID, timestamp
                    
                except Exception as e:
                    print(f"   ⚠️  Could not get transaction details: {e}")
                    return VerificationStatus.VALID, f"TX: {tx_hash[:20]}..."
            else:
                print(f"   ❌ Blockchain verification failed!")
                errors.append("On-chain hash does not match local hash")
                return VerificationStatus.INVALID, f"Block #INVALID"
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            errors.append(f"Blockchain verification error: {str(e)}")
            return VerificationStatus.ERROR, None
    
    def _determine_conclusion(
        self,
        hash_status: VerificationStatus,
        signature_status: VerificationStatus,
        blockchain_status: VerificationStatus
    ) -> Conclusion:
        """Determine overall verification conclusion"""
        
        # All valid = verified
        if (hash_status == VerificationStatus.VALID and
            signature_status == VerificationStatus.VALID and
            blockchain_status == VerificationStatus.VALID):
            return Conclusion.VERIFIED
        
        # Any invalid = failed
        if (hash_status == VerificationStatus.INVALID or
            signature_status == VerificationStatus.INVALID or
            blockchain_status == VerificationStatus.INVALID):
            return Conclusion.FAILED
        
        # Hash and signature valid but blockchain pending = partial
        if (hash_status == VerificationStatus.VALID and
            signature_status == VerificationStatus.VALID and
            blockchain_status == VerificationStatus.PENDING):
            return Conclusion.PARTIAL
        
        # Any error
        return Conclusion.ERROR
    
    # ==================== QUANTITY VERIFICATION ====================
    
    def verify_quantity_consistency(
        self,
        manifest_id: str
    ) -> QuantityVerificationResult:
        """
        Verify quantity consistency for a manifest.
        
        Checks:
        1. Total produced does not exceed manifest quantity
        2. Transfers don't exceed available quantity
        3. Deliveries don't exceed received quantity
        4. Net available is non-negative
        
        Args:
            manifest_id: Manifest to verify
        
        Returns:
            QuantityVerificationResult with all checks
        """
        print(f"\n{'=' * 70}")
        print(f"📊 VERIFYING QUANTITY CONSISTENCY: {manifest_id}")
        print(f"{'=' * 70}")
        
        discrepancies = []
        
        # Get manifest
        manifest = self.repo.get_manifest(manifest_id)
        
        if not manifest:
            discrepancies.append("Manifest not found")
            return QuantityVerificationResult(
                manifest_id=manifest_id,
                is_consistent=False,
                total_produced=0,
                total_transferred=0,
                total_received=0,
                total_delivered=0,
                net_available=0,
                discrepancies=discrepancies
            )
        
        manifest_limit = manifest["quantity"]
        print(f"\n📦 Manifest limit: {manifest_limit} units")
        
        # Get all records
        records = self.repo.get_all_records_for_manifest(manifest_id)
        
        if not records:
            print(f"   ℹ️  No records found")
            return QuantityVerificationResult(
                manifest_id=manifest_id,
                is_consistent=True,
                total_produced=0,
                total_transferred=0,
                total_received=0,
                total_delivered=0,
                net_available=0,
                discrepancies=[]
            )
        
        # Calculate totals
        total_produced = 0
        total_transferred = 0
        total_received = 0
        total_delivered = 0
        
        user_balances = {}  # user_address -> balance
        
        print(f"\n📋 Processing {len(records)} records...")
        
        for record in records:
            record_type = record["record_type"]
            quantity = record["quantity"]
            user = record["user_address"]
            
            print(f"\n   {record['record_id']}: {record_type} ({quantity} units)")
            print(f"      User: {user[:20]}...")
            
            # Update totals
            if record_type == "PRODUCED":
                total_produced += quantity
                user_balances[user] = user_balances.get(user, 0) + quantity
                print(f"      User balance: {user_balances[user]}")
                
            elif record_type == "TRANSFER":
                total_transferred += quantity
                
                # Check if user has enough
                current_balance = user_balances.get(user, 0)
                if current_balance < quantity:
                    msg = f"TRANSFER {record['record_id']}: User {user[:10]}... tried to transfer {quantity} but only has {current_balance}"
                    discrepancies.append(msg)
                    print(f"      ❌ {msg}")
                else:
                    user_balances[user] = current_balance - quantity
                    print(f"      User balance: {user_balances[user]}")
                    
            elif record_type == "RECEIVED":
                total_received += quantity
                user_balances[user] = user_balances.get(user, 0) + quantity
                print(f"      User balance: {user_balances[user]}")
                
            elif record_type == "DELIVERED":
                total_delivered += quantity
                
                # Check if user has enough
                current_balance = user_balances.get(user, 0)
                if current_balance < quantity:
                    msg = f"DELIVERED {record['record_id']}: User {user[:10]}... tried to deliver {quantity} but only has {current_balance}"
                    discrepancies.append(msg)
                    print(f"      ❌ {msg}")
                else:
                    user_balances[user] = current_balance - quantity
                    print(f"      User balance: {user_balances[user]}")
        
        # Calculate net available
        net_available = total_produced + total_received - total_transferred - total_delivered
        
        print(f"\n{'=' * 70}")
        print(f"📊 QUANTITY SUMMARY")
        print(f"{'=' * 70}")
        print(f"   Produced:    {total_produced}")
        print(f"   Received:    {total_received}")
        print(f"   Transferred: {total_transferred}")
        print(f"   Delivered:   {total_delivered}")
        print(f"   Net Available: {net_available}")
        
        # Check 1: Total produced exceeds manifest limit
        if total_produced > manifest_limit:
            msg = f"Total produced ({total_produced}) exceeds manifest limit ({manifest_limit})"
            discrepancies.append(msg)
            print(f"\n   ❌ {msg}")
        
        # Check 2: Negative available quantity
        if net_available < 0:
            msg = f"Negative net available quantity: {net_available}"
            discrepancies.append(msg)
            print(f"\n   ❌ {msg}")
        
        # Check 3: User balances
        print(f"\n👥 User Balances:")
        for user, balance in user_balances.items():
            print(f"   {user[:20]}...: {balance} units")
            if balance < 0:
                msg = f"User {user[:10]}... has negative balance: {balance}"
                discrepancies.append(msg)
                print(f"      ❌ {msg}")
        
        # Final result
        is_consistent = len(discrepancies) == 0
        
        print(f"\n{'=' * 70}")
        if is_consistent:
            print(f"✅ QUANTITIES ARE CONSISTENT")
        else:
            print(f"❌ QUANTITY DISCREPANCIES DETECTED ({len(discrepancies)})")
            for i, disc in enumerate(discrepancies, 1):
                print(f"   {i}. {disc}")
        print(f"{'=' * 70}")
        
        return QuantityVerificationResult(
            manifest_id=manifest_id,
            is_consistent=is_consistent,
            total_produced=total_produced,
            total_transferred=total_transferred,
            total_received=total_received,
            total_delivered=total_delivered,
            net_available=net_available,
            discrepancies=discrepancies
        )
    
    # ==================== BATCH VERIFICATION ====================
    
    def verify_all_records_for_manifest(
        self,
        manifest_id: str
    ) -> Dict[str, VerificationResult]:
        """
        Verify all records for a manifest.
        
        Args:
            manifest_id: Manifest identifier
        
        Returns:
            Dictionary mapping record_id to VerificationResult
        """
        print(f"\n{'=' * 70}")
        print(f"🔍 BATCH VERIFICATION: {manifest_id}")
        print(f"{'=' * 70}")
        
        records = self.repo.get_all_records_for_manifest(manifest_id)
        
        if not records:
            print(f"   ℹ️  No records found")
            return {}
        
        print(f"\n📋 Verifying {len(records)} records...")
        
        results = {}
        
        for record in records:
            record_id = record["record_id"]
            result = self.verify_record(record_id)
            results[record_id] = result
        
        # Summary
        print(f"\n{'=' * 70}")
        print(f"📊 BATCH VERIFICATION SUMMARY")
        print(f"{'=' * 70}")
        
        verified = sum(1 for r in results.values() if r.is_fully_verified())
        partial = sum(1 for r in results.values() if r.conclusion == Conclusion.PARTIAL)
        failed = sum(1 for r in results.values() if r.conclusion == Conclusion.FAILED)
        
        print(f"   Total records:  {len(results)}")
        print(f"   ✅ Verified:    {verified}")
        print(f"   ⚠️  Partial:     {partial}")
        print(f"   ❌ Failed:      {failed}")
        
        return results


# ==================== TESTING ====================

def test_verification_engine():
    """Test verification engine"""
    from user_identity import UserIdentity
    from data_structures import GoodsManifest, Record, RecordType
    
    print("\n" + "=" * 70)
    print("🧪 VERIFICATION ENGINE TEST")
    print("=" * 70)
    
    # Initialize
    repo = SupplyChainRepository("test_verification.db")
    engine = VerificationEngine(repo)
    
    # Create user
    user = UserIdentity()
    
    # Create manifest
    manifest = GoodsManifest(
        manifest_id="M-TEST-VER-001",
        good_type="Test Product",
        quantity=1000,
        creator=user.address,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    manifest_dict = manifest.model_dump()
    manifest_hash = compute_hash(manifest_dict)
    repo.save_manifest(manifest_dict, manifest_hash)
    
    # Create and save PRODUCED record
    produced = Record(
        record_id="R-VER-001",
        record_type=RecordType.PRODUCED,
        manifest_id="M-TEST-VER-001",
        quantity=1000,
        user=user.address,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    prod_dict = produced.model_dump(exclude_none=True)
    prod_hash = compute_hash(prod_dict)
    prod_sig = user.sign_record(prod_dict)
    
    repo.save_record({
        "record": prod_dict,
        "hash": prod_hash,
        "signature": prod_sig,
        "user_address": user.address
    }, tx_hash="0xabc123...")
    
    # Verify record
    result = engine.verify_record("R-VER-001")
    print(f"\n{result}")
    
    # Create TRANSFER record
    transfer = Record(
        record_id="R-VER-002",
        record_type=RecordType.TRANSFER,
        manifest_id="M-TEST-VER-001",
        quantity=600,
        user=user.address,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    trans_dict = transfer.model_dump(exclude_none=True)
    trans_hash = compute_hash(trans_dict)
    trans_sig = user.sign_record(trans_dict)
    
    repo.save_record({
        "record": trans_dict,
        "hash": trans_hash,
        "signature": trans_sig,
        "user_address": user.address
    }, tx_hash="0xdef456...")
    
    # Verify quantity consistency
    qty_result = engine.verify_quantity_consistency("M-TEST-VER-001")
    print(f"\n{qty_result}")
    
    repo.close()
    
    print("\n" + "=" * 70)
    print("✅ VERIFICATION ENGINE TEST COMPLETED!")
    print("=" * 70)


if __name__ == "__main__":
    test_verification_engine()
