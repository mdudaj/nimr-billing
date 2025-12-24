import redis
from django.db import connection
from django.http import JsonResponse
from django.conf import settings


def health_check(request):
    """System health check endpoint."""
    checks = {}
    
    # Redis health check
    try:
        r = redis.StrictRedis(host='redis', port=6379, socket_timeout=2)
        r.ping()
        checks['redis'] = {'status': 'healthy', 'message': 'Connected'}
    except redis.exceptions.BusyLoadingError:
        checks['redis'] = {'status': 'loading', 'message': 'Redis loading dataset'}
    except Exception as e:
        checks['redis'] = {'status': 'unhealthy', 'message': str(e)}
    
    # Database health check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = {'status': 'healthy', 'message': 'Connected'}
    except Exception as e:
        checks['database'] = {'status': 'unhealthy', 'message': str(e)}
    
    # Overall status
    overall_status = 'healthy'
    if any(check.get('status') == 'unhealthy' for check in checks.values()):
        overall_status = 'unhealthy'
    elif any(check.get('status') in ['loading', 'warning'] for check in checks.values()):
        overall_status = 'degraded'
    
    return JsonResponse({
        'status': overall_status,
        'checks': checks
    })
