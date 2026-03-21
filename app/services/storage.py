from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.models.schemas import WeddingState


class Storage:
    """Simple file-backed storage for planner state.

    Implemented defensively so main.py never crashes if I/O fails.
    """

    def __init__(self, state_path: str = "data/state.json") -> None:
        self.state_path = Path(state_path)

    def load_state(self) -> Optional[WeddingState]:
        """Load a structured WeddingState from disk if available.

        Returns None if the file does not exist or parsing fails.
        """
        try:
            if self.state_path.exists():
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                return WeddingState.model_validate(raw)
        except Exception:
            return None
        return None

    def save_state(self, state: WeddingState) -> bool:
        """Persist a structured WeddingState. Returns False if write fails."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = state.model_dump()
            self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            # After saving state, re-export CSV artifacts (best effort)
            try:
                self.export_budget_csv(state)
            except Exception:
                pass
            try:
                self.export_rooms_csv(state)
            except Exception:
                pass
            try:
                self.export_guests_csv(state)
            except Exception:
                pass
            return True
        except Exception:
            return False

    # ---- CSV export helpers ----
    def export_budget_csv(self, state: WeddingState, csv_path: str = "data/budget.csv") -> bool:
        """Export budget breakdown to a CSV with columns: category, amount, currency.

        Categories (rows):
        venue, catering, decor, accommodation, photography, entertainment, misc, total_estimated, remaining_balance
        """
        try:
            path = Path(csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            fin = state.financial
            currency = (fin.currency if fin else "USD")

            # Safely get numeric values defaulting to 0.0 if missing
            def num(getattr_name: str) -> float:
                try:
                    return float(getattr(fin, getattr_name)) if fin and getattr(fin, getattr_name) is not None else 0.0
                except Exception:
                    return 0.0

            rows = [
                ("venue", num("venue_cost"), currency),
                ("catering", num("catering_cost"), currency),
                ("decor", num("decor_cost"), currency),
                ("accommodation", num("accommodation_cost"), currency),
                ("photography", num("photography_cost"), currency),
                ("entertainment", num("entertainment_cost"), currency),
                ("misc", num("misc_cost"), currency),
                ("total_estimated", num("total_estimated"), currency),
                ("remaining_balance", num("remaining_balance"), currency),
            ]

            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["category", "amount", "currency"])  # header
                for r in rows:
                    writer.writerow(r)
            return True
        except Exception:
            return False

    def export_rooms_csv(self, state: WeddingState, csv_path: str = "data/rooms.csv") -> bool:
        """Export room allocation entries to CSV with columns: room_type, count."""
        try:
            path = Path(csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            allocation = []
            try:
                allocation = list(state.logistics.room_allocation) if state.logistics and state.logistics.room_allocation else []
            except Exception:
                allocation = []

            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["room_type", "count"])  # header
                for entry in allocation:
                    room_type = entry.get("room_type") if isinstance(entry, dict) else None
                    count = entry.get("count") if isinstance(entry, dict) else None
                    if room_type is None or count is None:
                        continue
                    writer.writerow([str(room_type), int(count)])
            return True
        except Exception:
            return False

    def export_guests_csv(self, state: WeddingState, csv_path: str = "data/guests.csv") -> bool:
        """Ensure guests.csv uses the new schema and desired row count.

        Columns (new schema): guest_id, guest_name, side, rsvp_status, assigned_room_type

        - Migrates old files that had `room_type_preference` by dropping that column.
        - Preserves existing rows and assignments when possible.
        - If guest_count increases, append placeholder rows Guest_{N+1}..Guest_{M}.
        - guest_id is a zero-padded numeric string.
        """
        try:
            path = Path(csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Desired count from state
            guest_count = 0
            try:
                guest_count = int(state.profile.guest_count) if state and state.profile and state.profile.guest_count else 0
            except Exception:
                guest_count = 0

            new_header = [
                "guest_id",
                "guest_name",
                "side",
                "rsvp_status",
                "assigned_room_type",
            ]

            old_header = [
                "guest_id",
                "guest_name",
                "side",
                "rsvp_status",
                "room_type_preference",
                "assigned_room_type",
            ]

            if not path.exists():
                # Fresh write
                pad = max(3, len(str(max(1, guest_count))))
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(new_header)
                    for i in range(1, guest_count + 1):
                        gid = str(i).zfill(pad)
                        gname = f"Guest_{gid}"
                        writer.writerow([gid, gname, "", "", ""])  # placeholders
                return True

            # If file exists, read existing content
            existing_rows: list[list[str]] = []
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                for row in reader:
                    existing_rows.append(row)

            if not existing_rows:
                # Corrupt/empty file: rewrite from scratch
                pad = max(3, len(str(max(1, guest_count))))
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(new_header)
                    for i in range(1, guest_count + 1):
                        gid = str(i).zfill(pad)
                        gname = f"Guest_{gid}"
                        writer.writerow([gid, gname, "", "", ""])  # placeholders
                return True

            # Determine existing data start (skip header if present)
            header_row = [c.strip().lower() for c in (existing_rows[0] if existing_rows else [])]
            is_old_header = header_row == [c.lower() for c in old_header]
            is_new_header = header_row == [c.lower() for c in new_header]

            start_idx = 1 if (is_old_header or is_new_header) else 0
            existing_data = existing_rows[start_idx:]
            existing_count = max(0, len(existing_data))

            # Determine padding from existing rows if any
            existing_pad = 0
            if existing_data:
                try:
                    existing_pad = len(str(existing_data[0][0]))
                except Exception:
                    existing_pad = 0
            pad = max(3, existing_pad, len(str(max(1, guest_count))))

            # If header is old or missing/mismatched, migrate by rewriting file
            if not is_new_header:
                migrated: list[list[str]] = []
                for row in existing_data:
                    if len(row) >= 6:  # old schema
                        gid, gname, side, rsvp, _pref, assigned = row[:6]
                        migrated.append([gid, gname, side, rsvp, assigned])
                    else:
                        # Best-effort mapping
                        vals = (row + [""] * 5)[:5]
                        migrated.append(vals)

                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(new_header)
                    for row in migrated:
                        writer.writerow(row)
                existing_rows = [new_header] + migrated
                existing_data = migrated
                existing_count = len(existing_data)
                # Fall-through to possible append below

            if existing_count >= guest_count:
                # Nothing to do; preserve file
                return True

            # Append new placeholder rows
            with path.open("a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for i in range(existing_count + 1, guest_count + 1):
                    gid = str(i).zfill(pad)
                    gname = f"Guest_{gid}"
                    writer.writerow([gid, gname, "", "", ""])  # placeholders
            return True
        except Exception:
            return False

    # ---- Guest CSV read/write helpers ----
    def read_guests(self, csv_path: str = "data/guests.csv") -> list[dict]:
        """Read guests.csv into a list of dicts with the new schema.

        Handles migration from the old header by dropping room_type_preference.
        Missing fields are set to empty strings.
        """
        try:
            path = Path(csv_path)
            if not path.exists():
                return []
            rows: list[dict] = []
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                raw = list(reader)
            if not raw:
                return []
            header = [c.strip().lower() for c in raw[0]]
            data = raw[1:] if raw and raw[0] else raw
            new_header = ["guest_id", "guest_name", "side", "rsvp_status", "assigned_room_type"]
            old_header = ["guest_id", "guest_name", "side", "rsvp_status", "room_type_preference", "assigned_room_type"]

            if header == [c.lower() for c in new_header]:
                idx = {k: i for i, k in enumerate(new_header)}
                for r in data:
                    rows.append({
                        "guest_id": r[idx["guest_id"]] if len(r) > idx["guest_id"] else "",
                        "guest_name": r[idx["guest_name"]] if len(r) > idx["guest_name"] else "",
                        "side": r[idx["side"]] if len(r) > idx["side"] else "",
                        "rsvp_status": r[idx["rsvp_status"]] if len(r) > idx["rsvp_status"] else "",
                        "assigned_room_type": r[idx["assigned_room_type"]] if len(r) > idx["assigned_room_type"] else "",
                    })
                return rows

            # Old header migration
            if header == [c.lower() for c in old_header]:
                for r in data:
                    vals = (r + [""] * 6)[:6]
                    gid, gname, side, rsvp, _pref, assigned = vals
                    rows.append({
                        "guest_id": gid,
                        "guest_name": gname,
                        "side": side,
                        "rsvp_status": rsvp,
                        "assigned_room_type": assigned,
                    })
                return rows

            # Unknown header: best-effort map by position
            for r in data:
                vals = (r + [""] * 5)[:5]
                rows.append({
                    "guest_id": vals[0],
                    "guest_name": vals[1],
                    "side": vals[2],
                    "rsvp_status": vals[3],
                    "assigned_room_type": vals[4],
                })
            return rows
        except Exception:
            return []

    def write_guests(self, rows: list[dict], csv_path: str = "data/guests.csv") -> bool:
        """Overwrite guests.csv with provided rows using the new schema."""
        try:
            path = Path(csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            header = ["guest_id", "guest_name", "side", "rsvp_status", "assigned_room_type"]
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for r in rows:
                    writer.writerow([
                        r.get("guest_id", ""),
                        r.get("guest_name", ""),
                        r.get("side", ""),
                        r.get("rsvp_status", ""),
                        r.get("assigned_room_type", ""),
                    ])
            return True
        except Exception:
            return False
