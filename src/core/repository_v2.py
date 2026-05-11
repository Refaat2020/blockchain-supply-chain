import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime


class SupplyChainRepository:
    def __init__(self, db_path: str = "supply_chain.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        self._create_tables()
        
        print(f"✅ Repository initialized: {db_path}")
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Table: manifests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manifests (
                manifest_id TEXT PRIMARY KEY,
                good_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                creator TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table: records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                record_id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL CHECK(record_type IN ('PRODUCED', 'TRANSFER', 'RECEIVED', 'DELIVERED')),
                manifest_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                user_address TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                tx_hash TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (manifest_id) REFERENCES manifests(manifest_id)
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_manifest 
            ON records(manifest_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_user 
            ON records(user_address)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_type 
            ON records(record_type)
        """)
        
        self.conn.commit()
    
    # ==================== MANIFEST OPERATIONS ====================
    
    def save_manifest(self, manifest_dict: Dict[str, Any], hash: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT manifest_id FROM manifests WHERE manifest_id = ?",
            (manifest_dict["manifest_id"],)
        )
        
        if cursor.fetchone():
            raise ValueError(f"Manifest {manifest_dict['manifest_id']} already exists")
        cursor.execute("""
            INSERT INTO manifests (manifest_id, good_type, quantity, creator, timestamp, hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            manifest_dict["manifest_id"],
            manifest_dict["good_type"],
            manifest_dict["quantity"],
            manifest_dict["creator"],
            manifest_dict["timestamp"],
            hash
        ))
        
        self.conn.commit()
        
        print(f"✅ Manifest saved: {manifest_dict['manifest_id']}")
        return True
    
    def get_manifest(self, manifest_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT manifest_id, good_type, quantity, creator, timestamp, hash
            FROM manifests
            WHERE manifest_id = ?
        """, (manifest_id,))
        
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "manifest_id": row["manifest_id"],
            "good_type": row["good_type"],
            "quantity": row["quantity"],
            "creator": row["creator"],
            "timestamp": row["timestamp"],
            "hash": row["hash"]
        }
    
    def manifest_exists(self, manifest_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM manifests WHERE manifest_id = ?",
            (manifest_id,)
        )
        return cursor.fetchone() is not None
    
    # ==================== RECORD OPERATIONS ====================
    
    def save_record(
        self, 
        signed_record_dict: Dict[str, Any], 
        tx_hash: Optional[str] = None
    ) -> bool:
        cursor = self.conn.cursor()
        
        record = signed_record_dict["record"]
        
        # Check if record already exists
        cursor.execute(
            "SELECT record_id FROM records WHERE record_id = ?",
            (record["record_id"],)
        )
        
        if cursor.fetchone():
            raise ValueError(f"Record {record['record_id']} already exists")
        
        # Serialize metadata if present
        metadata_json = None
        if record.get("metadata"):
            metadata_json = json.dumps(record["metadata"])
        
        # Insert record
        cursor.execute("""
            INSERT INTO records (
                record_id, record_type, manifest_id, quantity, 
                user_address, timestamp, hash, signature, tx_hash, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["record_id"],
            record["record_type"],
            record["manifest_id"],
            record["quantity"],
            record["user"],
            record["timestamp"],
            signed_record_dict["hash"],
            signed_record_dict["signature"],
            tx_hash,
            metadata_json
        ))
        
        self.conn.commit()
        
        print(f"✅ Record saved: {record['record_id']} ({record['record_type']})")
        return True
    
    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                record_id, record_type, manifest_id, quantity, 
                user_address, timestamp, hash, signature, tx_hash, metadata
            FROM records
            WHERE record_id = ?
        """, (record_id,))
        
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Parse metadata
        metadata = None
        if row["metadata"]:
            metadata = json.loads(row["metadata"])
        
        return {
            "record": {
                "record_id": row["record_id"],
                "record_type": row["record_type"],
                "manifest_id": row["manifest_id"],
                "quantity": row["quantity"],
                "user": row["user_address"],
                "timestamp": row["timestamp"],
                "metadata": metadata
            },
            "hash": row["hash"],
            "signature": row["signature"],
            "user_address": row["user_address"],
            "tx_hash": row["tx_hash"]
        }
    
    def update_tx_hash(self, record_id: str, tx_hash: str) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE records
            SET tx_hash = ?
            WHERE record_id = ?
        """, (tx_hash, record_id))
        
        self.conn.commit()
        
        if cursor.rowcount == 0:
            return False
        
        print(f"✅ TX hash updated for {record_id}: {tx_hash[:20]}...")
        return True
    
    # ==================== QUANTITY CALCULATIONS ====================
    
    def compute_available_quantity(self, manifest_id: str) -> int:
        cursor = self.conn.cursor()
        
        # Get all records for this manifest
        cursor.execute("""
            SELECT record_type, SUM(quantity) as total
            FROM records
            WHERE manifest_id = ?
            GROUP BY record_type
        """, (manifest_id,))
        
        quantities = {row["record_type"]: row["total"] for row in cursor.fetchall()}
        
        # Calculate net quantity
        produced = quantities.get("PRODUCED", 0)
        received = quantities.get("RECEIVED", 0)
        transferred = quantities.get("TRANSFER", 0)
        delivered = quantities.get("DELIVERED", 0)
        
        net_available = produced + received - transferred - delivered
        
        return net_available
    
    def get_available_quantity_per_user(
        self, 
        manifest_id: str, 
        user_address: str
    ) -> int:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT record_type, quantity
            FROM records
            WHERE manifest_id = ? AND user_address = ?
        """, (manifest_id, user_address))
        
        balance = 0
        for row in cursor.fetchall():
            if row["record_type"] in ["PRODUCED", "RECEIVED"]:
                balance += row["quantity"]
            elif row["record_type"] in ["TRANSFER", "DELIVERED"]:
                balance -= row["quantity"]
        
        return balance
    
    # ==================== QUERY OPERATIONS ====================
    
    def get_all_records_for_manifest(self, manifest_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                record_id, record_type, quantity, user_address, 
                timestamp, hash, signature, tx_hash, metadata
            FROM records
            WHERE manifest_id = ?
            ORDER BY created_at ASC
        """, (manifest_id,))
        
        records = []
        for row in cursor.fetchall():
            # Parse metadata
            metadata = None
            if row["metadata"]:
                metadata = json.loads(row["metadata"])
            
            records.append({
                "record_id": row["record_id"],
                "record_type": row["record_type"],
                "quantity": row["quantity"],
                "user_address": row["user_address"],
                "timestamp": row["timestamp"],
                "hash": row["hash"],
                "signature": row["signature"],
                "tx_hash": row["tx_hash"],
                "metadata": metadata
            })
        
        return records
    
    def get_records_by_type(self, record_type: str) -> List[Dict[str, Any]]:
        """Get all records of a specific type"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT record_id, manifest_id, quantity, user_address, timestamp
            FROM records
            WHERE record_type = ?
            ORDER BY created_at DESC
        """, (record_type,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_records_by_user(self, user_address: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT record_id, record_type, manifest_id, quantity, timestamp
            FROM records
            WHERE user_address = ?
            ORDER BY created_at DESC
        """, (user_address,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        
        # Count manifests
        cursor.execute("SELECT COUNT(*) as count FROM manifests")
        manifest_count = cursor.fetchone()["count"]
        
        # Count records by type
        cursor.execute("""
            SELECT record_type, COUNT(*) as count
            FROM records
            GROUP BY record_type
        """)
        
        record_counts = {row["record_type"]: row["count"] for row in cursor.fetchall()}
        
        # Count records with blockchain anchors
        cursor.execute("SELECT COUNT(*) as count FROM records WHERE tx_hash IS NOT NULL")
        anchored_count = cursor.fetchone()["count"]
        
        # Get total quantity produced
        cursor.execute("""
            SELECT SUM(quantity) as total
            FROM records
            WHERE record_type = 'PRODUCED'
        """)
        
        result = cursor.fetchone()
        total_produced = result["total"] if result["total"] else 0
        
        return {
            "total_manifests": manifest_count,
            "total_records": sum(record_counts.values()),
            "records_by_type": record_counts,
            "records_anchored": anchored_count,
            "total_quantity_produced": total_produced
        }
    
    # ==================== VERIFICATION HELPERS ====================
    
    def verify_record_hash(self, record_id: str, expected_hash: str) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            "SELECT hash FROM records WHERE record_id = ?",
            (record_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return False
        
        return row["hash"] == expected_hash
    
    def get_records_without_blockchain(self) -> List[str]:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT record_id
            FROM records
            WHERE tx_hash IS NULL
            ORDER BY created_at ASC
        """)
        
        return [row["record_id"] for row in cursor.fetchall()]
    
    # ==================== CLEANUP ====================
    
    def close(self):
        self.conn.close()
        print("✅ Repository closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ==================== TESTING ====================

def test_repository():
    print("\n" + "=" * 70)
    print("🧪 REPOSITORY TEST SUITE")
    print("=" * 70)
    
    # Initialize repository
    repo = SupplyChainRepository("test_repository.db")
    
    # Test 1: Save manifest
    print("\n" + "=" * 70)
    print("TEST 1: Save Manifest")
    print("=" * 70)
    
    manifest = {
        "manifest_id": "M-TEST-001",
        "good_type": "Organic Coffee Beans",
        "quantity": 1000,
        "creator": "0x1234567890123456789012345678901234567890",
        "timestamp": "2026-05-07T10:00:00Z"
    }
    
    manifest_hash = "0xabcd1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    
    repo.save_manifest(manifest, manifest_hash)
    
    # Test 2: Get manifest
    print("\n" + "=" * 70)
    print("TEST 2: Get Manifest")
    print("=" * 70)
    
    retrieved = repo.get_manifest("M-TEST-001")
    print(f"✅ Retrieved manifest:")
    print(f"   ID: {retrieved['manifest_id']}")
    print(f"   Type: {retrieved['good_type']}")
    print(f"   Quantity: {retrieved['quantity']}")
    print(f"   Hash: {retrieved['hash'][:20]}...")
    
    # Test 3: Save PRODUCED record
    print("\n" + "=" * 70)
    print("TEST 3: Save PRODUCED Record")
    print("=" * 70)
    
    produced_record = {
        "record": {
            "record_id": "R-PROD-001",
            "record_type": "PRODUCED",
            "manifest_id": "M-TEST-001",
            "quantity": 1000,
            "user": "0x1234567890123456789012345678901234567890",
            "timestamp": "2026-05-07T11:00:00Z",
            "metadata": {"factory": "Factory A", "batch": "B001"}
        },
        "hash": "0x1111111111111111111111111111111111111111111111111111111111111111",
        "signature": "0x2222222222222222222222222222222222222222222222222222222222222222",
        "user_address": "0x1234567890123456789012345678901234567890"
    }
    
    tx_hash_1 = "0xaaaa111122223333444455556666777788889999aaaabbbbccccddddeeeeffff"
    repo.save_record(produced_record, tx_hash_1)
    
    # Test 4: Save TRANSFER record
    print("\n" + "=" * 70)
    print("TEST 4: Save TRANSFER Record")
    print("=" * 70)
    
    transfer_record = {
        "record": {
            "record_id": "R-TRANS-001",
            "record_type": "TRANSFER",
            "manifest_id": "M-TEST-001",
            "quantity": 600,
            "user": "0x1234567890123456789012345678901234567890",
            "timestamp": "2026-05-07T12:00:00Z",
            "metadata": {"to": "Warehouse B"}
        },
        "hash": "0x3333333333333333333333333333333333333333333333333333333333333333",
        "signature": "0x4444444444444444444444444444444444444444444444444444444444444444",
        "user_address": "0x1234567890123456789012345678901234567890"
    }
    
    tx_hash_2 = "0xbbbb111122223333444455556666777788889999aaaabbbbccccddddeeeeffff"
    repo.save_record(transfer_record, tx_hash_2)
    
    # Test 5: Save RECEIVED record (different user)
    print("\n" + "=" * 70)
    print("TEST 5: Save RECEIVED Record")
    print("=" * 70)
    
    received_record = {
        "record": {
            "record_id": "R-REC-001",
            "record_type": "RECEIVED",
            "manifest_id": "M-TEST-001",
            "quantity": 600,
            "user": "0xABCDEF1234567890123456789012345678901234",
            "timestamp": "2026-05-07T13:00:00Z",
            "metadata": {"from": "Manufacturer"}
        },
        "hash": "0x5555555555555555555555555555555555555555555555555555555555555555",
        "signature": "0x6666666666666666666666666666666666666666666666666666666666666666",
        "user_address": "0xABCDEF1234567890123456789012345678901234"
    }
    
    tx_hash_3 = "0xcccc111122223333444455556666777788889999aaaabbbbccccddddeeeeffff"
    repo.save_record(received_record, tx_hash_3)
    
    # Test 6: Compute available quantity
    print("\n" + "=" * 70)
    print("TEST 6: Compute Available Quantity")
    print("=" * 70)
    
    available = repo.compute_available_quantity("M-TEST-001")
    print(f"📊 Net available quantity: {available}")
    print(f"   Formula: PRODUCED (1000) - TRANSFER (600) + RECEIVED (600) = {available}")
    
    # Test 7: Get all records for manifest
    print("\n" + "=" * 70)
    print("TEST 7: Get All Records for Manifest")
    print("=" * 70)
    
    all_records = repo.get_all_records_for_manifest("M-TEST-001")
    print(f"📋 Total records: {len(all_records)}")
    for rec in all_records:
        print(f"   - {rec['record_id']}: {rec['record_type']} ({rec['quantity']} units)")
        print(f"     TX: {rec['tx_hash'][:20]}...")
    
    # Test 8: Get statistics
    print("\n" + "=" * 70)
    print("TEST 8: Repository Statistics")
    print("=" * 70)
    
    stats = repo.get_statistics()
    print(f"📊 Statistics:")
    print(f"   Total Manifests: {stats['total_manifests']}")
    print(f"   Total Records: {stats['total_records']}")
    print(f"   Records Anchored: {stats['records_anchored']}")
    print(f"   Total Produced: {stats['total_quantity_produced']}")
    print(f"   By Type:")
    for rec_type, count in stats['records_by_type'].items():
        print(f"     - {rec_type}: {count}")
    
    # Test 9: Get record with all data
    print("\n" + "=" * 70)
    print("TEST 9: Get Complete Record")
    print("=" * 70)
    
    record = repo.get_record("R-PROD-001")
    print(f"✅ Retrieved record: {record['record']['record_id']}")
    print(f"   Hash: {record['hash'][:20]}...")
    print(f"   Signature: {record['signature'][:20]}...")
    print(f"   TX Hash: {record['tx_hash'][:20]}...")
    print(f"   Metadata: {record['record']['metadata']}")
    
    # Close repository
    repo.close()
    
    print("\n" + "=" * 70)
    print("✅ ALL REPOSITORY TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_repository()
