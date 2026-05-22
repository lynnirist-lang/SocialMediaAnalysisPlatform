import pytest


class TestSentimentAPI:
    """情感分析接口测试"""

    def test_get_distribution(self, client):
        """测试获取情感分布"""
        response = client.get("/api/sentiment/distribution")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "positive" in data["data"]
        assert "neutral" in data["data"]
        assert "negative" in data["data"]

        # 验证数据类型
        assert isinstance(data["data"]["positive"], int)
        assert isinstance(data["data"]["neutral"], int)
        assert isinstance(data["data"]["negative"], int)

    def test_get_trend(self, client):
        """测试获取情感趋势"""
        response = client.get("/api/sentiment/trend")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "dates" in data["data"]
        assert "scores" in data["data"]

        # 验证数组长度一致
        if data["data"]["dates"]:
            assert len(data["data"]["dates"]) == len(data["data"]["scores"])

    def test_get_heatmap(self, client):
        """测试获取情感热力图"""
        response = client.get("/api/sentiment/heatmap")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert isinstance(data["data"], list)

        # 如果有数据，验证格式 [hour, weekday, value]
        if data["data"]:
            first_item = data["data"][0]
            assert len(first_item) == 3
            assert 0 <= first_item[0] <= 23  # hour
            assert 0 <= first_item[1] <= 6  # weekday

    def test_get_posts_default(self, client):
        """测试获取情感博文（默认10条）"""
        response = client.get("/api/sentiment/posts")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "posts" in data["data"]
        assert len(data["data"]["posts"]) <= 10

    def test_get_posts_custom_size(self, client):
        """测试获取指定数量的情感博文"""
        page_size = 5
        response = client.get(f"/api/sentiment/posts?page_size={page_size}")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]["posts"]) <= page_size

    def test_post_structure(self, client):
        """测试博文数据结构"""
        response = client.get("/api/sentiment/posts?page_size=1")
        data = response.json()

        if data["data"]["posts"]:
            post = data["data"]["posts"][0]
            assert "create_time" in post
            assert "content" in post
            assert "sentiment" in post
            assert "sentiment_score" in post
            assert "note_id" in post
