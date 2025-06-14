// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable2Step.sol";
import "@openzeppelin/contracts/metatx/ERC2771Context.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

contract WrappedCascoin is ERC20, Ownable2Step, ERC2771Context {
    using ECDSA for bytes32;

    address public minter;
    address public relayer; // Address that can execute meta-transactions
    mapping(address user => uint256 nonce) public nonces; // Track nonces for each address
    string private _contractURI;

    event MinterChanged(address indexed oldMinter, address indexed newMinter);
    event RelayerChanged(address indexed oldRelayer, address indexed newRelayer);
    event MetaTransferExecuted(address indexed from, address indexed to, uint256 amount, uint256 nonce);
    event ContractURIUpdated(string newURI);
    event TokensBurned(address indexed account, uint256 amount);
    event ContractDeployed(address indexed owner, address indexed minter, address indexed relayer);
    event TokensMinted(address indexed to, uint256 amount);

    // Custom access control modifiers - only perform checks, no state changes
    modifier onlyMinter() {
        require(_msgSender() == minter, "wCAS: not minter");
        _;
    }

    modifier onlyRelayer() {
        require(_msgSender() == relayer, "wCAS: not relayer");
        _;
    }

    modifier onlyMinterOrApproved(address account, uint256 amount) {
        address sender = _msgSender();
        if (sender != minter) {
            // If not minter, check allowance like ERC20 transferFrom
            uint256 currentAllowance = allowance(account, sender);
            require(currentAllowance > amount - 1, "wCAS: exceeds allowance"); // Cheaper inequality
        }
        _;
    }

    modifier validAddress(address addr) {
        require(addr != address(0), "wCAS: zero address");
        _;
    }

    modifier validAmount(uint256 amount) {
        require(amount != 0, "wCAS: zero amount");
        _;
    }

    constructor(
        address initialOwner,
        address trustedForwarder
    ) payable 
      ERC20("Wrapped Cascoin", "wCAS") 
      Ownable(initialOwner) 
      ERC2771Context(trustedForwarder) 
      validAddress(initialOwner)
      validAddress(trustedForwarder)
    {
        minter = initialOwner; // Initially, the contract deployer is the minter
        relayer = initialOwner; // Initially, the contract deployer is the relayer
        
        emit ContractDeployed(initialOwner, minter, relayer);
    }

    function setMinter(address newMinter) public onlyOwner validAddress(newMinter) {
        address oldMinter = minter; // Cache storage variable
        if (oldMinter != newMinter) {
            minter = newMinter;
            emit MinterChanged(oldMinter, newMinter);
        }
    }

    function setRelayer(address newRelayer) public onlyOwner validAddress(newRelayer) {
        address oldRelayer = relayer; // Cache storage variable
        if (oldRelayer != newRelayer) {
            relayer = newRelayer;
            emit RelayerChanged(oldRelayer, newRelayer);
        }
    }

    function mint(address to, uint256 amount) public onlyMinter validAddress(to) validAmount(amount) {
        _mint(to, amount);
        emit TokensMinted(to, amount);
    }

    function burn(uint256 amount) public validAmount(amount) {
        address sender = _msgSender();
        _burn(sender, amount);
        emit TokensBurned(sender, amount);
    }

    /**
     * @dev Burns `amount` tokens from `account`, only callable by the minter or if caller has allowance.
     * This is used by the bridge to burn tokens when they are swapped back to the native CAS token.
     * For security, it follows ERC20 allowance pattern when not called by minter.
     */
    function burnFrom(address account, uint256 amount) public 
        onlyMinterOrApproved(account, amount) 
        validAddress(account) 
        validAmount(amount) 
    {
        address sender = _msgSender();
        address cachedMinter = minter; // Cache storage variable
        
        if (sender != cachedMinter) {
            // Update allowance after validation in modifier
            uint256 currentAllowance = allowance(account, sender);
            _approve(account, sender, currentAllowance - amount);
        }
        
        _burn(account, amount);
        emit TokensBurned(account, amount);
    }

    /**
     * @dev Meta-transaction version of transfer to bridge for gasless bridging
     * This allows users to send wCAS to the bridge without holding MATIC
     */
    function metaTransferToBridge(
        address bridgeAddress,
        uint256 amount,
        uint256 nonce,
        bytes memory signature
    ) public onlyRelayer validAddress(bridgeAddress) validAmount(amount) {
        // Cache storage variables for gas optimization
        address contractAddress = address(this);
        
        // Use abi.encode instead of abi.encodePacked to prevent hash collisions in signature verification
        // This is a security best practice for cryptographic operations
        bytes32 messageHash = keccak256(abi.encode(
            bridgeAddress,
            amount,
            nonce,
            contractAddress
        ));
        bytes32 ethSignedMessageHash = MessageHashUtils.toEthSignedMessageHash(messageHash);
        address from = ECDSA.recover(ethSignedMessageHash, signature);
        
        require(from != address(0), "wCAS: invalid signature");
        require(balanceOf(from) > amount - 1, "wCAS: insufficient balance"); // Cheaper inequality
        
        // Cache nonces[from] to avoid multiple SLOADs
        uint256 currentNonce = nonces[from];
        require(nonce == currentNonce, "wCAS: invalid nonce");
        
        // Increment nonce
        nonces[from] = currentNonce + 1;
        
        // Execute transfer
        _transfer(from, bridgeAddress, amount);
        
        emit MetaTransferExecuted(from, bridgeAddress, amount, nonce);
    }

    /**
     * @dev Override _msgSender() to support meta-transactions
     */
    function _msgSender() internal view override(Context, ERC2771Context) returns (address) {
        return ERC2771Context._msgSender();
    }

    /**
     * @dev Override _msgData() to support meta-transactions
     */
    function _msgData() internal view override(Context, ERC2771Context) returns (bytes calldata) {
        return ERC2771Context._msgData();
    }

    /**
     * @dev Override _contextSuffixLength to resolve multiple inheritance conflict
     */
    function _contextSuffixLength() internal view override(Context, ERC2771Context) returns (uint256) {
        return ERC2771Context._contextSuffixLength();
    }

    /**
     * @dev Returns the URI for the contract's metadata.
     */
    function contractURI() public view returns (string memory) {
        return _contractURI;
    }

    /**
     * @dev Sets the URI for the contract's metadata.
     * Can only be called by the owner.
     */
    function setContractURI(string memory newURI) public onlyOwner {
        string memory cachedContractURI = _contractURI; // Cache storage variable
        if (keccak256(bytes(cachedContractURI)) != keccak256(bytes(newURI))) {
            _contractURI = newURI;
            emit ContractURIUpdated(newURI);
        }
    }
} 