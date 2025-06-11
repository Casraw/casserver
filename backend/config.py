from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bridge.db")
    BRIDGE_WCAS_DEPOSIT_ADDRESS: str = os.getenv("BRIDGE_WCAS_DEPOSIT_ADDRESS", "0xYourBridgeWCASDepositAddressHereChangeMe")

    # Polygon Minting Service specific
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https_rpc_mumbai_maticvigil_com") # Example Mumbai RPC
    MINTER_PRIVATE_KEY: str = os.getenv("MINTER_PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000000") # DANGER: Placeholder
    WCAS_CONTRACT_ADDRESS: str = os.getenv("WCAS_CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000") # Placeholder
    WCAS_CONTRACT_ABI_JSON_PATH: str = os.getenv("WCAS_CONTRACT_ABI_JSON_PATH", "smart_contracts/wCAS_ABI.json")

    DEFAULT_GAS_LIMIT: int = int(os.getenv("DEFAULT_GAS_LIMIT", "200000"))
    DEFAULT_MAX_PRIORITY_FEE_PER_GAS_GWEI: float = float(os.getenv("DEFAULT_MAX_PRIORITY_FEE_PER_GAS_GWEI", "2.0"))

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

if settings.POLYGON_RPC_URL.startswith("https_"):
    settings.POLYGON_RPC_URL = settings.POLYGON_RPC_URL.replace("https_", "https://", 1)
