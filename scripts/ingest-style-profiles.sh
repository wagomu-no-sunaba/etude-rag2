#!/bin/bash
# ingest-style-profiles.sh
#
# Ingests style profiles and excerpts from Google Drive into Cloud SQL.
# Temporarily enables public IP for connection, then disables it after completion.
#
# Usage:
#   ./scripts/ingest-style-profiles.sh [options] [environment]
#
# Example:
#   ./scripts/ingest-style-profiles.sh dev
#   ./scripts/ingest-style-profiles.sh --content --style-profile dev
#   ./scripts/ingest-style-profiles.sh --all prod
#
# Options:
#   --content         Ingest content documents
#   --style-profile   Ingest style profiles
#   --style-excerpt   Ingest style excerpts
#   --all             Ingest all (content + style-profile + style-excerpt)
#   --skip-cleanup    Don't disable public IP after completion (for debugging)
#   --interactive     Prompt for selection interactively
#
# If no data type options are specified, --interactive mode is used.
#
# Requirements:
#   - gcloud CLI authenticated
#   - uv installed
#   - Access to Secret Manager and Google Drive

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
ENVIRONMENT="dev"
SKIP_CLEANUP=false
INGEST_CONTENT=false
INGEST_STYLE_PROFILE=false
INGEST_STYLE_EXCERPT=false
INTERACTIVE=false
OPTIONS_SPECIFIED=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --content)
            INGEST_CONTENT=true
            OPTIONS_SPECIFIED=true
            shift
            ;;
        --style-profile)
            INGEST_STYLE_PROFILE=true
            OPTIONS_SPECIFIED=true
            shift
            ;;
        --style-excerpt)
            INGEST_STYLE_EXCERPT=true
            OPTIONS_SPECIFIED=true
            shift
            ;;
        --all)
            INGEST_CONTENT=true
            INGEST_STYLE_PROFILE=true
            INGEST_STYLE_EXCERPT=true
            OPTIONS_SPECIFIED=true
            shift
            ;;
        --interactive|-i)
            INTERACTIVE=true
            shift
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
        *)
            ENVIRONMENT="$1"
            shift
            ;;
    esac
done

# If no options specified, use interactive mode
if [ "$OPTIONS_SPECIFIED" = false ]; then
    INTERACTIVE=true
fi

# Interactive selection
if [ "$INTERACTIVE" = true ]; then
    echo ""
    echo -e "${CYAN}=============================================="
    echo "Select data types to ingest"
    echo "==============================================${NC}"
    echo ""
    echo "Enter the numbers of data types to ingest (space-separated):"
    echo ""
    echo "  1) content        - Past articles for RAG retrieval"
    echo "  2) style_profile  - Writing style rules (1 per category)"
    echo "  3) style_excerpt  - Sample excerpts for style reference"
    echo "  4) all            - All of the above"
    echo ""
    read -p "Selection [e.g., 1 2 3 or 4]: " selections

    for sel in $selections; do
        case $sel in
            1) INGEST_CONTENT=true ;;
            2) INGEST_STYLE_PROFILE=true ;;
            3) INGEST_STYLE_EXCERPT=true ;;
            4)
                INGEST_CONTENT=true
                INGEST_STYLE_PROFILE=true
                INGEST_STYLE_EXCERPT=true
                ;;
            *)
                echo -e "${RED}Invalid selection: $sel${NC}"
                exit 1
                ;;
        esac
    done

    # Validate at least one selected
    if [ "$INGEST_CONTENT" = false ] && [ "$INGEST_STYLE_PROFILE" = false ] && [ "$INGEST_STYLE_EXCERPT" = false ]; then
        echo -e "${RED}No data types selected. Exiting.${NC}"
        exit 1
    fi

    echo ""
fi

# Configuration
PROJECT_ID="${GOOGLE_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
INSTANCE_NAME="etude-rag2-db-${ENVIRONMENT}"
DB_NAME="rag_db"
DB_USER="raguser"
SECRET_NAME="etude-rag2-db-password-${ENVIRONMENT}"
ENV_FILE="${PROJECT_ROOT}/.env"

# Validate project ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GOOGLE_PROJECT_ID not set and no default gcloud project configured${NC}"
    exit 1
fi

# Build mode string
MODE_STR=""
if [ "$INGEST_CONTENT" = true ]; then
    MODE_STR="${MODE_STR}content "
