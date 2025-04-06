Write-Host "Starting comprehensive Kubernetes resource cleanup..." -ForegroundColor Green

Write-Host "Deleting HorizontalPodAutoscaler..." -ForegroundColor Yellow
kubectl delete horizontalpodautoscaler urlshortener --ignore-not-found

Write-Host "Deleting Deployments..." -ForegroundColor Yellow
kubectl delete deployment redis --ignore-not-found
kubectl delete deployment urlshortener --ignore-not-found

Write-Host "Deleting Services..." -ForegroundColor Yellow
kubectl delete service redis --ignore-not-found
kubectl delete service urlshortener --ignore-not-found

Write-Host "Deleting ConfigMap..." -ForegroundColor Yellow
kubectl delete configmap urlshortener-config --ignore-not-found

Write-Host "Deleting Secret..." -ForegroundColor Yellow
kubectl delete secret urlshortener-secret --ignore-not-found

Write-Host "Waiting for resources to be fully terminated..." -ForegroundColor Cyan
Start-Sleep -Seconds 25

Write-Host "Current cluster state:" -ForegroundColor Green
kubectl get all

Write-Host "Cleanup completed!" -ForegroundColor Green