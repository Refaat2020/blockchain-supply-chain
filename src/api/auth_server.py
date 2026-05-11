

import secrets
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from eth_account.messages import encode_defunct
from web3 import Web3


# ==================== CONFIGURATION ====================

# JWT Configuration
JWT_SECRET_KEY = secrets.token_hex(32)  # In production, load from environment
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Challenge Configuration
CHALLENGE_EXPIRATION_SECONDS = 60
CHALLENGE_LENGTH = 32  # 32 bytes = 64 hex characters


# ==================== REQUEST/RESPONSE MODELS ====================

class ChallengeRequest(BaseModel):
    user_address: str = Field(
        ...,
        pattern=r"^0x[a-fA-F0-9]{40}$",
        description="Ethereum address of the user"
    )


class ChallengeResponse(BaseModel):
    challenge: str = Field(..., description="Random nonce to sign")
    expires_at: str = Field(...,
                            description="ISO timestamp when challenge expires")
    message: str = Field(..., description="Human-readable message")


class VerifyRequest(BaseModel):
    user_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    challenge: str = Field(..., description="The challenge that was issued")
    signature: str = Field(..., description="ECDSA signature of the challenge")


class VerifyResponse(BaseModel):
    authenticated: bool
    user_address: str
    token: str = Field(..., description="JWT session token")
    expires_at: str
    message: str


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str


# ==================== AUTHENTICATION MANAGER ====================

class AuthenticationManager:
    def __init__(
        self,
        jwt_secret: str = JWT_SECRET_KEY,
        challenge_ttl: int = CHALLENGE_EXPIRATION_SECONDS,
        token_ttl_hours: int = JWT_EXPIRATION_HOURS
    ):
        self.jwt_secret = jwt_secret
        self.challenge_ttl = challenge_ttl
        self.token_ttl = token_ttl_hours

        # In-memory storage (in production, use Redis)
        # user_address -> challenge_data
        self.active_challenges: Dict[str, Dict] = {}
        self.used_challenges: set = set()  # Prevent replay attacks

    # ==================== CHALLENGE GENERATION ====================

    def generate_challenge(self, user_address: str) -> ChallengeResponse:
        # Generate cryptographically secure random nonce
        nonce_bytes = secrets.token_bytes(CHALLENGE_LENGTH)
        challenge = "0x" + nonce_bytes.hex()

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(seconds=self.challenge_ttl)

        # Store challenge
        self.active_challenges[user_address] = {
            "challenge": challenge,
            "expires_at": expires_at,
            "created_at": datetime.utcnow()
        }

        print(f"🔐 Challenge generated for {user_address[:20]}...")
        print(f"   Challenge: {challenge[:20]}...")
        print(f"   Expires: {expires_at.isoformat()}")

        return ChallengeResponse(
            challenge=challenge,
            expires_at=expires_at.isoformat() + "Z",
            message="Sign this challenge with your private key to authenticate"
        )

    # ==================== SIGNATURE VERIFICATION ====================

    def verify_challenge(
        self,
        user_address: str,
        challenge: str,
        signature: str
    ) -> Tuple[bool, Optional[str]]:
        # Step 1: Check if challenge exists
        if user_address not in self.active_challenges:
            print(f"❌ No challenge found for {user_address[:20]}...")
            return False, None

        stored_data = self.active_challenges[user_address]

        # Step 2: Check challenge matches
        if stored_data["challenge"] != challenge:
            print(f"❌ Challenge mismatch for {user_address[:20]}...")
            return False, None

        # Step 3: Check not expired
        if datetime.utcnow() > stored_data["expires_at"]:
            print(f"❌ Challenge expired for {user_address[:20]}...")
            del self.active_challenges[user_address]
            return False, None

        # Step 4: Check not already used (replay protection)
        challenge_hash = hashlib.sha256(challenge.encode()).hexdigest()
        if challenge_hash in self.used_challenges:
            print(
                f"❌ Challenge already used (replay attack) for {user_address[:20]}...")
            return False, None

        # Step 5: Verify ECDSA signature
        try:
            # Create message hash (Ethereum signed message format)
            challenge_data = {"challenge": challenge}

            # Serialize to JSON for signing
            import json
            message_json = json.dumps(
                challenge_data, sort_keys=True, separators=(',', ':'))
            message_hash = hashlib.sha256(
                message_json.encode('utf-8')).digest()

            # Create Ethereum signed message
            message = encode_defunct(message_hash)

            # Recover address from signature
            from eth_account import Account
            recovered_address = Account.recover_message(
                message, signature=signature)

            # Verify address matches
            if recovered_address.lower() != user_address.lower():
                print(
                    f"❌ Signature verification failed for {user_address[:20]}...")
                print(f"   Expected: {user_address}")
                print(f"   Recovered: {recovered_address}")
                return False, None

        except Exception as e:
            print(f"❌ Signature verification error: {e}")
            return False, None

        # Step 6: Mark challenge as used
        self.used_challenges.add(challenge_hash)
        del self.active_challenges[user_address]

        # Step 7: Issue JWT token
        token = self._create_jwt_token(user_address)

        print(f"✅ Authentication successful for {user_address[:20]}...")

        return True, token

    # ==================== JWT TOKEN MANAGEMENT ====================

    def _create_jwt_token(self, user_address: str) -> str:
        # Token expiration
        expires_at = datetime.utcnow() + timedelta(hours=self.token_ttl)

        # JWT payload
        payload = {
            "user_address": user_address,
            "iat": datetime.utcnow(),  # Issued at
            "exp": expires_at,  # Expiration
            "jti": secrets.token_hex(16)  # Unique token ID
        }

        # Sign token
        token = jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

        return token

    def verify_token(self, token: str) -> Optional[str]:
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[JWT_ALGORITHM]
            )

            user_address = payload.get("user_address")

            if not user_address:
                return None

            return user_address

        except jwt.ExpiredSignatureError:
            print("❌ Token expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"❌ Invalid token: {e}")
            return None

    # ==================== CLEANUP ====================

    def cleanup_expired_challenges(self):
        now = datetime.utcnow()
        expired = [
            addr for addr, data in self.active_challenges.items()
            if data["expires_at"] < now
        ]

        for addr in expired:
            del self.active_challenges[addr]

        if expired:
            print(f"🧹 Cleaned up {len(expired)} expired challenges")

    def get_statistics(self) -> Dict:
        """Get authentication statistics"""
        return {
            "active_challenges": len(self.active_challenges),
            "used_challenges": len(self.used_challenges),
            "jwt_algorithm": JWT_ALGORITHM,
            "challenge_ttl_seconds": self.challenge_ttl,
            "token_ttl_hours": self.token_ttl
        }


# ==================== FASTAPI APPLICATION ====================

app = FastAPI(
    title="Supply Chain Authentication API",
    description="Mutual authentication with challenge-response protocol",
    version="1.0.0"
)

# Initialize authentication manager
auth_manager = AuthenticationManager()

# Security scheme for Swagger UI
security = HTTPBearer()


# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post(
    "/auth/challenge",
    response_model=ChallengeResponse,
    summary="Step 1: Request authentication challenge"
)
async def get_challenge(request: ChallengeRequest):
    try:
        # Clean up expired challenges
        auth_manager.cleanup_expired_challenges()

        # Generate challenge
        response = auth_manager.generate_challenge(request.user_address)

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate challenge: {str(e)}"
        )


