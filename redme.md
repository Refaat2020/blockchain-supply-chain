# 🔗 Blockchain-Based Supply Chain Tracking System

A complete, production-ready supply chain management system leveraging Ethereum blockchain technology for tamper-proof tracking and verification of goods throughout their lifecycle.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Ethereum](https://img.shields.io/badge/Blockchain-Ethereum-purple.svg)](https://ethereum.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Usage Examples](#usage-examples)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Security Features](#security-features)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

This project implements a **decentralized supply chain tracking system** that ensures transparency, security, and immutability of product records from production to delivery. By anchoring cryptographic hashes on the Ethereum blockchain, the system provides verifiable proof of authenticity without storing sensitive data on-chain.

### Problem Statement

Traditional supply chain systems face challenges:
- ❌ Centralized data storage vulnerable to tampering
- ❌ Lack of transparency across stakeholders
- ❌ No cryptographic proof of authenticity
- ❌ Difficulty tracking goods across multiple parties

### Our Solution

✅ **Cryptographic Authentication**: ECDSA digital signatures  
✅ **Blockchain Anchoring**: Immutable record of hashes on Ethereum  
✅ **Off-chain Storage**: Efficient SQLite repository for detailed data  
✅ **Zero-Trust Architecture**: All security relies on cryptography, not trusted parties  
✅ **Complete Verification**: Hash integrity + signature validation + blockchain proof  

---

## 🚀 Key Features

### 🔐 Cryptographic Security
- **ECDSA Key Pairs**: Each user has a unique Ethereum address
- **Digital Signatures**: All records cryptographically signed
- **SHA-256 Hashing**: Tamper-evident data integrity
- **Challenge-Response Authentication**: JWT token-based sessions

### ⛓️ Blockchain Integration
- **Ethereum Smart Contract**: Solidity-based hash anchoring
- **On-chain Verification**: Anyone can verify record authenticity
- **Timestamping**: Immutable proof of when records were created
- **Event Logs**: Transparent audit trail

### 📊 Supply Chain Operations
- **PRODUCE**: Record production of goods
- **TRANSFER**: Track goods movement between parties
- **RECEIVE**: Confirm receipt of goods
- **DELIVER**: Final delivery to end customer

### ✅ Comprehensive Verification
- Hash integrity checking
- Digital signature validation
- Blockchain proof verification
- Quantity consistency auditing

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Users                                    │
│              (Producer, Transporter, Receiver)                   │
│                  ECDSA Key Pairs                                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ HTTP/REST API (JWT Authentication)
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│              Supply Chain Manager (FastAPI)                      │
│  • User Authentication                                           │
│  • Operation Processing (PRODUCE/TRANSFER/RECEIVE/DELIVER)      │
│  • Signature Verification                                        │
│  • Quantity Validation                                           │
└─────────┬───────────────────────────┬───────────────────────────┘
          │                           │
          ↓                           ↓
┌─────────────────────┐    ┌──────────────────────────────────────┐
│   Repository        │    │   Ethereum Blockchain                 │
│   (SQLite)          │    │   Smart Contract                      │
│                     │    │                                       │
│ • Manifests         │    │ • Hash Anchoring                      │
│ • Records           │    │ • Event Logs                          │
│ • Signatures        │    │ • Timestamp Proof                     │
│ • Metadata          │    │ • Public Verification                 │
└─────────────────────┘    └───────────────────────────────────────┘
```

### Data Flow

1. **User generates** record and signs with private key
2. **Supply Chain Manager** validates signature and quantity
3. **Repository** stores complete record with signature
4. **Hash computed** from record data (SHA-256)
5. **Hash anchored** on Ethereum blockchain
6. **Transaction hash** stored for verification
7. **Anyone can verify** by comparing local hash with on-chain hash

---

## 🛠️ Technologies Used

### Blockchain & Cryptography
- **Ethereum**: Blockchain platform (Sepolia testnet)
- **Solidity**: Smart contract development
- **Web3.py**: Ethereum interaction library
- **eth-account**: ECDSA cryptography

### Backend
- **Python 3.10+**: Core programming language
- **FastAPI**: High-performance REST API framework
- **SQLAlchemy**: SQL toolkit and ORM
- **Pydantic**: Data validation using Python type hints

### Security
- **PyJWT**: JSON Web Token authentication
- **cryptography**: Cryptographic recipes and primitives

### Testing
- **pytest**: Testing framework
- **requests**: HTTP library for API testing

---

## 📥 Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd blockchain-supply-chain
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- eth-account, web3 (Ethereum)
- fastapi, uvicorn (API)
- pydantic, sqlalchemy (Data)
- pyjwt, cryptography (Security)
- requests, tabulate (Testing)

---

## ⚡ Quick Start

### Run the Complete Integration Test

This demonstrates the entire system in action:

```bash
python tests/integration_test_complete.py
```

**What it does:**
1. ✅ Creates 3 users (Producer, Transporter, Receiver)
2. ✅ Authenticates all users
3. ✅ Creates manifest for 100 Books
4. ✅ Producer produces 100 books → anchored on blockchain
5. ✅ Producer transfers 20 books → anchored on blockchain
6. ✅ Receiver receives 20 books → anchored on blockchain
7. ✅ Receiver delivers 10 books → anchored on blockchain
8. ✅ Verifies all records cryptographically
9. ✅ Tests security (rejects invalid operations)
10. ✅ Prints comprehensive summary table

**Expected Output:**
```
✅ ALL TESTS PASSED - INTEGRATION SUCCESSFUL!

+--------------------+-----------+-------------------------+-------------------------+
| Record ID          | Type      | Hash                    | Blockchain TX           |
+====================+===========+=========================+=========================+
| R-PROD-...         | PRODUCED  | 0x056b771c8f7d96cd16... | 0x08bbf0798368f6cd9c... |
| R-TRANS-...        | TRANSFER  | 0x5bfaa5602b63b79e0a... | 0x8975b6bf34f892f5a3... |
| R-REC-...          | RECEIVED  | 0x87dda12436384481b1... | 0x1090d9823e9a963d6f... |
| R-DEL-...          | DELIVERED | 0xcc7f168fdb3c3017dd... | 0x2a71338d23b7a3ea83... |
+--------------------+-----------+-------------------------+-------------------------+

📊 Final Statistics:
   Total Manifests:  1
   Total Records:    4
   Records Anchored: 4
   Total Produced:   100
```

---

## 📂 Project Structure

```
blockchain-supply-chain/
│
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── LICENSE                            # MIT License
│
├── contracts/                         # Smart Contracts
│   ├── SupplyChainAnchor.sol         # Solidity contract
│   └── SupplyChainAnchor_abi.json    # Contract ABI
│
├── src/                               # Source Code
│   ├── core/                          # Core Components
│   │   ├── user_identity.py          # User cryptography & ECDSA
│   │   ├── data_structures.py        # Data models (Manifest, Record)
│   │   └── repository_v2.py          # SQLite repository
│   │
│   ├── blockchain/                    # Blockchain Integration
│   │   ├── blockchain_client.py      # Web3 Ethereum client
│   │   └── deploy_contract.py        # Contract deployment
│   │
│   ├── api/                           # REST API
│   │   ├── auth_server.py            # Authentication server
│   │   ├── auth_client.py            # Authentication client
│   │   └── supply_chain_manager.py   # Main SCM API
│   │
│   └── verification/                  # Verification System
│       └── verification_engine.py     # Complete verification workflow
│
├── tests/                             # Test Suite
│   ├── test_authentication.py        # Auth system tests
│   ├── test_integration.py           # Basic integration tests
│   ├── test_blockchain_integration.py # Blockchain tests
│   └── integration_test_complete.py  # ⭐ Main end-to-end test
│
└── data/                              # Database Files (auto-created)
    └── *.db                           # SQLite databases
```

---

## 💡 Usage Examples

### Example 1: Create User Identity

```python
from src.core.user_identity import UserIdentity

# Generate new user with ECDSA key pair
user = UserIdentity()
print(f"Address: {user.address}")
print(f"Private Key: {user.private_key}")

# Sign a record
record = {"data": "important information"}
signature = user.sign_record(record)
print(f"Signature: {signature}")
```

### Example 2: Create and Verify Record

```python
from src.core.data_structures import Record, RecordType, compute_hash
from src.core.user_identity import UserIdentity

# Create user and record
user = UserIdentity()
record = Record(
    record_id="R-001",
    record_type=RecordType.PRODUCED,
    manifest_id="M-001",
    quantity=100,
    user=user.address,
    timestamp="2026-05-08T10:00:00Z"
)

# Sign record
record_dict = record.model_dump(exclude_none=True, mode='json')
signature = user.sign_record(record_dict)
record_hash = compute_hash(record_dict)

print(f"Hash: {record_hash}")
print(f"Signature: {signature}")
```

### Example 3: Verify Record Integrity

```python
from src.verification.verification_engine import VerificationEngine
from src.core.repository_v2 import SupplyChainRepository

# Initialize
repo = SupplyChainRepository("supply_chain.db")
engine = VerificationEngine(repo)

# Verify record
result = engine.verify_record("R-001")

print(f"Hash Integrity: {result.hash_integrity}")
print(f"Signature: {result.signature}")
print(f"Blockchain Proof: {result.blockchain_proof}")
print(f"Conclusion: {result.conclusion}")
```

---

## 📡 API Documentation

### Authentication Endpoints

#### POST /auth/challenge
Request authentication challenge.

**Request:**
```json
{
  "user_address": "0x1234567890123456789012345678901234567890"
}
```

**Response:**
```json
{
  "challenge": "0xabcd1234...",
  "expires_at": "2026-05-08T10:05:00Z",
  "message": "Sign this challenge with your private key"
}
```

#### POST /auth/verify
Verify signed challenge and get JWT token.

**Request:**
```json
{
  "user_address": "0x1234567890123456789012345678901234567890",
  "challenge": "0xabcd1234...",
  "signature": "0xdef456..."
}
```

**Response:**
```json
{
  "authenticated": true,
  "user_address": "0x1234567890123456789012345678901234567890",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2026-05-09T10:00:00Z"
}
```

### Supply Chain Operations

All operations require JWT token in `Authorization: Bearer <token>` header.

#### POST /produce
Record production of goods.

#### POST /transfer
Transfer goods to another party.

#### POST /receive
Confirm receipt of goods.

#### POST /deliver
Record final delivery.

#### GET /verify/{record_id}
Verify record integrity (public endpoint).

---

## 🧪 Testing

### Run All Tests

```bash
# Run main integration test
python tests/integration_test_complete.py

# Run authentication tests
python tests/test_authentication.py

# Run blockchain integration tests
python tests/test_blockchain_integration.py
```

### Test Coverage

- ✅ User identity and cryptography
- ✅ Digital signature generation and verification
- ✅ Record creation and hashing
- ✅ Authentication (challenge-response, JWT)
- ✅ Supply chain operations (all 4 types)
- ✅ Blockchain anchoring (mock)
- ✅ Complete verification workflow
- ✅ Quantity consistency validation
- ✅ Security (replay attacks, invalid signatures)

---

## 🔒 Security Features

### Cryptographic Security

1. **ECDSA Key Pairs**: secp256k1 curve (Ethereum-compatible)
2. **Digital Signatures**: Every record signed by user
3. **SHA-256 Hashing**: Canonical JSON serialization
4. **Replay Protection**: Single-use challenges
5. **JWT Authentication**: Secure session management

### Blockchain Security

1. **Immutable Anchoring**: Hashes stored on Ethereum
2. **Timestamping**: Block number provides proof-of-time
3. **Public Verification**: Anyone can verify without trusting SCM
4. **No Sensitive Data On-Chain**: Only hashes, never full records

### Application Security

1. **Zero-Trust Architecture**: SCM is not trusted authority
2. **Signature Verification**: All operations validated cryptographically
3. **Quantity Validation**: Prevents double-spending of goods
4. **Challenge Expiration**: 60-second timeout
5. **Error Handling**: Proper validation and error messages

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use type hints
- Add docstrings to all functions
- Write tests for new features


## 🗺️ Roadmap

### Current Version (v1.0)
- ✅ Core supply chain operations
- ✅ Blockchain anchoring
- ✅ Complete verification
- ✅ JWT authentication

### Future Enhancements (v2.0)
- [ ] Real Sepolia testnet deployment
- [ ] Web dashboard UI
- [ ] Mobile app (iOS/Android)
- [ ] IPFS integration for large files
- [ ] Multi-chain support (Polygon, BSC)
- [ ] Advanced analytics and reporting
- [ ] API rate limiting
- [ ] GraphQL API

