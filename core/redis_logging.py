import logging
import os
import redis


class RedisHandler(logging.Handler):
    def __init__(self, host="redis", port=6379, password="", key="django-logs"):
        logging.Handler.__init__(self)
        self.client = redis.StrictRedis(host=host, port=port, password=password)
        self.key = key

    def emit(self, record):
        try:
            self.client.rpush(self.key, self.format(record))
        except redis.RedisError:
            self.handleError(record)
