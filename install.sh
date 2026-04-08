#!/usr/bin/env bash
# ============================================================================
# Cognithor · Agent OS – Installation Script
# ============================================================================
#
# Usage:
#   chmod +x install.sh
#   ./install.sh              Full installation (interactive)
#   ./install.sh --minimal    Core only (no Web, no Telegram)
#   ./install.sh --full       Everything including Voice
#   ./install.sh --use-uv     Use uv instead of pip (10x faster)
#   ./install.sh --systemd    Install systemd services only
#   ./install.sh --uninstall  Uninstall
#
# Prerequisites:
#   - Python 3.12+
#   - pip (or uv with --use-uv)
#   - Ollama (installed and running)
#
# ============================================================================
set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# --- Configuration ---
JARVIS_HOME="${JARVIS_HOME:-$HOME/.jarvis}"
VENV_DIR="${JARVIS_HOME}/venv"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIN_PYTHON="3.12"
OLLAMA_URL="${JARVIS_OLLAMA_BASE_URL:-http://localhost:11434}"
USE_UV=false
PKG_INSTALLER=""  # "uv" or "pip", set in detect_installer

# --- Error Tracker ---
INSTALL_FAILED=false

# ============================================================================
# Helper functions
# ============================================================================

info()    { echo -e "${BLUE}[i]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[!]${NC}  $*"; }
error()   { echo -e "${RED}[X]${NC}  $*" >&2; }
fatal()   {
    error "$*"
    INSTALL_FAILED=true
    show_error_submission
    exit 1
}
header()  { echo -e "\n${BOLD}${CYAN}=== $* ===${NC}\n"; }

check_command() {
    command -v "$1" &>/dev/null
}

version_ge() {
    # Check if version $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1 | grep -qF "$2"
}

# ============================================================================
# Error Submission Helper
# ============================================================================

show_error_submission() {
    echo ""
    echo -e "${RED}${BOLD}[X] Installation failed.${NC}"
    echo ""
    echo "  Please open an issue on GitHub:"
    echo "  https://github.com/Alex8791-cyber/cognithor/issues/new"
    echo ""
    echo "  Include the output above as a log."
    echo ""
}

# ============================================================================
# Banner (dynamic version from pyproject.toml)
# ============================================================================

show_banner() {
    local version="unknown"
    if [[ -f "$REPO_DIR/pyproject.toml" ]]; then
        version=$(grep '^version' "$REPO_DIR/pyproject.toml" | head -1 | cut -d'"' -f2)
    fi

    echo -e "${BOLD}${CYAN}"
    cat << 'BANNER'

       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
BANNER
    echo -e "           Agent OS · v${version} · Installer"
    echo ""
    echo -e "${NC}"
}

# ============================================================================
# Installer detection (uv / pip)
# ============================================================================

detect_installer() {
    if [[ "$USE_UV" == true ]]; then
        if check_command uv; then
            local uv_ver
            uv_ver=$(uv --version 2>/dev/null | head -1)
            PKG_INSTALLER="uv"
            success "uv found ($uv_ver)"
            return 0
        else
            warn "uv not found, installing automatically..."
            local _uv_install_script
            _uv_install_script=$(mktemp)
            if curl -LsSf --max-time 30 https://astral.sh/uv/install.sh -o "$_uv_install_script"; then
                warn "Downloaded uv installer to $_uv_install_script -- executing..."
                sh "$_uv_install_script" 2>/dev/null
                rm -f "$_uv_install_script"
                # Update PATH
                export PATH="$HOME/.local/bin:$PATH"
                if check_command uv; then
                    local uv_ver
                    uv_ver=$(uv --version 2>/dev/null | head -1)
                    PKG_INSTALLER="uv"
                    success "uv installed ($uv_ver)"
                    return 0
                fi
            else
                rm -f "$_uv_install_script"
            fi
            warn "Could not install uv -- falling back to pip"
        fi
    fi

    # Auto-Detect: prefer uv if available
    if check_command uv; then
        local uv_ver
        uv_ver=$(uv --version 2>/dev/null | head -1)
        PKG_INSTALLER="uv"
        success "uv detected ($uv_ver) -- will be used"
        return 0
    fi

    # Fallback: pip
    if python3 -m pip --version &>/dev/null; then
        PKG_INSTALLER="pip"
        success "pip available"
        return 0
    fi

    echo ""
    error "pip not found!"
    echo ""
    echo "  Install pip with:"
    echo ""
    echo "    sudo apt install python3-pip"
    echo ""
    echo "  Then run again:"
    echo ""
    echo "    ./install.sh"
    echo ""
    INSTALL_FAILED=true
    show_error_submission
    exit 1
}

# ============================================================================
# Helper: Distro-specific Python install hint
# ============================================================================

