# Postmortem: Database Failover Incident — February 2024

## Incident: INC-20240208-DBFAIL

**Duration**: 2024-02-08 09:15 UTC — 2024-02-08 11:30 UTC (2h 15m)  
**Severity**: Critical  
**Impact**: All order processing halted, ~3,200 orders stuck in 'pending'

## Summary

The primary PostgreSQL instance ran out of disk space due to a runaway query log that wasn't being rotated. The automatic failover to the replica triggered but the replica was 45 minutes behind due to replication lag.

## Root Cause

- PostgreSQL query log was configured to log all queries (for debugging)
- Log file grew to 45GB over 2 weeks, filling the disk
- Primary database crashed with "no space left on device"
- Automatic failover promoted the replica
- Replica had 45-minute replication lag → data loss for recent transactions

## Lessons Learned

1. **Query logging** should never be set to `log_statement = 'all'` in production
2. **Disk monitoring** alerts should fire at 80% usage (was set to 95%)
3. **Replication lag** monitoring is critical
4. **Log rotation** must be configured and tested

## Action Items

- [x] Set `log_statement = 'ddl'` (only log schema changes)
- [x] Configure pgBadger for query analysis instead of raw logging
- [x] Add disk usage alert at 80% threshold
- [x] Add replication lag alert at > 5 minutes
- [x] Configure log rotation (max 1GB, 7 day retention)
- [ ] Test failover procedure quarterly