fi
if [ "$INGEST_STYLE_PROFILE" = true ]; then
    MODE_STR="${MODE_STR}style_profile "
fi
if [ "$INGEST_STYLE_EXCERPT" = true ]; then
    MODE_STR="${MODE_STR}style_excerpt "
fi

# Print banner
echo ""
echo -e "${BLUE}=============================================="
echo "Style Profile Ingestion Script"
echo "==============================================${NC}"
echo ""
echo "  Project:      ${PROJECT_ID}"
echo "  Environment:  ${ENVIRONMENT}"
echo "  Instance:     ${INSTANCE_NAME}"
echo "  Skip Cleanup: ${SKIP_CLEANUP}"
echo "  Data Types:   ${MODE_STR}"
echo ""

# Track state for cleanup
PUBLIC_IP_WAS_ENABLED=false
ORIGINAL_DB_HOST=""

# Cleanup function
cleanup() {
    local exit_code=$?

    echo ""
    echo -e "${YELLOW}>>> Cleanup${NC}"

    # Restore original DB_HOST in .env
    if [ -n "$ORIGINAL_DB_HOST" ] && [ -f "$ENV_FILE" ]; then
        echo "  Restoring DB_HOST to: $ORIGINAL_DB_HOST"
        # Use perl for cross-platform compatibility
        perl -pi -e "s/^DB_HOST=.*/DB_HOST=${ORIGINAL_DB_HOST}/" "$ENV_FILE"
        echo -e "  ${GREEN}[OK] .env restored${NC}"
    fi

    # Disable public IP if we enabled it
    if [ "$PUBLIC_IP_WAS_ENABLED" = true ] && [ "$SKIP_CLEANUP" = false ]; then
        echo "  Disabling public IP..."
        if gcloud sql instances patch "$INSTANCE_NAME" \
            --no-assign-ip \
            --project="$PROJECT_ID" \
            --quiet 2>/dev/null; then
            echo -e "  ${GREEN}[OK] Public IP disabled${NC}"
        else
            echo -e "  ${YELLOW}[WARN] Failed to disable public IP${NC}"
        fi
    elif [ "$SKIP_CLEANUP" = true ]; then
        echo -e "  ${YELLOW}[SKIP] Cleanup skipped (--skip-cleanup flag)${NC}"
    fi

    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}=============================================="
        echo "Ingestion completed successfully!"
        echo "==============================================${NC}"
    else
        echo -e "${RED}=============================================="
        echo "Ingestion failed with exit code: $exit_code"
        echo "==============================================${NC}"
    fi

    exit $exit_code
}

# Set trap to ensure cleanup runs
trap cleanup EXIT

# Function to check if instance has public IP
has_public_ip() {
    gcloud sql instances describe "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --format="value(ipAddresses[].type)" 2>/dev/null | grep -q "PRIMARY"
}

# Function to get public IP address
get_public_ip() {
    gcloud sql instances describe "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --format="value(ipAddresses[0].ipAddress)" 2>/dev/null
}