_python_install_hint() {
    local distro_id=""
    if [[ -f /etc/os-release ]]; then
        distro_id=$(. /etc/os-release && echo "${ID:-}")
    fi

    echo ""
    info "Install Python ${MIN_PYTHON}+:"
    echo ""
    case "$distro_id" in
        ubuntu)
            echo "    sudo add-apt-repository ppa:deadsnakes/ppa"
            echo "    sudo apt update"
            echo "    sudo apt install python3.12 python3.12-venv python3.12-dev"
            ;;
        debian)
            echo "    # Option 1: Enable backports"
            echo "    # Option 2: Use pyenv:"
            echo "    curl https://pyenv.run | bash"
            echo "    pyenv install 3.12"
            ;;
        fedora|rhel|centos|rocky|alma)
            echo "    sudo dnf install python3.12 python3.12-devel"
            ;;
        arch|manjaro)
            echo "    sudo pacman -S python"
            ;;
        opensuse*|sles)
            echo "    sudo zypper install python312 python312-devel"
            ;;
        *)
            echo "    https://www.python.org/downloads/"
            ;;
    esac
    echo ""
}

# ============================================================================
# Step 1: Check system prerequisites
# ============================================================================

check_prerequisites() {
    header "Checking system prerequisites"
    local errors=0

    # Python
    if check_command python3; then
        local py_version
        py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if version_ge "$py_version" "$MIN_PYTHON"; then
            success "Python $py_version found"
        else
            error "Python $py_version too old (need at least $MIN_PYTHON)"
            _python_install_hint
            errors=$((errors + 1))
        fi
    else
        error "Python3 not found"
        _python_install_hint
        errors=$((errors + 1))
    fi

    # pip
    if [[ "$USE_UV" != true ]]; then
        if python3 -m pip --version &>/dev/null; then
            success "pip available"
        else
            error "pip not found"
            echo ""
            echo "  Fix with:"
            echo "    sudo apt install python3-pip"
            echo ""
            fatal "pip is a required dependency. Please install and try again."
        fi
    fi

    # venv
    if python3 -m venv --help &>/dev/null; then
        success "venv module available"
    else
        error "venv not found"
        echo ""
        echo "  Fix with:"
        echo "    sudo apt install python3.12-venv"
        echo ""
        fatal "python3-venv is a required dependency. Please install and try again."
    fi

    # git (optional)
    if check_command git; then
        success "git available"
    else
        warn "git not found (optional, recommended for updates)"
    fi

    # Ollama
    if check_command ollama; then
        local ollama_version
        ollama_version=$(ollama --version 2>/dev/null | head -1 || echo "unknown")
        success "Ollama installed ($ollama_version)"
    else
        warn "Ollama not found -- LLM features will be limited without Ollama"
        read -rp "  Install Ollama now? [y/N] " _ollama_answer
        if [[ "$_ollama_answer" =~ ^[yY]$ ]]; then
            info "Installing Ollama..."
            local _ollama_install_script
            _ollama_install_script=$(mktemp)
            curl -fsSL --max-time 60 https://ollama.com/install.sh -o "$_ollama_install_script"
            if [ $? -eq 0 ] && sh "$_ollama_install_script"; then
                rm -f "$_ollama_install_script"
                success "Ollama installed"
                # Start Ollama server
                nohup ollama serve &>/dev/null &
                info "Waiting for Ollama server..."
                local _ollama_delay=1
                local _ollama_total=0
                while [[ $_ollama_total -lt 15 ]]; do
                    if curl -sf --max-time 2 "${OLLAMA_URL}/api/version" &>/dev/null; then
                        success "Ollama server started"
                        break
                    fi
                    sleep "$_ollama_delay"
                    _ollama_total=$((_ollama_total + _ollama_delay))
                    # Exponential backoff: 1, 2, 4 (capped)
                    _ollama_delay=$((_ollama_delay * 2))
                    [[ $_ollama_delay -gt 4 ]] && _ollama_delay=4
                done
                if [[ $_ollama_total -ge 15 ]]; then
                    warn "Ollama server not reachable after 15s -- start manually: ollama serve"
                fi
            else
                rm -f "$_ollama_install_script"
                error "Ollama installation failed"
                info "Install manually: curl -fsSL https://ollama.com/install.sh | sh"
            fi
        else
            info "Install later: curl -fsSL https://ollama.com/install.sh | sh"
        fi
    fi

    # Ollama server reachable?
    if curl -sf --max-time 3 "${OLLAMA_URL}/api/version" &>/dev/null; then
        success "Ollama server reachable (${OLLAMA_URL})"
    else
        warn "Ollama server not reachable at ${OLLAMA_URL}"
        info "Start with: ollama serve"
    fi

    # Flutter SDK (optional, for Flutter UI)
    if check_command flutter; then
        local flutter_ver
        flutter_ver=$(flutter --version 2>/dev/null | head -1 | awk '{print $2}')
        success "Flutter $flutter_ver found"
    else
        warn "Flutter SDK not found (optional -- needed for Flutter UI)"
        info "Install: https://docs.flutter.dev/get-started/install"
        read -rp "  Install Flutter SDK now? [y/N] " _flutter_answer
        if [[ "$_flutter_answer" =~ ^[yY]$ ]]; then
            info "Installing Flutter SDK..."
            if check_command git; then
                local flutter_dir="$HOME/.flutter"
                if [[ -d "$flutter_dir" ]]; then
                    info "Existing Flutter dir found at $flutter_dir"
                else
                    git clone https://github.com/flutter/flutter.git -b stable --depth 1 "$flutter_dir"
                fi
                export PATH="$flutter_dir/bin:$PATH"
                if check_command flutter; then
                    flutter precache --web 2>/dev/null || true
                    success "Flutter installed at $flutter_dir"
                    info "Add to PATH permanently:"
                    info "  echo 'export PATH=\"\$HOME/.flutter/bin:\$PATH\"' >> ~/.bashrc"
                else
                    error "Flutter installation failed"
                fi
            else
                error "git is required to install Flutter"
                info "Install git first, then retry"
            fi
        else
            info "Install later: https://docs.flutter.dev/get-started/install"
        fi
    fi

    if [[ $errors -gt 0 ]]; then
        fatal "$errors critical prerequisite(s) missing"
    fi
}

