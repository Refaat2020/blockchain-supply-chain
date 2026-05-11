import json
import os
from typing import Dict, Any, Optional, Tuple
from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # Newer versions of web3.py
    from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
from eth_account import Account


class BlockchainAnchorClient:

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        abi_path: str = "/home/claude/contracts/SupplyChainAnchor_abi.json",
        chain_id: int = 11155111  # Sepolia testnet
    ):
        # Connect to Ethereum node
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Add PoA middleware for testnets like Sepolia (if needed)
        try:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except:
            pass  # Skip if middleware not needed or already injected

        # Verify connection
        if not self.w3.is_connected():
            raise ConnectionError(
                f"Failed to connect to Ethereum node at {rpc_url}")

        print(f"✅ Connected to Ethereum node")
        print(f"   Chain ID: {self.w3.eth.chain_id}")
        print(f"   Latest block: {self.w3.eth.block_number}")

        # Load contract ABI
        with open(abi_path, 'r') as f:
            self.contract_abi = json.load(f)

        # Initialize contract
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self.contract_abi
        )

        self.chain_id = chain_id

        print(f"✅ Contract loaded at {self.contract_address}")

    # ==================== ANCHORING FUNCTIONS ====================

    def anchor_hash(
        self,
        record_id: str,
        hash_hex: str,
        private_key: str
    ) -> str:
        # Ensure hash has 0x prefix and is bytes32
        if not hash_hex.startswith('0x'):
            hash_hex = '0x' + hash_hex

        # Convert to bytes32
        record_hash_bytes = bytes.fromhex(hash_hex[2:])

        # Get account from private key
        account = Account.from_key(private_key)

        print(f"\n📤 Anchoring record: {record_id}")
        print(f"   Hash: {hash_hex[:20]}...")
        print(f"   From: {account.address}")

        # Build transaction
        nonce = self.w3.eth.get_transaction_count(account.address)

        # Estimate gas
        try:
            gas_estimate = self.contract.functions.anchorRecord(
                record_id,
                record_hash_bytes
            ).estimate_gas({'from': account.address})
        except Exception as e:
            raise ValueError(f"Transaction would fail: {e}")

        # Get current gas price
        gas_price = self.w3.eth.gas_price

        # Build transaction
        transaction = self.contract.functions.anchorRecord(
            record_id,
            record_hash_bytes
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': gas_estimate + 10000,  # Add buffer
            'gasPrice': gas_price,
            'nonce': nonce,
            'from': account.address
        })

        # Sign transaction
        signed_txn = self.w3.eth.account.sign_transaction(
            transaction,
            private_key=private_key
        )

        # Send transaction
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = tx_hash.hex()

        print(f"   TX Hash: {tx_hash_hex}")
        print(f"   Waiting for confirmation...")

        # Wait for transaction receipt
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt['status'] == 1:
            print(f"   ✅ Anchored in block {tx_receipt['blockNumber']}")
            print(f"   Gas used: {tx_receipt['gasUsed']}")
        else:
            print(f"   ❌ Transaction failed")
            raise Exception("Transaction failed")

        return tx_hash_hex

    # ==================== RETRIEVAL FUNCTIONS ====================

    def retrieve_hash(self, record_id: str) -> str:
        try:
            # Call contract (read-only, no gas needed)
            hash_bytes = self.contract.functions.getRecord(record_id).call()
            hash_hex = '0x' + hash_bytes.hex()

            print(f"\n🔍 Retrieved hash for {record_id}")
            print(f"   Hash: {hash_hex}")

            return hash_hex

        except Exception as e:
            raise ValueError(f"Record not found or error: {e}")

    def has_record(self, record_id: str) -> bool:
        return self.contract.functions.hasRecord(record_id).call()

    # ==================== VERIFICATION FUNCTIONS ====================

    def verify_on_chain(
        self,
        record_id: str,
        expected_hash: str
    ) -> Tuple[bool, Dict[str, Any]]:
        # Ensure expected hash has 0x prefix
        if not expected_hash.startswith('0x'):
            expected_hash = '0x' + expected_hash

        print(f"\n🔍 Verifying record: {record_id}")
        print(f"   Expected hash: {expected_hash[:20]}...")

        # Check if record exists
        if not self.has_record(record_id):
            print(f"   ❌ Record not found on-chain")
            return False, {
                "status": "NOT_FOUND",
                "record_id": record_id,
                "expected_hash": expected_hash,
                "on_chain_hash": None,
                "match": False
            }

        # Retrieve on-chain hash
        try:
            on_chain_hash = self.retrieve_hash(record_id)
        except Exception as e:
            return False, {
                "status": "ERROR",
                "record_id": record_id,
                "error": str(e)
            }

        # Compare hashes (case-insensitive)
        is_valid = on_chain_hash.lower() == expected_hash.lower()

        status = "VALID" if is_valid else "INVALID"
        symbol = "✅" if is_valid else "❌"

        print(f"   On-chain hash: {on_chain_hash[:20]}...")
        print(f"   {symbol} Verification: {status}")

        return is_valid, {
            "status": status,
            "record_id": record_id,
            "expected_hash": expected_hash,
            "on_chain_hash": on_chain_hash,
            "match": is_valid
        }

    # ==================== TRANSACTION DETAILS ====================

    def get_transaction_details(self, tx_hash: str) -> Dict[str, Any]:
        # Ensure tx_hash has 0x prefix
        if not tx_hash.startswith('0x'):
            tx_hash = '0x' + tx_hash

        print(f"\n📋 Getting transaction details...")
        print(f"   TX Hash: {tx_hash}")

        # Get transaction receipt
        try:
            tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception as e:
            raise ValueError(f"Transaction not found: {e}")

        # Get transaction details
        tx = self.w3.eth.get_transaction(tx_hash)

        # Get block details for timestamp
        block = self.w3.eth.get_block(tx_receipt['blockNumber'])

        # Calculate confirmations
        latest_block = self.w3.eth.block_number
        confirmations = latest_block - tx_receipt['blockNumber'] + 1

        details = {
            "tx_hash": tx_hash,
            "block_number": tx_receipt['blockNumber'],
            "confirmations": confirmations,
            "status": "SUCCESS" if tx_receipt['status'] == 1 else "FAILED",
            "gas_used": tx_receipt['gasUsed'],
            "gas_price": tx['gasPrice'],
            "from_address": tx['from'],
            "to_address": tx['to'],
            "timestamp": block['timestamp'],
            "block_hash": block['hash'].hex()
        }

        print(f"   Block: {details['block_number']}")
        print(f"   Confirmations: {details['confirmations']}")
        print(f"   Status: {details['status']}")
        print(f"   Gas used: {details['gas_used']}")

        return details

    # ==================== CONTRACT INFO ====================

    def get_total_records(self) -> int:
        return self.contract.functions.getTotalRecords().call()

    def get_contract_owner(self) -> str:
        return self.contract.functions.getOwner().call()

    # ==================== EVENT MONITORING ====================

    def get_anchor_events(
        self,
        from_block: int = 0,
        to_block: str = 'latest'
    ) -> list:
        event_filter = self.contract.events.RecordAnchored.create_filter(
            fromBlock=from_block,
            toBlock=to_block
        )

        events = event_filter.get_all_entries()

        result = []
        for event in events:
            result.append({
                "record_id": event['args']['recordId'],
                "record_hash": '0x' + event['args']['recordHash'].hex(),
                "timestamp": event['args']['timestamp'],
                "anchored_by": event['args']['anchoredBy'],
                "block_number": event['blockNumber'],
                "tx_hash": event['transactionHash'].hex()
            })

        return result


