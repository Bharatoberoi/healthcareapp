# GKE Deployment Guide — Medical Cost Estimation API

Step-by-step instructions to deploy your app to Google Kubernetes Engine using the files already in your project.

---

## Prerequisites

Before starting, make sure you have these installed on your machine:

| Tool | Install |
|---|---|
| **Google Cloud SDK** (`gcloud`) | [Install Guide](https://cloud.google.com/sdk/docs/install) |
| **kubectl** | `gcloud components install kubectl` |
| **Docker Desktop** | [Download](https://www.docker.com/products/docker-desktop/) |
| **Helm** (for monitoring) | `winget install Helm.Helm` |

Also ensure:
- You have a GCP project with billing enabled
- You're authenticated: `gcloud auth login`
- Docker is running

---

## Your K8s Files at a Glance

```
k8s/
├── deployment.yaml           ← Main Deployment (3 replicas, FAISS preload, probes)
├── deployment-runtime-temp.yaml ← Alternate: git-clone-at-runtime (no Docker build needed)
├── service.yaml              ← LoadBalancer Service (port 80 → 8000)
├── configmap.yaml            ← Config values (LOG_LEVEL, ENVIRONMENT)
├── hpa.yaml                  ← Autoscaler (3-10 pods, CPU 70%, memory 80%)
├── README.md                 ← Node pool guidance
└── monitoring/
    ├── servicemonitor.yaml          ← Prometheus ServiceMonitor
    ├── prometheusrule.yaml          ← Alert/recording rules
    ├── grafana-service-code-slo.json ← Grafana dashboard JSON
    ├── grafana-dashboard-configmap.yaml ← Dashboard as ConfigMap
    └── values.yaml                  ← Helm values for kube-prometheus-stack

scripts/
├── create_gke_cluster.ps1    ← Creates GKE cluster + FAISS node pool
├── install_monitoring.ps1    ← Installs Prometheus + Grafana via Helm
├── gh_create_and_push.ps1    ← Creates GitHub repo and pushes code
├── start_all.ps1             ← Start local services
└── stop_all.ps1              ← Stop local services
```

---

## Step 1 — Set Your GCP Project

Open **PowerShell** and set your project:

```powershell
$PROJECT = "gen-lang-client-0281947410"   # ← your GCP project ID from gcp_project.py
$REGION  = "us-central1"
$CLUSTER = "service-code-cluster"

gcloud config set project $PROJECT
```

---

## Step 2 — Create the GKE Cluster

You already have a script for this. Run it:

```powershell
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"

# Option A: Use the existing script (recommended)
.\scripts\create_gke_cluster.ps1 -PROJECT $PROJECT -REGION $REGION -CLUSTER $CLUSTER

# Option B: Manual equivalent
gcloud services enable container.googleapis.com compute.googleapis.com --project $PROJECT

gcloud container clusters create $CLUSTER `
  --region $REGION `
  --num-nodes 1 `
  --machine-type n2-standard-4 `
  --enable-ip-alias `
  --project $PROJECT

# Create dedicated high-memory node pool for FAISS workloads
gcloud container node-pools create faiss-nodepool `
  --cluster $CLUSTER `
  --region $REGION `
  --machine-type n2-highmem-4 `
  --num-nodes 1 `
  --node-labels workload=faiss `
  --project $PROJECT
```

**What this does:**
- Creates a regional GKE cluster with one default node
- Creates a `faiss-nodepool` with high-memory nodes (your `deployment.yaml` has `nodeAffinity` to schedule pods here)
- Configures `kubectl` to point to the new cluster

> ⏱ This takes **5-10 minutes**. Wait for it to finish.

Once done, verify:
```powershell
kubectl get nodes
# Should show nodes from both pools
```

---

## Step 3 — Build & Push Docker Image

You need to build your Docker image and push it to Google Artifact Registry (or GCR):

```powershell
# Enable Artifact Registry API
gcloud services enable artifactregistry.googleapis.com --project $PROJECT

# Create a Docker repository in Artifact Registry
gcloud artifacts repositories create healthcareapp `
  --repository-format=docker `
  --location=$REGION `
  --project=$PROJECT

# Configure Docker to authenticate with Artifact Registry
gcloud auth configure-docker "$REGION-docker.pkg.dev"

# Build the Docker image
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"
docker build -t "$REGION-docker.pkg.dev/$PROJECT/healthcareapp/service-code-resolution-api:latest" .

# Push to Artifact Registry
docker push "$REGION-docker.pkg.dev/$PROJECT/healthcareapp/service-code-resolution-api:latest"
```

> **Note:** Your `Dockerfile` is already set up correctly — it copies the code, installs dependencies, and runs uvicorn on port 8000.

---

## Step 4 — Create Kubernetes Secret for API Keys

Your OpenAI and Anthropic API keys need to be injected into the cluster as a Secret:

```powershell
# Replace with your REAL keys (these are NOT committed to git)
kubectl create secret generic api-keys `
  --from-literal=OPENAI_API_KEY="sk-proj-YOUR-REAL-KEY-HERE" `
  --from-literal=ANTHROPIC_API_KEY="sk-ant-YOUR-REAL-KEY-HERE"

# Verify
kubectl get secret api-keys
```

---

## Step 5 — Update deployment.yaml with Real Image + Secret Refs

Before applying, you need to edit `k8s/deployment.yaml` with two changes:

### 5a. Update the container image to your Artifact Registry URL

Change line 24:
```yaml
# FROM:
image: service-code-resolution-api:latest
imagePullPolicy: IfNotPresent

# TO:
image: us-central1-docker.pkg.dev/gen-lang-client-0281947410/healthcareapp/service-code-resolution-api:latest
imagePullPolicy: Always
```

### 5b. Add API key environment variables from the Secret

Add these lines after `PRELOAD_FAISS` (line 33):
```yaml
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: OPENAI_API_KEY
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: ANTHROPIC_API_KEY
```

---

## Step 6 — Deploy to GKE

Apply all Kubernetes manifests:

```powershell
cd "c:\Users\HP\OneDrive\Desktop\Bhargav\code_3 - Copy"

# Apply in order: config → deployment → service → autoscaler
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Or apply everything at once:
# kubectl apply -f k8s/
```

**What gets created:**
| Resource | File | What it does |
|---|---|---|
| ConfigMap | `configmap.yaml` | Sets `LOG_LEVEL=INFO`, `ENVIRONMENT=production` |
| Deployment | `deployment.yaml` | 3 replicas, FAISS preload, health/readiness/startup probes |
| Service | `service.yaml` | LoadBalancer exposing port 80 → container port 8000 |
| HPA | `hpa.yaml` | Auto-scales 3→10 pods based on CPU (70%) and memory (80%) |

---

## Step 7 — Verify Deployment

```powershell
# Watch pods come up (wait for all 3 to be READY 1/1)
kubectl get pods -w

# Check deployment status
kubectl rollout status deployment/service-code-resolution-api

# Get the external IP (may take 1-2 minutes for LoadBalancer)
kubectl get svc service-code-resolution-api
```

Once you see an `EXTERNAL-IP`:
```powershell
$EXTERNAL_IP = kubectl get svc service-code-resolution-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Test health endpoint
curl "http://${EXTERNAL_IP}/health"
# Expected: {"status":"ok"}

# Test readiness endpoint
curl "http://${EXTERNAL_IP}/ready"
# Expected: {"ready":true,"faiss_loaded":true}

# Test service code resolution
curl "http://${EXTERNAL_IP}/resolve-service-codes?query=chiropractor"

# Test Swagger docs
# Open in browser: http://<EXTERNAL_IP>/docs
```

---

## Step 8 — Install Monitoring (Optional but Recommended)

```powershell
# Use the existing script
.\scripts\install_monitoring.ps1

# This installs:
# - Prometheus (metrics collection)
# - Grafana (dashboards) with your SLO dashboard auto-imported
# - ServiceMonitor for scraping /metrics from your pods
```

After installation:
```powershell
# Apply ServiceMonitor and alerting rules
kubectl apply -f k8s/monitoring/servicemonitor.yaml
kubectl apply -f k8s/monitoring/prometheusrule.yaml

# Get Grafana URL
kubectl get svc prometheus-grafana -n monitoring
# Login: admin / changeme (change this in production!)
```

---

## Step 9 — Verify Autoscaling

```powershell
# Check HPA status
kubectl get hpa

# You should see:
# NAME                              REFERENCE                            TARGETS   MINPODS   MAXPODS
# service-code-resolution-api-hpa   Deployment/service-code-resolution   <cpu>%    3         10
```

---

## Quick Reference: Common Operations

```powershell
# View logs from a pod
kubectl logs -f deployment/service-code-resolution-api

# Restart all pods (after code/image update)
kubectl rollout restart deployment/service-code-resolution-api

# Scale manually
kubectl scale deployment/service-code-resolution-api --replicas=5

# Update image after a new build
docker build -t "$REGION-docker.pkg.dev/$PROJECT/healthcareapp/service-code-resolution-api:v2" .
docker push "$REGION-docker.pkg.dev/$PROJECT/healthcareapp/service-code-resolution-api:v2"
kubectl set image deployment/service-code-resolution-api api="$REGION-docker.pkg.dev/$PROJECT/healthcareapp/service-code-resolution-api:v2"

# Delete everything (teardown)
kubectl delete -f k8s/
gcloud container clusters delete $CLUSTER --region $REGION --project $PROJECT
```

---

## Alternative: Quick Deploy WITHOUT Docker Build

Your `deployment-runtime-temp.yaml` offers a shortcut — it uses an **initContainer** that clones your GitHub repo and installs deps at pod startup (no Docker build needed):

```powershell
# Push code to GitHub first
.\scripts\gh_create_and_push.ps1 -Token "ghp_YOUR_GITHUB_TOKEN"

# Then deploy using the runtime deployment
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment-runtime-temp.yaml
kubectl apply -f k8s/service.yaml
```

> ⚠️ This is slower to start (clones repo + installs deps every pod restart) and is better suited for **testing**, not production.

---

## Architecture on GKE

```
                 Internet
                    │
            ┌───────▼───────┐
            │  GCP Load     │   ← k8s/service.yaml (type: LoadBalancer)
            │  Balancer     │      port 80 → 8000
            └───────┬───────┘
                    │
     ┌──────────────┼──────────────┐
     │              │              │
  ┌──▼──┐       ┌──▼──┐       ┌──▼──┐
  │Pod 1│       │Pod 2│       │Pod 3│    ← k8s/deployment.yaml (3 replicas)
  │:8000│       │:8000│       │:8000│      on faiss-nodepool (n2-highmem-4)
  └─────┘       └─────┘       └─────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
            ┌───────▼───────┐
            │   HPA         │   ← k8s/hpa.yaml (3→10 pods)
            │   CPU: 70%    │      auto-scale on CPU/memory
            │   Mem: 80%    │
            └───────────────┘
```

Each pod runs:
1. **FastAPI** (uvicorn, 2 workers) on port 8000
2. **FAISS index** preloaded into memory (~600KB)
3. **MCP subprocess servers** for provider lookup & cost estimation
