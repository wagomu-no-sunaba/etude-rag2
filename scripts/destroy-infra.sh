#!/bin/bash
# Destroy Infrastructure Script
# Usage: ./scripts/destroy-infra.sh [--force] [--use-terraform]
#
# Completely removes all GCP resources. Use when shutting down the project.
# WARNING: This will permanently delete all data!

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
FORCE=false
USE_TERRAFORM=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --force|-f)
            FORCE=true
            shift
            ;;
        --use-terraform|-t)
            USE_TERRAFORM=true
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to send macOS notification
notify() {
    local title="$1"
    local message="$2"
    local sound="$3"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "display notification \"${message}\" with title \"${title}\" sound name \"${sound}\"" 2>/dev/null || true
    fi
}

echo "=========================================="
echo -e "${RED}DESTROY Infrastructure${NC}"
echo "=========================================="
echo ""
echo -e "${RED}WARNING: This will PERMANENTLY DELETE all resources!${NC}"
echo ""
echo "Resources to be deleted:"
echo "  - Cloud Run: etude-rag2-api-${ENVIRONMENT}"
echo "  - Cloud Run: etude-rag2-streamlit-${ENVIRONMENT}"
echo "  - Cloud Run Job: etude-rag2-ingester-${ENVIRONMENT}"
echo "  - Cloud SQL: etude-rag2-db-${ENVIRONMENT} (ALL DATA WILL BE LOST)"
echo "  - VPC Connector: etude-rag2-vpc-${ENVIRONMENT}"
echo "  - Artifact Registry: etude-rag2"
echo "  - Secret Manager secrets"
echo "  - Service accounts"
echo "  - VPC / Subnet"
echo ""

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No project ID set. Run 'gcloud config set project PROJECT_ID'${NC}"
    exit 1
fi
echo "Project: ${PROJECT_ID}"
echo ""

# Confirmation prompt (requires typing project ID)
if [ "$FORCE" != true ]; then
    echo -e "${YELLOW}To confirm destruction, type the project ID:${NC}"
    read -p "> " confirm_project
    if [ "$confirm_project" != "$PROJECT_ID" ]; then
        echo "Project ID does not match. Cancelled."
        exit 0
    fi
fi

START_TIME=$(date +%s)

# Use Terraform if requested
if [ "$USE_TERRAFORM" = true ]; then
    echo ""
    echo ">>> Using Terraform to destroy infrastructure..."

    # Disable deletion protection for Cloud SQL
    echo ""
    echo ">>> Disabling Cloud SQL deletion protection..."
    gcloud sql instances patch "etude-rag2-db-${ENVIRONMENT}" \
        --no-deletion-protection \
        --quiet 2>/dev/null || true

    cd "${PROJECT_ROOT}/terraform"
    terraform destroy -auto-approve

    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS=$((ELAPSED % 60))

    echo ""
    echo "=========================================="
    echo -e "${GREEN}Infrastructure destroyed via Terraform!${NC}"
    echo "=========================================="
    echo "Elapsed time: ${MINUTES}m ${SECONDS}s"

    notify "Infrastructure Destroyed" "All resources have been deleted" "Glass"
    exit 0
fi

# Manual deletion (gcloud commands)
echo ""
echo ">>> Deleting Cloud Run services..."
gcloud run services delete "etude-rag2-api-${ENVIRONMENT}" --region="${REGION}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} etude-rag2-api-${ENVIRONMENT} deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-api-${ENVIRONMENT} not found."

gcloud run services delete "etude-rag2-streamlit-${ENVIRONMENT}" --region="${REGION}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} etude-rag2-streamlit-${ENVIRONMENT} deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-streamlit-${ENVIRONMENT} not found."

echo ""
echo ">>> Deleting Cloud Run Job..."
gcloud run jobs delete "etude-rag2-ingester-${ENVIRONMENT}" --region="${REGION}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} etude-rag2-ingester-${ENVIRONMENT} job deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-ingester-${ENVIRONMENT} job not found."

echo ""
echo ">>> Deleting VPC Access Connector..."
gcloud compute networks vpc-access connectors delete "etude-rag2-vpc-${ENVIRONMENT}" --region="${REGION}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} VPC Connector deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} VPC Connector not found."

echo ""
echo ">>> Disabling Cloud SQL deletion protection..."
gcloud sql instances patch "etude-rag2-db-${ENVIRONMENT}" \
    --no-deletion-protection \
    --quiet 2>/dev/null || true

echo ""
echo ">>> Deleting Cloud SQL instance (this may take several minutes)..."
gcloud sql instances delete "etude-rag2-db-${ENVIRONMENT}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} etude-rag2-db-${ENVIRONMENT} deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-db-${ENVIRONMENT} not found."

echo ""
echo ">>> Deleting Artifact Registry repository..."
gcloud artifacts repositories delete etude-rag2 --location="${REGION}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} etude-rag2 repository deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2 repository not found."

echo ""
echo ">>> Deleting Secret Manager secrets..."
for secret in "etude-rag2-db-password-${ENVIRONMENT}" "etude-rag2-drive-folder-id-${ENVIRONMENT}" "etude-rag2-my-email-${ENVIRONMENT}" "etude-rag2-service-account-key-${ENVIRONMENT}"; do
    gcloud secrets delete "${secret}" --quiet 2>/dev/null && \
        echo -e "${GREEN}[OK]${NC} Secret ${secret} deleted." || \
        echo -e "${YELLOW}[SKIP]${NC} Secret ${secret} not found."
done

echo ""
echo ">>> Deleting service accounts..."
gcloud iam service-accounts delete "etude-rag2-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} etude-rag2-${ENVIRONMENT} service account deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-${ENVIRONMENT} service account not found."

echo ""
echo ">>> Deleting VPC resources..."
# Delete private service connection
gcloud services vpc-peerings delete --network="etude-rag2-vpc-${ENVIRONMENT}" --quiet 2>/dev/null || true

# Delete subnet
gcloud compute networks subnets delete "etude-rag2-subnet-${ENVIRONMENT}" --region="${REGION}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} Subnet deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} Subnet not found."

# Delete VPC
gcloud compute networks delete "etude-rag2-vpc-${ENVIRONMENT}" --quiet 2>/dev/null && \
    echo -e "${GREEN}[OK]${NC} VPC deleted." || \
    echo -e "${YELLOW}[SKIP]${NC} VPC not found."

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "=========================================="
echo -e "${GREEN}Infrastructure destroyed!${NC}"
echo "=========================================="
echo ""
echo "Elapsed time: ${MINUTES}m ${SECONDS}s"
echo ""
echo -e "${YELLOW}Note: Some resources may take additional time to fully delete.${NC}"
echo -e "${YELLOW}Check the GCP Console to verify all resources are removed.${NC}"
echo "=========================================="

notify "Infrastructure Destroyed" "All resources have been deleted" "Glass"
