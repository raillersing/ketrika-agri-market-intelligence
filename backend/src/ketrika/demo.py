"""Retired historical T11.6 runner; never mutate data or claim qualification."""

import sys


def main() -> int:
    """Fail before loading application clients, test datasets or credentials."""
    sys.stderr.write(
        "Historical demo certification is retired (ADR-009). "
        "Use isolated software checks; measured qualification is pending R0.7.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
