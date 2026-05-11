import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import our modules
from data_structures import (
    GoodsManifest, Record, SignedRecord, RecordType,
    compute_hash, to_signed_record, verify_signed_record
)
from user_identity import UserIdentity, SignatureVerifier
from repository import SupplyChainRepository


# ==================== REQUEST/RESPONSE MODELS ====================

class ManifestCreateRequest(BaseModel):
    manifest_id: str
    good_type: str
    quantity: int = Field(gt=0)
    creator: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    timestamp: str


class OperationRequest(BaseModel):
    record_id: str
    record_type: RecordType
    manifest_id: str
    quantity: int = Field(gt=0)
    user: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    timestamp: str
    signature: str  # Signature of the entire record
    metadata: Optional[Dict] = None


class ChallengeRequest(BaseModel):
    user_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")


class ChallengeResponse(BaseModel):
    challenge: str
    expires_at: str


class AuthRequest(BaseModel):
    user_address: str
    challenge: str
    signature: str


class OperationResponse(BaseModel):
    success: bool
    record_id: str
    record_hash: str
    blockchain_tx_hash: str
    message: str


class VerificationResponse(BaseModel):
    record_id: str
    valid: bool
    hash_matches: bool
    signature_valid: bool
    blockchain_anchored: bool
    blockchain_tx_hash: Optional[str]
    details: Dict


# ==================== BLOCKCHAIN SIMULATOR ====================

class BlockchainSimulator:
    def __init__(self):
        self.block_number = 1000000
        self.anchored_hashes = {}

    def anchor_hash(self, record_hash: str) -> Dict[str, any]:
        # Simulate transaction hash
        tx_hash = "0x" + hashlib.sha256(
            (record_hash + str(datetime.utcnow())).encode()
        ).hexdigest()

        # Simulate block mining
        self.block_number += 1

        # Store anchor
        self.anchored_hashes[record_hash] = {
            "tx_hash": tx_hash,
            "block_number": self.block_number,
            "timestamp": datetime.utcnow().isoformat()
        }

        return {
            "tx_hash": tx_hash,
            "block_number": self.block_number
        }

    def verify_anchor(self, record_hash: str) -> Optional[Dict]:
        """Verify if a hash is anchored on blockchain"""
        return self.anchored_hashes.get(record_hash)


# ==================== AUTHENTICATION MANAGER ====================

class AuthenticationManager:
    def __init__(self, challenge_ttl_seconds: int = 300):
        # user_address -> {challenge, expires_at}
        self.challenges: Dict[str, Dict] = {}
        # user_address -> expires_at
        self.authenticated_users: Dict[str, datetime] = {}
        self.challenge_ttl = challenge_ttl_seconds
        self.session_ttl = 3600  # 1 hour

    def generate_challenge(self, user_address: str) -> ChallengeResponse:
        # Generate random 32-byte challenge
        challenge = secrets.token_hex(32)
        expires_at = datetime.utcnow() + timedelta(seconds=self.challenge_ttl)

        self.challenges[user_address] = {
            "challenge": challenge,
            "expires_at": expires_at
        }

        return ChallengeResponse(
            challenge=challenge,
            expires_at=expires_at.isoformat()
        )

    def verify_challenge(
        self,
        user_address: str,
        challenge: str,
        signature: str
    ) -> bool:
        # Check if challenge exists
        if user_address not in self.challenges:
            return False

        stored_challenge = self.challenges[user_address]

        # Check challenge matches
        if stored_challenge["challenge"] != challenge:
            return False

        # Check not expired
        if datetime.utcnow() > stored_challenge["expires_at"]:
            del self.challenges[user_address]
            return False

        # Verify signature
        challenge_data = {"challenge": challenge}
        verifier = SignatureVerifier()

        if not verifier.verify_signature(challenge_data, signature, user_address):
            return False

        # Authentication successful
        del self.challenges[user_address]
        self.authenticated_users[user_address] = datetime.utcnow() + timedelta(
            seconds=self.session_ttl
        )

        return True

    def is_authenticated(self, user_address: str) -> bool:
        if user_address not in self.authenticated_users:
            return False

        # Check if session expired
        if datetime.utcnow() > self.authenticated_users[user_address]:
            del self.authenticated_users[user_address]
            return False

        return True


# ==================== SUPPLY CHAIN MANAGER ====================

