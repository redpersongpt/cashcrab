#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="${REPO_OWNER:-redpersongpt}"
REPO_NAME="${REPO_NAME:-cashcrab}"
CASHCRAB_REF="${CASHCRAB_REF:-main}"
INSTALL_ROOT="${CASHCRAB_HOME:-$HOME/.local/share/cashcrab}"
BIN_DIR="${CASHCRAB_BIN_DIR:-$HOME/.local/bin}"
VENV_DIR="$INSTALL_ROOT/venv"
SOURCE_DIR="$INSTALL_ROOT/source"
ARCHIVE_URL="https://codeload.github.com/${REPO_OWNER}/${REPO_NAME}/tar.gz/refs/heads/${CASHCRAB_REF}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

choose_profile() {
  for candidate in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    if [ -f "$candidate" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  printf '%s' "$HOME/.profile"
}

ensure_path_line() {
  local profile
  profile="$(choose_profile)"
  mkdir -p "$(dirname "$profile")"
  touch "$profile"

  if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$profile"; then
    {
      echo
      echo '# Added by CashCrab installer'
      echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >>"$profile"
    echo "Updated PATH in $profile"
  fi
}

need curl
need tar
need python3

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"

echo "Downloading CashCrab from GitHub..."
curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/cashcrab.tar.gz"
tar -xzf "$TMP_DIR/cashcrab.tar.gz" -C "$TMP_DIR"

EXTRACTED_DIR="$TMP_DIR/${REPO_NAME}-${CASHCRAB_REF}"
if [ ! -d "$EXTRACTED_DIR" ]; then
  echo "Could not find extracted source directory: $EXTRACTED_DIR" >&2
  exit 1
fi

rm -rf "$SOURCE_DIR"
mkdir -p "$SOURCE_DIR"
cp -R "$EXTRACTED_DIR"/. "$SOURCE_DIR"

echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

echo "Installing CashCrab..."
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel >/dev/null
"$VENV_DIR/bin/pip" install "$SOURCE_DIR" >/dev/null

cat >"$BIN_DIR/cashcrab" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/cashcrab" "\$@"
EOF
chmod +x "$BIN_DIR/cashcrab"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  ensure_path_line
fi

echo
echo "CashCrab installed."
echo "Command: $BIN_DIR/cashcrab"
echo
echo "Next:"
echo "  1. Restart your terminal or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  2. Run: cashcrab"
