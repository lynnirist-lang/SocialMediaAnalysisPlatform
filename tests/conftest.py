import pytest
import sys
import os
from pathlib import Path

project_file = Path(__file__).parent.parent
sys.path.insert(0, str(project_file))

from fastapi.testclient import TestClient
from backend.api.main import app


@pytest.fixture(scope="session")
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture(scope="session")
def base_url():
    """基础URL配置"""
    return "http://localhost:8000"


# 待更正
@pytest.fixture
def valid_date_range():
    """有效的日期范围"""
    return {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }


@pytest.fixture
def pagination_params():
    """分页参数"""
    return {
        "page": 1,
        "page_size": 10
    }


@pytest.fixture
def report_test_data():
    """报告导出测试数据"""
    return {
        "date_range": [],
        "search_keyword": ""
    }


@pytest.fixture
def report_client():
    """报告导出专用客户端（使用真实HTTP请求）"""
    import requests
    return requests


@pytest.fixture
def mock_redis_data():
    """Redis 缓存模拟数据"""
    return {
        "posts": [{"note_id": "123", "content": "test post"}],
        "comments": [{"note_id": "456", "content": "test comment"}],
        "user_stats": [{"user_id": "789", "nickname": "test_user"}],
        "bertopic": [{"Topic": 1, "Count": 10}]
    }