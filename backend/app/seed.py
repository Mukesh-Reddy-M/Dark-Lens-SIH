"""Load or deterministically reset the local Nightjar synthetic case."""

from __future__ import annotations

import argparse

from .database import init_db, seed_nightjar, session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-nightjar", action="store_true", help="replace only the Nightjar case and its child records")
    args = parser.parse_args()
    init_db()
    with session() as db:
        seed_nightjar(db, reset=args.reset_nightjar)
    print("Nightjar synthetic case is ready (SYNTHETIC records only).")


if __name__ == "__main__":
    main()
