# NIMR Billing System - Deployment Guide

## Quick Deployment

### 1. Apply Database Migrations
```bash
python manage.py migrate
```

### 2. Restart Services
```bash
docker-compose down
docker-compose up -d
```

### 3. Verify Health
```bash
curl http://localhost/health/
```

## Detailed Steps

### Prerequisites
- Docker and Docker Compose installed
- Environment variables configured in `.env` file

### Environment Setup
Ensure these variables are set in your `.env` file:
```env
DB_USERNAME=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

### Step-by-Step Deployment

1. **Stop existing services**
   ```bash
   docker-compose down
   ```

2. **Build new images**
   ```bash
   docker-compose build
   ```

3. **Start database first**
   ```bash
   docker-compose up -d db redis
   ```

4. **Wait for database to be ready**
   ```bash
   docker-compose logs -f db
   # Wait for "database system is ready to accept connections"
   ```

5. **Run migrations**
   ```bash
   docker-compose run --rm ws-app python manage.py migrate
   ```

6. **Start all services**
   ```bash
   docker-compose up -d
   ```

7. **Verify deployment**
   ```bash
   # Check service status
   docker-compose ps
   
   # Check health endpoint
   curl http://localhost/health/
   
   # Check logs
   docker-compose logs -f ws-app
   ```

### Rollback Plan

If issues occur, rollback using:
```bash
# Stop new services
docker-compose down

# Restore from backup (if needed)
# docker-compose run --rm db pg_restore ...

# Start with previous configuration
git checkout HEAD~1
docker-compose up -d
```

## Monitoring After Deployment

### Health Checks
- Monitor `/health/` endpoint every 30 seconds
- Set up alerts for unhealthy status

### Log Monitoring
```bash
# Monitor application logs
docker-compose logs -f ws-app

# Monitor Redis logs
docker-compose logs -f redis

# Check error logs
tail -f logs/django_errors.log
```

### Performance Monitoring
```bash
# Check Redis memory usage
docker-compose exec redis redis-cli info memory

# Check database connections
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT count(*) FROM pg_stat_activity;"
```

## Troubleshooting

### Redis Issues
```bash
# Check Redis status
docker-compose exec redis redis-cli ping

# Check Redis memory
docker-compose exec redis redis-cli info memory

# Clear Redis if needed (CAUTION: This will clear all cached data)
docker-compose exec redis redis-cli flushall
```

### Database Issues
```bash
# Check database connectivity
docker-compose exec db pg_isready

# Check for long-running queries
docker-compose exec db psql -U $DB_USERNAME -d $DB_NAME -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
```

### Application Issues
```bash
# Check application logs
docker-compose logs --tail=100 ws-app

# Run system cleanup
docker-compose exec ws-app python manage.py cleanup_system

# Check health status
curl -v http://localhost/health/
```
