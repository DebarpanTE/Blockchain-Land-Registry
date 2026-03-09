import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class Transaction:
    """Represents a land registry transaction."""
    tx_id: str
    tx_type: str  # REGISTER, TRANSFER, UPDATE, ENCUMBER
    land_id: str
    from_address: str
    to_address: str
    data: Dict[str, Any]
    timestamp: float
    signature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_hash(self) -> str:
        tx_string = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()


@dataclass
class Block:
    """Represents a block in the blockchain."""
    index: int
    transactions: List[Transaction]
    timestamp: float
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    block_hash: str = ""

    def compute_hash(self) -> str:
        block_dict = {
            "index": self.index,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_dict, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }