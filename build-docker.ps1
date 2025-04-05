Write-Host "Building Docker image for URL shortener..." -ForegroundColor Cyan

docker build -t urlshortener:latest .

Write-Host "`nVerifying image..." -ForegroundColor Cyan
docker images urlshortener:latest

Write-Host "`nImage built successfully!" -ForegroundColor Green
Write-Host "Note: If using Minikube, you may need to run the following command:" -ForegroundColor Yellow
Write-Host "minikube image load urlshortener:latest" -ForegroundColor Yellow
