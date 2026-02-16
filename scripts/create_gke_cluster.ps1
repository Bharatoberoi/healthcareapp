param(
    [string]$PROJECT = "<GCP_PROJECT>",
    [string]$CLUSTER = "service-code-cluster",
    [string]$REGION = "us-central1",
    [int]$CONTROL_PLANE_NODES = 1,
    [string]$FAISS_NODEPOOL = "faiss-nodepool",
    # Use a smaller default machine to avoid quota issues in small projects
    [string]$FAISS_MACHINE = "n2-highmem-4",
    # Default to single FAISS node to reduce CPU/quota requirements
    [int]$FAISS_NODES = 1,
    [switch]$Preemptible  # set this flag to create preemptible (spot) nodes
)

Write-Host "Enabling required GCP APIs..."
gcloud services enable container.googleapis.com compute.googleapis.com --project $PROJECT

Write-Host "Creating regional GKE cluster: $CLUSTER (region=$REGION)"
gcloud container clusters create $CLUSTER `
  --region $REGION `
  --num-nodes $CONTROL_PLANE_NODES `
  --machine-type n2-standard-4 `
  --enable-ip-alias `
  --project $PROJECT

Write-Host "Creating FAISS node pool (high-memory)"
$preemptibleFlag = $null
if ($Preemptible) { $preemptibleFlag = "--preemptible" }
gcloud container node-pools create $FAISS_NODEPOOL `
  --cluster $CLUSTER `
  --region $REGION `
  --machine-type $FAISS_MACHINE `
  --num-nodes $FAISS_NODES `
  $preemptibleFlag `
  --node-labels=workload=faiss `
  --project $PROJECT

Write-Host "Getting credentials for kubectl"
gcloud container clusters get-credentials $CLUSTER --region $REGION --project $PROJECT

Write-Host "Cluster and node pool created.\nNext: apply k8s manifests (kubectl apply -f k8s/) and create GCR registry / set up CI secrets."