class SupplyChainManager:

    def __init__(self, repository: SupplyChainRepository, blockchain: BlockchainSimulator):
        self.repo = repository
        self.blockchain = blockchain
        self.verifier = SignatureVerifier()

    def create_manifest(self, manifest: GoodsManifest) -> bool:
        # Check if manifest already exists
        if self.repo.manifest_exists(manifest.manifest_id):
            raise ValueError(f"Manifest {manifest.manifest_id} already exists")

        # Store in repository
        success = self.repo.create_manifest(manifest.model_dump())

        if not success:
            raise ValueError("Failed to create manifest")

        return True

    def process_operation(self, operation: OperationRequest) -> OperationResponse:
        # 1. Verify manifest exists
        manifest = self.repo.get_manifest(operation.manifest_id)
        if not manifest:
            raise ValueError(f"Manifest {operation.manifest_id} not found")

        # 2. Create Record object
        record = Record(
            record_id=operation.record_id,
            record_type=operation.record_type,
            manifest_id=operation.manifest_id,
            quantity=operation.quantity,
            user=operation.user,
            timestamp=operation.timestamp,
            metadata=operation.metadata
        )

        # 3. Compute hash
        record_dict = record.model_dump(exclude_none=True)
        record_hash = compute_hash(record_dict)

        # 4. Verify signature
        if not self.verifier.verify_signature(
            record_dict,
            operation.signature,
            operation.user
        ):
            raise ValueError("Invalid signature")

        # 5. Validate quantity constraints
        self._validate_quantity(
            operation.record_type,
            operation.manifest_id,
            operation.user,
            operation.quantity,
            manifest["quantity"]
        )

        # 6. Store record in repository
        self.repo.create_record(
            record_dict,
            record_hash,
            operation.signature,
            operation.user
        )

        # 7. Anchor hash on blockchain
        anchor_result = self.blockchain.anchor_hash(record_hash)

        # 8. Update repository with blockchain tx
        self.repo.anchor_record_on_blockchain(
            operation.record_id,
            anchor_result["tx_hash"],
            anchor_result["block_number"]
        )

        return OperationResponse(
            success=True,
            record_id=operation.record_id,
            record_hash=record_hash,
            blockchain_tx_hash=anchor_result["tx_hash"],
            message=f"{operation.record_type} operation completed successfully"
        )

    def _validate_quantity(
        self,
        record_type: RecordType,
        manifest_id: str,
        user_address: str,
        requested_qty: int,
        manifest_total_qty: int
    ):
        if record_type == RecordType.PRODUCED:
            # Check total produced doesn't exceed manifest limit
            total_produced = self.repo.get_total_produced(manifest_id)
            if total_produced + requested_qty > manifest_total_qty:
                raise ValueError(
                    f"Cannot produce {requested_qty} units. "
                    f"Would exceed manifest limit of {manifest_total_qty}"
                )

        elif record_type in [RecordType.TRANSFER, RecordType.DELIVERED]:
            # Check user has sufficient available quantity
            available = self.repo.get_available_quantity(
                manifest_id, user_address)
            if available < requested_qty:
                raise ValueError(
                    f"Insufficient quantity. Available: {available}, "
                    f"Requested: {requested_qty}"
                )

        # RECEIVED has no constraint (receiving from someone else)

    def verify_record(self, record_id: str) -> VerificationResponse:
        # Get record from repository
        stored_record = self.repo.get_record(record_id)
        if not stored_record:
            raise ValueError(f"Record {record_id} not found")

        # Reconstruct Record object
        record = Record(**stored_record["record"])
        signed_record = SignedRecord(
            record=record,
            hash=stored_record["hash"],
            signature=stored_record["signature"],
            user_address=stored_record["user_address"]
        )

        # Verify cryptographic integrity
        is_valid = verify_signed_record(signed_record)

        # Check hash
        record_dict = record.model_dump(exclude_none=True)
        computed_hash = compute_hash(record_dict)
        hash_matches = computed_hash == stored_record["hash"]

        # Check signature
        signature_valid = self.verifier.verify_signature(
            record_dict,
            stored_record["signature"],
            stored_record["user_address"]
        )

        # Check blockchain anchor
        blockchain_anchored = stored_record.get("blockchain_anchored", False)
        blockchain_tx_hash = stored_record.get("blockchain_tx_hash")

        return VerificationResponse(
            record_id=record_id,
            valid=is_valid and hash_matches and signature_valid,
            hash_matches=hash_matches,
            signature_valid=signature_valid,
            blockchain_anchored=blockchain_anchored,
            blockchain_tx_hash=blockchain_tx_hash,
            details={
                "record_hash": stored_record["hash"],
                "computed_hash": computed_hash,
                "signer_address": stored_record["user_address"],
                "record_type": stored_record["record"]["record_type"],
                "manifest_id": stored_record["record"]["manifest_id"],
                "quantity": stored_record["record"]["quantity"]
            }
        )


