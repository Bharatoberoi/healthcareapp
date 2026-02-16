#!/bin/bash

# GitHub Repository Secrets Setup Script
# This script sets up the required GitHub repository secrets for the CI/CD pipeline

set -e

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
CLUSTER="service-code-cluster"

# Display usage
usage() {
    echo "Usage: $0 -p PROJECT_ID -z ZONE -k KEY_FILE [-c CLUSTER_NAME]"
    echo ""
    echo "Options:"
    echo "  -p PROJECT_ID    GCP project ID (required)"
    echo "  -z ZONE          GKE cluster zone/region (required)"
    echo "  -k KEY_FILE      Path to GCP service account JSON key file (required)"
    echo "  -c CLUSTER_NAME  GKE cluster name (default: service-code-cluster)"
    echo ""
    echo "Example:"
    echo "  $0 -p my-gcp-project -z us-central1 -k ~/service-account-key.json"
    exit 1
}

# Parse command line arguments
while getopts "p:z:k:c:h" opt; do
    case $opt in
        p) PROJECT="$OPTARG" ;;
        z) ZONE="$OPTARG" ;;
        k) KEY_FILE="$OPTARG" ;;
        c) CLUSTER="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Check required parameters
if [ -z "$PROJECT" ] || [ -z "$ZONE" ] || [ -z "$KEY_FILE" ]; then
    echo -e "${RED}Error: Missing required parameters${NC}"
    usage
fi

# Ensure GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed.${NC}"
    echo "Please install it from https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI.${NC}"
    echo "Please run 'gh auth login' first."
    exit 1
fi

# Verify service account key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo -e "${RED}Error: Service account key file not found: $KEY_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Setting up GitHub repository secrets...${NC}"
echo ""

# Set GKE_CLUSTER
echo "Setting GKE_CLUSTER = $CLUSTER"
echo "$CLUSTER" | gh secret set GKE_CLUSTER

# Set GCP_PROJECT
echo "Setting GCP_PROJECT = $PROJECT"
echo "$PROJECT" | gh secret set GCP_PROJECT

# Set GKE_ZONE
echo "Setting GKE_ZONE = $ZONE"
echo "$ZONE" | gh secret set GKE_ZONE

# Set GCP_SA_KEY
echo "Setting GCP_SA_KEY from $KEY_FILE"
gh secret set GCP_SA_KEY < "$KEY_FILE"

echo ""
echo -e "${GREEN}All secrets set successfully!${NC}"
echo ""
echo "Verifying secrets..."
gh secret list

echo ""
echo -e "${GREEN}Setup complete! You can now run the CI/CD workflow.${NC}"
