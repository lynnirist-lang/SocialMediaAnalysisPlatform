"""
Redis 缓存配置
"""

REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None,
    'decode_responses': True,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
}

CACHE_TTL = {
    'posts': 3600,
    'comments': 3600,
    'user_stats': 7200,
    'sentiment': 86400,
    'bertopic': 86400,
    'dashboard_summary': 300,
}