# ==================== FASTAPI APPLICATION ====================

# Initialize components
app = FastAPI(
    title="Supply Chain Manager API",
    description="Decentralized Supply Chain Tracking System",
    version="1.0.0"
)

repository = SupplyChainRepository("supply_chain.db")
blockchain = BlockchainSimulator()
scm = SupplyChainManager(repository, blockchain)
auth_manager = AuthenticationManager()


# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Supply Chain Manager",
        "version": "1.0.0",
        "blockchain": "Ethereum Sepolia (Simulated)"
    }


@app.post("/auth/challenge")
async def get_challenge(request: ChallengeRequest) -> ChallengeResponse:
    return auth_manager.generate_challenge(request.user_address)


@app.post("/auth/verify")
async def verify_auth(request: AuthRequest) -> Dict:
    success = auth_manager.verify_challenge(
        request.user_address,
        request.challenge,
        request.signature
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    return {
        "authenticated": True,
        "user_address": request.user_address,
        "message": "Authentication successful"
    }


def get_authenticated_user(x_user_address: str = Header(...)) -> str:
    if not auth_manager.is_authenticated(x_user_address):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please authenticate first."
        )
    return x_user_address


@app.post("/manifest", dependencies=[Depends(get_authenticated_user)])
async def create_manifest(manifest: GoodsManifest) -> Dict:
    try:
        scm.create_manifest(manifest)

        return {
            "success": True,
            "manifest_id": manifest.manifest_id,
            "message": "Manifest created successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/produce", dependencies=[Depends(get_authenticated_user)])
async def produce_goods(operation: OperationRequest) -> OperationResponse:
    if operation.record_type != RecordType.PRODUCED:
        raise HTTPException(
            status_code=400,
            detail="This endpoint only accepts PRODUCED operations"
        )

    try:
        return scm.process_operation(operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/transfer", dependencies=[Depends(get_authenticated_user)])
async def transfer_goods(operation: OperationRequest) -> OperationResponse:
    if operation.record_type != RecordType.TRANSFER:
        raise HTTPException(
            status_code=400,
            detail="This endpoint only accepts TRANSFER operations"
        )

    try:
        return scm.process_operation(operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/receive", dependencies=[Depends(get_authenticated_user)])
async def receive_goods(operation: OperationRequest) -> OperationResponse:
    if operation.record_type != RecordType.RECEIVED:
        raise HTTPException(
            status_code=400,
            detail="This endpoint only accepts RECEIVED operations"
        )

    try:
        return scm.process_operation(operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/deliver", dependencies=[Depends(get_authenticated_user)])
async def deliver_goods(operation: OperationRequest) -> OperationResponse:
    if operation.record_type != RecordType.DELIVERED:
        raise HTTPException(
            status_code=400,
            detail="This endpoint only accepts DELIVERED operations"
        )

    try:
        return scm.process_operation(operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/verify/{record_id}")
async def verify_record(record_id: str) -> VerificationResponse:
    try:
        return scm.verify_record(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/manifest/{manifest_id}")
async def get_manifest(manifest_id: str) -> Dict:
    manifest = repository.get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return manifest


@app.get("/records/{manifest_id}")
async def get_records_by_manifest(manifest_id: str) -> List[Dict]:
    records = repository.get_records_by_manifest(manifest_id)
    return records


@app.get("/quantity/{manifest_id}/{user_address}")
async def get_available_quantity(manifest_id: str, user_address: str) -> Dict:
    quantity = repository.get_available_quantity(manifest_id, user_address)
    return {
        "manifest_id": manifest_id,
        "user_address": user_address,
        "available_quantity": quantity
    }


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn

    print("\n🏭 SUPPLY CHAIN MANAGER STARTING")
    print("=" * 70)
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/")
    print("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=8000)
