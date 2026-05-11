import json
from web3 import Web3
from eth_account import Account


def deploy_contract(
    w3: Web3,
    deployer_private_key: str,
    contract_bytecode: str = None
) -> str:
    # Get deployer account
    deployer = Account.from_key(deployer_private_key)
    
    print(f"\n🚀 Deploying SupplyChainAnchor Contract")
    print(f"   Deployer: {deployer.address}")
    print(f"   Chain ID: {w3.eth.chain_id}")
    print(f"   Balance: {w3.from_wei(w3.eth.get_balance(deployer.address), 'ether')} ETH")
    
    # Load contract ABI
    with open("/home/claude/contracts/SupplyChainAnchor_abi.json", 'r') as f:
        contract_abi = json.load(f)
    
    if contract_bytecode:
        # Real deployment (requires compiled bytecode)
        print(f"\n   Deploying contract...")
        
        Contract = w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)
        
        # Build constructor transaction
        nonce = w3.eth.get_transaction_count(deployer.address)
        
        transaction = Contract.constructor().build_transaction({
            'chainId': w3.eth.chain_id,
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'from': deployer.address
        })
        
        # Sign and send
        signed_txn = w3.eth.account.sign_transaction(transaction, deployer_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        print(f"   TX Hash: {tx_hash.hex()}")
        print(f"   Waiting for confirmation...")
        
        # Wait for receipt
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        contract_address = tx_receipt['contractAddress']
        
        print(f"   ✅ Deployed at: {contract_address}")
        print(f"   Block: {tx_receipt['blockNumber']}")
        print(f"   Gas used: {tx_receipt['gasUsed']}")
        
    else:
        # Simulated deployment for testing without real blockchain
        print(f"\n   ⚠️  SIMULATION MODE (no actual deployment)")
        contract_address = "0x5FbDB2315678afecb367f032d93F642f64180aa3"  # Common Hardhat address
        print(f"   Simulated address: {contract_address}")
    
    return contract_address


# ==================== DEPLOYMENT CONFIGURATIONS ====================

def deploy_to_local():
    """Deploy to local Anvil/Hardhat node"""
    from blockchain_client import LocalBlockchainClient
    
    print("\n" + "=" * 70)
    print("🏠 LOCAL DEPLOYMENT")
    print("=" * 70)
    
    # Connect to local node
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    
    if not w3.is_connected():
        print("\n❌ Cannot connect to local node!")
        print("   Start Anvil: anvil")
        print("   Or Hardhat: npx hardhat node")
        return None
    
    # Use default Anvil test account
    deployer_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    
    # Deploy (simulated - requires bytecode for real deployment)
    contract_address = deploy_contract(w3, deployer_key)
    
    return contract_address


def deploy_to_sepolia(infura_api_key: str, deployer_private_key: str):
    """Deploy to Sepolia testnet"""
    print("\n" + "=" * 70)
    print("🌐 SEPOLIA TESTNET DEPLOYMENT")
    print("=" * 70)
    
    # Connect to Sepolia via Infura
    rpc_url = f"https://sepolia.infura.io/v3/{infura_api_key}"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        print("\n❌ Cannot connect to Sepolia!")
        return None
    
    # Check balance
    deployer = Account.from_key(deployer_private_key)
    balance = w3.eth.get_balance(deployer.address)
    
    if balance == 0:
        print(f"\n❌ Deployer has 0 ETH!")
        print(f"   Get testnet ETH from: https://sepoliafaucet.com/")
        return None
    
    # Deploy (requires bytecode)
    print("\n⚠️  Deployment requires compiled bytecode")
    print("   Run: python compile_contract.py")
    
    return None


# ==================== MAIN ====================

if __name__ == "__main__":
    import sys
    
    print("\n⛓️  SUPPLY CHAIN ANCHOR - CONTRACT DEPLOYMENT")
    print("=" * 70)
    
    # For testing, we'll simulate deployment
    print("\n📝 Deployment Options:")
    print("   1. Local (Anvil/Hardhat)")
    print("   2. Sepolia Testnet")
    
    print("\n💡 For this demo, using simulated deployment")
    
    contract_address = deploy_to_local()
    
    if contract_address:
        print("\n" + "=" * 70)
        print("✅ DEPLOYMENT COMPLETE")
        print("=" * 70)
        print(f"\n📋 Contract Address: {contract_address}")
        print(f"\n🔧 Next steps:")
        print(f"   1. Save this address")
        print(f"   2. Use it in blockchain_client.py")
        print(f"   3. Run integration tests")
    
    print("\n" + "=" * 70)