@app.post(
    "/auth/verify",
    response_model=VerifyResponse,
    summary="Step 2: Verify signed challenge"
)
async def verify_challenge(request: VerifyRequest):
    # Verify signature
    success, token = auth_manager.verify_challenge(
        request.user_address,
        request.challenge,
        request.signature
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Invalid signature or expired challenge."
        )

    # Calculate token expiration
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)

    return VerifyResponse(
        authenticated=True,
        user_address=request.user_address,
        token=token,
        expires_at=expires_at.isoformat() + "Z",
        message="Authentication successful. Use the token in Authorization header."
    )


# ==================== AUTHENTICATION MIDDLEWARE ====================

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    token = credentials.credentials

    # Verify token
    user_address = auth_manager.verify_token(token)

    if not user_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please authenticate again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user_address


# ==================== PROTECTED ENDPOINTS (EXAMPLES) ====================

@app.get("/")
async def root():
    return {
        "service": "Supply Chain Authentication API",
        "version": "1.0.0",
        "endpoints": {
            "POST /auth/challenge": "Request authentication challenge",
            "POST /auth/verify": "Verify signed challenge and get JWT token",
            "GET /protected/profile": "Example protected endpoint"
        }
    }


@app.get(
    "/protected/profile",
    summary="Get user profile (protected)"
)
async def get_profile(user_address: str = Depends(verify_token)):
    return {
        "user_address": user_address,
        "message": f"Welcome, {user_address}!",
        "authenticated": True
    }


@app.get(
    "/protected/stats",
    summary="Get authentication statistics (protected)"
)
async def get_stats(user_address: str = Depends(verify_token)):
    """Get authentication system statistics"""
    stats = auth_manager.get_statistics()
    stats["requesting_user"] = user_address
    return stats


# ==================== TESTING ENDPOINT ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn

    print("\n🔐 MUTUAL AUTHENTICATION SERVER")
    print("=" * 70)
    print("Starting authentication server...")
    print("API Docs: http://localhost:8000/docs")
    print("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=8000)
