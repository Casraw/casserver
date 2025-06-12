// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/metatx/ERC2771Context.sol";

contract WrappedCascoinMetaTx is ERC20, Ownable, ERC2771Context {
    address public minter;
    address public relayer; // Address that can execute meta-transactions

    event MinterChanged(address indexed oldMinter, address indexed newMinter);
    event RelayerChanged(address indexed oldRelayer, address indexed newRelayer);

    constructor(
        address initialOwner,
        address trustedForwarder
    ) ERC20("Wrapped Cascoin", "wCAS") Ownable(initialOwner) ERC2771Context(trustedForwarder) {
        minter = initialOwner; // Initially, the contract deployer is the minter
        relayer = initialOwner; // Initially, the contract deployer is the relayer
    }

    function setMinter(address newMinter) public onlyOwner {
        require(newMinter != address(0), "wCAS: new minter cannot be the zero address");
        address oldMinter = minter;
        minter = newMinter;
        emit MinterChanged(oldMinter, newMinter);
    }

    function setRelayer(address newRelayer) public onlyOwner {
        require(newRelayer != address(0), "wCAS: new relayer cannot be the zero address");
        address oldRelayer = relayer;
        relayer = newRelayer;
        emit RelayerChanged(oldRelayer, newRelayer);
    }

    function mint(address to, uint256 amount) public {
        require(_msgSender() == minter, "wCAS: caller is not the minter");
        _mint(to, amount);
    }

    function burn(uint256 amount) public {
        _burn(_msgSender(), amount);
    }

    /**
     * @dev Burns `amount` tokens from `account`, only callable by the minter.
     * This is used by the bridge to burn tokens when they are swapped back to the native CAS token.
     */
    function burnFrom(address account, uint256 amount) public {
        require(_msgSender() == minter, "wCAS: caller is not the minter");
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
        require(_msgSender() == relayer, "wCAS: caller is not the authorized relayer");
        
        // Verify the signature and execute the transfer
        // Implementation would include signature verification logic
        // For now, this is a simplified version
        
        address from = _recoverSigner(bridgeAddress, amount, nonce, signature);
        require(balanceOf(from) >= amount, "wCAS: insufficient balance");
        
        _transfer(from, bridgeAddress, amount);
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
     * @dev Recover signer from signature (simplified)
     */
    function _recoverSigner(
        address to,
        uint256 amount,
        uint256 nonce,
        bytes memory signature
    ) internal pure returns (address) {
        // This would implement proper signature recovery
        // For production, use OpenZeppelin's ECDSA library
        // This is a placeholder implementation
        return address(0); // Placeholder
    }
} 