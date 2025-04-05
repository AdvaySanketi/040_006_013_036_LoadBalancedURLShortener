Write-Host "Installing MetalLB..." -ForegroundColor Cyan
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.10/config/manifests/metallb-native.yaml

Write-Host "Waiting for MetalLB to be ready..." -ForegroundColor Cyan
kubectl wait --namespace metallb-system `
  --for=condition=ready pod `
  --selector=app=metallb `
  --timeout=90s

$manifestsPath = ".\k8s-manifests.yaml"
Write-Host "Applying Kubernetes manifests..." -ForegroundColor Cyan
kubectl apply -f $manifestsPath

Write-Host "Waiting for services to be ready..." -ForegroundColor Cyan
kubectl wait --for=condition=available --timeout=120s deployment/urlshortener
kubectl wait --for=condition=available --timeout=90s deployment/redis

Write-Host "Getting the external IP address..." -ForegroundColor Cyan
$attempts = 0
$maxAttempts = 10
$externalIP = $null

while ($attempts -lt $maxAttempts) {
    $externalIP = kubectl get service urlshortener -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
    if ($externalIP) {
        break
    }
    $attempts++
    Write-Host "Waiting for external IP... (Attempt $attempts/$maxAttempts)" -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

if (-not $externalIP) {
    Write-Host "Could not get external IP. Please check MetalLB configuration." -ForegroundColor Red
    exit 1
}

Write-Host "External IP: $externalIP" -ForegroundColor Green

Write-Host "`nSetup complete!" -ForegroundColor Green

Write-Host "`nTo check logs, use:"
Write-Host "kubectl get all" -ForegroundColor Yellow
Write-Host "kubectl logs -l app=urlshortener" -ForegroundColor Yellow
Write-Host "kubectl logs -l app=redis" -ForegroundColor Yellow
