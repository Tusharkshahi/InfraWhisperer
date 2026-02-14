# Runbook: Disk Pressure / Node Storage Full

## Severity: High

## Symptoms
- Node condition shows `DiskPressure: True`
- Pods being evicted from the node
- Container image pull failures (`no space left on device`)
- PersistentVolumeClaim stuck in Pending

## Diagnosis Steps

1. **Check node conditions**: `kubectl describe node <node-name>`
2. **Check disk usage** on the node
3. **Identify large consumers**:
   - Container logs (especially for verbose/debug logging)
   - Unused container images
   - Old ReplicaSets / completed Jobs

## Remediation

1. **Clean up unused images**: `docker system prune` or `crictl rmi --prune`
2. **Rotate and compress old logs**: Configure log rotation in container runtime
3. **Delete completed Jobs and old ReplicaSets**
4. **Expand PersistentVolume** if applicable
5. **Add additional nodes** to the cluster to distribute storage load
