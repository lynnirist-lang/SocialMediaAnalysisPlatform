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


class TestTopicEvolutionAPI:
    """主题演化接口测试"""

    def test_evolution_default_params(self, client):
        """测试获取主题演化（默认参数）"""
        response = client.get("/api/topic/evolution")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "series" in data["data"]
        assert "legend" in data["data"]

    def test_evolution_week_interval(self, client):
        """测试按周粒度获取主题演化"""
        response = client.get("/api/topic/evolution?interval=week&top_n=6")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "series" in data["data"]
        assert "legend" in data["data"]
        assert isinstance(data["data"]["series"], list)
        assert isinstance(data["data"]["legend"], list)

    def test_evolution_day_interval(self, client):
        """测试按天粒度获取主题演化"""
        response = client.get("/api/topic/evolution?interval=day&top_n=6")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "series" in data["data"]
        assert "legend" in data["data"]

    def test_evolution_month_interval(self, client):
        """测试按月粒度获取主题演化"""
        response = client.get("/api/topic/evolution?interval=month&top_n=6")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "series" in data["data"]
        assert "legend" in data["data"]

    def test_evolution_custom_top_n(self, client):
        """测试自定义 top_n 参数"""
        top_n = 3
        response = client.get(f"/api/topic/evolution?interval=week&top_n={top_n}")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]["legend"]) <= top_n

    def test_evolution_series_structure(self, client):
        """测试演化数据中 series 条目的结构"""
        response = client.get("/api/topic/evolution?interval=week&top_n=6")
        data = response.json()

        if data["data"]["series"]:
            entry = data["data"]["series"][0]
            # 每条 series 记录应为 [date_str, count, topic_name]
            assert len(entry) == 3
            assert isinstance(entry[0], str)
            assert isinstance(entry[1], int)
            assert isinstance(entry[2], str)

    def test_evolution_empty_data(self, client):
        """测试无数据时的演化接口响应"""
        response = client.get("/api/topic/evolution?interval=week&top_n=6")
        data = response.json()

        # 即使没有数据也应当返回合法结构
        assert "series" in data["data"]
        assert "legend" in data["data"]
        assert isinstance(data["data"]["series"], list)
        assert isinstance(data["data"]["legend"], list)

    def test_evolution_legend_matches_series(self, client):
        """测试 legend 中的话题与 series 中的话题一致"""
        response = client.get("/api/topic/evolution?interval=week&top_n=6")
        data = response.json()

        if data["data"]["series"] and data["data"]["legend"]:
            legend_set = set(data["data"]["legend"])
            for entry in data["data"]["series"]:
                assert entry[2] in legend_set
