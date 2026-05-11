// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SupplyChainAnchor
 * @dev Anchors supply chain record hashes on Ethereum blockchain
 * @notice This contract provides tamper-proof timestamping and integrity verification
 */
contract SupplyChainAnchor {
    
    // ==================== STATE VARIABLES ====================
    
    /// @dev Mapping from record_id to its anchored hash
    mapping(string => bytes32) private recordHashes;
    
    /// @dev Mapping to track if a record_id has been anchored (prevents overwriting)
    mapping(string => bool) private recordExists;
    
    /// @dev Total number of records anchored
    uint256 public totalRecords;
    
    /// @dev Contract owner (for potential admin functions)
    address public owner;
    
    
    // ==================== EVENTS ====================
    
    /**
     * @dev Emitted when a new record is anchored
     * @param recordId Unique identifier for the supply chain record
     * @param recordHash SHA-256 hash of the record (as bytes32)
     * @param timestamp Block timestamp when record was anchored
     * @param anchoredBy Address that anchored the record
     */
    event RecordAnchored(
        string indexed recordId,
        bytes32 indexed recordHash,
        uint256 timestamp,
        address indexed anchoredBy
    );
    
    /**
     * @dev Emitted when a record verification is performed
     * @param recordId The record being verified
     * @param isValid Whether the verification succeeded
     */
    event RecordVerified(
        string indexed recordId,
        bool isValid
    );
    
    
    // ==================== ERRORS ====================
    
    /// @dev Thrown when trying to anchor a record that already exists
    error RecordAlreadyAnchored(string recordId);
    
    /// @dev Thrown when trying to retrieve a record that doesn't exist
    error RecordNotFound(string recordId);
    
    /// @dev Thrown when providing an empty record_id
    error InvalidRecordId();
    
    /// @dev Thrown when providing a zero hash
    error InvalidHash();
    
    
    // ==================== CONSTRUCTOR ====================
    
    constructor() {
        owner = msg.sender;
        totalRecords = 0;
    }
    
    
    // ==================== MODIFIERS ====================
    
    /**
     * @dev Ensures the record_id is not empty
     */
    modifier validRecordId(string memory recordId) {
        if (bytes(recordId).length == 0) {
            revert InvalidRecordId();
        }
        _;
    }
    
    /**
     * @dev Ensures the hash is not zero
     */
    modifier validHash(bytes32 hash) {
        if (hash == bytes32(0)) {
            revert InvalidHash();
        }
        _;
    }
    
    
    // ==================== PUBLIC FUNCTIONS ====================
    
    /**
     * @notice Anchor a supply chain record hash on the blockchain
     * @dev Stores the hash permanently and emits an event
     * @param recordId Unique identifier for the record (e.g., "R-PROD-001")
     * @param recordHash SHA-256 hash of the record (32 bytes)
     * @custom:security Only allows storing once - no overwriting
     */
    function anchorRecord(
        string memory recordId, 
        bytes32 recordHash
    ) 
        public 
        validRecordId(recordId)
        validHash(recordHash)
    {
        // Check if record already exists
        if (recordExists[recordId]) {
            revert RecordAlreadyAnchored(recordId);
        }
        
        // Store the hash
        recordHashes[recordId] = recordHash;
        recordExists[recordId] = true;
        totalRecords++;
        
        // Emit event for indexing and monitoring
        emit RecordAnchored(
            recordId,
            recordHash,
            block.timestamp,
            msg.sender
        );
    }
    
    /**
     * @notice Retrieve the anchored hash for a record
     * @param recordId The record identifier to look up
     * @return The stored hash (bytes32)
     * @custom:throws RecordNotFound if record doesn't exist
     */
    function getRecord(string memory recordId) 
        public 
        view 
        validRecordId(recordId)
        returns (bytes32) 
    {
        if (!recordExists[recordId]) {
            revert RecordNotFound(recordId);
        }
        
        return recordHashes[recordId];
    }
    
    /**
     * @notice Check if a record has been anchored
     * @param recordId The record identifier to check
     * @return true if the record exists, false otherwise
     */
    function hasRecord(string memory recordId) 
        public 
        view 
        validRecordId(recordId)
        returns (bool) 
    {
        return recordExists[recordId];
    }
    
    /**
     * @notice Verify that a record's hash matches the on-chain value
     * @param recordId The record identifier
     * @param expectedHash The hash to verify against
     * @return true if hashes match, false otherwise
     */
    function verifyRecord(
        string memory recordId, 
        bytes32 expectedHash
    ) 
        public 
        returns (bool) 
    {
        bool isValid = false;
        
        if (recordExists[recordId]) {
            isValid = (recordHashes[recordId] == expectedHash);
        }
        
        emit RecordVerified(recordId, isValid);
        return isValid;
    }
    
    /**
     * @notice Batch anchor multiple records in a single transaction
     * @dev More gas-efficient for anchoring multiple records
     * @param recordIds Array of record identifiers
     * @param recordHashesArray Array of corresponding hashes
     * @custom:security Arrays must have same length
     */
    function anchorRecordsBatch(
        string[] memory recordIds,
        bytes32[] memory recordHashesArray
    ) 
        public 
    {
        require(
            recordIds.length == recordHashesArray.length,
            "Arrays length mismatch"
        );
        
        for (uint256 i = 0; i < recordIds.length; i++) {
            // Use the single anchor function for each record
            // This will revert the entire transaction if any record fails
            anchorRecord(recordIds[i], recordHashesArray[i]);
        }
    }
    
    
    // ==================== VIEW FUNCTIONS ====================
    
    /**
     * @notice Get total number of anchored records
     * @return The total count
     */
    function getTotalRecords() public view returns (uint256) {
        return totalRecords;
    }
    
    /**
     * @notice Get contract owner address
     * @return The owner address
     */
    function getOwner() public view returns (address) {
        return owner;
    }
}
