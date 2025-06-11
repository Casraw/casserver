// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract WrappedCascoin is ERC20, Ownable {
    address public minter;

    event MinterChanged(address indexed oldMinter, address indexed newMinter);

    constructor(address initialOwner) ERC20("Wrapped Cascoin", "wCAS") Ownable(initialOwner) {
        minter = initialOwner; // Initially, the contract deployer is the minter
    }

    function setMinter(address newMinter) public onlyOwner {
        require(newMinter != address(0), "wCAS: new minter cannot be the zero address");
        address oldMinter = minter;
        minter = newMinter;
        emit MinterChanged(oldMinter, newMinter);
    }

    function mint(address to, uint256 amount) public {
        require(msg.sender == minter, "wCAS: caller is not the minter");
        _mint(to, amount);
    }

    function burn(uint256 amount) public {
        _burn(msg.sender, amount);
    }

    // OPTIONAL: If you want users to burn their tokens and have the bridge process it
    // function burnFrom(address account, uint256 amount) public {
    //     require(msg.sender == minter, "wCAS: caller is not the minter"); // Or some other authorized burner
    //     _burn(account, amount);
    // }
}
