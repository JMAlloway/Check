#!/usr/bin/env python3
"""
DEPRECATED: This script has been moved to scripts/create_admin.py

The new script includes:
- Environment guards (blocks production/pilot/staging/uat)
- Interactive prompts for credentials
- Random password generation option
- No hardcoded default credentials

Usage:
    python -m scripts.create_admin
"""

import sys
import warnings

warnings.warn(
    "create_admin.py is deprecated. Use 'python -m scripts.create_admin' instead.",
    DeprecationWarning,
    stacklevel=2,
)

print("=" * 60, file=sys.stderr)
print("DEPRECATED: This script has moved!", file=sys.stderr)
print("=" * 60, file=sys.stderr)
print(file=sys.stderr)
print("Please use the new script instead:", file=sys.stderr)
print(file=sys.stderr)
print("    python -m scripts.create_admin", file=sys.stderr)
print(file=sys.stderr)
print("The new script includes security improvements:", file=sys.stderr)
print("  - Blocks execution in production/pilot/staging/uat", file=sys.stderr)
print("  - Interactive prompts (no hardcoded credentials)", file=sys.stderr)
print("  - Random password generation option", file=sys.stderr)
print("=" * 60, file=sys.stderr)

sys.exit(1)
