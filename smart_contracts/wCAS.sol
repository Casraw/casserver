// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/metatx/ERC2771Context.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

contract WrappedCascoin is ERC20, Ownable, ERC2771Context {
    using ECDSA for bytes32;

    address public minter;
    address public relayer; // Address that can execute meta-transactions
    mapping(address => uint256) public nonces; // Track nonces for each address
    string private _contractURI;

    event MinterChanged(address indexed oldMinter, address indexed newMinter);
    event RelayerChanged(address indexed oldRelayer, address indexed newRelayer);
    event MetaTransferExecuted(address indexed from, address indexed to, uint256 amount, uint256 nonce);
    event ContractURIUpdated(string newURI);

    constructor(
        address initialOwner,
        address trustedForwarder
    ) payable ERC20("Wrapped Cascoin", "wCAS") Ownable(initialOwner) ERC2771Context(trustedForwarder) {
        minter = initialOwner; // Initially, the contract deployer is the minter
        relayer = initialOwner; // Initially, the contract deployer is the relayer
    }

    function setMinter(address newMinter) public onlyOwner {
        require(newMinter != address(0), "wCAS: zero address");
        address oldMinter = minter;
        if (oldMinter != newMinter) {
            minter = newMinter;
            emit MinterChanged(oldMinter, newMinter);
        }
    }

    function setRelayer(address newRelayer) public onlyOwner {
        require(newRelayer != address(0), "wCAS: zero address");
        address oldRelayer = relayer;
        if (oldRelayer != newRelayer) {
            relayer = newRelayer;
            emit RelayerChanged(oldRelayer, newRelayer);
        }
    }

    function mint(address to, uint256 amount) public {
        require(_msgSender() == minter, "wCAS: not minter");
        _mint(to, amount);
    }

    function burn(uint256 amount) public {
        require(amount > 0, "wCAS: zero amount");
        _burn(_msgSender(), amount);
    }

    /**
     * @dev Burns `amount` tokens from `account`, only callable by the minter or if caller has allowance.
     * This is used by the bridge to burn tokens when they are swapped back to the native CAS token.
     * For security, it follows ERC20 allowance pattern when not called by minter.
     */
    function burnFrom(address account, uint256 amount) public {
        require(account != address(0), "wCAS: zero address");
        require(amount > 0, "wCAS: zero amount");
        
        address sender = _msgSender(); // Cache _msgSender()
        if (sender != minter) {
            // If not minter, check and update allowance like ERC20 transferFrom
            uint256 currentAllowance = allowance(account, sender);
            require(currentAllowance > amount - 1, "wCAS: exceeds allowance"); // Cheaper inequality
            _approve(account, sender, currentAllowance - amount);
        }
        
        _burn(account, amount);
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
    ) public {
        address sender = _msgSender(); // Cache _msgSender()
        require(sender == relayer, "wCAS: not relayer");
        
        // Inline signature recovery to save gas
        bytes32 messageHash = keccak256(abi.encodePacked(
            bridgeAddress,
            amount,
            nonce,
            address(this)
        ));
        bytes32 ethSignedMessageHash = MessageHashUtils.toEthSignedMessageHash(messageHash);
        address from = ECDSA.recover(ethSignedMessageHash, signature);
        
        require(balanceOf(from) > amount - 1, "wCAS: insufficient balance"); // Cheaper inequality
        require(nonce == nonces[from], "wCAS: invalid nonce");
        
        // Increment nonce
        nonces[from]++;
        
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
        if (keccak256(bytes(_contractURI)) != keccak256(bytes(newURI))) {
            _contractURI = newURI;
            emit ContractURIUpdated(newURI);
        }
    }
} 