# ============================================================================
# Step 2: Ollama models (optional, never blocking)
# ============================================================================

detect_hardware_tier() {
    # Detect hardware tier based on VRAM and RAM
    local vram_mb=0
    local ram_mb=0
    local gpu_count=0
    local vram_str="no GPU"

    # VRAM via nvidia-smi (supports multi-GPU: sums all GPUs)
    if check_command nvidia-smi; then
        local _nvsmi_output
        _nvsmi_output=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null) || true
        if [[ -n "$_nvsmi_output" ]]; then
            # Sum VRAM across all GPUs (one value per line)
            local _total_vram=0
            while IFS= read -r _line; do
                _line=$(echo "$_line" | tr -d ' \r')
                if [[ "$_line" =~ ^[0-9]+$ ]]; then
                    _total_vram=$(( _total_vram + _line ))
                    gpu_count=$(( gpu_count + 1 ))
                fi
            done <<< "$_nvsmi_output"
            vram_mb=$_total_vram
        fi
        if [[ "$vram_mb" -gt 0 ]]; then
            local vram_gb=$(( vram_mb / 1024 ))
            if [[ "$gpu_count" -gt 1 ]]; then
                vram_str="${vram_gb} GB VRAM (${gpu_count} GPUs)"
            else
                vram_str="${vram_gb} GB VRAM"
            fi
        fi
    # AMD GPU via rocm-smi (Radeon)
    elif check_command rocm-smi; then
        local _rocm_output
        _rocm_output=$(rocm-smi --showmeminfo vram --json 2>/dev/null) || true
        if [[ -n "$_rocm_output" ]]; then
            local _total_vram=0
            # Parse JSON output: extract "Total Memory (B)" values
            while IFS= read -r _vram_bytes; do
                _vram_bytes=$(echo "$_vram_bytes" | tr -d ' ",' | grep -oP '[0-9]+')
                if [[ -n "$_vram_bytes" && "$_vram_bytes" =~ ^[0-9]+$ ]]; then
                    _total_vram=$(( _total_vram + _vram_bytes / 1048576 ))
                    gpu_count=$(( gpu_count + 1 ))
                fi
            done < <(echo "$_rocm_output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for card in data.values():
        if isinstance(card, dict):
            total = card.get('Total Memory (B)', card.get('VRAM Total Memory (B)', 0))
            if total: print(total)
except: pass
" 2>/dev/null)
            vram_mb=$_total_vram
        fi
        if [[ "$vram_mb" -gt 0 ]]; then
            local vram_gb=$(( vram_mb / 1024 ))
            if [[ "$gpu_count" -gt 1 ]]; then
                vram_str="${vram_gb} GB VRAM AMD (${gpu_count} GPUs)"
            else
                vram_str="${vram_gb} GB VRAM AMD"
            fi
        fi
    fi

    # RAM via /proc/meminfo
    if [[ -f /proc/meminfo ]]; then
        local ram_kb
        ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        ram_mb=$(( ram_kb / 1024 ))
    fi

    local ram_gb=$(( ram_mb / 1024 ))
    local cpu_cores
    cpu_cores=$(nproc 2>/dev/null || echo "4")

    # Determine tier
    local tier="minimal"
    if [[ $ram_gb -ge 64 && $cpu_cores -ge 16 && $vram_mb -ge 49152 ]]; then
        tier="enterprise"
    elif [[ $vram_mb -ge 16384 && $ram_gb -ge 32 ]]; then
        tier="power"
    elif [[ $vram_mb -ge 8192 && $ram_gb -ge 16 ]]; then
        tier="standard"
    fi

    # Display
    echo ""
    info "Your system: ${vram_str}, ${ram_gb} GB RAM, ${cpu_cores} cores"
    info "Hardware tier: ${BOLD}$(echo "$tier" | tr '[:lower:]' '[:upper:]')${NC}"

    case "$tier" in
        minimal)
            info "Models: qwen3:8b, nomic-embed-text"
            info "Tip: At least 8 GB VRAM recommended for better quality"
            ;;
        standard)
            info "Models: qwen3:8b, qwen3:32b, nomic-embed-text"
            info "Tip: 'cognithor --lite' for only 6 GB VRAM"
            ;;
        power|enterprise)
            info "Models: qwen3:8b, qwen3:32b, qwen3-coder:30b, nomic-embed-text"
            info "Tip: 'cognithor --lite' for only 6 GB VRAM"
            ;;
    esac
    echo ""
}

