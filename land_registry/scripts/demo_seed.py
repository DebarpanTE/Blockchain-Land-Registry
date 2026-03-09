#!/usr/bin/env python3
"""
demo_seed.py — Seeds sample data and prints a testing guide.

Usage:
  1. Start the server:   python api/app.py
  2. Run this script:    python scripts/demo_seed.py
"""

import requests # type: ignore
import json
import sys

BASE = "http://localhost:5000"


def h(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print('═'*60)


def req(method, path, body=None, caller=None, label=""):
    headers = {"Content-Type": "application/json"}
    if caller:
        headers["X-Caller-Address"] = caller
    r = getattr(requests, method)(f"{BASE}{path}", json=body, headers=headers)
    data = r.json()
    status = "✅" if data.get("success") else "❌"
    print(f"\n{status} {label or path}")
    print(json.dumps(data, indent=2)[:600])
    return data


def main():
    h("STEP 1 — Register Officials")
    req("post", "/api/officials", {
        "address": "OFF_001",
        "name": "Alice Registrar",
        "role": "registrar",
        "department": "Kolkata District Land Registry"
    }, label="Register official OFF_001")

    req("post", "/api/officials", {
        "address": "OFF_002",
        "name": "Bob Senior Officer",
        "role": "senior_registrar",
        "department": "West Bengal Revenue Dept"
    }, label="Register official OFF_002")

    h("STEP 2 — Register Citizens")
    req("post", "/api/citizens", {
        "address": "CIT_001",
        "name": "Ravi Kumar",
        "national_id": "AADHAR-9876-5432-1011",
        "contact": "ravi.kumar@email.com"
    }, label="Register citizen Ravi Kumar")

    req("post", "/api/citizens", {
        "address": "CIT_002",
        "name": "Priya Sharma",
        "national_id": "AADHAR-1111-2222-3333",
        "contact": "priya.sharma@email.com"
    }, label="Register citizen Priya Sharma")

    req("post", "/api/citizens", {
        "address": "CIT_003",
        "name": "Arjun Patel",
        "national_id": "AADHAR-4444-5555-6666",
        "contact": "arjun.patel@email.com"
    }, label="Register citizen Arjun Patel")

    h("STEP 3 — Register Land Parcel")
    r = req("post", "/api/lands", {
        "title_number": "LND-KOL-2024-001",
        "location": "Plot 5, Sector 12, New Town, Kolkata 700156",
        "area_sqm": 450,
        "land_use": "residential",
        "owner_address": "CIT_001",
        "owner_name": "Ravi Kumar",
        "coordinates": "22.5726° N, 88.3639° E",
        "valuation": 7500000,
    }, caller="OFF_001", label="Register Plot 5 to Ravi Kumar")

    if not r.get("success"):
        print("❌ Could not register land. Is the server running?")
        sys.exit(1)

    land_id = r["data"]["land_id"]
    print(f"\n  🏷️  Land ID: {land_id}")

    # Second parcel
    req("post", "/api/lands", {
        "title_number": "LND-KOL-2024-002",
        "location": "Shop 12, MG Road, Kolkata 700007",
        "area_sqm": 120,
        "land_use": "commercial",
        "owner_address": "CIT_002",
        "owner_name": "Priya Sharma",
        "valuation": 12000000,
    }, caller="OFF_001", label="Register Shop 12 to Priya Sharma")

    h("STEP 4 — Encumber Land (Mortgage)")
    req("post", f"/api/lands/{land_id}/encumber", {
        "details": "HDFC Bank Home Loan — ₹4,000,000 — Loan#HDFC-2024-8821"
    }, caller="OFF_001", label="Encumber Plot 5 with HDFC mortgage")

    h("STEP 5 — Attempt Transfer While Encumbered (Should Fail)")
    req("post", f"/api/lands/{land_id}/transfer", {
        "new_owner_address": "CIT_002",
        "new_owner_name": "Priya Sharma",
        "transfer_type": "SALE"
    }, caller="OFF_001", label="Transfer attempt — SHOULD FAIL (encumbered)")

    h("STEP 6 — Release Encumbrance")
    req("post", f"/api/lands/{land_id}/release-encumbrance", {},
        caller="OFF_001", label="Release HDFC mortgage")

    h("STEP 7 — Transfer Ownership")
    req("post", f"/api/lands/{land_id}/transfer", {
        "new_owner_address": "CIT_002",
        "new_owner_name": "Priya Sharma",
        "transfer_type": "SALE",
        "notes": "Sale deed registered at Sub-Registrar Office on 23 Feb 2024"
    }, caller="OFF_001", label="Transfer Plot 5: Ravi → Priya (SALE)")

    h("STEP 8 — Raise Dispute")
    req("post", f"/api/lands/{land_id}/dispute", {
        "reason": "CIT_003 claims boundary encroachment — 2m overlap on north side"
    }, caller="CIT_003", label="Arjun Patel raises boundary dispute")

    h("STEP 9 — Resolve Dispute")
    req("post", f"/api/lands/{land_id}/resolve-dispute", {
        "resolution": "Court Order #WB/2024/1234: Dispute resolved. Priya Sharma is rightful owner."
    }, caller="OFF_002", label="Bob resolves dispute via court order")

    h("STEP 10 — Query Full History")
    req("get", f"/api/lands/{land_id}/history", label="Full blockchain + ownership history")

    h("STEP 11 — Validate Blockchain")
    req("get", "/api/blockchain/validate", label="Chain integrity validation")

    h("STEP 12 — System Stats")
    req("get", "/api/stats", label="System statistics")

    h("DEMO COMPLETE ✅")
    print("""
  All operations demonstrated:
  ✅ Role-based access (officials vs citizens)
  ✅ Land registration with blockchain mining
  ✅ Encumbrance (mortgage) and release
  ✅ Failed transfer enforcement (encumbered land)
  ✅ Ownership transfer with history tracking
  ✅ Dispute raise and resolution workflow
  ✅ Full blockchain audit trail
  ✅ Chain integrity validation

  🌐 Open http://localhost:5000 to explore the dashboard!
""")


if __name__ == "__main__":
    main()