# ==================== LOCAL TESTING (Anvil/Hardhat) ====================

class LocalBlockchainClient(BlockchainAnchorClient):
    def __init__(
        self,
        contract_address: str,
        rpc_url: str = "http://127.0.0.1:8545",
        abi_path: str = "/home/claude/contracts/SupplyChainAnchor_abi.json"
    ):
        super().__init__(
            rpc_url=rpc_url,
            contract_address=contract_address,
            abi_path=abi_path,
            chain_id=1337  # Default for local nodes
        )

    def get_test_account(self, index: int = 0) -> Tuple[str, str]:
        accounts = self.w3.eth.accounts
        if index >= len(accounts):
            raise ValueError(f"Account index {index} not available")

        address = accounts[index]
        balance = self.w3.eth.get_balance(address)

        print(f"\n👤 Test Account #{index}")
        print(f"   Address: {address}")
        print(f"   Balance: {self.w3.from_wei(balance, 'ether')} ETH")

        # Note: Private keys not directly accessible from node
        # For Anvil, use: anvil --accounts 10
        # Default Anvil private key for account 0:
        default_private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

        return address, default_private_key


# ==================== USAGE EXAMPLES ====================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("⛓️  BLOCKCHAIN ANCHORING CLIENT")
    print("=" * 70)

    print("\n📝 This module provides:")
    print("   1. anchor_hash() - Anchor record hashes on blockchain")
    print("   2. retrieve_hash() - Retrieve anchored hashes")
    print("   3. verify_on_chain() - Verify integrity")
    print("   4. get_transaction_details() - Get TX info")

    print("\n🔧 Usage Example:")
    print("""
    from blockchain_client import BlockchainAnchorClient
    
    # Initialize client
    client = BlockchainAnchorClient(
        rpc_url="https://sepolia.infura.io/v3/YOUR_KEY",
        contract_address="0xYOUR_CONTRACT_ADDRESS"
    )
    
    # Anchor a hash
    tx_hash = client.anchor_hash(
        record_id="R-PROD-001",
        hash_hex="0xabcd1234...",
        private_key="0xYOUR_PRIVATE_KEY"
    )
    
    # Verify
    is_valid, details = client.verify_on_chain(
        "R-PROD-001",
        "0xabcd1234..."
    )
    """)

    print("\n" + "=" * 70)
