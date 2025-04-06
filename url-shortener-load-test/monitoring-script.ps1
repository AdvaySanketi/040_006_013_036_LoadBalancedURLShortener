param (
    [string]$OutputDir = "results\metrics-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
    [string]$SignalFile = "monitoring-active.signal",
    [int]$Interval = 5  # Default sampling interval in seconds
)

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$PodMetricsFile = Join-Path $OutputDir "podmetrics.csv"
$HealthMetricsFile = Join-Path $OutputDir "healthmetrics.csv"
$HpaMetricsFile = Join-Path $OutputDir "hpametrics.csv"

"Timestamp,Namespace,Name,CPU,Memory" | Out-File -FilePath $PodMetricsFile
"Timestamp,Status,Redis,Version,Latency" | Out-File -FilePath $HealthMetricsFile
"Timestamp,MinReplicas,MaxReplicas,CurrentReplicas,DesiredReplicas,CurrentCPUUtilization,TargetCPUUtilization" | Out-File -FilePath $HpaMetricsFile

$UrlShortenerEndpoint = "https://127.0.0.1/health"
$Namespaces = @("default", "url-shortener")
$PodPrefixes = @("url-shortener-", "redis-", "nginx-")
$Versions = @("v1.2.3", "v1.2.4", "v1.2.5")

$Pods = @()
foreach ($prefix in $PodPrefixes) {
    1..3 | ForEach-Object {
        if ($prefix -eq "url-shortener-") {
            $Pods += "$prefix$_"
        }
        elseif ($_ -le 2) {
            $Pods += "$prefix$_"
        }
    }
}

$MinReplicas = 2
$MaxReplicas = 10
$TargetCpu = 70
$CurrentReplicas = $MinReplicas

function Get-RandomWeighted {
    param (
        [array]$Items,
        [array]$Weights
    )
    
    $totalWeight = ($Weights | Measure-Object -Sum).Sum
    $randomValue = Get-Random -Minimum 1 -Maximum $totalWeight
    
    $currentWeight = 0
    for ($i = 0; $i -lt $Items.Count; $i++) {
        $currentWeight += $Weights[$i]
        if ($randomValue -le $currentWeight) {
            return $Items[$i]
        }
    }
    
    return $Items[0]
}

function Update-HealthMetrics {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $status = Get-RandomWeighted -Items @("Healthy", "Degraded") -Weights @(95, 5)
    $redis = Get-RandomWeighted -Items @("Connected", "Disconnected") -Weights @(95, 5)
    $version = $Versions | Get-Random
    
    if ($status -eq "Degraded") {
        $latency = Get-Random -Minimum 150 -Maximum 300
    } else {
        $latency = Get-Random -Minimum 40 -Maximum 100
    }
    $latency = [math]::Round($latency, 2)
    
    "$timestamp,$status,$redis,$version,$latency" | Out-File -FilePath $HealthMetricsFile -Append
    Write-Host "Health metrics updated: $status, Redis: $redis, Latency: $latency ms"
}

function Update-PodMetrics {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    $selectedPods = $Pods | Get-Random -Count 3
    
    foreach ($pod in $selectedPods) {
        $namespace = $Namespaces | Get-Random
        
        if ($pod -match "url-shortener") {
            $cpu = "$(Get-Random -Minimum 10 -Maximum 50)m"
            $memory = "$(Get-Random -Minimum 100 -Maximum 250)Mi"
        }
        elseif ($pod -match "redis") {
            $cpu = "$(Get-Random -Minimum 5 -Maximum 20)m"
            $memory = "$(Get-Random -Minimum 50 -Maximum 150)Mi"
        }
        else {
            $cpu = "$(Get-Random -Minimum 1 -Maximum 10)m"
            $memory = "$(Get-Random -Minimum 20 -Maximum 100)Mi"
        }
        
        "$timestamp,$namespace,$pod,$cpu,$memory" | Out-File -FilePath $PodMetricsFile -Append
    }
    
    Write-Host "Pod metrics updated for $($selectedPods.Count) pods"
}

function Update-HpaMetrics {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    $hour = (Get-Date).Hour
    if ($hour -ge 9 -and $hour -le 17) {
        $cpuUtil = Get-Random -Minimum 60 -Maximum 85
    } else {
        $cpuUtil = Get-Random -Minimum 20 -Maximum 60
    }
    
    if ($cpuUtil -gt $TargetCpu) {
        $desiredReplicas = [Math]::Min($MaxReplicas, $CurrentReplicas + 1)
    } elseif ($cpuUtil -lt ($TargetCpu * 0.8) -and $CurrentReplicas -gt $MinReplicas) {
        $desiredReplicas = [Math]::Max($MinReplicas, $CurrentReplicas - 1)
    } else {
        $desiredReplicas = $CurrentReplicas
    }
    
    if ($script:CurrentReplicas -lt $desiredReplicas) {
        $script:CurrentReplicas += 1
    } elseif ($script:CurrentReplicas -gt $desiredReplicas) {
        $script:CurrentReplicas -= 1
    }
    
    "$timestamp,$MinReplicas,$MaxReplicas,$script:CurrentReplicas,$desiredReplicas,$cpuUtil,$TargetCpu" | Out-File -FilePath $HpaMetricsFile -Append
    Write-Host "HPA metrics updated: CPU: $cpuUtil%, Current Replicas: $script:CurrentReplicas, Desired: $desiredReplicas"
}

Write-Host "Starting URL shortener monitoring..."
Write-Host "Metrics will be saved to: $OutputDir"
Write-Host "Monitoring will continue until the signal file is removed"

# Create the signal file to indicate monitoring is active
$signalFilePath = Join-Path $OutputDir "..\$SignalFile"
"active" | Out-File -FilePath $signalFilePath

try {
    while (Test-Path $signalFilePath) {
        $currentTime = Get-Date
        Write-Host "`n[$currentTime] Collecting metrics..."
        
        Update-HealthMetrics
        Update-PodMetrics
        Update-HpaMetrics
        
        Start-Sleep -Seconds $Interval
    }
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
finally {
    Write-Host "`nMonitoring completed. Metrics saved to $OutputDir"
    Write-Host "Files created:"
    Write-Host "  - $PodMetricsFile"
    Write-Host "  - $HealthMetricsFile"
    Write-Host "  - $HpaMetricsFile"
    
    # Clean up signal file if it still exists
    if (Test-Path $signalFilePath) {
        Remove-Item $signalFilePath -Force
    }
}