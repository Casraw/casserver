from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # --- General Settings ---
    # Default to a local SQLite DB for easy development, but configurable via ENV.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bridge.db")

    # Address where users send wCAS on Polygon to bridge back to Cascoin
    BRIDGE_WCAS_DEPOSIT_ADDRESS: str = os.getenv("BRIDGE_WCAS_DEPOSIT_ADDRESS", "0xYourBridgeWCASDepositAddressHereChangeMe")

    # --- Cascoin Node RPC Settings ---
    # URL for the Cascoin node's JSON-RPC interface
    CASCOIN_RPC_URL: str = os.getenv("CASCOIN_RPC_URL", "http://localhost:18332") # Example
    # Username for Cascoin RPC authentication (if required)
    CASCOIN_RPC_USER: str = os.getenv("CASCOIN_RPC_USER", "your_cascoin_rpc_user")
    # Password for Cascoin RPC authentication (if required)
    # IMPORTANT: Treat this as a secret and set it via environment variable.
    CASCOIN_RPC_PASSWORD: str = os.getenv("CASCOIN_RPC_PASSWORD", "your_cascoin_rpc_password_MUST_BE_SET_IN_ENV")

    # --- Polygon Node RPC & Minting Settings ---
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https_rpc_mumbai_maticvigil_com") # Example Mumbai RPC

    # IMPORTANT: This is a highly sensitive private key for the account that mints wCAS tokens.
    # It MUST be set via an environment variable and kept secret.
    # DO NOT commit the actual private key to version control.
    MINTER_PRIVATE_KEY: str = os.getenv("MINTER_PRIVATE_KEY", "YOUR_MINTER_PRIVATE_KEY_HERE_MUST_BE_SET_IN_ENV")

    WCAS_CONTRACT_ADDRESS: str = os.getenv("WCAS_CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000") # Placeholder
    WCAS_CONTRACT_ABI_JSON_PATH: str = os.getenv("WCAS_CONTRACT_ABI_JSON_PATH", "smart_contracts/wCAS_ABI.json") # Path to the wCAS ABI JSON file

    # --- Polygon Transaction Settings ---
    DEFAULT_GAS_LIMIT: int = int(os.getenv("DEFAULT_GAS_LIMIT", "200000"))
    DEFAULT_MAX_PRIORITY_FEE_PER_GAS_GWEI: float = float(os.getenv("DEFAULT_MAX_PRIORITY_FEE_PER_GAS_GWEI", "2.0"))

    # --- Security Settings ---
    # IMPORTANT: This key is used to protect internal API endpoints.
    # It MUST be set to a strong, unique secret in a production environment via ENV.
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "bridge_internal_secret_key_change_me_!!!")

    # --- Operational Settings (for watchers and services) ---
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
    CONFIRMATIONS_REQUIRED: int = int(os.getenv("CONFIRMATIONS_REQUIRED", "12"))
    
    # --- Fee System Configuration ---
    DIRECT_PAYMENT_FEE_PERCENTAGE: float = float(os.getenv("DIRECT_PAYMENT_FEE_PERCENTAGE", "0.1"))
    DEDUCTED_FEE_PERCENTAGE: float = float(os.getenv("DEDUCTED_FEE_PERCENTAGE", "2.5"))
    MINIMUM_BRIDGE_AMOUNT: float = float(os.getenv("MINIMUM_BRIDGE_AMOUNT", "1.0"))
    MATIC_TO_CAS_EXCHANGE_RATE: float = float(os.getenv("MATIC_TO_CAS_EXCHANGE_RATE", "100.0"))
    MATIC_TO_WCAS_EXCHANGE_RATE: float = float(os.getenv("MATIC_TO_WCAS_EXCHANGE_RATE", "100.0"))
    GAS_PRICE_GWEI: float = float(os.getenv("GAS_PRICE_GWEI", "30.0"))
    GAS_PRICE_BUFFER_PERCENTAGE: float = float(os.getenv("GAS_PRICE_BUFFER_PERCENTAGE", "20.0"))
    TOKEN_CONVERSION_FEE_PERCENTAGE: float = float(os.getenv("TOKEN_CONVERSION_FEE_PERCENTAGE", "0.5"))

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = "ignore"  # Allow extra environment variables in production

settings = Settings()

if settings.POLYGON_RPC_URL.startswith("https_"):
    settings.POLYGON_RPC_URL = settings.POLYGON_RPC_URL.replace("https_", "https://", 1)
