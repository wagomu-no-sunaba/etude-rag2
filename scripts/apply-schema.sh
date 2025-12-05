#!/bin/bash
# apply-schema.sh
#
# Applies the database schema to Cloud SQL.
# Temporarily enables public IP for connection, then disables it after completion.
#
# Usage:
#   ./scripts/apply-schema.sh [environment]
#
# Example:
#   ./scripts/apply-schema.sh dev
#   ./scripts/apply-schema.sh prod
#
# Requirements:
#   - gcloud CLI authenticated
#   - psql installed
#   - Access to Secret Manager

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default environment
ENVIRONMENT="${1:-dev}"

# Configuration
PROJECT_ID="${GOOGLE_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
INSTANCE_NAME="etude-rag2-db-${ENVIRONMENT}"
DB_NAME="rag_db"
DB_USER="raguser"
SECRET_NAME="etude-rag2-db-password-${ENVIRONMENT}"
SCHEMA_FILE="schemas/schema.sql"
REGION="us-central1"

# Validate project ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GOOGLE_PROJECT_ID not set and no default gcloud project configured${NC}"
    exit 1
fi

# Check if schema file exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SCHEMA_PATH="${PROJECT_ROOT}/${SCHEMA_FILE}"

if [ ! -f "$SCHEMA_PATH" ]; then
    echo -e "${RED}Error: Schema file not found: ${SCHEMA_PATH}${NC}"
    exit 1
fi

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: psql is not installed. Please install PostgreSQL client.${NC}"
    exit 1
fi

echo "=============================================="
echo "Cloud SQL Schema Application Script"
echo "=============================================="
echo ""
echo "  Project:     ${PROJECT_ID}"
echo "  Environment: ${ENVIRONMENT}"
echo "  Instance:    ${INSTANCE_NAME}"
echo "  Database:    ${DB_NAME}"
echo "  Schema:      ${SCHEMA_FILE}"
echo ""

# Function to check if instance has public IP
has_public_ip() {
    gcloud sql instances describe "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --format="value(ipAddresses[].type)" 2>/dev/null | grep -q "PRIMARY"
}

# Function to enable public IP
enable_public_ip() {
    echo -e "${YELLOW}Enabling public IP for Cloud SQL instance...${NC}"
    gcloud sql instances patch "$INSTANCE_NAME" \
        --assign-ip \
        --project="$PROJECT_ID" \
        --quiet

    # Wait for operation to complete
    echo "Waiting for instance to be ready..."
    sleep 10

    # Wait until instance is RUNNABLE
    while true; do
        STATUS=$(gcloud sql instances describe "$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --format="value(state)" 2>/dev/null)
        if [ "$STATUS" = "RUNNABLE" ]; then
            break
        fi
        echo "  Instance state: $STATUS, waiting..."
        sleep 5
    done

    echo -e "${GREEN}Public IP enabled successfully${NC}"
}

# Function to disable public IP
disable_public_ip() {
    echo -e "${YELLOW}Disabling public IP for Cloud SQL instance...${NC}"
    gcloud sql instances patch "$INSTANCE_NAME" \
        --no-assign-ip \
        --project="$PROJECT_ID" \
        --quiet
    echo -e "${GREEN}Public IP disabled successfully${NC}"
}

# Function to get database password from Secret Manager
get_db_password() {
    gcloud secrets versions access latest \
        --secret="$SECRET_NAME" \
        --project="$PROJECT_ID" 2>/dev/null
}

# Function to apply schema
apply_schema() {
    local password="$1"
    local public_ip="$2"

    echo -e "${YELLOW}Applying schema...${NC}"

    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -f "$SCHEMA_PATH" \
        -v ON_ERROR_STOP=1

    echo -e "${GREEN}Schema applied successfully${NC}"
}

# Function to verify schema
verify_schema() {
    local password="$1"
    local public_ip="$2"

    echo ""
    echo -e "${YELLOW}Verifying schema...${NC}"
    echo ""

    # Show tables
    echo -e "${GREEN}=== Tables ===${NC}"
    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "\dt"

    # Show table structure for documents table
    echo ""
    echo -e "${GREEN}=== Documents Table Structure ===${NC}"
    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "\d documents"

    # Show indexes
    echo ""
    echo -e "${GREEN}=== Indexes ===${NC}"
    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'documents';"

    # Show extensions
    echo ""
    echo -e "${GREEN}=== Installed Extensions ===${NC}"
    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_trgm');"

    # Show row count
    echo ""
    echo -e "${GREEN}=== Row Count ===${NC}"
    PGPASSWORD="$password" psql \
        -h "$public_ip" \
        -p 5432 \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t \
        -c "SELECT COUNT(*) as total_documents FROM documents;"
    echo "  documents in table"
}

# Track if we enabled public IP (so we know to disable it)
PUBLIC_IP_WAS_ENABLED=false

# Cleanup function
cleanup() {
    if [ "$PUBLIC_IP_WAS_ENABLED" = true ]; then
        echo ""
        disable_public_ip
    fi
}

# Set trap to ensure cleanup runs
trap cleanup EXIT

# Main execution
echo "Step 1: Checking Cloud SQL instance configuration..."

if has_public_ip; then
    echo "  Public IP is already enabled"
else
    echo "  Public IP is not enabled"
    enable_public_ip
    PUBLIC_IP_WAS_ENABLED=true
fi

echo ""
echo "Step 2: Getting database credentials..."

DB_PASSWORD=$(get_db_password)
if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}Error: Failed to retrieve database password from Secret Manager${NC}"
    exit 1
