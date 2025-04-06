import os
import sys
import json
import glob
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import logging
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_k6_results(results_dir):
    """Load and parse k6 JSON results"""
    k6_result_file = os.path.join(results_dir, 'k6-results.json')
    
    if not os.path.exists(k6_result_file):
        logger.warning(f"K6 results file not found: {k6_result_file}")
        return None
    
    try:
        metrics = []
        with open(k6_result_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if 'type' in data and data['type'] == 'Point':
                        metrics.append(data)
                except json.JSONDecodeError:
                    continue
        
        logger.info(f"Loaded {len(metrics)} k6 metrics from {k6_result_file}")
        return metrics
    except Exception as e:
        logger.error(f"Error loading k6 results: {str(e)}")
        return None

def load_csv_metrics(results_dir, metrics_dir):
    """Load CSV metrics collected during the test"""
    metrics = {}
    
    file_variants = {
        'pod': ['podmetrics.csv', 'pod-metrics.csv'],
        'health': ['healthmetrics.csv', 'health-metrics.csv'],
        'hpa': ['hpametrics.csv', 'hpa-metrics.csv']
    }
    
    if not os.path.exists(metrics_dir):
        logger.warning(f"Metrics directory not found: {metrics_dir}")
        os.makedirs(metrics_dir, exist_ok=True)
    
    for key, filenames in file_variants.items():
        metrics[key] = None
        for filename in filenames:
            file_path = os.path.join(metrics_dir, filename)
            if os.path.exists(file_path):
                try:
                    metrics[key] = pd.read_csv(file_path)
                    logger.info(f"Loaded {key} metrics from {filename}: {len(metrics[key])} rows")
                    break  
                except Exception as e:
                    logger.error(f"Error loading {key} metrics from {filename}: {str(e)}")
        
        if metrics[key] is None:
            logger.warning(f"{key} metrics file not found in: {metrics_dir}")
    
    return metrics

def analyze_k6_results(metrics):
    """Analyze k6 test results"""
    if not metrics:
        logger.warning("No k6 metrics to analyze")
        return None
    
    try:
        results = {}
        for point in metrics:
            metric = point.get('metric', '')
            timestamp = point.get('data', {}).get('time', '')
            value = point.get('data', {}).get('value', 0)
            
            if metric not in results:
                results[metric] = {'timestamps': [], 'values': []}
            
            results[metric]['timestamps'].append(timestamp)
            results[metric]['values'].append(value)
        
        dataframes = {}
        for metric, data in results.items():
            if data['timestamps'] and data['values']:
                df = pd.DataFrame({
                    'timestamp': [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in data['timestamps']],
                    'value': data['values']
                })
                df = df.sort_values('timestamp')
                dataframes[metric] = df
        
        logger.info(f"Analyzed {len(dataframes)} k6 metrics")
        return dataframes
    except Exception as e:
        logger.error(f"Error analyzing k6 results: {str(e)}")
        return None

def analyze_pod_metrics(pod_metrics):
    """Analyze pod metrics"""
    if pod_metrics is None or pod_metrics.empty:
        logger.warning("No pod metrics to analyze")
        return None
    
    try:
        pod_metrics['CPU_Value'] = pod_metrics['CPU'].apply(
            lambda x: float(x.replace('m', '')) / 1000 if isinstance(x, str) and 'm' in x else float(x)
        )
        
        pod_metrics['Memory_Value'] = pod_metrics['Memory'].apply(
            lambda x: float(x.replace('Mi', '')) if isinstance(x, str) and 'Mi' in x else 
                    (float(x.replace('Ki', '')) / 1024 if isinstance(x, str) and 'Ki' in x else 
                    (float(x.replace('Gi', '')) * 1024 if isinstance(x, str) and 'Gi' in x else float(x)))
        )
        
        pod_metrics['Timestamp'] = pd.to_datetime(pod_metrics['Timestamp'])
        
        pod_metrics_grouped = pod_metrics.groupby(['Name', pd.Grouper(key='Timestamp', freq='30s')]).agg({
            'CPU_Value': 'mean',
            'Memory_Value': 'mean'
        }).reset_index()
        
        logger.info(f"Analyzed pod metrics for {len(pod_metrics['Name'].unique())} pods")
        return pod_metrics_grouped
    except Exception as e:
        logger.error(f"Error analyzing pod metrics: {str(e)}\n{traceback.format_exc()}")
        return None

def analyze_hpa_metrics(hpa_metrics):
    """Analyze HPA metrics with enhanced error handling"""
    if hpa_metrics is None or hpa_metrics.empty:
        logger.warning("No HPA metrics to analyze")
        return None
    
    try:
        logger.info(f"HPA metrics columns: {list(hpa_metrics.columns)}")
        
        hpa_metrics['Timestamp'] = pd.to_datetime(hpa_metrics['Timestamp'])
        
        column_mapping = {
            'MinReplicas': ['MinReplicas', 'minReplicas'],
            'MaxReplicas': ['MaxReplicas', 'maxReplicas'],
            'CurrentReplicas': ['CurrentReplicas', 'currentReplicas'],
            'DesiredReplicas': ['DesiredReplicas', 'desiredReplicas'],
            'CurrentCPUUtilization': ['CurrentCPUUtilization', 'currentCPUUtilization', 'CPUUtilization'],
            'TargetCPUUtilization': ['TargetCPUUtilization', 'targetCPUUtilization', 'targetCPU']
        }
        
        standardized_df = pd.DataFrame()
        standardized_df['Timestamp'] = hpa_metrics['Timestamp']
        
        for std_col, variants in column_mapping.items():
            found = False
            for variant in variants:
                if variant in hpa_metrics.columns:
                    standardized_df[std_col] = pd.to_numeric(hpa_metrics[variant], errors='coerce')
                    found = True
                    break
            
            if not found:
                logger.warning(f"Column {std_col} not found in HPA metrics")
                
                if std_col in ['CurrentReplicas', 'DesiredReplicas']:
                    standardized_df[std_col] = 2  
                elif std_col in ['CurrentCPUUtilization', 'TargetCPUUtilization']:
                    standardized_df[std_col] = 50 if std_col == 'TargetCPUUtilization' else 30
                else:
                    standardized_df[std_col] = 0
        
        logger.info(f"Analyzed HPA metrics with {len(standardized_df)} records")
        return standardized_df
    except Exception as e:
        logger.error(f"Error analyzing HPA metrics: {str(e)}\n{traceback.format_exc()}")
        
        return None

def generate_plots(results_dir, k6_data, pod_data, hpa_data):
    """Generate plots from the analyzed data with enhanced HPA plotting"""
    plots_dir = os.path.join(results_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    plot_count = 0
    
    if k6_data:
        for metric, df in k6_data.items():
            try:
                if 'http_req_duration' in metric:
                    plt.figure(figsize=(12, 6))
                    plt.plot(df['timestamp'], df['value'])
                    plt.title(f'K6 {metric}')
                    plt.xlabel('Time')
                    plt.ylabel('Duration (ms)')
                    plt.grid(True)
                    plt.tight_layout()
                    plt.savefig(os.path.join(plots_dir, f'k6_{metric.replace(".", "_")}.png'))
                    plt.close()
                    plot_count += 1
                
                if 'vus' in metric or 'http_reqs' in metric:
                    plt.figure(figsize=(12, 6))
                    plt.plot(df['timestamp'], df['value'])
                    plt.title(f'K6 {metric}')
                    plt.xlabel('Time')
                    plt.ylabel('Count')
                    plt.grid(True)
                    plt.tight_layout()
                    plt.savefig(os.path.join(plots_dir, f'k6_{metric.replace(".", "_")}.png'))
                    plt.close()
                    plot_count += 1
            except Exception as e:
                logger.error(f"Error generating k6 plot for {metric}: {str(e)}")
    
    
    if pod_data is not None:
        try:
            pod_groups = pod_data.groupby('Name')
            for name, group in pod_groups:
                
                plt.figure(figsize=(12, 6))
                plt.plot(group['Timestamp'], group['CPU_Value'])
                plt.title(f'Pod {name} - CPU Usage')
                plt.xlabel('Time')
                plt.ylabel('CPU (cores)')
                plt.grid(True)
                plt.tight_layout()
                plt.savefig(os.path.join(plots_dir, f'pod_{name}_cpu.png'))
                plt.close()
                plot_count += 1
                
                plt.figure(figsize=(12, 6))
                plt.plot(group['Timestamp'], group['Memory_Value'])
                plt.title(f'Pod {name} - Memory Usage')
                plt.xlabel('Time')
                plt.ylabel('Memory (MB)')
                plt.grid(True)
                plt.tight_layout()
                plt.savefig(os.path.join(plots_dir, f'pod_{name}_memory.png'))
                plt.close()
                plot_count += 1
        except Exception as e:
            logger.error(f"Error generating pod metrics plots: {str(e)}")
    
    if hpa_data is not None and not hpa_data.empty:
        try:
            logger.info("Generating HPA plots...")
            
            logger.info(f"HPA data columns: {list(hpa_data.columns)}")
            logger.info(f"HPA data rows: {len(hpa_data)}")
            
            required_columns = ['Timestamp', 'CurrentReplicas', 'DesiredReplicas']
            if all(col in hpa_data.columns for col in required_columns):
                
                plt.figure(figsize=(12, 6))
                plt.plot(hpa_data['Timestamp'], hpa_data['CurrentReplicas'], label='Current Replicas', marker='o')
                plt.plot(hpa_data['Timestamp'], hpa_data['DesiredReplicas'], label='Desired Replicas', marker='x')
                plt.title('HPA Replica Count')
                plt.xlabel('Time')
                plt.ylabel('Replicas')
                plt.legend()
                plt.grid(True)
                plt.tight_layout()
                
                try:
                    hpa_replicas_file = os.path.join(plots_dir, 'hpa_replicas.png')
                    plt.savefig(hpa_replicas_file)
                    logger.info(f"Saved HPA replicas plot to {hpa_replicas_file}")
                    plot_count += 1
                except Exception as e:
                    logger.error(f"Error saving HPA replicas plot: {str(e)}")
                finally:
                    plt.close()
            else:
                logger.warning(f"Required columns for HPA replicas plot missing: {[col for col in required_columns if col not in hpa_data.columns]}")
            
            if 'CurrentCPUUtilization' in hpa_data.columns and 'TargetCPUUtilization' in hpa_data.columns:
                if pd.notna(hpa_data['CurrentCPUUtilization']).any():
                    plt.figure(figsize=(12, 6))
                    plt.plot(hpa_data['Timestamp'], hpa_data['CurrentCPUUtilization'], label='Current CPU', marker='o')
                    plt.axhline(y=hpa_data['TargetCPUUtilization'].iloc[0], color='r', linestyle='--', label='Target CPU')
                    plt.title('HPA CPU Utilization')
                    plt.xlabel('Time')
                    plt.ylabel('CPU Utilization %')
                    plt.legend()
                    plt.grid(True)
                    plt.tight_layout()
                    
                    try:
                        hpa_cpu_file = os.path.join(plots_dir, 'hpa_cpu.png')
                        plt.savefig(hpa_cpu_file)
                        logger.info(f"Saved HPA CPU plot to {hpa_cpu_file}")
                        plot_count += 1
                    except Exception as e:
                        logger.error(f"Error saving HPA CPU plot: {str(e)}")
                    finally:
                        plt.close()
                else:
                    logger.warning("CurrentCPUUtilization contains only NaN values, skipping HPA CPU plot")
            else:
                logger.warning("CurrentCPUUtilization or TargetCPUUtilization columns missing, skipping HPA CPU plot")
        except Exception as e:
            logger.error(f"Error generating HPA plots: {str(e)}\n{traceback.format_exc()}")
    else:
        logger.warning("No HPA data available for plotting")
    
    logger.info(f"Generated {plot_count} plots in {plots_dir}")
    return plot_count

def create_hpa_plots_from_csv(metrics_dir, plots_dir):
    """Create HPA plots directly from CSV without going through the analysis steps"""
    logger.info("Attempting to create HPA plots directly from CSV...")
    
    
    hpa_file_variants = ['hpametrics.csv', 'hpa-metrics.csv']
    hpa_data = None
    
    for filename in hpa_file_variants:
        file_path = os.path.join(metrics_dir, filename)
        if os.path.exists(file_path):
            try:
                hpa_data = pd.read_csv(file_path)
                logger.info(f"Loaded HPA metrics from {filename}: {len(hpa_data)} rows")
                break
            except Exception as e:
                logger.error(f"Error loading HPA metrics from {filename}: {str(e)}")
    
    if hpa_data is None or hpa_data.empty:
        logger.warning("Could not load HPA metrics from any expected files")
        return 0
    
    try:
        hpa_data['Timestamp'] = pd.to_datetime(hpa_data['Timestamp'])
        numeric_cols = ['MinReplicas', 'MaxReplicas', 'CurrentReplicas', 'DesiredReplicas', 
                        'CurrentCPUUtilization', 'TargetCPUUtilization']
        
        for col in numeric_cols:
            if col in hpa_data.columns:
                hpa_data[col] = pd.to_numeric(hpa_data[col], errors='coerce')
        
        plot_count = 0
        os.makedirs(plots_dir, exist_ok=True)
        
        if all(col in hpa_data.columns for col in ['Timestamp', 'CurrentReplicas', 'DesiredReplicas']):
            plt.figure(figsize=(12, 6))
            plt.plot(hpa_data['Timestamp'], hpa_data['CurrentReplicas'], label='Current Replicas', marker='o')
            plt.plot(hpa_data['Timestamp'], hpa_data['DesiredReplicas'], label='Desired Replicas', marker='x')
            plt.title('HPA Replica Count')
            plt.xlabel('Time')
            plt.ylabel('Replicas')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            
            hpa_replicas_file = os.path.join(plots_dir, 'hpa_replicas.png')
            plt.savefig(hpa_replicas_file)
            logger.info(f"Saved HPA replicas plot to {hpa_replicas_file}")
            plot_count += 1
            plt.close()
        
        if all(col in hpa_data.columns for col in ['Timestamp', 'CurrentCPUUtilization', 'TargetCPUUtilization']):
            plt.figure(figsize=(12, 6))
            plt.plot(hpa_data['Timestamp'], hpa_data['CurrentCPUUtilization'], label='Current CPU', marker='o')
            plt.axhline(y=hpa_data['TargetCPUUtilization'].iloc[0], color='r', linestyle='--', label='Target CPU')
            plt.title('HPA CPU Utilization')
            plt.xlabel('Time')
            plt.ylabel('CPU Utilization %')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            
            hpa_cpu_file = os.path.join(plots_dir, 'hpa_cpu.png')
            plt.savefig(hpa_cpu_file)
            logger.info(f"Saved HPA CPU plot to {hpa_cpu_file}")
            plot_count += 1
            plt.close()
        
        return plot_count
    
    except Exception as e:
        logger.error(f"Error creating direct HPA plots: {str(e)}\n{traceback.format_exc()}")
        return 0

def generate_report(results_dir, k6_metrics, pod_metrics, hpa_metrics):
    """Generate HTML report with the analysis results"""
    report_file = os.path.join(results_dir, 'report.html')
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>URL Shortener Load Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2, h3 {{ color: 
            .section {{ margin-bottom: 30px; }}
            .plot {{ margin: 20px 0; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid 
            th {{ background-color: 
            tr:nth-child(even) {{ background-color: 
        </style>
    </head>
    <body>
        <h1>URL Shortener Load Test Report</h1>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="section">
            <h2>Summary</h2>
            <p>This report summarizes the results of the load test performed on the URL Shortener application.</p>
        </div>
        
        <div class="section">
            <h2>Performance Metrics</h2>
    """
    
    plots_dir = os.path.join('plots')
    plot_files = glob.glob(os.path.join(results_dir, plots_dir, '*.png'))
    
    for plot_file in sorted(plot_files):
        rel_path = os.path.join(plots_dir, os.path.basename(plot_file))
        html_content += f"""
            <div class="plot">
                <h3>{os.path.basename(plot_file).replace('.png', '').replace('_', ' ')}</h3>
                <img src="{rel_path}" alt="{os.path.basename(plot_file)}" style="max-width: 100%;" />
            </div>
        """
    
    html_content += """
        <div class="section">
            <h2>Statistics</h2>
    """
    
    if k6_metrics:
        http_req_metrics = {k: v for k, v in k6_metrics.items() if 'http_req' in k}
        if http_req_metrics:
            html_content += """
            <h3>HTTP Request Metrics</h3>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Min</th>
                    <th>Avg</th>
                    <th>Max</th>
                    <th>p90</th>
                    <th>p95</th>
                </tr>
            """
            
            for metric, df in http_req_metrics.items():
                if len(df) > 0:
                    html_content += f"""
                    <tr>
                        <td>{metric}</td>
                        <td>{df['value'].min():.2f}</td>
                        <td>{df['value'].mean():.2f}</td>
                        <td>{df['value'].max():.2f}</td>
                        <td>{df['value'].quantile(0.9):.2f}</td>
                        <td>{df['value'].quantile(0.95):.2f}</td>
                    </tr>
                    """
            
            html_content += """
            </table>
            """
    
    if pod_metrics is not None:
        pod_groups = pod_metrics.groupby('Name')
        html_content += """
            <h3>Pod Resource Usage</h3>
            <table>
                <tr>
                    <th>Pod</th>
                    <th>Avg CPU</th>
                    <th>Max CPU</th>
                    <th>Avg Memory</th>
                    <th>Max Memory</th>
                </tr>
        """
        
        for name, group in pod_groups:
            html_content += f"""
                <tr>
                    <td>{name}</td>
                    <td>{group['CPU_Value'].mean():.3f} cores</td>
                    <td>{group['CPU_Value'].max():.3f} cores</td>
                    <td>{group['Memory_Value'].mean():.1f} MB</td>
                    <td>{group['Memory_Value'].max():.1f} MB</td>
                </tr>
            """
        
        html_content += """
            </table>
        """
    
    html_content += """
        </div>
        
        <div class="section">
            <h2>Conclusions</h2>
            <p>Based on the load test results, here are the key findings:</p>
            <ul>
                <li>The application's performance under load was tested with gradually increasing traffic.</li>
                <li>Check if the autoscaling performed as expected by examining the HPA metrics.</li>
                <li>Examine the latency metrics to identify potential bottlenecks.</li>
                <li>Look for any error rates or failed requests that may indicate issues under load.</li>
            </ul>
            <p>For detailed analysis, examine the individual metrics and logs in the results directory.</p>
        </div>
    </body>
    </html>
    """
    
    with open(report_file, 'w') as f:
        f.write(html_content)
    
    logger.info(f"Report generated at: {report_file}")
    return report_file

def find_latest_results_dir():
    """Find the most recently created load test results directory"""
    dirs = glob.glob('results/load-test-results-*')
    if not dirs:
        logger.warning("No previous load test results found")
        return None, None
    
    max_dir = max(dirs, key=os.path.getctime)
    metrics_dir = os.path.join(max_dir, 'metrics')
    logger.info(f"Found latest results directory: {max_dir}")
    return max_dir, metrics_dir

def main():
    if len(sys.argv) < 3:
        results_dir, metrics_dir = find_latest_results_dir()
        if not results_dir:
            logger.error("No results directory specified and no results found.")
            logger.info("Usage: python analyze-results.py [results_directory] [metrics_directory]")
            sys.exit(1)
    else:
        results_dir = sys.argv[1]
        metrics_dir = sys.argv[2]
    
    logger.info(f"Analyzing results in: {results_dir}")
    
    try:
        logger.info("Loading k6 results...")
        k6_results = load_k6_results(results_dir)
        k6_data = analyze_k6_results(k6_results)
        
        logger.info("Loading metrics...")
        csv_metrics = load_csv_metrics(results_dir, metrics_dir)
        
        pod_data = analyze_pod_metrics(csv_metrics.get('pod'))
        
        hpa_data = analyze_hpa_metrics(csv_metrics.get('hpa'))
        
        logger.info("Generating plots...")
        plots_dir = os.path.join(results_dir, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        generate_plots(results_dir, k6_data, pod_data, hpa_data)
        
        hpa_plot_files = glob.glob(os.path.join(plots_dir, 'hpa_*.png'))
        if not hpa_plot_files:
            logger.info("No HPA plots found - attempting direct creation from CSV")
            hpa_plots_count = create_hpa_plots_from_csv(metrics_dir, plots_dir)
            if hpa_plots_count > 0:
                logger.info(f"Created {hpa_plots_count} HPA plots directly from CSV")
        
        logger.info("Generating report...")
        report_file = generate_report(results_dir, k6_data, pod_data, hpa_data)
        
        logger.info(f"\nAnalysis complete! Report generated at: {report_file}")
        print(f"\nAnalysis complete! Report generated at: {report_file}")
    
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}\n{traceback.format_exc()}")
        print(f"Error during analysis: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()