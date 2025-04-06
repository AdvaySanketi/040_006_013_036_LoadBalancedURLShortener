@echo off
setlocal

echo ===== URL Shortener Load Test =====

where k6 > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: k6 is not installed. Please install it using `choco install k6`
    exit /b 1
)

where kubectl > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: kubectl is not found in PATH
    exit /b 1
)

where python > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not found in PATH
    exit /b 1
)

set TIMESTAMP=%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set RESULTS_DIR=results\load-test-results-%TIMESTAMP%
set METRICS_DIR=%RESULTS_DIR%\metrics
set SIGNAL_FILE=monitoring-active.signal

mkdir %RESULTS_DIR%
mkdir %METRICS_DIR%

echo ==============================================
echo Test results will be saved to: %RESULTS_DIR%
echo ==============================================

echo.
echo [1/7] Starting monitoring...
start /B powershell -ExecutionPolicy Bypass -File monitoring-script.ps1 -OutputDir %METRICS_DIR% -SignalFile %SIGNAL_FILE% -Interval 5
echo Monitoring started. It will continue until the test is completed.

echo.
echo [2/7] Saving current Kubernetes state...
kubectl get all > %RESULTS_DIR%\k8s-before.txt
kubectl get pods -o wide > %RESULTS_DIR%\pods-before.txt
kubectl get hpa -o yaml > %RESULTS_DIR%\hpa-before.yaml

echo.
echo [3/7] Starting load test...
echo Running k6 load test - this may take a few minutes...
k6 run --quiet --out json=%RESULTS_DIR%\k6-results.json load-test-script.js > %RESULTS_DIR%\k6-output.txt

echo.
echo [4/7] Saving Kubernetes state after test...
kubectl get all > %RESULTS_DIR%\k8s-after.txt
kubectl get pods -o wide > %RESULTS_DIR%\pods-after.txt
kubectl get hpa -o yaml > %RESULTS_DIR%\hpa-after.yaml

echo.
echo [5/7] Gathering logs from pods...
for /f "tokens=1" %%i in ('kubectl get pods -l app^=urlshortener -o name') do (
    echo Getting logs from %%i
    kubectl logs %%i > %RESULTS_DIR%\%%~ni-logs.txt
)

echo.
echo [6/7] Stopping monitoring...
echo Stopping monitoring process...
if exist "%RESULTS_DIR%\%SIGNAL_FILE%" (
    del "%RESULTS_DIR%\%SIGNAL_FILE%"
    echo Signal file removed, monitoring will stop.
    timeout /t 5 /nobreak > nul
) else (
    echo Warning: Signal file not found. Monitoring may have stopped unexpectedly.
)

echo.
echo [7/7] Analyzing test results...
python analyze-results.py %RESULTS_DIR% %METRICS_DIR%
if %ERRORLEVEL% neq 0 (
    echo Warning: Analysis script returned an error. Check the logs for details.
)

echo.
echo ==============================================
echo Test completed! Results available in %RESULTS_DIR%
echo ==============================================
echo.
echo Summary of available artifacts:
echo  - Full HTML report: %RESULTS_DIR%\report.html
echo  - K6 performance data: %RESULTS_DIR%\k6-output.txt
echo  - Pod scaling information: %RESULTS_DIR%\k8s-before.txt and %RESULTS_DIR%\k8s-after.txt
echo  - Pod logs: %RESULTS_DIR%\*-logs.txt
echo  - Visualizations: %RESULTS_DIR%\plots folder
echo.

endlocal