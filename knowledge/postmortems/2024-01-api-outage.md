# Postmortem: API Gateway Outage — January 2024

## Incident: INC-20240115-APIGW

**Duration**: 2024-01-15 14:30 UTC — 2024-01-15 16:45 UTC (2h 15m)  
**Severity**: Critical  
**Impact**: All API traffic was affected, ~15,000 requests failed

## Summary

The API Gateway ran out of memory (OOMKilled) during a traffic spike caused by a marketing email campaign. The deployment had a memory limit of 256Mi which was insufficient for the increased connection count.

## Root Cause

- Marketing sent a campaign email to 50,000 users at 14:30 UTC
- Traffic spike of 3x normal peak within 5 minutes
- API Gateway connection pool grew beyond its memory limit
- Kubernetes OOMKilled the pod (exit code 137)
- New pod started but was immediately overwhelmed → CrashLoopBackOff

## Timeline

| Time (UTC) | Event |
|-----------|-------|
| 14:30 | Marketing email sent to 50k users |
| 14:35 | Traffic spike detected (3x normal) |
| 14:38 | API Gateway pod OOMKilled |
| 14:39 | CrashLoopBackOff begins |
| 14:45 | PagerDuty alert fires |
| 15:00 | SRE team investigates |
| 15:15 | Root cause identified: memory limit too low |
| 15:20 | Memory limit increased to 512Mi, deployment scaled to 3 replicas |
| 16:00 | Service fully recovered |
| 16:45 | Traffic returned to normal |

## Lessons Learned

1. **Memory limits** should account for 3x peak traffic
2. **HPA (Horizontal Pod Autoscaler)** should be configured for the API gateway
3. **Marketing campaigns** should trigger a pre-scaling procedure
4. **Load testing** should simulate traffic spikes before production

## Action Items

- [x] Increase API Gateway memory limit to 512Mi
- [x] Add HPA with CPU/memory-based scaling
- [x] Create runbook for marketing campaign pre-scaling
- [ ] Implement load testing pipeline in CI/CD
