# Runbook: Pod CrashLoopBackOff

## Severity: High

## Symptoms
- Pod status shows `CrashLoopBackOff`
- Pod restart count is rapidly increasing
- Container exits with non-zero exit code

## Diagnosis Steps

1. **Check pod logs** for the current and previous container:
   ```
   kubectl logs <pod-name> --previous
   ```

2. **Describe the pod** to see events and conditions:
   ```
   kubectl describe pod <pod-name>
   ```

3. **Identify the exit code**:
   - **Exit code 1**: Application error (config, code bug, missing dependency)
   - **Exit code 137**: OOMKilled (memory limit exceeded)
   - **Exit code 139**: Segmentation fault
   - **Exit code 143**: SIGTERM (graceful shutdown timeout)

4. **Check dependencies**: Is the pod failing because a downstream service is unavailable?

## Common Root Causes

| Root Cause | Indicators | Fix |
|-----------|------------|-----|
| Missing secrets | "permission denied" or "secret not found" in logs | Fix Vault/secrets config |
| Wrong config | Application config errors | Fix ConfigMap/env vars |
| OOMKill | Exit code 137, high memory usage | Increase memory limits |
| Dependency down | Connection refused/timeout to downstream | Fix downstream service |
| Bad image | Image pull errors, missing entrypoint | Fix Dockerfile or image tag |

## Remediation

1. For **missing secrets**: Verify Vault permissions and secret paths
2. For **OOMKill**: Increase memory limits in deployment spec
3. For **dependency issues**: Fix the downstream service first
4. For **code bugs**: Check recent deployments, rollback if needed
5. **Last resort**: Rollback to the previous known-good version

## Related Runbooks
- Service Returning 5xx Errors
- Database Slow Queries (if DB is the failing dependency)
