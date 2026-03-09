"""
Land Registry Smart Contract
─────────────────────────────
Enforces business rules for land registration, ownership transfer,
encumbrance, and dispute management on top of the blockchain layer.
"""

import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class LandStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISPUTED = "DISPUTED"
    ENCUMBERED = "ENCUMBERED"  # mortgaged / lien
    FROZEN = "FROZEN"          # frozen by authority


class TransactionType(str, Enum):
    REGISTER = "REGISTER"
    TRANSFER = "TRANSFER"
    ENCUMBER = "ENCUMBER"
    RELEASE_ENCUMBRANCE = "RELEASE_ENCUMBRANCE"
    DISPUTE = "DISPUTE"
    RESOLVE_DISPUTE = "RESOLVE_DISPUTE"
    UPDATE_DETAILS = "UPDATE_DETAILS"


@dataclass
class LandParcel:
    land_id: str
    title_number: str
    location: str
    area_sqm: float
    land_use: str           # residential, commercial, agricultural, etc.
    owner_address: str
    owner_name: str
    status: str = LandStatus.ACTIVE
    registered_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    encumbrance_details: Optional[str] = None
    dispute_details: Optional[str] = None
    coordinates: Optional[str] = None
    valuation: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OwnershipRecord:
    record_id: str
    land_id: str
    previous_owner: str
    new_owner: str
    transfer_type: str
    transfer_date: float
    transaction_id: str
    registered_by: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class LandRegistryContract:
    """
    Smart Contract: enforces all registry rules.
    Operates over an in-memory state; blockchain stores the audit log.
    """

    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.lands: Dict[str, LandParcel] = {}             # land_id -> parcel
        self.title_index: Dict[str, str] = {}              # title_number -> land_id
        self.ownership_history: List[OwnershipRecord] = []
        self.officials: Dict[str, Dict] = {}               # address -> profile
        self.citizens: Dict[str, Dict] = {}                # address -> profile

    # ══════════════════════════════════════════════════════════════════════
    #  USER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════

    def register_official(self, address: str, name: str, role: str, department: str) -> Dict:
        if address in self.officials:
            raise ValueError(f"Official {address} already registered.")
        self.officials[address] = {
            "address": address,
            "name": name,
            "role": role,
            "department": department,
            "registered_at": time.time(),
        }
        return self.officials[address]

    def register_citizen(self, address: str, name: str, national_id: str, contact: str) -> Dict:
        if address in self.citizens:
            raise ValueError(f"Citizen {address} already registered.")
        self.citizens[address] = {
            "address": address,
            "name": name,
            "national_id": national_id,
            "contact": contact,
            "registered_at": time.time(),
        }
        return self.citizens[address]

    def _require_official(self, address: str):
        if address not in self.officials:
            raise PermissionError(f"Address {address} is not a registered official.")

    def _require_owner(self, land_id: str, address: str):
        parcel = self._get_parcel(land_id)
        if parcel.owner_address != address:
            raise PermissionError(f"Address {address} is not the owner of land {land_id}.")

    # ══════════════════════════════════════════════════════════════════════
    #  LAND REGISTRATION
    # ══════════════════════════════════════════════════════════════════════

    def register_land(
        self,
        registrar_address: str,
        title_number: str,
        location: str,
        area_sqm: float,
        land_use: str,
        owner_address: str,
        owner_name: str,
        coordinates: Optional[str] = None,
        valuation: float = 0.0,
        metadata: Optional[Dict] = None,
    ) -> LandParcel:
        self._require_official(registrar_address)

        if title_number in self.title_index:
            raise ValueError(f"Title number {title_number} already registered.")
        if area_sqm <= 0:
            raise ValueError("Area must be positive.")

        land_id = str(uuid.uuid4())
        parcel = LandParcel(
            land_id=land_id,
            title_number=title_number,
            location=location,
            area_sqm=area_sqm,
            land_use=land_use,
            owner_address=owner_address,
            owner_name=owner_name,
            coordinates=coordinates,
            valuation=valuation,
            metadata=metadata or {},
        )

        self.lands[land_id] = parcel
        self.title_index[title_number] = land_id

        # Blockchain record
        self.blockchain.create_transaction(
            tx_type=TransactionType.REGISTER,
            land_id=land_id,
            from_address=registrar_address,
            to_address=owner_address,
            data=parcel.to_dict(),
        )

        return parcel

    # ══════════════════════════════════════════════════════════════════════
    #  OWNERSHIP TRANSFER
    # ══════════════════════════════════════════════════════════════════════

    def transfer_ownership(
        self,
        registrar_address: str,
        land_id: str,
        new_owner_address: str,
        new_owner_name: str,
        transfer_type: str = "SALE",
        notes: str = "",
    ) -> OwnershipRecord:
        self._require_official(registrar_address)
        parcel = self._get_parcel(land_id)

        if parcel.status == LandStatus.FROZEN:
            raise ValueError("Land is frozen and cannot be transferred.")
        if parcel.status == LandStatus.DISPUTED:
            raise ValueError("Land is under dispute and cannot be transferred.")
        if parcel.status == LandStatus.ENCUMBERED:
            raise ValueError("Land is encumbered (mortgaged). Release encumbrance first.")

        old_owner = parcel.owner_address
        old_name = parcel.owner_name

        # Update state
        parcel.owner_address = new_owner_address
        parcel.owner_name = new_owner_name
        parcel.last_updated = time.time()

        record = OwnershipRecord(
            record_id=str(uuid.uuid4()),
            land_id=land_id,
            previous_owner=old_owner,
            new_owner=new_owner_address,
            transfer_type=transfer_type,
            transfer_date=time.time(),
            transaction_id="",
            registered_by=registrar_address,
            notes=notes,
        )
        self.ownership_history.append(record)

        tx = self.blockchain.create_transaction(
            tx_type=TransactionType.TRANSFER,
            land_id=land_id,
            from_address=old_owner,
            to_address=new_owner_address,
            data={
                "record": record.to_dict(),
                "transfer_type": transfer_type,
                "old_owner_name": old_name,
                "new_owner_name": new_owner_name,
                "notes": notes,
            },
        )
        record.transaction_id = tx.tx_id
        return record

    # ══════════════════════════════════════════════════════════════════════
    #  ENCUMBRANCE (MORTGAGE / LIEN)
    # ══════════════════════════════════════════════════════════════════════

    def encumber_land(self, registrar_address: str, land_id: str, details: str) -> LandParcel:
        self._require_official(registrar_address)
        parcel = self._get_parcel(land_id)

        if parcel.status != LandStatus.ACTIVE:
            raise ValueError(f"Cannot encumber land with status {parcel.status}.")

        parcel.status = LandStatus.ENCUMBERED
        parcel.encumbrance_details = details
        parcel.last_updated = time.time()

        self.blockchain.create_transaction(
            tx_type=TransactionType.ENCUMBER,
            land_id=land_id,
            from_address=registrar_address,
            to_address=parcel.owner_address,
            data={"details": details},
        )
        return parcel

    def release_encumbrance(self, registrar_address: str, land_id: str) -> LandParcel:
        self._require_official(registrar_address)
        parcel = self._get_parcel(land_id)

        if parcel.status != LandStatus.ENCUMBERED:
            raise ValueError("Land is not currently encumbered.")

        parcel.status = LandStatus.ACTIVE
        parcel.encumbrance_details = None
        parcel.last_updated = time.time()

        self.blockchain.create_transaction(
            tx_type=TransactionType.RELEASE_ENCUMBRANCE,
            land_id=land_id,
            from_address=registrar_address,
            to_address=parcel.owner_address,
            data={"released_at": time.time()},
        )
        return parcel

    # ══════════════════════════════════════════════════════════════════════
    #  DISPUTES
    # ══════════════════════════════════════════════════════════════════════

    def raise_dispute(self, requestor_address: str, land_id: str, reason: str) -> LandParcel:
        parcel = self._get_parcel(land_id)
        parcel.status = LandStatus.DISPUTED
        parcel.dispute_details = reason
        parcel.last_updated = time.time()

        self.blockchain.create_transaction(
            tx_type=TransactionType.DISPUTE,
            land_id=land_id,
            from_address=requestor_address,
            to_address=parcel.owner_address,
            data={"reason": reason},
        )
        return parcel

    def resolve_dispute(self, registrar_address: str, land_id: str, resolution: str) -> LandParcel:
        self._require_official(registrar_address)
        parcel = self._get_parcel(land_id)

        if parcel.status != LandStatus.DISPUTED:
            raise ValueError("Land is not under dispute.")

        parcel.status = LandStatus.ACTIVE
        parcel.dispute_details = None
        parcel.last_updated = time.time()

        self.blockchain.create_transaction(
            tx_type=TransactionType.RESOLVE_DISPUTE,
            land_id=land_id,
            from_address=registrar_address,
            to_address=parcel.owner_address,
            data={"resolution": resolution},
        )
        return parcel

    # ══════════════════════════════════════════════════════════════════════
    #  QUERIES (PUBLIC / CITIZEN ACCESS)
    # ══════════════════════════════════════════════════════════════════════

    def get_land(self, land_id: str) -> LandParcel:
        return self._get_parcel(land_id)

    def get_land_by_title(self, title_number: str) -> LandParcel:
        if title_number not in self.title_index:
            raise KeyError(f"Title {title_number} not found.")
        return self.lands[self.title_index[title_number]]

    def get_lands_by_owner(self, owner_address: str) -> List[LandParcel]:
        return [p for p in self.lands.values() if p.owner_address == owner_address]

    def get_ownership_history(self, land_id: str) -> List[OwnershipRecord]:
        return [r for r in self.ownership_history if r.land_id == land_id]

    def get_blockchain_history(self, land_id: str) -> List[Dict]:
        return self.blockchain.get_land_history(land_id)

    def get_all_lands(self) -> List[LandParcel]:
        return list(self.lands.values())

    def get_chain_stats(self) -> Dict:
        return self.blockchain.get_chain_stats()

    # ─────────────────────────── Helpers ──────────────────────────────────

    def _get_parcel(self, land_id: str) -> LandParcel:
        if land_id not in self.lands:
            raise KeyError(f"Land {land_id} not found.")
        return self.lands[land_id]