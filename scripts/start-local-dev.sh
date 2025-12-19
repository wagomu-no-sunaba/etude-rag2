#!/bin/bash
# start-local-dev.sh
#
# Starts the local development environment with Cloud SQL connection.
# Temporarily enables public IP on Cloud SQL, then runs the API server.
# On exit (Ctrl+C), automatically disables public IP for security.
#
# Usage:
#   ./scripts/start-local-dev.sh [environment] [options]
#
# Examples:
#   ./scripts/start-local-dev.sh              # dev environment, start API server
#   ./scripts/start-local-dev.sh dev          # explicit dev environment
#   ./scripts/start-local-dev.sh dev --shell  # open psql shell instead of API server
#   ./scripts/start-local-dev.sh dev --proxy  # use Cloud SQL Auth Proxy instead
#
# Requirements:
#   - gcloud CLI authenticated
#   - uv installed (for API server)
#   - psql installed (for --shell option)
#   - cloud-sql-proxy installed (for --proxy option)
#
# Security:
#   - Public IP is automatically disabled when the script exits
#   - Your current IP is whitelisted temporarily
#   - Use Ctrl+C to stop and cleanup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-dev}"
MODE="api"  # api, shell, or proxy

# Parse options
shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --shell)
            MODE="shell"
            shift
            ;;
        --proxy)
            MODE="proxy"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Configuration