# Function to wait for instance to be ready
wait_for_instance() {
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        STATUS=$(gcloud sql instances describe "$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --format="value(state)" 2>/dev/null)

        if [ "$STATUS" = "RUNNABLE" ]; then
            return 0
        fi

        echo "    Instance state: $STATUS, waiting..."
        sleep 5
        attempt=$((attempt + 1))
    done

    echo -e "${RED}Error: Instance did not become ready in time${NC}"
    return 1
}

# ============================================
# Step 1: Check Google Drive authentication
# ============================================
echo -e "${YELLOW}>>> Step 1/8: Checking Google Drive authentication${NC}"

# Required scopes for this script
REQUIRED_SCOPES="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.readonly"

# Check if ADC credentials exist
ADC_FILE="${HOME}/.config/gcloud/application_default_credentials.json"
if [ ! -f "$ADC_FILE" ]; then
    echo "  Application Default Credentials not found."
    echo ""
    echo -e "${CYAN}Running: gcloud auth application-default login${NC}"
    echo "  This will open a browser for Google account authentication."
    echo "  Please grant access to Google Drive (read-only)."
    echo ""

    if gcloud auth application-default login --scopes="$REQUIRED_SCOPES"; then
        echo -e "  ${GREEN}[OK] Authentication successful${NC}"
    else
        echo -e "${RED}Error: Authentication failed${NC}"
        exit 1
    fi
else
    # Check if Drive scope is included
    if grep -q "drive" "$ADC_FILE" 2>/dev/null; then
        echo "  ADC credentials found with Drive scope"
        echo -e "  ${GREEN}[OK] Already authenticated${NC}"
    else
        echo "  ADC credentials found but missing Google Drive scope."
        echo ""
        echo -e "${YELLOW}Need to re-authenticate with Drive scope.${NC}"
        echo ""
        read -p "Re-authenticate now? [Y/n]: " answer
        answer=${answer:-Y}

        if [[ "$answer" =~ ^[Yy]$ ]]; then
            echo ""
            echo -e "${CYAN}Running: gcloud auth application-default login${NC}"
            echo "  This will open a browser for Google account authentication."
            echo ""

            if gcloud auth application-default login --scopes="$REQUIRED_SCOPES"; then
                echo -e "  ${GREEN}[OK] Authentication successful${NC}"
            else
                echo -e "${RED}Error: Authentication failed${NC}"
                exit 1
            fi
        else
            echo -e "${RED}Authentication required. Exiting.${NC}"
            exit 1
        fi
    fi
fi

# ============================================
# Step 2: Save original DB_HOST
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 2/8: Reading current configuration${NC}"

if [ -f "$ENV_FILE" ]; then
    ORIGINAL_DB_HOST=$(grep "^DB_HOST=" "$ENV_FILE" | cut -d'=' -f2)
    echo "  Current DB_HOST: $ORIGINAL_DB_HOST"
    echo -e "  ${GREEN}[OK] Configuration read${NC}"
else
    echo -e "${RED}Error: .env file not found at $ENV_FILE${NC}"
    echo "  Run: ./scripts/sync-env-from-secrets.sh $ENVIRONMENT"
    exit 1
fi

# ============================================
# Step 2: Enable Public IP
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 3/8: Enabling Cloud SQL public IP${NC}"

if has_public_ip; then
    echo "  Public IP is already enabled"
    echo -e "  ${GREEN}[OK] Skipped${NC}"
else
    echo "  Enabling public IP (this may take 30-60 seconds)..."
    if gcloud sql instances patch "$INSTANCE_NAME" \
        --assign-ip \
        --project="$PROJECT_ID" \
        --quiet; then
        PUBLIC_IP_WAS_ENABLED=true
        echo "  Waiting for instance to be ready..."
        wait_for_instance
        echo -e "  ${GREEN}[OK] Public IP enabled${NC}"
    else
        echo -e "${RED}Error: Failed to enable public IP${NC}"
        exit 1
    fi
fi

# ============================================
# Step 3: Get Public IP Address
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 4/8: Getting public IP address${NC}"

PUBLIC_IP=$(get_public_ip)
if [ -z "$PUBLIC_IP" ]; then
    echo -e "${RED}Error: Failed to get public IP address${NC}"
    exit 1
fi
echo "  Public IP: $PUBLIC_IP"
echo -e "  ${GREEN}[OK] Retrieved${NC}"

# ============================================
# Step 4: Authorize Current IP
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 5/8: Authorizing your IP address${NC}"

# Get current IPv4 address
MY_IP=$(curl -4 -s --max-time 10 ifconfig.me 2>/dev/null)
if [ -z "$MY_IP" ]; then
    MY_IP=$(curl -4 -s --max-time 10 api.ipify.org 2>/dev/null)
fi
if [ -z "$MY_IP" ]; then
    MY_IP=$(curl -4 -s --max-time 10 ipv4.icanhazip.com 2>/dev/null)
fi

if [ -z "$MY_IP" ]; then
    echo -e "${RED}Error: Failed to get your public IP address${NC}"
    exit 1
fi

# Validate IPv4 format
if [[ ! "$MY_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid IPv4 address: $MY_IP${NC}"
    exit 1
fi

echo "  Your IP: $MY_IP"

if gcloud sql instances patch "$INSTANCE_NAME" \
    --authorized-networks="${MY_IP}/32" \
    --project="$PROJECT_ID" \
    --quiet; then
    echo -e "  ${GREEN}[OK] IP authorized${NC}"
else
    echo -e "${RED}Error: Failed to authorize IP${NC}"
    exit 1
fi

# Wait for authorization to take effect
sleep 5

# ============================================
# Step 5: Update .env with Public IP
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 6/8: Updating .env file${NC}"

# Use perl for cross-platform compatibility (avoids macOS sed -i issues)
perl -pi -e "s/^DB_HOST=.*/DB_HOST=${PUBLIC_IP}/" "$ENV_FILE"

echo "  DB_HOST updated to: $PUBLIC_IP"
echo -e "  ${GREEN}[OK] .env updated${NC}"

# ============================================
# Step 6: Run Ingestion
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 7/8: Running ingestion${NC}"
echo ""

cd "$PROJECT_ROOT"

# Get folder ID from .env
FOLDER_ID=$(grep "^TARGET_FOLDER_ID=" "$ENV_FILE" | cut -d'=' -f2)
if [ -z "$FOLDER_ID" ]; then
    echo -e "${RED}Error: TARGET_FOLDER_ID not found in .env${NC}"
    exit 1
fi

INGESTION_FAILED=false

# Ingest content if selected
if [ "$INGEST_CONTENT" = true ]; then
    echo -e "${CYAN}--- Ingesting: content ---${NC}"
    if uv run python src/main.py --folder-id "$FOLDER_ID" --data-type content -v; then
        echo -e "${GREEN}[OK] content ingestion completed${NC}"
    else
        echo -e "${RED}[FAILED] content ingestion failed${NC}"
        INGESTION_FAILED=true
    fi
    echo ""
fi

# Ingest style_profile if selected
if [ "$INGEST_STYLE_PROFILE" = true ]; then
    echo -e "${CYAN}--- Ingesting: style_profile ---${NC}"
    if uv run python src/main.py --folder-id "$FOLDER_ID" --data-type style_profile -v; then
        echo -e "${GREEN}[OK] style_profile ingestion completed${NC}"
    else
        echo -e "${RED}[FAILED] style_profile ingestion failed${NC}"
        INGESTION_FAILED=true
    fi
    echo ""
fi

# Ingest style_excerpt if selected
if [ "$INGEST_STYLE_EXCERPT" = true ]; then
    echo -e "${CYAN}--- Ingesting: style_excerpt ---${NC}"
    if uv run python src/main.py --folder-id "$FOLDER_ID" --data-type style_excerpt -v; then
        echo -e "${GREEN}[OK] style_excerpt ingestion completed${NC}"
    else
        echo -e "${RED}[FAILED] style_excerpt ingestion failed${NC}"
        INGESTION_FAILED=true
    fi
    echo ""
fi

if [ "$INGESTION_FAILED" = true ]; then
    echo -e "${RED}Some ingestion tasks failed${NC}"
    # Continue to verification anyway
fi

# ============================================
# Step 7: Verify Results
# ============================================
echo ""
echo -e "${YELLOW}>>> Step 8/8: Verifying results${NC}"

# Get database password
DB_PASSWORD=$(gcloud secrets versions access latest \
    --secret="$SECRET_NAME" \
    --project="$PROJECT_ID" 2>/dev/null)

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${YELLOW}[WARN] Could not retrieve DB password for verification${NC}"
else
    echo ""
    echo -e "${BLUE}=== style_profiles table ===${NC}"
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$PUBLIC_IP" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "SELECT article_type, profile_type, LENGTH(content) as content_chars,
            embedding IS NOT NULL as has_embedding,
            created_at::date as created
            FROM style_profiles
            ORDER BY article_type, profile_type;" 2>/dev/null || echo "  (Could not query table)"

    echo ""
    echo -e "${BLUE}=== Summary ===${NC}"
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$PUBLIC_IP" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t \
        -c "SELECT
            (SELECT COUNT(*) FROM style_profiles WHERE profile_type = 'profile') as profiles,
            (SELECT COUNT(*) FROM style_profiles WHERE profile_type = 'excerpt') as excerpts,
            (SELECT COUNT(*) FROM documents) as documents;" 2>/dev/null | \
        awk '{print "  Profiles: " $1 "\n  Excerpts: " $3 "\n  Documents: " $5}' || echo "  (Could not query summary)"

    echo ""
    echo -e "  ${GREEN}[OK] Verification completed${NC}"
fi

# Cleanup will be called by trap
exit 0
