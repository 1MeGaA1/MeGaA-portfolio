"""Create login accounts for Vortex (staff + a demo member).

Run from the server folder (no need for the server to be running):
    python tools\\provision.py
    python tools\\provision.py --staff-user owner --staff-pass mypass --pin 4321
    python tools\\provision.py --member-email me@x.com --member-pass 1234 --member-hours 5

Staff accounts sign in to the admin panel (the whole back office). The demo member is for
logging in on a station/kiosk. Safe to run repeatedly — it updates existing accounts.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vortex_server.auth import hash_password
from vortex_server.config import load_settings
from vortex_server.db import Database
from vortex_server.engine import Engine
from vortex_server.ws import Hub


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staff-user", default="owner")
    ap.add_argument("--staff-pass", default="vortex123")
    ap.add_argument("--pin", default="4321")
    ap.add_argument("--role", default="admin")
    ap.add_argument("--member-email", default="demo@vortex.gg")
    ap.add_argument("--member-user", default="demo")
    ap.add_argument("--member-pass", default="demo123")
    ap.add_argument("--member-hours", type=float, default=5.0)
    ap.add_argument("--no-member", action="store_true")
    args = ap.parse_args()

    settings = load_settings()
    db = Database(settings.db_path)
    db.init_schema()
    engine = Engine(db, settings, Hub())
    engine.seed_defaults()   # ensures admin/admin, groups, packages exist

    # ---- staff account ----
    row = db.one("SELECT id FROM staff WHERE username=?", (args.staff_user,))
    now = engine.now_iso()
    if row:
        db.execute("UPDATE staff SET password_hash=?, pin_hash=?, role=? WHERE id=?",
                   (hash_password(args.staff_pass), hash_password(args.pin), args.role, row["id"]))
        staff_action = "updated"
    else:
        db.insert("INSERT INTO staff (username, password_hash, pin_hash, role, created_at) VALUES (?,?,?,?,?)",
                  (args.staff_user, hash_password(args.staff_pass), hash_password(args.pin), args.role, now))
        staff_action = "created"

    lines = []
    lines.append("=" * 58)
    lines.append("  VORTEX ACCOUNTS")
    lines.append("=" * 58)
    lines.append("")
    lines.append(f"  ADMIN PANEL  (the whole system)   [{staff_action}]")
    lines.append(f"    open      : http://localhost:{settings.port}/admin/")
    lines.append(f"    username  : {args.staff_user}")
    lines.append(f"    password  : {args.staff_pass}")
    lines.append(f"    exit PIN  : {args.pin}   (typed on a station after Ctrl+Shift+Q)")
    lines.append(f"    (the built-in 'admin' / 'admin' account also still works)")

    # ---- demo member ----
    if not args.no_member:
        m = db.one("SELECT id FROM members WHERE email=?", (args.member_email.lower(),))
        if m:
            db.execute("UPDATE members SET password_hash=?, enabled=1 WHERE id=?",
                       (hash_password(args.member_pass), m["id"]))
            mid = m["id"]
        else:
            view = engine.create_member(args.member_email, args.member_pass, args.member_user, "GOLD")
            mid = view["id"]
        seconds = int(args.member_hours * 3600)
        db.execute("UPDATE members SET time_balance_seconds=? WHERE id=?", (seconds, mid))
        db.insert(
            "INSERT INTO transactions (kind, member_id, seconds, amount, note, created_at) "
            "VALUES ('topup',?,?,?,?,?)",
            (mid, seconds, 0, "provisioned demo time", now),
        )
        member = db.one("SELECT username, email FROM members WHERE id=?", (mid,))
        lines.append("")
        lines.append("  DEMO MEMBER  (log in on a station / kiosk)")
        lines.append(f"    email     : {member['email']}")
        lines.append(f"    username  : {member['username']}")
        lines.append(f"    password  : {args.member_pass}")
        lines.append(f"    time      : {args.member_hours:g} hours")

    lines.append("")
    lines.append(f"  database    : {settings.db_path}")
    lines.append("=" * 58)
    db.close()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
