#!/bin/bash
# Resume Infrastructure Script
# Usage: ./scripts/resume-infra.sh [--force]
#
# Restarts GCP resources that were paused with pause-infra.sh

set -e

REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
FORCE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --force|-f)
            FORCE=true
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
echo "Resume Infrastructure"
echo "=========================================="
echo ""
echo -e "${YELLOW}This will start the following resources:${NC}"
echo "  - Cloud SQL: etude-rag2-db-${ENVIRONMENT}"
echo "  - Cloud Run: etude-rag2-api-${ENVIRONMENT} (max-instances=10)"
echo "  - Cloud Run: etude-rag2-streamlit-${ENVIRONMENT} (max-instances=5)"
echo ""

# Confirmation prompt
if [ "$FORCE" != true ]; then
    read -p "Are you sure you want to resume the infrastructure? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

START_TIME=$(date +%s)

echo ""
echo ">>> Starting Cloud SQL instance (etude-rag2-db-${ENVIRONMENT})..."
echo "    (This may take a few minutes)"
if gcloud sql instances patch "etude-rag2-db-${ENVIRONMENT}" --activation-policy=ALWAYS --quiet 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Cloud SQL instance starting."
else
    echo -e "${YELLOW}[SKIP]${NC} Cloud SQL instance already running or not found."
fi

echo ""
echo ">>> Restoring Cloud Run services max instances..."
if gcloud run services update "etude-rag2-api-${ENVIRONMENT}" --region="${REGION}" --max-instances=10 --quiet 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} etude-rag2-api-${ENVIRONMENT} set to max 10 instances."
else
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-api-${ENVIRONMENT} not found or already configured."
fi

if gcloud run services update "etude-rag2-streamlit-${ENVIRONMENT}" --region="${REGION}" --max-instances=5 --quiet 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} etude-rag2-streamlit-${ENVIRONMENT} set to max 5 instances."
else
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-streamlit-${ENVIRONMENT} not found or already configured."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

# Get service URLs
BACKEND_URL=$(gcloud run services describe "etude-rag2-api-${ENVIRONMENT}" --region="${REGION}" --format="value(status.url)" 2>/dev/null || echo "N/A")
FRONTEND_URL=$(gcloud run services describe "etude-rag2-streamlit-${ENVIRONMENT}" --region="${REGION}" --format="value(status.url)" 2>/dev/null || echo "N/A")

echo ""
echo "=========================================="
echo -e "${GREEN}Infrastructure resumed successfully!${NC}"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  Backend:  ${BACKEND_URL}"
echo "  Frontend: ${FRONTEND_URL}"
echo ""
echo "Elapsed time: ${MINUTES}m ${SECONDS}s"
echo ""
echo -e "${YELLOW}Note: Cloud SQL may take a few minutes to become fully available.${NC}"
echo "=========================================="

notify "Infrastructure Resumed" "All resources have been started" "Glass"
