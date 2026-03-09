"""
Test Suite — Land Registry Blockchain System
Run: python -m pytest tests/test_registry.py -v
"""

import pytest # type: ignore
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blockchain.chain import Blockchain
from contracts.land_registry import LandRegistryContract, LandStatus


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def system():
    """Fresh blockchain + contract per test."""
    bc = Blockchain()
    reg = LandRegistryContract(bc)
    reg.register_official("OFF_001", "Alice Registrar", "registrar", "Land Dept")
    reg.register_official("OFF_002", "Bob Senior", "senior_registrar", "Land Dept")
    reg.register_citizen("CIT_001", "Ravi Kumar", "AADHAR-1111", "ravi@example.com")
    reg.register_citizen("CIT_002", "Priya Sharma", "AADHAR-2222", "priya@example.com")
    reg.register_citizen("CIT_003", "Arjun Patel", "AADHAR-3333", "arjun@example.com")
    return bc, reg


@pytest.fixture
def registered_land(system):
    bc, reg = system
    parcel = reg.register_land(
        registrar_address="OFF_001",
        title_number="LND-2024-001",
        location="Plot 5, Sector 12, Kolkata",
        area_sqm=500,
        land_use="residential",
        owner_address="CIT_001",
        owner_name="Ravi Kumar",
        coordinates="22.5726° N, 88.3639° E",
        valuation=5_000_000,
    )
    return bc, reg, parcel


# ══════════════════════════════════════════════════════════════════════════
#  BLOCKCHAIN TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestBlockchain:

    def test_genesis_block_created(self, system):
        bc, _ = system
        assert len(bc.chain) == 1
        assert bc.chain[0].index == 0
        assert bc.chain[0].previous_hash == "0" * 64

    def test_chain_valid_after_genesis(self, system):
        bc, _ = system
        assert bc.is_chain_valid()

    def test_block_mined_with_proof_of_work(self, registered_land):
        bc, _, _ = registered_land
        last_block = bc.last_block
        difficulty_prefix = "0" * bc.DIFFICULTY
        assert last_block.hash.startswith(difficulty_prefix), \
            f"Hash {last_block.hash} doesn't meet difficulty {bc.DIFFICULTY}"

    def test_chain_grows_with_transactions(self, registered_land):
        bc, reg, parcel = registered_land
        initial_blocks = len(bc.chain)
        reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya Sharma")
        assert len(bc.chain) == initial_blocks + 1

    def test_tampered_chain_is_invalid(self, registered_land):
        bc, _, _ = registered_land
        # Tamper with a transaction
        bc.chain[1].transactions[0].data["tampered"] = True
        assert not bc.is_chain_valid()

    def test_chain_stats(self, registered_land):
        bc, _, _ = registered_land
        stats = bc.get_chain_stats()
        assert stats["total_blocks"] >= 2
        assert stats["total_transactions"] >= 1
        assert stats["is_valid"] is True

    def test_land_history_in_blockchain(self, registered_land):
        bc, reg, parcel = registered_land
        reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya Sharma")
        history = bc.get_land_history(parcel.land_id)
        assert len(history) == 2  # REGISTER + TRANSFER
        tx_types = [h["tx_type"] for h in history]
        assert "REGISTER" in tx_types
        assert "TRANSFER" in tx_types


# ══════════════════════════════════════════════════════════════════════════
#  USER MANAGEMENT TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestUserManagement:

    def test_register_official(self, system):
        _, reg = system
        assert "OFF_001" in reg.officials
        assert reg.officials["OFF_001"]["name"] == "Alice Registrar"

    def test_register_citizen(self, system):
        _, reg = system
        assert "CIT_001" in reg.citizens
        assert reg.citizens["CIT_001"]["national_id"] == "AADHAR-1111"

    def test_duplicate_official_raises(self, system):
        _, reg = system
        with pytest.raises(ValueError, match="already registered"):
            reg.register_official("OFF_001", "Duplicate", "registrar", "Dept")

    def test_duplicate_citizen_raises(self, system):
        _, reg = system
        with pytest.raises(ValueError, match="already registered"):
            reg.register_citizen("CIT_001", "Dup", "NID-XXX", "")

    def test_unofficial_cannot_register_land(self, system):
        _, reg = system
        with pytest.raises(PermissionError):
            reg.register_land("CIT_001", "T-999", "Somewhere", 100, "residential", "CIT_002", "Name")


