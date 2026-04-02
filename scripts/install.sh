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

say() {
  printf '%s\n' "$1"
}

step() {
  printf '\n==> %s\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1" >&2
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

banner() {
  cat <<'EOF'
  ____           __    ______           __
 / ___|__ _ ___ / /_  / ____/________ _/ /_
/ /__/ _` / __// __ \/ /   / ___/ __ `/ __ \
\___/\__,_/\__/ \____/_/   /_/   \__,_/\__/

CashCrab installer
EOF
}

have() {
  command -v "$1" >/dev/null 2>&1
}

need_sudo() {
  if [ "$(id -u)" -ne 0 ] && ! have sudo; then
    die "Need sudo to install system packages."
  fi
}

apt_install() {
  need_sudo
  sudo apt-get update
  sudo apt-get install -y "$@"
}

dnf_install() {
  need_sudo
  sudo dnf install -y "$@"
}

yum_install() {
  need_sudo
  sudo yum install -y "$@"
}

pacman_install() {
  need_sudo
  sudo pacman -Sy --noconfirm "$@"
}

zypper_install() {
  need_sudo
  sudo zypper --non-interactive install "$@"
}

brew_install() {
  brew install "$@"
}

ensure_python() {
  if have python3; then
    return 0
  fi

  step "Python 3 not found. Trying to install it"

  if have brew; then
    brew_install python
  elif have apt-get; then
    apt_install python3 python3-venv python3-pip tar
  elif have dnf; then
    dnf_install python3 python3-pip tar
  elif have yum; then
    yum_install python3 tar
  elif have pacman; then
    pacman_install python tar
  elif have zypper; then
    zypper_install python3 python3-pip tar
  else
    die "Python 3 is missing and no supported package manager was found."
  fi

  have python3 || die "Python 3 install did not succeed."
}

ensure_tar() {
  if have tar; then
    return 0
  fi

  step "tar not found. Trying to install it"

  if have brew; then
    brew_install gnu-tar
  elif have apt-get; then
    apt_install tar
  elif have dnf; then
    dnf_install tar
  elif have yum; then
    yum_install tar
  elif have pacman; then
    pacman_install tar
  elif have zypper; then
    zypper_install tar
  else
    die "tar is missing and no supported package manager was found."
  fi

  have tar || die "tar install did not succeed."
}

ensure_venv_support() {
  if python3 - <<'PY' >/dev/null 2>&1
import venv
PY
  then
    return 0
  fi

  step "Python venv support is missing. Trying to install it"

  if have apt-get; then
    apt_install python3-venv
  else
    die "python3 exists but the venv module is missing."
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
    say "Added ~/.local/bin to PATH in $profile"
  fi
}

install_cashcrab() {
  local tmp_dir extracted_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT

  mkdir -p "$INSTALL_ROOT" "$BIN_DIR"

  step "Downloading CashCrab"
  curl -fsSL "$ARCHIVE_URL" -o "$tmp_dir/cashcrab.tar.gz"
  tar -xzf "$tmp_dir/cashcrab.tar.gz" -C "$tmp_dir"

  extracted_dir="$tmp_dir/${REPO_NAME}-${CASHCRAB_REF}"
  [ -d "$extracted_dir" ] || die "Could not find extracted source directory: $extracted_dir"

  rm -rf "$SOURCE_DIR"
  mkdir -p "$SOURCE_DIR"
  cp -R "$extracted_dir"/. "$SOURCE_DIR"

  step "Creating private environment"
  python3 -m venv "$VENV_DIR"

  step "Installing app dependencies"
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

  step "Checking optional media tools"
  if have ffmpeg; then
    say "ffmpeg: found"
  else
    warn "ffmpeg not found. Video generation may fail until you install it."
  fi

  if have magick || have convert; then
    say "ImageMagick: found"
  else
    warn "ImageMagick not found. Some MoviePy text/subtitle operations may need it."
  fi

  cat <<EOF

CashCrab is installed.

Command:
  cashcrab

If the command is not found right away:
  export PATH="\$HOME/.local/bin:\$PATH"

Then run:
  cashcrab
EOF
}

banner
step "Checking installer dependencies"
have curl || die "curl is required to run this installer."
ensure_tar
ensure_python
ensure_venv_support
install_cashcrab
