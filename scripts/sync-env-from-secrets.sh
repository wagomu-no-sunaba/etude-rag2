#!/bin/bash
# sync-env-from-secrets.sh
#
# Generates a .env file from Google Cloud Secret Manager.
# This eliminates the need to maintain .env and terraform.tfvars separately.
#
# Usage:
#   ./scripts/sync-env-from-secrets.sh [environment]
#
# Example:
#   ./scripts/sync-env-from-secrets.sh dev
#   ./scripts/sync-env-from-secrets.sh prod

set -e

# Default environment
ENVIRONMENT="${1:-dev}"

# Get project ID from gcloud config or environment
PROJECT_ID="${GOOGLE_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: GOOGLE_PROJECT_ID not set and no default gcloud project configured"
    exit 1
fi

echo "Syncing secrets from Secret Manager..."
echo "  Project: $PROJECT_ID"
echo "  Environment: $ENVIRONMENT"
echo ""

# Function to get secret value (returns empty string if not found)
get_secret() {
    local secret_name="$1"
    gcloud secrets versions access latest \
        --secret="${secret_name}" \
        --project="${PROJECT_ID}" 2>/dev/null || echo ""
}

# Fetch secrets
echo "Fetching secrets..."
DB_PASSWORD=$(get_secret "etude-rag2-db-password-${ENVIRONMENT}")
TARGET_FOLDER_ID=$(get_secret "etude-rag2-drive-folder-id-${ENVIRONMENT}")
MY_EMAIL=$(get_secret "etude-rag2-my-email-${ENVIRONMENT}")

# Get Terraform outputs for non-secret values (if available)
TERRAFORM_DIR="terraform"
if [ -d "$TERRAFORM_DIR" ]; then
    echo "Reading Terraform outputs..."
    cd "$TERRAFORM_DIR"

    # Try to get outputs, but don't fail if Terraform isn't initialized
    if terraform output -json > /dev/null 2>&1; then
        DB_HOST=$(terraform output -raw db_private_ip 2>/dev/null || echo "localhost")
        DB_NAME=$(terraform output -raw db_name 2>/dev/null || echo "rag_db")
        DB_USER=$(terraform output -raw db_user 2>/dev/null || echo "raguser")
        REGION=$(terraform output -raw region 2>/dev/null || echo "us-central1")
    else
        echo "  Terraform not initialized, using defaults"
        DB_HOST="localhost"
        DB_NAME="rag_db"
        DB_USER="postgres"
        REGION="us-central1"
    fi
    cd ..
else
    DB_HOST="localhost"
    DB_NAME="rag_db"
    DB_USER="postgres"
    REGION="us-central1"
fi

# Generate .env file
ENV_FILE=".env"
echo "Generating ${ENV_FILE}..."

cat > "$ENV_FILE" << EOF
# Generated from Secret Manager - DO NOT EDIT MANUALLY
# Run ./scripts/sync-env-from-secrets.sh to regenerate
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Google Cloud
GOOGLE_PROJECT_ID=${PROJECT_ID}
GOOGLE_LOCATION=${REGION}
ENVIRONMENT=${ENVIRONMENT}

# Database
DB_HOST=${DB_HOST}
DB_PORT=5432
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}

# Google Drive
TARGET_FOLDER_ID=${TARGET_FOLDER_ID}

# Email
MY_EMAIL=${MY_EMAIL}

# Vertex AI (defaults)
EMBEDDING_MODEL=text-embedding-004
LLM_MODEL=gemini-1.5-pro
LLM_TEMPERATURE=0.3

# Hybrid Search Parameters (defaults)
HYBRID_SEARCH_K=20
RRF_K=50
FINAL_K=10

# Reranker (defaults)
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_TOP_K=5
USE_FP16=true

# Chunking (defaults)
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EOF

echo ""
echo "Done! .env file has been generated."
echo ""
echo "Note: Non-secret configuration values use defaults."
echo "These can be overridden by editing .env or setting environment variables."