# ══════════════════════════════════════════════════════════════════════════
#  LAND REGISTRATION TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestLandRegistration:

    def test_land_registered_successfully(self, registered_land):
        _, reg, parcel = registered_land
        assert parcel.land_id in reg.lands
        assert parcel.title_number == "LND-2024-001"
        assert parcel.owner_address == "CIT_001"
        assert parcel.status == LandStatus.ACTIVE

    def test_title_number_indexed(self, registered_land):
        _, reg, parcel = registered_land
        assert "LND-2024-001" in reg.title_index

    def test_duplicate_title_raises(self, registered_land):
        _, reg, parcel = registered_land
        with pytest.raises(ValueError, match="already registered"):
            reg.register_land("OFF_001", "LND-2024-001", "Elsewhere", 200, "commercial", "CIT_002", "Priya")

    def test_negative_area_raises(self, system):
        _, reg = system
        with pytest.raises(ValueError, match="positive"):
            reg.register_land("OFF_001", "T-NEG", "Loc", -100, "residential", "CIT_001", "Ravi")

    def test_get_land_by_id(self, registered_land):
        _, reg, parcel = registered_land
        fetched = reg.get_land(parcel.land_id)
        assert fetched.title_number == parcel.title_number

    def test_get_land_by_title(self, registered_land):
        _, reg, parcel = registered_land
        fetched = reg.get_land_by_title("LND-2024-001")
        assert fetched.land_id == parcel.land_id

    def test_get_lands_by_owner(self, registered_land):
        _, reg, parcel = registered_land
        lands = reg.get_lands_by_owner("CIT_001")
        assert len(lands) == 1
        assert lands[0].land_id == parcel.land_id

    def test_unknown_land_raises(self, system):
        _, reg = system
        with pytest.raises(KeyError):
            reg.get_land("nonexistent-id")


# ══════════════════════════════════════════════════════════════════════════
#  TRANSFER TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestOwnershipTransfer:

    def test_transfer_succeeds(self, registered_land):
        _, reg, parcel = registered_land
        record = reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya Sharma")
        updated = reg.get_land(parcel.land_id)
        assert updated.owner_address == "CIT_002"
        assert record.previous_owner == "CIT_001"

    def test_ownership_history_tracked(self, registered_land):
        _, reg, parcel = registered_land
        reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya Sharma")
        reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_003", "Arjun Patel")
        history = reg.get_ownership_history(parcel.land_id)
        assert len(history) == 2
        assert history[0].previous_owner == "CIT_001"
        assert history[1].previous_owner == "CIT_002"

    def test_citizen_cannot_transfer(self, registered_land):
        _, reg, parcel = registered_land
        with pytest.raises(PermissionError):
            reg.transfer_ownership("CIT_001", parcel.land_id, "CIT_002", "Priya")

    def test_transfer_types_recorded(self, registered_land):
        _, reg, parcel = registered_land
        record = reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya", "INHERITANCE")
        assert record.transfer_type == "INHERITANCE"


# ══════════════════════════════════════════════════════════════════════════
#  ENCUMBRANCE TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestEncumbrance:

    def test_encumber_land(self, registered_land):
        _, reg, parcel = registered_land
        updated = reg.encumber_land("OFF_001", parcel.land_id, "Mortgage with XYZ Bank")
        assert updated.status == LandStatus.ENCUMBERED
        assert "XYZ Bank" in updated.encumbrance_details

    def test_cannot_transfer_encumbered_land(self, registered_land):
        _, reg, parcel = registered_land
        reg.encumber_land("OFF_001", parcel.land_id, "Mortgage")
        with pytest.raises(ValueError, match="encumbered"):
            reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya")

    def test_release_encumbrance(self, registered_land):
        _, reg, parcel = registered_land
        reg.encumber_land("OFF_001", parcel.land_id, "Mortgage")
        released = reg.release_encumbrance("OFF_001", parcel.land_id)
        assert released.status == LandStatus.ACTIVE
        assert released.encumbrance_details is None

    def test_transfer_after_release(self, registered_land):
        _, reg, parcel = registered_land
        reg.encumber_land("OFF_001", parcel.land_id, "Mortgage")
        reg.release_encumbrance("OFF_001", parcel.land_id)
        record = reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya")
        assert record.new_owner == "CIT_002"

    def test_double_encumbrance_raises(self, registered_land):
        _, reg, parcel = registered_land
        reg.encumber_land("OFF_001", parcel.land_id, "Mortgage 1")
        with pytest.raises(ValueError):
            reg.encumber_land("OFF_001", parcel.land_id, "Mortgage 2")


