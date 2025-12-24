import logging
import os
import redis
import time


class RedisHandler(logging.Handler):
    def __init__(self, host="redis", port=6379, password="", key="django-logs"):
        logging.Handler.__init__(self)
        self.client = redis.StrictRedis(
            host=host, port=port, password=password, 
            socket_connect_timeout=1, socket_timeout=1
        )
        self.key = key
        self.circuit_breaker = {
            'failures': 0,
            'last_failure': 0,
            'threshold': 5,
            'timeout': 30
        }

    def emit(self, record):
        # Circuit breaker check
        if self._is_circuit_open():
            return
            
        try:
            self.client.rpush(self.key, self.format(record))
            self._reset_circuit()
        except redis.exceptions.BusyLoadingError:
            # Redis is loading, silently skip
            pass
        except (redis.RedisError, ConnectionError, TimeoutError):
            self._record_failure()

    def _is_circuit_open(self):
        if self.circuit_breaker['failures'] >= self.circuit_breaker['threshold']:
            if time.time() - self.circuit_breaker['last_failure'] < self.circuit_breaker['timeout']:
                return True
            # Reset after timeout
            self.circuit_breaker['failures'] = 0
        return False

    def _record_failure(self):
        self.circuit_breaker['failures'] += 1
        self.circuit_breaker['last_failure'] = time.time()

    def _reset_circuit(self):
        self.circuit_breaker['failures'] = 0