PROJECT_ID="${GOOGLE_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
INSTANCE_NAME="etude-rag2-db-${ENVIRONMENT}"
INSTANCE_CONNECTION_NAME="${PROJECT_ID}:us-central1:${INSTANCE_NAME}"
DB_NAME="rag_db"
DB_USER="raguser"
SECRET_NAME="etude-rag2-db-password-${ENVIRONMENT}"
LOCAL_PORT=5432
API_PORT=8000

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Validate project ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GOOGLE_PROJECT_ID not set and no default gcloud project configured${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       Local Development Environment - Cloud SQL           ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Project:${NC}     ${PROJECT_ID}"
echo -e "  ${BLUE}Environment:${NC} ${ENVIRONMENT}"
echo -e "  ${BLUE}Instance:${NC}    ${INSTANCE_NAME}"
echo -e "  ${BLUE}Mode:${NC}        ${MODE}"
echo ""

# Track state for cleanup
PUBLIC_IP_WAS_ENABLED=false
PROXY_PID=""

# ============================================================================
# Helper Functions
# ============================================================================

has_public_ip() {
    gcloud sql instances describe "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --format="value(ipAddresses[].type)" 2>/dev/null | grep -q "PRIMARY"
}

enable_public_ip() {
    echo -e "${YELLOW}[1/5] Enabling public IP for Cloud SQL instance...${NC}"
    gcloud sql instances patch "$INSTANCE_NAME" \
        --assign-ip \
        --project="$PROJECT_ID" \
        --quiet

    # Wait for instance to be ready
    echo "      Waiting for instance to be ready..."
    sleep 10

    while true; do
        STATUS=$(gcloud sql instances describe "$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --format="value(state)" 2>/dev/null)
        if [ "$STATUS" = "RUNNABLE" ]; then
            break
        fi
        echo "      Instance state: $STATUS, waiting..."
        sleep 5
    done

    echo -e "      ${GREEN}✓ Public IP enabled${NC}"
}

disable_public_ip() {
    echo ""
    echo -e "${YELLOW}Disabling public IP for Cloud SQL instance...${NC}"
    gcloud sql instances patch "$INSTANCE_NAME" \
        --no-assign-ip \
        --project="$PROJECT_ID" \
        --quiet 2>/dev/null || true
    echo -e "${GREEN}✓ Public IP disabled (security restored)${NC}"
}

get_db_password() {
    gcloud secrets versions access latest \
        --secret="$SECRET_NAME" \
        --project="$PROJECT_ID" 2>/dev/null
}

get_public_ip() {
    gcloud sql instances describe "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --format="value(ipAddresses[0].ipAddress)" 2>/dev/null
}

authorize_current_ip() {
    echo -e "${YELLOW}[3/5] Authorizing your IP address...${NC}"

    # Get current IPv4 address
    MY_IP=$(curl -4 -s --max-time 10 ifconfig.me 2>/dev/null)
    if [ -z "$MY_IP" ]; then
        MY_IP=$(curl -4 -s --max-time 10 api.ipify.org 2>/dev/null)
    fi
    if [ -z "$MY_IP" ]; then
        MY_IP=$(curl -4 -s --max-time 10 ipv4.icanhazip.com 2>/dev/null)
    fi

    if [ -z "$MY_IP" ] || [[ ! "$MY_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${RED}Error: Failed to get valid IPv4 address${NC}"
        exit 1
    fi

    echo "      Your IP: $MY_IP"

    gcloud sql instances patch "$INSTANCE_NAME" \
        --authorized-networks="${MY_IP}/32" \
        --project="$PROJECT_ID" \
        --quiet

    echo -e "      ${GREEN}✓ IP authorized${NC}"
    sleep 3  # Wait for authorization to propagate
}

update_env_file() {
    local public_ip="$1"
    local password="$2"

    echo -e "${YELLOW}[4/5] Updating .env file for Cloud SQL...${NC}"

    # Backup current .env
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        cp "${PROJECT_ROOT}/.env" "${PROJECT_ROOT}/.env.backup"
    fi

    # Create .env with Cloud SQL connection
    cat > "${PROJECT_ROOT}/.env" <<EOF
# Generated by start-local-dev.sh - DO NOT COMMIT
# Temporary Cloud SQL connection for local development
# Original backup: .env.backup

# Google Cloud
GOOGLE_PROJECT_ID=${PROJECT_ID}
GOOGLE_LOCATION=us-central1
ENVIRONMENT=${ENVIRONMENT}

# Database (Cloud SQL via public IP)
DB_HOST=${public_ip}
DB_PORT=5432
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${password}

# Google Drive (from Secret Manager)
TARGET_FOLDER_ID=$(gcloud secrets versions access latest --secret="etude-rag2-drive-folder-id-${ENVIRONMENT}" --project="$PROJECT_ID" 2>/dev/null || echo "")

# Email (from Secret Manager)
MY_EMAIL=$(gcloud secrets versions access latest --secret="etude-rag2-my-email-${ENVIRONMENT}" --project="$PROJECT_ID" 2>/dev/null || echo "")

# Vertex AI
EMBEDDING_MODEL=text-embedding-004
LLM_MODEL=gemini-2.0-flash
LLM_TEMPERATURE=0.3

# Hybrid Search Parameters
HYBRID_SEARCH_K=20
RRF_K=60
FINAL_K=10

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=5
USE_FP16=true

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EOF

    echo -e "      ${GREEN}✓ .env updated with Cloud SQL config${NC}"
}

update_env_for_proxy() {
    local password="$1"

    echo -e "${YELLOW}[2/3] Updating .env file for Cloud SQL Proxy...${NC}"

    # Backup current .env
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        cp "${PROJECT_ROOT}/.env" "${PROJECT_ROOT}/.env.backup"
    fi

    # Create .env with localhost connection (proxy)
    cat > "${PROJECT_ROOT}/.env" <<EOF
# Generated by start-local-dev.sh --proxy - DO NOT COMMIT
# Cloud SQL Proxy connection for local development
# Original backup: .env.backup

# Google Cloud
GOOGLE_PROJECT_ID=${PROJECT_ID}
GOOGLE_LOCATION=us-central1
ENVIRONMENT=${ENVIRONMENT}

# Database (Cloud SQL via Auth Proxy)
DB_HOST=localhost
DB_PORT=${LOCAL_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${password}

# Google Drive (from Secret Manager)
TARGET_FOLDER_ID=$(gcloud secrets versions access latest --secret="etude-rag2-drive-folder-id-${ENVIRONMENT}" --project="$PROJECT_ID" 2>/dev/null || echo "")

# Email (from Secret Manager)
MY_EMAIL=$(gcloud secrets versions access latest --secret="etude-rag2-my-email-${ENVIRONMENT}" --project="$PROJECT_ID" 2>/dev/null || echo "")

# Vertex AI
EMBEDDING_MODEL=text-embedding-004
LLM_MODEL=gemini-2.0-flash
LLM_TEMPERATURE=0.3

# Hybrid Search Parameters
HYBRID_SEARCH_K=20
RRF_K=60
FINAL_K=10

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=5
USE_FP16=true

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EOF

    echo -e "      ${GREEN}✓ .env updated for proxy mode${NC}"
}

restore_env_file() {
    if [ -f "${PROJECT_ROOT}/.env.backup" ]; then
        mv "${PROJECT_ROOT}/.env.backup" "${PROJECT_ROOT}/.env"
        echo -e "${GREEN}✓ .env restored from backup${NC}"
    fi
}

# ============================================================================
# Cleanup (runs on exit)
# ============================================================================

cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"

    # Kill proxy if running
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        echo "Stopping Cloud SQL Auth Proxy..."
        kill "$PROXY_PID" 2>/dev/null || true
    fi

    # Disable public IP if we enabled it
    if [ "$PUBLIC_IP_WAS_ENABLED" = true ]; then
        disable_public_ip
    fi

    # Restore .env
    restore_env_file

    echo ""
    echo -e "${GREEN}✓ Cleanup complete. Goodbye!${NC}"
}

trap cleanup EXIT INT TERM

# ============================================================================
# Mode: Cloud SQL Auth Proxy
# ============================================================================

run_proxy_mode() {
    # Check if cloud-sql-proxy is installed
    if ! command -v cloud-sql-proxy &> /dev/null; then
        echo -e "${RED}Error: cloud-sql-proxy is not installed${NC}"
        echo ""
        echo "Install with: brew install cloud-sql-proxy"
        echo "Or: curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.arm64"
        exit 1
    fi

    echo -e "${YELLOW}[1/3] Getting database credentials...${NC}"
    DB_PASSWORD=$(get_db_password)
    if [ -z "$DB_PASSWORD" ]; then
        echo -e "${RED}Error: Failed to get database password${NC}"
        exit 1
    fi
    echo -e "      ${GREEN}✓ Password retrieved${NC}"

    update_env_for_proxy "$DB_PASSWORD"

    echo -e "${YELLOW}[3/3] Starting Cloud SQL Auth Proxy...${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}Cloud SQL Auth Proxy running on localhost:${LOCAL_PORT}${NC}"
    echo ""
    echo "  Connect with psql:"
    echo -e "    ${BLUE}PGPASSWORD=\$DB_PASSWORD psql -h localhost -p ${LOCAL_PORT} -U ${DB_USER} -d ${DB_NAME}${NC}"
    echo ""
    echo "  Start API server in another terminal:"
    echo -e "    ${BLUE}uv run uvicorn src.api.main:app --reload --port ${API_PORT}${NC}"
    echo ""
    echo -e "  ${YELLOW}Press Ctrl+C to stop${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Run proxy in foreground
    cloud-sql-proxy "$INSTANCE_CONNECTION_NAME" --port "$LOCAL_PORT"
}

# ============================================================================
# Mode: Direct Public IP Connection
# ============================================================================

run_direct_mode() {
    # Step 1: Check/Enable public IP
    echo -e "${YELLOW}[1/5] Checking Cloud SQL public IP status...${NC}"
    if has_public_ip; then
        echo -e "      ${GREEN}✓ Public IP already enabled${NC}"
    else
        enable_public_ip
        PUBLIC_IP_WAS_ENABLED=true
    fi

    # Step 2: Get credentials
    echo -e "${YELLOW}[2/5] Getting database credentials...${NC}"
    DB_PASSWORD=$(get_db_password)
    if [ -z "$DB_PASSWORD" ]; then
        echo -e "${RED}Error: Failed to get database password${NC}"
        exit 1
    fi
    echo -e "      ${GREEN}✓ Password retrieved${NC}"

    # Step 3: Authorize IP
    authorize_current_ip

    # Step 4: Get public IP and update .env
    PUBLIC_IP=$(get_public_ip)
    if [ -z "$PUBLIC_IP" ]; then
        echo -e "${RED}Error: Failed to get public IP address${NC}"
        exit 1
    fi
    echo "      Cloud SQL IP: $PUBLIC_IP"

    update_env_file "$PUBLIC_IP" "$DB_PASSWORD"

    # Step 5: Run based on mode
    if [ "$MODE" = "shell" ]; then
        run_psql_shell "$PUBLIC_IP" "$DB_PASSWORD"
    else
        run_api_server "$PUBLIC_IP" "$DB_PASSWORD"
    fi
}

run_psql_shell() {
    local public_ip="$1"
    local password="$2"

    echo -e "${YELLOW}[5/5] Opening psql shell...${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}Connected to Cloud SQL: ${INSTANCE_NAME}${NC}"
    echo ""
    echo -e "  ${YELLOW}Type \\q to exit and cleanup${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""

    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME"
}

run_api_server() {
    local public_ip="$1"
    local password="$2"

    echo -e "${YELLOW}[5/5] Starting API server...${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}API Server starting on http://localhost:${API_PORT}${NC}"
    echo ""
    echo "  Endpoints:"
    echo -e "    ${BLUE}http://localhost:${API_PORT}/${NC}          - HTMX UI"
    echo -e "    ${BLUE}http://localhost:${API_PORT}/docs${NC}       - API Documentation"
    echo -e "    ${BLUE}http://localhost:${API_PORT}/health${NC}     - Health Check"
    echo ""
    echo "  Database:"
    echo -e "    ${BLUE}${INSTANCE_NAME}${NC} via ${public_ip}"
    echo ""
    echo -e "  ${YELLOW}Press Ctrl+C to stop and cleanup${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""

    cd "$PROJECT_ROOT"
    uv run uvicorn src.api.main:app --reload --port "$API_PORT"
}

# ============================================================================
# Main
# ============================================================================

if [ "$MODE" = "proxy" ]; then
    run_proxy_mode
else
    run_direct_mode
fi