# ══════════════════════════════════════════════════════════════════════════
#  DISPUTE TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestDisputes:

    def test_raise_dispute(self, registered_land):
        _, reg, parcel = registered_land
        updated = reg.raise_dispute("CIT_002", parcel.land_id, "Boundary encroachment")
        assert updated.status == LandStatus.DISPUTED

    def test_cannot_transfer_disputed_land(self, registered_land):
        _, reg, parcel = registered_land
        reg.raise_dispute("CIT_002", parcel.land_id, "Claim")
        with pytest.raises(ValueError, match="dispute"):
            reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya")

    def test_resolve_dispute(self, registered_land):
        _, reg, parcel = registered_land
        reg.raise_dispute("CIT_002", parcel.land_id, "Claim")
        resolved = reg.resolve_dispute("OFF_001", parcel.land_id, "Claim dismissed by court")
        assert resolved.status == LandStatus.ACTIVE
        assert resolved.dispute_details is None

    def test_only_official_resolves_dispute(self, registered_land):
        _, reg, parcel = registered_land
        reg.raise_dispute("CIT_002", parcel.land_id, "Claim")
        with pytest.raises(PermissionError):
            reg.resolve_dispute("CIT_003", parcel.land_id, "Fake resolution")


# ══════════════════════════════════════════════════════════════════════════
#  INTEGRATION TEST — Full Lifecycle
# ══════════════════════════════════════════════════════════════════════════

class TestFullLifecycle:

    def test_complete_land_lifecycle(self, system):
        bc, reg = system

        # 1. Register land
        parcel = reg.register_land(
            "OFF_001", "LND-INT-001", "123 Main St, Delhi", 800, "commercial",
            "CIT_001", "Ravi Kumar", valuation=10_000_000
        )
        assert parcel.status == LandStatus.ACTIVE

        # 2. Encumber (mortgage)
        reg.encumber_land("OFF_001", parcel.land_id, "HDFC Bank Mortgage — ₹5,000,000")
        assert reg.get_land(parcel.land_id).status == LandStatus.ENCUMBERED

        # 3. Release mortgage
        reg.release_encumbrance("OFF_001", parcel.land_id)
        assert reg.get_land(parcel.land_id).status == LandStatus.ACTIVE

        # 4. Transfer ownership (sale)
        reg.transfer_ownership("OFF_001", parcel.land_id, "CIT_002", "Priya Sharma", "SALE")
        assert reg.get_land(parcel.land_id).owner_address == "CIT_002"

        # 5. Raise dispute
        reg.raise_dispute("CIT_003", parcel.land_id, "Contested boundary")
        assert reg.get_land(parcel.land_id).status == LandStatus.DISPUTED

        # 6. Resolve dispute
        reg.resolve_dispute("OFF_002", parcel.land_id, "Court order: CIT_002 is rightful owner")
        assert reg.get_land(parcel.land_id).status == LandStatus.ACTIVE

        # 7. Blockchain integrity
        assert bc.is_chain_valid()

        # 8. Verify history
        blockchain_history = reg.get_blockchain_history(parcel.land_id)
        tx_types = [tx["tx_type"] for tx in blockchain_history]
        expected = ["REGISTER", "ENCUMBER", "RELEASE_ENCUMBRANCE", "TRANSFER", "DISPUTE", "RESOLVE_DISPUTE"]
        assert tx_types == expected, f"Expected {expected}, got {tx_types}"

        print("\n✅ Full lifecycle test PASSED — 6 transaction types verified across", len(bc.chain), "blocks")