fi
echo "  Password retrieved from Secret Manager"

echo ""
echo "Step 3: Getting public IP address..."

PUBLIC_IP=$(gcloud sql instances describe "$INSTANCE_NAME" \
    --project="$PROJECT_ID" \
    --format="value(ipAddresses[0].ipAddress)" 2>/dev/null)

if [ -z "$PUBLIC_IP" ]; then
    echo -e "${RED}Error: Failed to get public IP address${NC}"
    exit 1
fi
echo "  Public IP: $PUBLIC_IP"

echo ""
echo "Step 4: Authorizing current IP address..."

# Get current IPv4 address (Cloud SQL only supports IPv4)
# Use -4 flag to force IPv4, try multiple services for reliability
MY_IP=$(curl -4 -s --max-time 10 ifconfig.me 2>/dev/null)
if [ -z "$MY_IP" ]; then
    MY_IP=$(curl -4 -s --max-time 10 api.ipify.org 2>/dev/null)
fi
if [ -z "$MY_IP" ]; then
    MY_IP=$(curl -4 -s --max-time 10 ipv4.icanhazip.com 2>/dev/null)
fi
if [ -z "$MY_IP" ]; then
    echo -e "${RED}Error: Failed to get current IPv4 address${NC}"
    echo -e "${RED}Cloud SQL requires IPv4. Please check your network connection.${NC}"
    exit 1
fi

# Validate that it's an IPv4 address (simple check)
if [[ ! "$MY_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid IPv4 address received: $MY_IP${NC}"
    echo -e "${RED}Cloud SQL only supports IPv4 addresses.${NC}"
    exit 1
fi

echo "  Your IP: $MY_IP"

# Authorize IP
gcloud sql instances patch "$INSTANCE_NAME" \
    --authorized-networks="${MY_IP}/32" \
    --project="$PROJECT_ID" \
    --quiet

echo "  IP authorized for connection"

# Wait a moment for the authorization to take effect
sleep 5

echo ""
echo "Step 5: Applying database schema..."

apply_schema "$DB_PASSWORD" "$PUBLIC_IP"

echo ""
echo "Step 6: Verifying schema application..."

verify_schema "$DB_PASSWORD" "$PUBLIC_IP"

echo ""
echo "=============================================="
echo -e "${GREEN}Schema application completed successfully!${NC}"
echo "=============================================="
