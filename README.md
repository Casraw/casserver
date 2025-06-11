# Cascoin-Polygon Bridge

This project implements a blockchain bridge between Cascoin (a Bitcoin fork) and Polygon, allowing for the transfer of value between the two chains via a wrapped token (wCAS).

## Features

- Transfer Cascoin to Polygon (minting wCAS).
- Transfer wCAS from Polygon back to Cascoin (burning wCAS and releasing CAS).
- Frontend for user interaction.
- Backend API for managing deposit addresses.
- Blockchain watchers for monitoring transactions on both chains.
- ERC20 smart contract for wCAS on Polygon.

## Project Structure

- `backend/`: FastAPI application for API endpoints and core logic.
- `database/`: Database models and migration scripts (if any).
- `frontend/`: HTML and JavaScript for the user interface.
- `smart_contracts/`: Solidity smart contract for the wCAS token.
- `watchers/`: Python scripts for monitoring Cascoin and Polygon blockchains.
- `tests/`: Unit and integration tests.

## Setup and Installation (To be updated)

(Instructions will be added as development progresses)
