#!/usr/bin/env bash
# Install local Git hooks for the APEX repo.
#
# Run once after cloning:
#   bash scripts/install_hooks.sh
#
# This installs a pre-commit hook that runs scripts/check_safe_defaults.py
# and blocks the commit if any of the three live-trading lock layers are
# unsafe.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_PATH="$REPO_ROOT/.git/hooks/pre-commit"

cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
# APEX pre-commit hook — refuses commits that disable the safety lock.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
python "$REPO_ROOT/scripts/check_safe_defaults.py"
HOOK

chmod +x "$HOOK_PATH"
echo "Installed pre-commit hook at $HOOK_PATH"
