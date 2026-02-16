FAISS node pool (recommended for low-latency retrieval)

Create a dedicated high-memory node pool and label it so pods with the FAISS index are scheduled there.

Example (GKE - regional):

  gcloud container node-pools create faiss-nodepool \
    --cluster="<CLUSTER>" \
    --region="<REGION>" \
    --machine-type=n2-highmem-8 \
    --num-nodes=2 \
    --node-labels=workload=faiss

After creating the node pool, ensure nodes have the label `cloud.google.com/gke-nodepool=faiss-nodepool` (GKE sets this automatically).

Notes:
- `k8s/deployment.yaml` uses nodeAffinity to schedule pods that keep the FAISS index on nodes labeled `faiss-nodepool`.
- Aim for memory >= 8Gi for FAISS-backed pods.

Monitoring & SLOs
- `prometheus.io/scrape` annotation is added to the Deployment; pods expose `/metrics`.
- `k8s/monitoring/servicemonitor.yaml` and `k8s/monitoring/prometheusrule.yaml` include sample ServiceMonitor and alerting/recording rules for Prometheus Operator.
- A sample Grafana dashboard is available at `k8s/monitoring/grafana-service-code-slo.json` (import into Grafana).

Create cluster + nodepool
- Use `scripts/create_gke_cluster.ps1` to create a regional cluster and a high-memory `faiss-nodepool`.
- After creating the cluster: `kubectl apply -f k8s/` to deploy the app and monitoring resources.

Install Prometheus + Grafana (Helm)
- Local (PowerShell): `./scripts/install_monitoring.ps1` — this installs `kube-prometheus-stack` and applies the Grafana dashboard ConfigMap.
- CI: the `deploy` job in `.github/workflows/gke-deploy.yml` now installs the Helm chart automatically.
- Grafana dashboard: available via LoadBalancer (service `prometheus-grafana` in `monitoring` namespace). Default admin: `admin` / `changeme` (override via `k8s/monitoring/values.yaml`).
