# Runbook: High CPU Usage

## Severity: Medium

## Symptoms
- CPU usage consistently above 80% of limits
- Increased request latency (p95/p99)
- CPU throttling detected in metrics
- Prometheus alert: `HighCPUUsage`

## Diagnosis Steps

1. **Check CPU metrics**:
   ```promql
   rate(container_cpu_usage_seconds_total{namespace="default"}[5m])
   ```

2. **Identify hottest pods**: Sort by CPU and compare to limits

3. **Check if single pod or all replicas**: If all — likely traffic spike or code regression

4. **Look for correlated events**:
   - Recent deployments (code regression?)
   - Traffic spikes (scale up needed?)
   - Cron jobs or batch operations

## Remediation

1. **Scale horizontally**: Add more replicas to distribute load
2. **Check for CPU-intensive operations** in application logs
3. **Increase CPU limits** if consistently hitting the cap
4. **Optimize code** if a recent deployment caused the spike
