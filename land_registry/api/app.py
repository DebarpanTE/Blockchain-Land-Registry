"""
Land Registry API — Flask Application
"""

import os
import sys
from functools import wraps

from flask import Flask, request, jsonify, render_template

# Resolve the project root (one level above this api/ folder)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from blockchain.chain import Blockchain
from contracts.land_registry import LandRegistryContract


TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "frontend", "templates")
STATIC_DIR = os.path.join(PROJECT_ROOT, "frontend", "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# ── Bootstrap ─────────────────────────────────────────────────────────────
blockchain = Blockchain()
registry = LandRegistryContract(blockchain)

# Seed a default system official
try:
    registry.register_official(
        address="SYSTEM_ADMIN",
        name="System Administrator",
        role="super_admin",
        department="Land Registry Authority",
    )
except Exception:
    pass


# ── Auth Helper ───────────────────────────────────────────────────────────

def get_caller() -> str:
    """Extract caller address from X-Caller-Address header."""
    return request.headers.get("X-Caller-Address", "ANONYMOUS")


def official_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        caller = get_caller()
        if caller not in registry.officials:
            return jsonify({"error": "Official access required"}), 403
        return f(*args, **kwargs)
    return decorated


def handle(fn):
    """Wrap a handler to catch exceptions and return JSON errors."""
    try:
        result = fn()
        return jsonify({"success": True, "data": result}), 200
    except (PermissionError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except KeyError as e:
        return jsonify({"success": False, "error": f"Not found: {e}"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
#  DASHBOARD (HTML)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/")
def dashboard():
    stats = registry.get_chain_stats()
    lands = [p.to_dict() for p in registry.get_all_lands()]
    return render_template("dashboard.html", stats=stats, lands=lands)


# ══════════════════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/officials", methods=["POST"])
def api_register_official():
    b = request.json or {}
    return handle(lambda: registry.register_official(
        address=b["address"], name=b["name"],
        role=b.get("role", "registrar"), department=b.get("department", ""),
    ))


@app.route("/api/citizens", methods=["POST"])
def api_register_citizen():
    b = request.json or {}
    return handle(lambda: registry.register_citizen(
        address=b["address"], name=b["name"],
        national_id=b["national_id"], contact=b.get("contact", ""),
    ))


@app.route("/api/officials", methods=["GET"])
def api_list_officials():
    return handle(lambda: list(registry.officials.values()))


@app.route("/api/citizens", methods=["GET"])
def api_list_citizens():
    return handle(lambda: list(registry.citizens.values()))


# ══════════════════════════════════════════════════════════════════════════
#  LAND OPERATIONS
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/lands", methods=["POST"])
@official_required
def api_register_land():
    b = request.json or {}
    caller = get_caller()
    return handle(lambda: registry.register_land(
        registrar_address=caller,
        title_number=b["title_number"],
        location=b["location"],
        area_sqm=float(b["area_sqm"]),
        land_use=b.get("land_use", "residential"),
        owner_address=b["owner_address"],
        owner_name=b["owner_name"],
        coordinates=b.get("coordinates"),
        valuation=float(b.get("valuation", 0)),
        metadata=b.get("metadata", {}),
    ).to_dict())


@app.route("/api/lands", methods=["GET"])
def api_list_lands():
    owner = request.args.get("owner")
    return handle(lambda: (
        [p.to_dict() for p in registry.get_lands_by_owner(owner)]
        if owner else [p.to_dict() for p in registry.get_all_lands()]
    ))


@app.route("/api/lands/<land_id>", methods=["GET"])
def api_get_land(land_id):
    return handle(lambda: registry.get_land(land_id).to_dict())


@app.route("/api/lands/title/<title_number>", methods=["GET"])
def api_get_by_title(title_number):
    return handle(lambda: registry.get_land_by_title(title_number).to_dict())


@app.route("/api/lands/<land_id>/transfer", methods=["POST"])
@official_required
def api_transfer(land_id):
    b = request.json or {}
    caller = get_caller()
    return handle(lambda: registry.transfer_ownership(
        registrar_address=caller,
        land_id=land_id,
        new_owner_address=b["new_owner_address"],
        new_owner_name=b["new_owner_name"],
        transfer_type=b.get("transfer_type", "SALE"),
        notes=b.get("notes", ""),
    ).to_dict())


@app.route("/api/lands/<land_id>/encumber", methods=["POST"])
@official_required
def api_encumber(land_id):
    b = request.json or {}
    caller = get_caller()
    return handle(lambda: registry.encumber_land(
        registrar_address=caller,
        land_id=land_id,
        details=b.get("details", ""),
    ).to_dict())


@app.route("/api/lands/<land_id>/release-encumbrance", methods=["POST"])
@official_required
def api_release(land_id):
    caller = get_caller()
    return handle(lambda: registry.release_encumbrance(caller, land_id).to_dict())


@app.route("/api/lands/<land_id>/dispute", methods=["POST"])
def api_dispute(land_id):
    b = request.json or {}
    caller = get_caller()
    return handle(lambda: registry.raise_dispute(caller, land_id, b.get("reason", "")).to_dict())


@app.route("/api/lands/<land_id>/resolve-dispute", methods=["POST"])
@official_required
def api_resolve(land_id):
    b = request.json or {}
    caller = get_caller()
    return handle(lambda: registry.resolve_dispute(caller, land_id, b.get("resolution", "")).to_dict())


# ══════════════════════════════════════════════════════════════════════════
#  HISTORY & BLOCKCHAIN
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/lands/<land_id>/history", methods=["GET"])
def api_history(land_id):
    return handle(lambda: {
        "ownership_history": [r.to_dict() for r in registry.get_ownership_history(land_id)],
        "blockchain_history": registry.get_blockchain_history(land_id),
    })


@app.route("/api/blockchain", methods=["GET"])
def api_blockchain():
    return handle(lambda: {
        "chain": blockchain.to_dict(),
        "stats": blockchain.get_chain_stats(),
    })


@app.route("/api/blockchain/validate", methods=["GET"])
def api_validate():
    return handle(lambda: {
        "is_valid": blockchain.is_chain_valid(),
        "total_blocks": len(blockchain.chain),
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return handle(lambda: {
        "blockchain": blockchain.get_chain_stats(),
        "total_lands": len(registry.lands),
        "total_officials": len(registry.officials),
        "total_citizens": len(registry.citizens),
    })


if __name__ == "__main__":
    print("🏛️  Land Registry Blockchain System")
    print("   Running at http://localhost:5000")
    app.run(debug=True, port=5000)
