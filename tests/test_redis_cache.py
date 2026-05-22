import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from pathlib import Path
from backend.services.data_loader import DataLoader


class TestDataLoaderRedis:
    """测试 DataLoader 的 Redis 缓存功能"""

    @patch('backend.services.data_loader.redis')
    def test_redis_connection_success(self, mock_redis):
        """测试 Redis 连接成功"""
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)

        assert loader.use_cache is True
        assert loader.redis_client is not None
        mock_redis.Redis.assert_called_once()
        mock_redis_client.ping.assert_called_once()

    @patch('backend.services.data_loader.redis')
    def test_redis_connection_failure(self, mock_redis):
        """测试 Redis 连接失败降级"""
        mock_redis.Redis.side_effect = Exception("Connection refused")

        loader = DataLoader(use_cache=True)

        assert loader.use_cache is False
        assert loader.redis_client is None

    def test_redis_import_failure(self):
        """测试 redis 模块不可用时的降级"""
        with patch('backend.services.data_loader.REDIS_AVAILABLE', False):
            loader = DataLoader(use_cache=True)

            assert loader.use_cache is False
            assert loader.redis_client is None

    @patch('backend.services.data_loader.redis')
    def test_cache_hit(self, mock_redis):
        """测试缓存命中"""
        import json
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = json.dumps([{"id": 1, "name": "test"}])
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)
        key = loader._generate_cache_key("test", param="value")

        result = loader._get_from_cache(key)

        assert result == [{"id": 1, "name": "test"}]
        mock_redis_client.get.assert_called_once()

    @patch('backend.services.data_loader.redis')
    def test_cache_miss(self, mock_redis):
        """测试缓存未命中"""
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)
        key = loader._generate_cache_key("test", param="value")

        result = loader._get_from_cache(key)

        assert result is None

    @patch('backend.services.data_loader.redis')
    def test_set_cache(self, mock_redis):
        """测试设置缓存"""
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True, cache_ttl=3600)
        key = "test:key"
        data = [{"id": 1}]

        loader._set_to_cache(key, data)

        mock_redis_client.setex.assert_called_once()
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][0] == key
        assert call_args[0][1] == 3600

    @patch('backend.services.data_loader.redis')
    def test_invalidate_cache(self, mock_redis):
        """测试清除缓存"""
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.keys.return_value = ["key1", "key2"]
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)

        loader.invalidate_all_cache()

        mock_redis_client.keys.assert_called_once_with("*")
        mock_redis_client.delete.assert_called_once_with("key1", "key2")

    def test_generate_cache_key(self):
        """测试缓存键生成"""
        loader = DataLoader(use_cache=False)

        key1 = loader._generate_cache_key("posts", start_date="2024-01-01")
        key2 = loader._generate_cache_key("posts", start_date="2024-01-01")
        key3 = loader._generate_cache_key("posts", start_date="2024-01-02")

        assert key1 == key2
        assert key1 != key3
        assert key1.startswith("posts:")

    @patch('backend.services.data_loader.redis')
    def test_load_posts_with_cache(self, mock_redis):
        """测试 load_posts 使用缓存"""
        import json
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        cached_data = [{"note_id": "123", "content": "test"}]
        mock_redis_client.get.return_value = json.dumps(cached_data)
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)

        with patch.object(loader, '_get_from_cache', return_value=cached_data):
            result = loader.load_posts()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

    @patch('backend.services.data_loader.redis')
    def test_load_comments_with_cache(self, mock_redis):
        """测试 load_comments 使用缓存"""
        import json
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        cached_data = [{"note_id": "456", "content": "comment"}]
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)

        with patch.object(loader, '_get_from_cache', return_value=cached_data):
            result = loader.load_comments()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

    @patch('backend.services.data_loader.redis')
    def test_load_bertopic_with_cache(self, mock_redis):
        """测试 load_bertopic_results 使用缓存"""
        import json
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        cached_data = [{"Topic": 1, "Count": 10}]
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)

        with patch.object(loader, '_get_from_cache', return_value=cached_data):
            result = loader.load_bertopic_results()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

    @patch('backend.services.data_loader.redis')
    def test_load_user_stats_with_cache(self, mock_redis):
        """测试 load_user_stats 使用缓存"""
        import json
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        cached_data = [{"user_id": "123", "nickname": "test"}]
        mock_redis.Redis.return_value = mock_redis_client

        loader = DataLoader(use_cache=True)

        with patch.object(loader, '_get_from_cache', return_value=cached_data):
            result = loader.load_user_stats()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
