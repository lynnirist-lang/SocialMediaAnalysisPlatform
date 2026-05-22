import pytest


class TestTopicAPI:
    """主题分析接口测试"""

    def test_get_keywords_default(self, client):
        """测试获取关键词（默认20个）"""
        response = client.get("/api/topic/keywords")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert isinstance(data["data"], list)
        assert len(data["data"]) <= 20

    def test_get_keywords_custom_count(self, client):
        """测试获取指定数量的关键词"""
        top_n = 10
        response = client.get(f"/api/topic/keywords?top_n={top_n}")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]) <= top_n

    def test_keyword_structure(self, client):
        """测试关键词数据结构"""
        response = client.get("/api/topic/keywords?top_n=1")
        data = response.json()

        if data["data"]:
            keyword = data["data"][0]
            assert "word" in keyword
            assert "count" in keyword
            assert "topic" in keyword

    def test_get_clusters(self, client):
        """测试获取聚类数据"""
        response = client.get("/api/topic/clusters")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "nodes" in data["data"]
        assert "links" in data["data"]
        assert "categories" in data["data"]

    def test_clusters_structure(self, client):
        """测试聚类数据结构"""
        response = client.get("/api/topic/clusters")
        data = response.json()

        # 验证节点结构
        if data["data"]["nodes"]:
            node = data["data"]["nodes"][0]
            assert "name" in node
            assert "value" in node
            assert "symbolSize" in node
            assert "category" in node
            assert "draggable" in node

    def test_get_topic_details_valid(self, client):
        """测试获取话题详情（有效ID）"""
        # 先获取一个有效的话题ID
        clusters_response = client.get("/api/topic/clusters")
        clusters_data = clusters_response.json()

        if clusters_data["data"]["nodes"]:
            # 这里假设可以通过节点名称反查，实际可能需要调整
            # 暂时跳过详细测试
            pass

    def test_get_topic_details_invalid(self, client):
        """测试获取话题详情（无效ID）"""
        response = client.get("/api/topic/details/999999")
        # 可能返回404或空数据
        assert response.status_code in [200, 404]

    def test_get_bar_chart(self, client):
        """测试获取柱状图数据"""
        response = client.get("/api/topic/bar")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "topics" in data["data"]
        assert "categories" in data["data"]
        assert "positive" in data["data"]
        assert "neutral" in data["data"]
        assert "negative" in data["data"]
