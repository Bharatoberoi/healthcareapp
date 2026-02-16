param(
    [string]$HELM_RELEASE = "prometheus",
    [string]$NAMESPACE = "monitoring",
    [string]$VALUES_FILE = "k8s/monitoring/values.yaml"
)

Write-Host "Adding Helm repo: prometheus-community"
try {
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
} catch {
    Write-Host "Helm repo add skipped or failed (it may already exist): $_"
}
helm repo update

Write-Host "Installing/upgrading kube-prometheus-stack (release=$HELM_RELEASE, ns=$NAMESPACE)"
helm upgrade --install $HELM_RELEASE prometheus-community/kube-prometheus-stack `
  -n $NAMESPACE --create-namespace -f $VALUES_FILE

Write-Host "Applying Grafana dashboard ConfigMap"
kubectl apply -f k8s/monitoring/grafana-dashboard-configmap.yaml

Write-Host "Waiting for Grafana LoadBalancer IP (timeout ~5 min)"
for ($i = 0; $i -lt 30; $i++) {
    $ip = kubectl get svc prometheus-grafana -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null
    if ($ip) {
        Write-Host "Grafana available at: http://$ip (admin/changeme)"
        break
    }
    Start-Sleep -Seconds 10
}
if (-not $ip) { kubectl get svc -n $NAMESPACE; Write-Host "Grafana LoadBalancer IP not ready yet." }
