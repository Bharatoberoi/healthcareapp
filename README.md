# Healthcare Service Code Resolution API

A Python-based healthcare application that provides service code resolution using FAISS for vector similarity search and integrates with various microservices.

## Overview

This application is designed to run on Google Kubernetes Engine (GKE) and includes:
- Service code resolution API
- FAISS-backed vector search
- Cost estimation services
- Provider lookup functionality
- Monitoring with Prometheus and Grafana
- CI/CD pipeline for automated deployments

## Getting Started

### Prerequisites

- Python 3.x
- Docker (for containerization)
- Google Cloud Platform account
- GKE cluster (see setup instructions below)
- GitHub repository with required secrets configured

### GitHub Secrets Setup

**IMPORTANT**: Before running the CI/CD pipeline, you must configure GitHub repository secrets.

See [SECRETS_SETUP.md](SECRETS_SETUP.md) for detailed instructions on setting up the required secrets:

- `GKE_CLUSTER` - GKE cluster name (default: `service-code-cluster`)
- `GCP_PROJECT` - Your GCP project ID
- `GKE_ZONE` - Cluster zone/region (e.g., `us-central1`)
- `GCP_SA_KEY` - Service account JSON key

Quick setup using the provided script:
```bash
# For Linux/Mac users
./scripts/setup_github_secrets.sh -p your-gcp-project -z us-central1 -k path/to/service-account-key.json

# For Windows PowerShell users
./scripts/setup_github_secrets.ps1 -Project "your-gcp-project" -Zone "us-central1" -KeyFile "path/to/service-account-key.json"
```

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python main.py
   ```

3. Run tests:
   ```bash
   python test_api.py
   python test_complete_workflow.py
   ```

### GKE Cluster Setup

Create a GKE cluster with FAISS node pool using the provided script:

```powershell
./scripts/create_gke_cluster.ps1 -PROJECT "your-gcp-project" -REGION "us-central1"
```

This will create:
- A regional GKE cluster named `service-code-cluster`
- A high-memory node pool for FAISS workloads
- Proper node labels for pod scheduling

See [k8s/README.md](k8s/README.md) for more details on Kubernetes configuration and monitoring.

### Deployment

The application is automatically deployed to GKE when code is pushed to the `main` branch via GitHub Actions.

The CI/CD workflow (`.github/workflows/gke-deploy.yml`):
1. Builds a Docker image
2. Pushes to Google Container Registry (GCR)
3. Deploys to GKE
4. Installs monitoring stack (Prometheus + Grafana)
5. Runs load tests

## Project Structure

- `app/` - Application modules and services
- `k8s/` - Kubernetes manifests and monitoring configuration
- `scripts/` - Helper scripts for setup and deployment
- `load-test/` - Load testing scripts
- `main.py` - Main application entry point
- `SECRETS_SETUP.md` - GitHub secrets configuration guide

## Monitoring

The application includes built-in monitoring with:
- Prometheus for metrics collection
- Grafana dashboards for visualization
- Custom SLO/SLA tracking
- Alert rules for critical issues

Access Grafana after deployment:
```bash
kubectl get svc prometheus-grafana -n monitoring
```

Default credentials: `admin` / `prom-operator` (can be changed in `k8s/monitoring/values.yaml`)

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests locally
4. Submit a pull request

## License

[Add your license information here]
