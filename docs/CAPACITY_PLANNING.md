# Capacity Planning Guide

This document provides guidance for capacity planning and scaling the Check Review Console for bank pilot and production deployments.

## Table of Contents
- [Current Resource Requirements](#current-resource-requirements)
- [Scaling Guidelines](#scaling-guidelines)
- [Growth Projections](#growth-projections)
- [Performance Benchmarks](#performance-benchmarks)
- [Monitoring and Alerts](#monitoring-and-alerts)
- [Scaling Procedures](#scaling-procedures)

---

## Current Resource Requirements

### Minimum Requirements (Development/Demo)

| Component | CPU | Memory | Storage | Notes |
|-----------|-----|--------|---------|-------|
| Backend API | 0.5 cores | 512 MB | - | Single instance |
| PostgreSQL | 0.5 cores | 512 MB | 10 GB | Basic config |
| Redis | 0.25 cores | 256 MB | 1 GB | Cache only |
| Frontend | 0.25 cores | 256 MB | - | Static assets |
| **Total** | **1.5 cores** | **1.5 GB** | **11 GB** | |

### Recommended Requirements (Bank Pilot)

| Component | CPU | Memory | Storage | Instances | Notes |
|-----------|-----|--------|---------|-----------|-------|
| Backend API | 2 cores | 2 GB | - | 2 | Load balanced |
| PostgreSQL | 4 cores | 8 GB | 100 GB | 1 primary | SSD required |
| Redis | 1 core | 2 GB | 10 GB | 1 | Persistence enabled |
| Nginx | 0.5 cores | 512 MB | - | 2 | Load balancer |
| Prometheus | 1 core | 2 GB | 50 GB | 1 | 15-day retention |
| Grafana | 0.5 cores | 512 MB | 5 GB | 1 | Dashboard storage |
| **Total** | **11.5 cores** | **17 GB** | **165 GB** | | |

### Production Requirements (Full Deployment)

| Component | CPU | Memory | Storage | Instances | Notes |
|-----------|-----|--------|---------|-----------|-------|
| Backend API | 4 cores | 4 GB | - | 4+ | Auto-scaling |
| PostgreSQL Primary | 8 cores | 32 GB | 500 GB | 1 | NVMe SSD |
| PostgreSQL Replica | 8 cores | 32 GB | 500 GB | 2 | Read replicas |
| Redis Primary | 2 cores | 8 GB | 50 GB | 1 | HA config |
| Redis Replica | 2 cores | 8 GB | 50 GB | 1 | Failover |
| Nginx | 2 cores | 2 GB | - | 2 | Active-passive |
| Prometheus | 2 cores | 8 GB | 200 GB | 1 | 30-day retention |
| **Total** | **46 cores** | **136 GB** | **1.8 TB** | | |

---

## Scaling Guidelines

### Horizontal Scaling (Backend API)

The backend API is stateless and can be horizontally scaled.

**When to scale:**
- CPU utilization > 70% sustained for 5+ minutes
- Request latency P95 > 500ms
- Request queue depth increasing

**Scaling formula:**
```
Required instances = ceil(Peak RPS / 100)

Example:
- Peak 500 requests/second
- Required: ceil(500/100) = 5 instances
```

**Kubernetes HPA Configuration:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: check-review-backend
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: check-review-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Vertical Scaling (Database)

PostgreSQL typically scales vertically for write-heavy workloads.

**When to scale:**
- Connection pool saturation (> 80% utilized)
- Query latency increasing
- Lock contention detected
- Storage approaching capacity

**Sizing formula:**
```
Memory = max(shared_buffers, active_connections * work_mem)

shared_buffers = 25% of system RAM (max 8GB typical)
work_mem = 4MB per connection (adjust based on queries)
maintenance_work_mem = 512MB - 2GB

Example for 100 connections:
- Minimum RAM: max(8GB, 100 * 4MB) = 8GB
- Recommended: 16-32GB for headroom
```

### Redis Scaling

**Memory calculation:**
```
Redis Memory = (Session Size * Active Sessions) + (Cache Size * Cache Entries)

Example:
- 1000 active sessions * 2KB = 2MB
- 10000 cache entries * 1KB = 10MB
- Total: ~15MB (add 50% buffer = 25MB minimum)
```

---

## Growth Projections

### Data Growth Model

| Metric | Daily Growth | Monthly Growth | Annual Growth |
|--------|-------------|----------------|---------------|
| Check Items | 1,000 | 30,000 | 360,000 |
| Decisions | 900 | 27,000 | 324,000 |
| Audit Logs | 5,000 | 150,000 | 1,800,000 |
| Item Views | 3,000 | 90,000 | 1,080,000 |

### Storage Growth Projection

| Data Type | Size per Record | Annual Volume | Annual Storage |
|-----------|-----------------|---------------|----------------|
| Check Items | 2 KB | 360,000 | 720 MB |
| Decisions | 1 KB | 324,000 | 324 MB |
| Audit Logs | 500 bytes | 1,800,000 | 900 MB |
| Images (refs) | 100 bytes | 720,000 | 72 MB |
| **Total** | | | **~2 GB/year** |

**With 7-year audit retention:**
```
Total Storage = 2 GB/year * 7 years + indices (30%) + overhead (20%)
             = 14 GB * 1.5 = 21 GB minimum for audit data
```

### Concurrent User Scaling

| Users | Backend Instances | Database Connections | Redis Memory |
|-------|-------------------|---------------------|--------------|
| 10 | 1 | 20 | 256 MB |
| 50 | 2 | 50 | 512 MB |
| 100 | 2-3 | 100 | 1 GB |
| 500 | 4-6 | 200 | 2 GB |
| 1000 | 8-10 | 400 | 4 GB |

---

## Performance Benchmarks

### API Response Time Targets

| Endpoint Category | P50 | P95 | P99 | Max |
|-------------------|-----|-----|-----|-----|
| Authentication | 50ms | 150ms | 300ms | 1s |
| Check List | 100ms | 250ms | 500ms | 2s |
| Check Detail | 50ms | 150ms | 300ms | 1s |
| Make Decision | 100ms | 300ms | 500ms | 2s |
| Audit Log | 150ms | 400ms | 800ms | 3s |
| Reports | 200ms | 500ms | 1000ms | 5s |

### Throughput Targets

| Scenario | Target RPS | Sustained Duration |
|----------|------------|-------------------|
| Normal Operation | 100 | Continuous |
| Peak Period | 300 | 1 hour |
| Batch Processing | 500 | 30 minutes |
| Stress Test | 1000 | 5 minutes |

### Database Query Benchmarks

| Query Type | Target | Index Required |
|------------|--------|----------------|
| Check by ID | < 5ms | Primary key |
| Check list (page) | < 50ms | status, tenant_id |
| Audit by resource | < 20ms | resource_type, resource_id |
| Decision by user | < 30ms | user_id, created_at |

---

## Monitoring and Alerts

### Capacity Alerts

```yaml
# Prometheus alert rules for capacity planning
groups:
  - name: capacity
    rules:
      - alert: HighCPUUsage
        expr: avg(rate(process_cpu_seconds_total[5m])) > 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage above 70% for 10 minutes"

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024 / 1024 > 3500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage above 3.5GB"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connections"
          description: "More than 80 database connections"

      - alert: DiskSpaceLow
        expr: (pg_database_size_bytes / 1024 / 1024 / 1024) > 80
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Database storage high"
          description: "Database size exceeds 80GB"

      - alert: RequestLatencyHigh
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High request latency"
          description: "P95 latency above 500ms"
```

### Grafana Dashboard Queries

```promql
# CPU usage trend
rate(process_cpu_seconds_total[1h])

# Memory growth rate
delta(process_resident_memory_bytes[24h])

# Request rate trend
rate(http_requests_total[1h])

# Database size growth
delta(pg_database_size_bytes[7d])

# Connection pool utilization
pg_stat_activity_count / 100  # Assuming 100 max connections
```

---

## Scaling Procedures

### Adding Backend Instances

```bash
# Docker Compose
docker-compose up -d --scale backend=3

# Kubernetes
kubectl scale deployment check-review-backend --replicas=3 -n check-review

# Verify scaling
kubectl get pods -n check-review -l app=check-review-backend
```

### Database Vertical Scaling

```bash
# 1. Schedule maintenance window
# 2. Create backup
pg_dump -U postgres check_review > backup_$(date +%Y%m%d).sql

# 3. Stop application
docker-compose stop backend

# 4. Update PostgreSQL resources (docker-compose.yml)
# resources:
#   limits:
#     cpus: '4'
#     memory: 16G

# 5. Restart database
docker-compose up -d db

# 6. Verify and tune
docker exec check_review_db psql -U postgres -c "SHOW shared_buffers;"

# 7. Restart application
docker-compose up -d backend
```

### Adding Read Replicas

```bash
# 1. Configure primary for replication
# postgresql.conf:
# wal_level = replica
# max_wal_senders = 3

# 2. Create replication user
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'secret';

# 3. Add replica to pg_hba.conf
# host replication replicator replica_ip/32 md5

# 4. Create replica
pg_basebackup -h primary_host -U replicator -D /var/lib/postgresql/data -P

# 5. Configure replica
# recovery.conf:
# standby_mode = on
# primary_conninfo = 'host=primary_host user=replicator password=secret'

# 6. Start replica
docker-compose up -d db-replica

# 7. Verify replication
SELECT * FROM pg_stat_replication;
```

---

## Capacity Planning Checklist

### Monthly Review

- [ ] Review current resource utilization
- [ ] Check storage growth trends
- [ ] Analyze query performance
- [ ] Review error rates and latency
- [ ] Update growth projections

### Quarterly Review

- [ ] Load testing against projections
- [ ] Review scaling thresholds
- [ ] Update capacity requirements
- [ ] Budget planning for growth
- [ ] DR capacity verification

### Pre-Scale Checklist

- [ ] Verify backup is current
- [ ] Test scaling procedure in staging
- [ ] Notify stakeholders
- [ ] Schedule maintenance window
- [ ] Prepare rollback plan

---

## Cost Estimation

### Cloud Infrastructure (AWS Example)

| Component | Instance Type | Monthly Cost |
|-----------|--------------|--------------|
| Backend (x2) | t3.medium | $60 |
| PostgreSQL | db.r5.large | $180 |
| Redis | cache.t3.medium | $50 |
| ALB | - | $25 |
| Storage (200GB) | gp3 | $20 |
| **Total** | | **~$335/month** |

### Scaling Cost Impact

| Scale Factor | Additional Cost | Notes |
|--------------|-----------------|-------|
| +1 Backend | +$30/month | Linear scaling |
| +100GB Storage | +$10/month | Linear scaling |
| 2x Database | +$180/month | Next instance size |

---

*Last Updated: 2024-01-15*
*Document Version: 1.0*
