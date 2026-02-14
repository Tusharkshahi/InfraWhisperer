# Runbook: Database Slow Queries

## Severity: Medium

## Symptoms
- Increased p95/p99 response latency across services
- `pg_stat_activity` shows long-running queries
- Connection pool exhaustion warnings
- Application timeout errors

## Diagnosis Steps

1. **List active slow queries**:
   ```sql
   SELECT pid, now() - query_start AS duration, state, query 
   FROM pg_stat_activity 
   WHERE state != 'idle' 
     AND now() - query_start > interval '5 seconds'
   ORDER BY duration DESC;
   ```

2. **Run EXPLAIN ANALYZE** on the offending query to see the execution plan

3. **Check for missing indexes**:
   ```sql
   SELECT schemaname, relname, seq_scan, idx_scan 
   FROM pg_stat_user_tables 
   WHERE seq_scan > 1000 AND idx_scan < 100
   ORDER BY seq_scan DESC;
   ```

4. **Check connection count**: Are we running out of connections?

## Remediation

1. **Add indexes** for columns used in WHERE and JOIN clauses
2. **Optimize queries** to avoid sequential scans on large tables
3. **Consider read replicas** for heavy read workloads
4. **Tune connection pool** settings (max connections, idle timeout)
5. **Kill stuck queries** if necessary: `SELECT pg_terminate_backend(<pid>)`
