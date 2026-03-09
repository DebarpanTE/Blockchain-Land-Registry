import hashlib
import json
import time
import uuid
from typing import List, Optional, Dict, Any
from .block import Block, Transaction


class Blockchain:
    """
    Blockchain implementation for Land Registry System.
    Implements Proof-of-Work consensus with a difficulty target.
    """

    DIFFICULTY = 3  # Number of leading zeros required in hash
    MINING_REWARD = 0  # No crypto reward; registry is permissioned

    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self._create_genesis_block()

    # ─────────────────────────── Chain Bootstrap ──────────────────────────

    def _create_genesis_block(self):
        genesis = Block(
            index=0,
            transactions=[],
            timestamp=time.time(),
            previous_hash="0" * 64,
        )
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis)

    # ─────────────────────────── Mining ───────────────────────────────────

    def mine_pending_transactions(self, miner_address: str = "SYSTEM") -> Block:
        """Mine all pending transactions into a new block."""
        if not self.pending_transactions:
            raise ValueError("No pending transactions to mine.")

        block = Block(
            index=len(self.chain),
            transactions=self.pending_transactions,
            timestamp=time.time(),
            previous_hash=self.last_block.hash,
        )

        block.hash = self._proof_of_work(block)
        self.chain.append(block)
        self.pending_transactions = []
        return block

    def _proof_of_work(self, block: Block) -> str:
        """Find a nonce that satisfies the difficulty target."""
        target = "0" * self.DIFFICULTY
        block.nonce = 0
        computed = block.compute_hash()
        while not computed.startswith(target):
            block.nonce += 1
            computed = block.compute_hash()
        return computed

    # ─────────────────────────── Transactions ─────────────────────────────

    def add_transaction(self, transaction: Transaction) -> str:
        """Add a validated transaction to the pending pool."""
        self.pending_transactions.append(transaction)
        return transaction.tx_id

    def create_transaction(
        self,
        tx_type: str,
        land_id: str,
        from_address: str,
        to_address: str,
        data: Dict[str, Any],
        auto_mine: bool = True,
    ) -> Transaction:
        """Create, queue, and optionally auto-mine a transaction."""
        tx = Transaction(
            tx_id=str(uuid.uuid4()),
            tx_type=tx_type,
            land_id=land_id,
            from_address=from_address,
            to_address=to_address,
            data=data,
            timestamp=time.time(),
        )
        self.add_transaction(tx)
        if auto_mine:
            self.mine_pending_transactions()
        return tx

    # ─────────────────────────── Validation ───────────────────────────────

    def is_chain_valid(self) -> bool:
        """Validate the full chain integrity."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith("0" * self.DIFFICULTY):
                return False
        return True

    # ─────────────────────────── Queries ──────────────────────────────────

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def get_land_history(self, land_id: str) -> List[Dict]:
        """Return all transactions related to a specific land parcel."""
        history = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.land_id == land_id:
                    entry = tx.to_dict()
                    entry["block_index"] = block.index
                    entry["block_hash"] = block.hash
                    history.append(entry)
        return history

    def get_all_transactions(self) -> List[Dict]:
        """Return every transaction across all blocks."""
        all_txs = []
        for block in self.chain:
            for tx in block.transactions:
                entry = tx.to_dict()
                entry["block_index"] = block.index
                all_txs.append(entry)
        return all_txs

    def to_dict(self) -> List[Dict]:
        return [block.to_dict() for block in self.chain]

    def get_chain_stats(self) -> Dict:
        total_txs = sum(len(b.transactions) for b in self.chain)
        return {
            "total_blocks": len(self.chain),
            "total_transactions": total_txs,
            "pending_transactions": len(self.pending_transactions),
            "is_valid": self.is_chain_valid(),
            "difficulty": self.DIFFICULTY,
        }