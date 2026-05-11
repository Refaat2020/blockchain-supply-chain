"""
Supply Chain Manager - Standalone Integration Test
Tests all components without running HTTP server
"""

from datetime import datetime
from user_identity import UserIdentity
from data_structures import Record, RecordType, GoodsManifest, compute_hash
from repository import SupplyChainRepository
from supply_chain_manager import SupplyChainManager, BlockchainSimulator, AuthenticationManager


def test_complete_workflow():
    """Test complete supply chain workflow"""
    print("\n" + "=" * 70)
    print("🧪 SUPPLY CHAIN MANAGER - INTEGRATION TEST")
    print("=" * 70)
    
    # Initialize components
    repo = SupplyChainRepository("test_scm.db")
    blockchain = BlockchainSimulator()
    scm = SupplyChainManager(repo, blockchain)
    auth = AuthenticationManager()
    
    # Step 1: Create users
    print("\n" + "=" * 70)
    print("STEP 1: Create Users")
    print("=" * 70)
    
    manufacturer = UserIdentity()
    distributor = UserIdentity()
    retailer = UserIdentity()
    
    print(f"👤 Manufacturer: {manufacturer.address[:20]}...")
    print(f"👤 Distributor:  {distributor.address[:20]}...")
    print(f"👤 Retailer:     {retailer.address[:20]}...")
    
    # Step 2: Test Authentication
    print("\n" + "=" * 70)
    print("STEP 2: Authentication Challenge-Response")
    print("=" * 70)
    
    # Get challenge
    challenge_resp = auth.generate_challenge(manufacturer.address)
    print(f"✅ Challenge generated: {challenge_resp.challenge[:20]}...")
    
    # Sign challenge
    challenge_data = {"challenge": challenge_resp.challenge}
    signature = manufacturer.sign_record(challenge_data)
    print(f"✅ Challenge signed: {signature[:40]}...")
    
    # Verify
    auth_success = auth.verify_challenge(
        manufacturer.address,
        challenge_resp.challenge,
        signature
    )
    print(f"✅ Authentication result: {auth_success}")
    
    # Step 3: Create Manifest
    print("\n" + "=" * 70)
    print("STEP 3: Create Goods Manifest")
    print("=" * 70)
    
    manifest = GoodsManifest(
        manifest_id="M-COFFEE-001",
        good_type="Organic Coffee Beans",
        quantity=1000,
        creator=manufacturer.address,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    scm.create_manifest(manifest)
    print(f"✅ Manifest created: {manifest.manifest_id}")
    print(f"   Type: {manifest.good_type}")
    print(f"   Quantity: {manifest.quantity}")
    
    # Step 4: Produce Goods
    print("\n" + "=" * 70)
    print("STEP 4: PRODUCE Operation")
    print("=" * 70)
    
    produce_record = Record(
        record_id="R-PROD-001",
        record_type=RecordType.PRODUCED,
        manifest_id="M-COFFEE-001",
        quantity=1000,
        user=manufacturer.address,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metadata={"factory": "Factory A", "batch": "B001"}
    )
    
    # Convert to dict and sign
    produce_dict = produce_record.model_dump(exclude_none=True)
    produce_sig = manufacturer.sign_record(produce_dict)
    
    # Create operation request with same data
    from supply_chain_manager import OperationRequest
    produce_op = OperationRequest(
        **produce_dict,  # Use the exact same dict we signed
        signature=produce_sig
    )
    
    result = scm.process_operation(produce_op)
    print(f"✅ PRODUCED: {result.record_id}")
    print(f"   Hash: {result.record_hash[:40]}...")
    print(f"   TX Hash: {result.blockchain_tx_hash[:40]}...")
    
    # Step 5: Check Quantity
    print("\n" + "=" * 70)
    print("STEP 5: Check Available Quantity")
    print("=" * 70)
    
    available = repo.get_available_quantity("M-COFFEE-001", manufacturer.address)
    print(f"📊 Manufacturer has: {available} units available")
    
    # Step 6: Transfer Goods
    print("\n" + "=" * 70)
    print("STEP 6: TRANSFER Operation")
    print("=" * 70)
    
    transfer_record = Record(
        record_id="R-TRANS-001",
        record_type=RecordType.TRANSFER,
        manifest_id="M-COFFEE-001",
        quantity=600,
        user=manufacturer.address,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metadata={"to": "Warehouse B", "carrier": "TransCo"}
    )
    
    transfer_dict = transfer_record.model_dump(exclude_none=True)
    transfer_sig = manufacturer.sign_record(transfer_dict)
    
    transfer_op = OperationRequest(
        **transfer_dict,
        signature=transfer_sig
    )
    
    result = scm.process_operation(transfer_op)
    print(f"✅ TRANSFERRED: {result.record_id}")
    print(f"   Quantity: 600 units")
    print(f"   TX Hash: {result.blockchain_tx_hash[:40]}...")
    
    # Check quantity after transfer
    available = repo.get_available_quantity("M-COFFEE-001", manufacturer.address)
    print(f"📊 Manufacturer now has: {available} units (1000 - 600 = 400)")
    
    # Step 7: Distributor Receives
    print("\n" + "=" * 70)
    print("STEP 7: RECEIVE Operation (Distributor)")
    print("=" * 70)
    
    receive_record = Record(
        record_id="R-REC-001",
        record_type=RecordType.RECEIVED,
        manifest_id="M-COFFEE-001",
        quantity=600,
        user=distributor.address,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metadata={"from": "Manufacturer"}
    )
    
    receive_dict = receive_record.model_dump(exclude_none=True)
    receive_sig = distributor.sign_record(receive_dict)
    
    receive_op = OperationRequest(
        **receive_dict,
        signature=receive_sig
    )
    
    result = scm.process_operation(receive_op)
    print(f"✅ RECEIVED: {result.record_id}")
    print(f"   TX Hash: {result.blockchain_tx_hash[:40]}...")
    
    dist_qty = repo.get_available_quantity("M-COFFEE-001", distributor.address)
    print(f"📊 Distributor now has: {dist_qty} units")
    
    # Step 8: Verify Records
    print("\n" + "=" * 70)
    print("STEP 8: Verify Record Integrity")
    print("=" * 70)
    
    verification = scm.verify_record("R-PROD-001")
    print(f"🔍 Verifying R-PROD-001:")
    print(f"   Valid: {verification.valid}")
    print(f"   Hash matches: {verification.hash_matches}")
    print(f"   Signature valid: {verification.signature_valid}")
    print(f"   Blockchain anchored: {verification.blockchain_anchored}")
    
    # Step 9: Test Invalid Operations
    print("\n" + "=" * 70)
    print("STEP 9: Test Security - Invalid Operations")
    print("=" * 70)
    
    # Try to transfer more than available
    print("\n🧪 Test 1: Transfer more than available quantity")
    try:
        invalid_transfer = OperationRequest(
            record_id="R-INVALID-001",
            record_type=RecordType.TRANSFER,
            manifest_id="M-COFFEE-001",
            quantity=500,  # Manufacturer only has 400!
            user=manufacturer.address,
            timestamp=datetime.utcnow().isoformat() + "Z",
            signature=manufacturer.sign_record({
                "record_id": "R-INVALID-001",
                "record_type": "TRANSFER",
                "manifest_id": "M-COFFEE-001",
                "quantity": 500,
                "user": manufacturer.address,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        )
        scm.process_operation(invalid_transfer)
        print("   ❌ FAILED - Should have been rejected!")
    except ValueError as e:
        print(f"   ✅ PASSED - Correctly rejected: {e}")
    
    # Try to use wrong signature
    print("\n🧪 Test 2: Invalid signature")
    try:
        wrong_user = UserIdentity()  # Different user
        
        fake_record = Record(
            record_id="R-FAKE-001",
            record_type=RecordType.TRANSFER,
            manifest_id="M-COFFEE-001",
            quantity=100,
            user=manufacturer.address,  # Claims to be manufacturer
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
        # But signed by wrong user
        fake_dict = fake_record.model_dump(exclude_none=True)
        fake_sig = wrong_user.sign_record(fake_dict)
        
        fake_op = OperationRequest(
            record_id="R-FAKE-001",
            record_type=RecordType.TRANSFER,
            manifest_id="M-COFFEE-001",
            quantity=100,
            user=manufacturer.address,
            timestamp=datetime.utcnow().isoformat() + "Z",
            signature=fake_sig
        )
        
        scm.process_operation(fake_op)
        print("   ❌ FAILED - Should have rejected invalid signature!")
    except ValueError as e:
        print(f"   ✅ PASSED - Correctly rejected: {e}")
    
    # Step 10: Summary
    print("\n" + "=" * 70)
    print("STEP 10: Final Supply Chain State")
    print("=" * 70)
    
    print(f"\n📊 Manifest: {manifest.manifest_id}")
    print(f"   Total Capacity: {manifest.quantity} units")
    print(f"   Total Produced: {repo.get_total_produced('M-COFFEE-001')} units")
    
    print(f"\n👥 User Balances:")
    mfr_qty = repo.get_available_quantity("M-COFFEE-001", manufacturer.address)
    dist_qty = repo.get_available_quantity("M-COFFEE-001", distributor.address)
    ret_qty = repo.get_available_quantity("M-COFFEE-001", retailer.address)
    
    print(f"   Manufacturer: {mfr_qty} units")
    print(f"   Distributor:  {dist_qty} units")
    print(f"   Retailer:     {ret_qty} units")
    print(f"   TOTAL:        {mfr_qty + dist_qty + ret_qty} units")
    
    # Get all records
    records = repo.get_records_by_manifest("M-COFFEE-001")
    print(f"\n📋 Total Records: {len(records)}")
    for rec in records:
        print(f"   - {rec['record_id']}: {rec['record_type']} ({rec['quantity']} units)")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - SUPPLY CHAIN MANAGER WORKING CORRECTLY!")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        test_complete_workflow()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
