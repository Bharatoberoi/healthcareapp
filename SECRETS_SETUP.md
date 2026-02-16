# GitHub Repository Secrets Setup

This document provides instructions for setting up the required GitHub repository secrets for the CI/CD pipeline.

## Required Secrets

The `.github/workflows/gke-deploy.yml` workflow requires the following repository secrets to be configured:

### 1. GKE_CLUSTER
- **Name**: `GKE_CLUSTER`
- **Value**: `service-code-cluster`
- **Description**: The name of the Google Kubernetes Engine (GKE) cluster where the application will be deployed.

### 2. GCP_PROJECT
- **Name**: `GCP_PROJECT`
- **Value**: Your Google Cloud Platform project ID
- **Description**: The GCP project ID where your resources are hosted.

### 3. GKE_ZONE
- **Name**: `GKE_ZONE`
- **Value**: The zone/region where your GKE cluster is deployed (e.g., `us-central1`)
- **Description**: The geographical location of your GKE cluster.

### 4. GCP_SA_KEY
- **Name**: `GCP_SA_KEY`
- **Value**: JSON key for a GCP service account
- **Description**: Service account JSON key with permissions to:
  - Push images to Google Container Registry (GCR)
  - Update GKE deployments
  - Get GKE cluster credentials

## Setup Instructions

### Option 1: Using GitHub Web UI

1. Navigate to your repository on GitHub
2. Click on **Settings** tab
3. In the left sidebar, click on **Secrets and variables** > **Actions**
4. Click **New repository secret**
5. For each secret listed above:
   - Enter the **Name** (e.g., `GKE_CLUSTER`)
   - Enter the **Value** (e.g., `service-code-cluster`)
   - Click **Add secret**

### Option 2: Using GitHub CLI (gh)

If you have the GitHub CLI installed and authenticated, you can run the following commands:

```bash
# Set GKE_CLUSTER secret
gh secret set GKE_CLUSTER --body "service-code-cluster"

# Set GCP_PROJECT secret (replace with your project ID)
gh secret set GCP_PROJECT --body "your-gcp-project-id"

# Set GKE_ZONE secret (replace with your cluster zone)
gh secret set GKE_ZONE --body "us-central1"

# Set GCP_SA_KEY secret (replace with path to your service account JSON key)
gh secret set GCP_SA_KEY < path/to/service-account-key.json
```

### Option 3: Using the Setup Script

Run the provided PowerShell script to set up the secrets:

```powershell
./scripts/setup_github_secrets.ps1 -Project "your-gcp-project-id" -Zone "us-central1" -KeyFile "path/to/service-account-key.json"
```

## Verification

After setting up the secrets, you can verify they exist by:

1. Going to **Settings** > **Secrets and variables** > **Actions** in your GitHub repository
2. You should see all four secrets listed (the values will be hidden)

Alternatively, use the GitHub CLI:

```bash
gh secret list
```

## Notes

- The default cluster name is `service-code-cluster` as defined in `scripts/create_gke_cluster.ps1`
- Never commit service account keys or secrets directly to the repository
- Ensure the service account has the minimum required permissions for security best practices
- Secrets are encrypted and only exposed to GitHub Actions workflows
