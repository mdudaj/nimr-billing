# NIMR Billing System - Monitoring Guide

## Health Check Endpoint

### Endpoint: `/health/`

**Response Format:**
```json
{
  "status": "healthy|degraded|unhealthy",
  "checks": {
    "redis": {
      "status": "healthy|loading|unhealthy",
      "message": "Connection status"
    },
    "database": {
      "status": "healthy|unhealthy", 
      "message": "Connection status"
    },
    "memory": {
      "status": "healthy|warning|unknown",
      "usage_percent": 45.2,
      "available_gb": 12.5
    }
  }
}
```

### Status Meanings
- **healthy**: All systems operational
- **degraded**: Some systems have warnings (Redis loading, high memory)
- **unhealthy**: Critical systems failing

## Key Metrics to Monitor

### 1. Application Health
```bash
# Check every 30 seconds
curl -s http://localhost/health/ | jq '.status'
```

### 2. Redis Metrics
```bash
# Memory usage
docker-compose exec redis redis-cli info memory | grep used_memory_human

# Key count
docker-compose exec redis redis-cli dbsize

# Connection count
docker-compose exec redis redis-cli info clients | grep connected_clients
```

### 3. Database Metrics
```bash
# Active connections
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Database size
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));"

# Slow queries (>5 seconds)
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds';"
```

### 4. System Resources
```bash
# Container memory usage
docker stats --no-stream

# Disk usage
df -h

# Log file sizes
du -sh logs/
```

## Alerting Thresholds

### Critical Alerts (Immediate Action Required)
- Health endpoint returns "unhealthy"
- Redis memory usage > 90%
- Database connections > 80% of max
- Disk usage > 85%
- Application container restart loops

### Warning Alerts (Monitor Closely)
- Health endpoint returns "degraded" 
- Redis memory usage > 70%
- Database connections > 60% of max
- High error rate in logs
- Response time > 5 seconds

## Log Analysis

### Error Log Patterns
```bash
# Check for Redis connection errors
grep -i "redis.*error" logs/django_errors.log

# Check for database errors
grep -i "database.*error" logs/django_errors.log

# Check for payment gateway issues
grep -i "paymentgatewaylog" logs/django_errors.log
```

### Performance Issues
```bash
# Slow database queries
grep "duration.*ms" logs/django_errors.log | grep -E "[0-9]{4,}"

# Memory warnings
grep -i "memory" logs/django_errors.log

# Connection timeouts
grep -i "timeout" logs/django_errors.log
```

## Automated Monitoring Setup

### Using curl and cron
```bash
# Add to crontab (crontab -e)
*/1 * * * * curl -s http://localhost/health/ | jq -r '.status' | grep -v healthy && echo "ALERT: System unhealthy" | mail -s "NIMR Billing Alert" admin@example.com
```

### Using systemd timer
Create `/etc/systemd/system/nimr-health-check.service`:
```ini
[Unit]
Description=NIMR Billing Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -s http://localhost/health/
User=monitoring
```

Create `/etc/systemd/system/nimr-health-check.timer`:
```ini
[Unit]
Description=Run NIMR health check every minute
Requires=nimr-health-check.service

[Timer]
OnCalendar=*:*:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Maintenance Tasks

### Daily
- Check health endpoint status
- Review error logs for new issues
- Monitor Redis memory usage

### Weekly  
- Run system cleanup: `python manage.py cleanup_system`
- Check database performance metrics
- Review log file sizes and rotate if needed

### Monthly
- Analyze performance trends
- Review and update alerting thresholds
- Check for security updates

## Troubleshooting Common Issues

### High Redis Memory Usage
```bash
# Check key distribution
docker-compose exec redis redis-cli --bigkeys

# Check expiration policies
docker-compose exec redis redis-cli config get maxmemory-policy

# Manual cleanup (if safe)
docker-compose exec redis redis-cli flushall
```

### Database Performance Issues
```bash
# Check for missing indexes
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT schemaname, tablename, attname, n_distinct, correlation FROM pg_stats WHERE schemaname = 'public' ORDER BY n_distinct DESC;"

# Analyze query performance
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

### Application Errors
```bash
# Check recent errors
tail -100 logs/django_errors.log

# Check for memory leaks
docker stats ws_app --no-stream

# Restart application if needed
docker-compose restart ws-app
```