ensure_ollama_models() {
    header "Checking Ollama models"

    detect_hardware_tier

    if ! curl -sf "${OLLAMA_URL}/api/version" &>/dev/null; then
        warn "Ollama not reachable -- download models manually:"
        info "  ollama pull qwen3:8b"
        info "  ollama pull nomic-embed-text"
        info "  ollama pull qwen3:32b     (optional, if >=24GB VRAM)"
        return 0
    fi

    # Query installed models
    local installed
    installed=$(curl -sf "${OLLAMA_URL}/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(m['name'])
" 2>/dev/null || echo "")

    # Required models (check only, never auto-download)
    local required_models=("qwen3:8b" "nomic-embed-text")
    local optional_models=("qwen3:32b")
    local missing_required=()

    for model in "${required_models[@]}"; do
        local base_name="${model%%:*}"
        if echo "$installed" | grep -q "$base_name"; then
            success "$model already installed"
        else
            warn "$model MISSING (required model)"
            missing_required+=("$model")
        fi
    done

    for model in "${optional_models[@]}"; do
        local base_name="${model%%:*}"
        if echo "$installed" | grep -q "$base_name"; then
            success "$model already installed"
        else
            info "$model not installed (optional, for better quality)"
        fi
    done

    # Summary of missing models -- ask user
    if [[ ${#missing_required[@]} -gt 0 ]]; then
        echo ""
        warn "Missing ${#missing_required[@]} required model(s): ${missing_required[*]}"
        echo ""
        read -rp "  Download missing models now? [y/N] " _pull_answer
        if [[ "$_pull_answer" =~ ^[yY]$ ]]; then
            for model in "${missing_required[@]}"; do
                info "Downloading $model..."
                if ollama pull "$model"; then
                    success "$model installed"
                else
                    warn "Failed to download $model"
                    echo "    Manually: ollama pull $model"
                fi
            done
        else
            info "Download models later with:"
            echo ""
            for model in "${missing_required[@]}"; do
                echo "    ollama pull $model"
            done
            echo ""
            info "Installation will continue -- models can be downloaded later."
        fi
        echo ""
    fi
}

# ============================================================================
# Step 3: Virtual Environment + Installation
# ============================================================================

setup_venv() {
    header "Python Virtual Environment"

    # If venv dir exists but activate is missing, it's corrupted
    if [[ -d "$VENV_DIR" ]]; then
        if [[ -f "$VENV_DIR/bin/activate" ]]; then
            info "Existing venv found: $VENV_DIR"
            # shellcheck disable=SC1091
            source "$VENV_DIR/bin/activate"
            success "venv activated"
            return 0
        else
            warn "Corrupted venv detected (bin/activate missing) -- recreating"
            rm -rf "$VENV_DIR"
        fi
    fi

    # Create fresh venv
    if [[ "$PKG_INSTALLER" == "uv" ]]; then
        info "Creating venv with uv in $VENV_DIR ..."
        uv venv "$VENV_DIR" --python python3
    else
        info "Creating venv in $VENV_DIR ..."
        python3 -m venv "$VENV_DIR"
    fi

    # Verify activate exists before sourcing
    if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
        fatal "venv creation failed: $VENV_DIR/bin/activate not found"
    fi

    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    if [[ "$PKG_INSTALLER" == "pip" ]]; then
        pip install --upgrade pip setuptools wheel --quiet
    fi
    success "venv created and activated"
}

install_jarvis() {
    header "Installing Cognithor"

    local install_extras="$1"
    local spec="${REPO_DIR}"
    if [[ -n "$install_extras" ]]; then
        spec="${REPO_DIR}[${install_extras}]"
    fi

    if [[ "$PKG_INSTALLER" == "uv" ]]; then
        info "Installing cognithor[$install_extras] with uv from $REPO_DIR ..."
        uv pip install -e "$spec" --quiet 2>&1 | tail -5
    else
        echo ""
        info "Installing cognithor[$install_extras] with pip from $REPO_DIR ..."
        info "Installing packages... (may take 2-5 minutes)"
        echo ""
        pip install -e "$spec" --progress-bar on 2>&1 | tail -20
    fi

    # Install identity extras if missing
    if ! python3 -c "import jarvis.identity" 2>/dev/null; then
        echo "  [INFO] Installing identity module..."
        pip install -e ".[identity]" --quiet 2>/dev/null || echo "  [WARNING] Identity install failed"
    fi

    # Install pysqlcipher3 for GDPR encryption at rest
    if python3 -c "import pysqlcipher3" 2>/dev/null; then
        success "pysqlcipher3 available (GDPR encryption)"
    else
        echo "  [INFO] Installing pysqlcipher3 for GDPR encryption at rest..."
        # System library required first
        if command -v apt-get &>/dev/null; then
            sudo apt-get install -y libsqlcipher-dev 2>/dev/null || true
        elif command -v brew &>/dev/null; then
            brew install sqlcipher 2>/dev/null || true
        fi
        pip install pysqlcipher3 --quiet 2>/dev/null && \
            success "pysqlcipher3 installed" || \
            warn "pysqlcipher3 install failed -- database encryption unavailable. Install libsqlcipher-dev (Ubuntu) or sqlcipher (macOS) and retry."
    fi

    # Verify installation
    if python3 -c "import jarvis; print(f'Cognithor v{jarvis.__version__}')" 2>/dev/null; then
        success "Cognithor installed successfully"
    else
        fatal "Installation failed -- pip install encountered errors"
    fi

    # Check CLI
    if "$VENV_DIR/bin/jarvis" --version &>/dev/null; then
        local ver
        ver=$("$VENV_DIR/bin/jarvis" --version 2>&1)
        success "CLI available: $ver"
    else
        warn "CLI 'jarvis' not in PATH -- use: $VENV_DIR/bin/jarvis"
    fi

    # Flutter UI Build (preferred)
    local flutter_app_dir="$REPO_DIR/flutter_app"
    local flutter_web_dist="$flutter_app_dir/build/web/index.html"
    if check_command flutter && [[ -f "$flutter_app_dir/pubspec.yaml" ]]; then
        info "Building Flutter Web UI..."
        if (cd "$flutter_app_dir" && flutter pub get --no-example 2>&1 | tail -3 && flutter build web --release 2>&1 | tail -5); then
            success "Flutter Web UI built (flutter_app/build/web/)"
        else
            warn "Flutter build failed -- falling back to legacy UI"
        fi
    elif [[ -f "$flutter_web_dist" ]]; then
        success "Pre-built Flutter UI available"
    fi

    # Legacy Web-UI Build (Node.js fallback)
    local ui_dir="$REPO_DIR/ui"
    local ui_dist="$ui_dir/dist/index.html"
    if [[ ! -f "$flutter_web_dist" ]]; then
        if check_command node && check_command npm; then
            if [[ ! -d "$ui_dir/node_modules" ]]; then
                info "Installing legacy UI dependencies (npm install)..."
                (cd "$ui_dir" && npm install --silent 2>&1 | tail -5) || true
            fi
            if [[ ! -f "$ui_dist" ]]; then
                info "Building legacy UI (npm run build)..."
                if (cd "$ui_dir" && npm run build --silent 2>&1 | tail -5); then
                    success "Legacy UI build created (ui/dist/)"
                else
                    warn "npm run build failed -- CLI mode available"
                fi
            else
                success "Legacy UI build exists (ui/dist/)"
            fi
        elif [[ -f "$ui_dist" ]]; then
            success "Pre-built legacy UI available (Node.js not needed)"
        else
            echo ""
            warn "No UI toolkit found"
            info "CLI mode is fully available"
            echo ""
            info "For the Flutter UI (recommended):"
            echo "    https://docs.flutter.dev/get-started/install"
            echo "    cd $flutter_app_dir && flutter pub get && flutter build web"
            echo ""
            info "Or install Node.js for the legacy React UI:"
            echo "    https://nodejs.org/en/download/"
            echo "    cd $ui_dir && npm install && npm run build"
            echo ""
        fi
    fi
}

# ============================================================================
# Step 4: Directory structure + Config
# ============================================================================

create_directory_safe() {
    # Creates a single directory with error handling and verbose output
    local dir="$1"
    if [[ -d "$dir" ]]; then
        info "  [exists]  $dir"
        return 0
    fi
    local err_file
    err_file=$(mktemp "${TMPDIR:-/tmp}/jarvis_mkdir_XXXXXX" 2>/dev/null || echo "/tmp/jarvis_mkdir_err")
    if mkdir -p "$dir" 2>"$err_file"; then
        success "  [created] $dir"
        rm -f "$err_file" 2>/dev/null
    else
        local err
        err=$(cat "$err_file" 2>/dev/null || echo "unknown error")
        rm -f "$err_file" 2>/dev/null
        error "Could not create directory: $dir"
        error "Error: $err"
        echo ""
        echo "  Fix with:"
        echo "    sudo mkdir -p $dir"
        echo "    sudo chown \$(whoami) $dir"
        echo ""
        fatal "Directory creation failed. Check permissions."
    fi
}

setup_directories() {
    header "Creating directory structure"

    # Core directories that Cognithor needs
    local dirs=(
        "$JARVIS_HOME"
        "$JARVIS_HOME/memory"
        "$JARVIS_HOME/memory/episodes"
        "$JARVIS_HOME/memory/procedures"
        "$JARVIS_HOME/memory/knowledge"
        "$JARVIS_HOME/memory/sessions"
        "$JARVIS_HOME/index"
        "$JARVIS_HOME/logs"
        "$JARVIS_HOME/cache"
        "$JARVIS_HOME/workspace"
        "$JARVIS_HOME/workspace/tmp"
    )

    for dir in "${dirs[@]}"; do
        create_directory_safe "$dir"
    done

    # Run jarvis --init-only for any extra setup (with timeout)
    info "Running jarvis --init-only..."
    if timeout 30 "$VENV_DIR/bin/jarvis" --init-only 2>/dev/null; then
        success "jarvis --init-only completed"
    else
        local _exit_code=$?
        if [[ $_exit_code -eq 124 ]]; then
            warn "jarvis --init-only timed out after 30s -- skipped"
        else
            warn "jarvis --init-only failed (exit code: $_exit_code) -- skipped"
        fi
    fi
    success "Directory structure in $JARVIS_HOME complete"

    # Config file
    local config_file="$JARVIS_HOME/config.yaml"
    if [[ -f "$config_file" ]]; then
        info "config.yaml already exists -- not overwriting"
    else
        if [[ -f "$REPO_DIR/config.yaml.example" ]]; then
            cp "$REPO_DIR/config.yaml.example" "$config_file"
            success "config.yaml created from template"
        else
            warn "config.yaml.example not found -- skipped"
        fi
    fi

    # Locale-based language detection
    if [[ -f "$config_file" ]] && ! grep -q "^language:" "$config_file" 2>/dev/null; then
        local _lang_code="${LANG%%_*}"
        _lang_code="${_lang_code:-en}"
        local _detected_lang="en"
        if [[ "$_lang_code" == "de" ]]; then
            _detected_lang="de"
        fi
        # Write language to the top of config.yaml
        local _tmp_cfg
        _tmp_cfg=$(mktemp "${TMPDIR:-/tmp}/jarvis_cfg_XXXXXX")
        echo "language: \"${_detected_lang}\"" > "$_tmp_cfg"
        cat "$config_file" >> "$_tmp_cfg"
        mv "$_tmp_cfg" "$config_file"
        success "Language detected: ${_detected_lang} (locale: ${_lang_code})"
    fi

    # .env (optional)
    local env_file="$JARVIS_HOME/.env"
    if [[ ! -f "$env_file" ]]; then
        if [[ -f "$REPO_DIR/.env.example" ]]; then
            cp "$REPO_DIR/.env.example" "$env_file"
            chmod 600 "$env_file"
            success ".env created (permissions: 600)"
        fi
    fi
}

# ============================================================================
# Step 5: Systemd services
# ============================================================================

install_systemd() {
    header "Systemd Services"

    local service_dir="$HOME/.config/systemd/user"
    mkdir -p "$service_dir"

    # Cognithor Core Service
    local service_file="$service_dir/jarvis.service"
    cat > "$service_file" << UNIT
[Unit]
Description=Cognithor Agent OS
Documentation=https://github.com/Alex8791-cyber/cognithor
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=${VENV_DIR}/bin/jarvis
WorkingDirectory=${JARVIS_HOME}
EnvironmentFile=-${JARVIS_HOME}/.env
Restart=on-failure
RestartSec=10
WatchdogSec=300

# Security
NoNewPrivileges=true
ProtectHome=read-only
ReadWritePaths=${JARVIS_HOME} /tmp/jarvis

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jarvis

[Install]
WantedBy=default.target
UNIT
    success "jarvis.service created"

    # WebUI Service (optional)
    local webui_file="$service_dir/jarvis-webui.service"
    cat > "$webui_file" << UNIT
[Unit]
Description=Cognithor Web-UI (FastAPI)
Documentation=https://github.com/Alex8791-cyber/cognithor
After=jarvis.service
BindsTo=jarvis.service

[Service]
Type=simple
ExecStart=${VENV_DIR}/bin/python -m uvicorn jarvis.channels.webui:create_app --host 127.0.0.1 --port 8080 --factory
WorkingDirectory=${JARVIS_HOME}
EnvironmentFile=-${JARVIS_HOME}/.env
Restart=on-failure
RestartSec=5

# Security
NoNewPrivileges=true
ProtectHome=read-only
ReadWritePaths=${JARVIS_HOME} /tmp/jarvis

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jarvis-webui

[Install]
WantedBy=default.target
UNIT
    success "jarvis-webui.service created"

    # Daemon Reload
    systemctl --user daemon-reload 2>/dev/null || true
    success "systemd daemon-reload"

    info "Manage services:"
    info "  systemctl --user start jarvis        # Start"
    info "  systemctl --user stop jarvis         # Stop"
    info "  systemctl --user enable jarvis       # Autostart"
    info "  journalctl --user -u jarvis -f       # Logs"
    info "  systemctl --user start jarvis-webui  # Start Web-UI"
}

# ============================================================================
# Step 6: Logrotate
# ============================================================================

setup_logrotate() {
    header "Log Rotation"

    local logrotate_dir="$JARVIS_HOME/logrotate.d"
    mkdir -p "$logrotate_dir"

    cat > "$logrotate_dir/jarvis" << CONF
${JARVIS_HOME}/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    dateext
    dateformat -%Y-%m-%d
    create 0640
}

${JARVIS_HOME}/logs/*.jsonl {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    dateext
    dateformat -%Y-%m-%d
    create 0640
}
CONF
    success "logrotate configuration created"
    info "For system logrotate: sudo ln -s $logrotate_dir/jarvis /etc/logrotate.d/jarvis"
}

# ============================================================================
# Step 7: Smoke test
# ============================================================================

run_smoke_test() {
    header "Smoke Test"

    if [[ -f "$REPO_DIR/scripts/smoke_test.py" ]]; then
        "$VENV_DIR/bin/python" "$REPO_DIR/scripts/smoke_test.py" \
            --jarvis-home "$JARVIS_HOME" \
            --ollama-url "$OLLAMA_URL" \
            --venv "$VENV_DIR"
    else
        warn "smoke_test.py not found -- skipped"
    fi

    # LLM smoke test: short request to Ollama
    if curl -sf --max-time 3 "${OLLAMA_URL}/api/version" &>/dev/null; then
        info "LLM smoke test..."
        local _llm_response
        _llm_response=$(curl -sf --max-time 30 "${OLLAMA_URL}/api/chat" \
            -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Say hello briefly."}],"stream":false}' \
            2>/dev/null)
        if [[ -n "$_llm_response" ]]; then
            local _llm_answer
            _llm_answer=$(echo "$_llm_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('message', {}).get('content', '').strip()[:80])
except: pass
" 2>/dev/null)
            if [[ -n "$_llm_answer" ]]; then
                success "LLM responds: $_llm_answer"
            else
                warn "LLM responded empty -- model may not be ready yet"
            fi
        else
            warn "LLM smoke test: No response (timeout or model not loaded)"
        fi
    else
        info "LLM smoke test skipped (Ollama not reachable)"
    fi
}

# ============================================================================
# Step 8: Shell integration
# ============================================================================

setup_shell_integration() {
    header "Shell Integration"

    local shell_rc=""
    if [[ -f "$HOME/.bashrc" ]]; then
        shell_rc="$HOME/.bashrc"
    elif [[ -f "$HOME/.zshrc" ]]; then
        shell_rc="$HOME/.zshrc"
    fi

    local alias_line="alias jarvis='${VENV_DIR}/bin/jarvis'"
    local activate_line="# Cognithor Agent OS"

    if [[ -n "$shell_rc" ]]; then
        if grep -qF "Cognithor Agent OS" "$shell_rc" 2>/dev/null || grep -qF "Jarvis Agent OS" "$shell_rc" 2>/dev/null; then
            info "Shell integration already present in $shell_rc"
        else
            {
                echo ""
                echo "$activate_line"
                echo "$alias_line"
            } >> "$shell_rc"
            success "Alias 'jarvis' added to $shell_rc"
        fi
    else
        info "No .bashrc/.zshrc found -- add manually:"
        info "  $alias_line"
    fi
}

# ============================================================================
# Step 8b: .desktop files (Linux desktop integration)
# ============================================================================

create_desktop_entry() {
    header "Desktop Integration"

    local apps_dir="$HOME/.local/share/applications"
    mkdir -p "$apps_dir"

    # CLI Launcher
    cat > "$apps_dir/cognithor.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Cognithor (CLI)
Comment=Cognithor Agent OS - Terminal
Exec=${VENV_DIR}/bin/jarvis
Icon=utilities-terminal
Terminal=true
Categories=Utility;Development;
StartupNotify=false
DESKTOP
    success "cognithor.desktop created"

    # Web-UI Launcher
    cat > "$apps_dir/cognithor-webui.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Cognithor Web-UI
Comment=Cognithor Agent OS - Web Interface
Exec=bash -c '${VENV_DIR}/bin/python -m jarvis --no-cli & sleep 3 && xdg-open http://localhost:8741; wait'
Icon=applications-internet
Terminal=false
Categories=Utility;Development;
StartupNotify=true
DESKTOP
    success "cognithor-webui.desktop created"

    # Update desktop database
    if check_command update-desktop-database; then
        update-desktop-database "$apps_dir" 2>/dev/null || true
        success "Desktop database updated"
    fi
}

# ============================================================================
# Uninstall
# ============================================================================

uninstall() {
    header "Uninstall Cognithor"

    warn "This removes the Cognithor installation (NOT your data in ~/.jarvis)"

    read -rp "Continue? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        info "Cancelled."
        exit 0
    fi

    # Stop services
    systemctl --user stop jarvis jarvis-webui 2>/dev/null || true
    systemctl --user disable jarvis jarvis-webui 2>/dev/null || true

    # Remove service files
    rm -f "$HOME/.config/systemd/user/jarvis.service"
    rm -f "$HOME/.config/systemd/user/jarvis-webui.service"
    systemctl --user daemon-reload 2>/dev/null || true

    # Remove venv
    if [[ -d "$VENV_DIR" ]]; then
        rm -rf "$VENV_DIR"
        success "Virtual environment removed"
    fi

    # Remove shell alias (portable: works on GNU sed and BSD/macOS sed)
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [[ -f "$rc" ]] && grep -q "Cognithor Agent OS\|Jarvis Agent OS\|jarvis.*venv.*bin.*jarvis" "$rc" 2>/dev/null; then
            grep -v "Cognithor Agent OS" "$rc" | grep -v "Jarvis Agent OS" | grep -v "jarvis.*venv.*bin.*jarvis" > "${rc}.jarvis_tmp" \
                && mv "${rc}.jarvis_tmp" "$rc" \
                || rm -f "${rc}.jarvis_tmp"
        fi
    done

    success "Cognithor uninstalled"
    info "Your data in $JARVIS_HOME was NOT deleted"
    info "To fully remove: rm -rf $JARVIS_HOME"
}

# ============================================================================
# Summary
# ============================================================================

show_summary() {
    header "Installation complete"

    echo -e "${GREEN}${BOLD}"
    cat << 'DONE'
  [OK] Cognithor Agent OS successfully installed!
DONE
    echo -e "${NC}"

    echo "  Getting started:"
    echo "    jarvis                              # CLI chat"
    echo "    jarvis --config ~/my-config.yaml    # Custom config"
    echo ""
    echo "  Systemd:"
    echo "    systemctl --user start jarvis       # Run as service"
    echo "    systemctl --user enable jarvis      # Autostart"
    echo ""
    echo "  Directories:"
    echo "    $JARVIS_HOME/                       # Home"
    echo "    $JARVIS_HOME/config.yaml            # Configuration"
    echo "    $JARVIS_HOME/memory/                # All memories"
    echo "    $JARVIS_HOME/logs/                  # Logs + Audit"
    echo ""
    echo "  Next steps:"
    echo "    1. Review and customize config.yaml"
    echo "    2. Start jarvis and test"
    echo "    3. Optional: Enable Telegram/WebUI/Flutter"
    echo ""
    if check_command flutter && [[ -f "$REPO_DIR/flutter_app/pubspec.yaml" ]]; then
        echo "  Flutter UI:"
        echo "    cd flutter_app && flutter run -d chrome    # Dev mode"
        echo "    cd flutter_app && flutter build web        # Production build"
        echo ""
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    show_banner

    # Parse arguments
    local mode="interactive"
    for arg in "$@"; do
        case "$arg" in
            --use-uv) USE_UV=true ;;
            --minimal|--full|--systemd|--uninstall|--help|-h) mode="$arg" ;;
        esac
    done

    case "$mode" in
        --uninstall)
            uninstall
            exit 0
            ;;
        --systemd)
            install_systemd
            exit 0
            ;;
        --minimal)
            check_prerequisites
            detect_installer
            setup_venv
            install_jarvis ""
            setup_directories
            run_smoke_test
            show_summary
            ;;
        --full)
            check_prerequisites
            detect_installer
            ensure_ollama_models
            setup_venv
            install_jarvis "full"
            setup_directories
            install_systemd
            setup_logrotate
            setup_shell_integration
            create_desktop_entry
            run_smoke_test
            show_summary
            ;;
        --help|-h)
            echo "Usage: $0 [--minimal|--full|--use-uv|--systemd|--uninstall|--help]"
            echo ""
            echo "  (no arguments)    Interactive installation"
            echo "  --minimal         Core packages only"
            echo "  --full            Everything including Voice + Systemd"
            echo "  --use-uv          Use uv instead of pip (10x faster)"
            echo "  --systemd         Install systemd services only"
            echo "  --uninstall       Uninstall"
            exit 0
            ;;
        *)
            # Interactive installation (default)
            check_prerequisites
            detect_installer
            ensure_ollama_models
            setup_venv
            install_jarvis "all,dev"
            setup_directories
            install_systemd
            setup_logrotate
            setup_shell_integration
            create_desktop_entry
            run_smoke_test
            show_summary
            ;;
    esac
}

main "$@"
