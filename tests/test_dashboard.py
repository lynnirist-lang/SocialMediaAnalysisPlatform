import pytest


class TestDashboardAPI:
    """数据看板接口测试"""

    def test_get_summary(self, client):
        """测试获取数据概览"""
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "total_posts" in data["data"]
        assert "total_users" in data["data"]
        assert "avg_sentiment" in data["data"]

        # 验证数据类型
        assert isinstance(data["data"]["total_posts"], int)
        assert isinstance(data["data"]["total_users"], int)
        assert isinstance(data["data"]["avg_sentiment"], float)

    def test_get_summary_with_date_filter(self, client, valid_date_range):
        """测试带日期过滤的数据概览"""
        response = client.get(
            "/api/dashboard/summary",
            params=valid_date_range
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_trend(self, client):
        """测试获取趋势数据"""
        response = client.get("/api/dashboard/trend")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "dates" in data["data"]
        assert "post_counts" in data["data"]
        assert "user_counts" in data["data"]

        # 验证数组长度一致
        if data["data"]["dates"]:
            assert len(data["data"]["dates"]) == len(data["data"]["post_counts"])
            assert len(data["data"]["dates"]) == len(data["data"]["user_counts"])

    def test_get_wordcloud(self, client):
        """测试获取词云数据"""
        response = client.get("/api/dashboard/wordcloud")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert isinstance(data["data"], list)

        # 如果有数据，验证数据结构
        if data["data"]:
            first_item = data["data"][0]
            assert "name" in first_item
            assert "value" in first_item
