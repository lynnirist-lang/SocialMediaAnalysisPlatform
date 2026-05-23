import pytest


class TestUserAPI:
    """用户画像接口测试"""

    def test_get_stats(self, client):
        """测试获取用户统计摘要"""
        response = client.get("/api/user/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "avg_pagerank" in data["data"]
        assert "network_density" in data["data"]
        assert "core_nodes" in data["data"]
        assert "propagation_levels" in data["data"]

    def test_get_network_default(self, client):
        """测试获取用户网络（默认50个节点）"""
        response = client.get("/api/user/network")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "nodes" in data["data"]
        assert "links" in data["data"]
        assert len(data["data"]["nodes"]) <= 50

    def test_get_network_custom_size(self, client):
        """测试获取指定数量的用户网络"""
        top_n = 20
        response = client.get(f"/api/user/network?top_n={top_n}")
        assert response.status_code == 200

        data = response.json()
        assert len(data["data"]["nodes"]) <= top_n

    def test_network_node_structure(self, client):
        """测试网络节点结构"""
        response = client.get("/api/user/network?top_n=1")
        data = response.json()

        if data["data"]["nodes"]:
            node = data["data"]["nodes"][0]
            assert "id" in node
            assert "name" in node
            assert "value" in node
            assert "symbolSize" in node
            assert "category" in node

    def test_get_role_distribution(self, client):
        """测试获取用户角色分布"""
        response = client.get("/api/user/role-distribution")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert isinstance(data["data"], list)

        if data["data"]:
            first_item = data["data"][0]
            assert "name" in first_item
            assert "value" in first_item

    def test_get_user_list_default(self, client, pagination_params):
        """测试获取用户列表（默认分页）"""
        response = client.get("/api/user/list")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "users" in data["data"]
        assert "total" in data["data"]
        assert "page" in data["data"]
        assert "page_size" in data["data"]

    def test_get_user_list_with_pagination(self, client):
        """测试带分页参数的用户列表"""
        params = {"page": 1, "page_size": 5}
        response = client.get("/api/user/list", params=params)
        assert response.status_code == 200

        data = response.json()
        assert len(data["data"]["users"]) <= 5
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5

    def test_get_user_detail_valid(self, client):
        """测试获取用户详情（有效ID）"""
        # 先获取一个有效的用户ID
        list_response = client.get("/api/user/list?page_size=1")
        list_data = list_response.json()

        if list_data["data"]["users"]:
            user_id = list_data["data"]["users"][0]["user_id"]
            response = client.get(f"/api/user/{user_id}")
            assert response.status_code == 200

            data = response.json()
            assert data["code"] == 200
            assert "user_id" in data["data"]

    def test_get_user_detail_invalid(self, client):
        """测试获取用户详情（无效ID）"""
        response = client.get("/api/user/nonexistent_user")
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["code"] == 404

    def test_user_list_new_fields_present(self, client):
        """测试用户列表响应中包含新增字段"""
        response = client.get("/api/user/list")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200

        if data["data"]["users"]:
            user = data["data"]["users"][0]
            assert "activity_score" in user
            assert "influence_score" in user
            assert "sentiment_tendency" in user
            assert "top_topics" in user

    def test_user_list_activity_score_range(self, client):
        """测试 activity_score 的取值范围在 0-100 之间"""
        response = client.get("/api/user/list")
        data = response.json()

        if data["data"]["users"]:
            for user in data["data"]["users"]:
                score = user["activity_score"]
                assert isinstance(score, (int, float))
                assert 0 <= score <= 100

    def test_user_list_influence_score_range(self, client):
        """测试 influence_score 的取值范围在 0-1 之间"""
        response = client.get("/api/user/list")
        data = response.json()

        if data["data"]["users"]:
            for user in data["data"]["users"]:
                score = user["influence_score"]
                assert isinstance(score, (int, float))
                assert 0 <= score <= 1

    def test_user_list_sentiment_tendency_values(self, client):
        """测试 sentiment_tendency 仅包含合法取值"""
        response = client.get("/api/user/list")
        data = response.json()

        valid_tendencies = {"积极", "消极", "中性"}
        if data["data"]["users"]:
            for user in data["data"]["users"]:
                assert user["sentiment_tendency"] in valid_tendencies

    def test_user_list_top_topics_structure(self, client):
        """测试 top_topics 为最多两项的字符串列表"""
        response = client.get("/api/user/list")
        data = response.json()

        if data["data"]["users"]:
            for user in data["data"]["users"]:
                top_topics = user["top_topics"]
                assert isinstance(top_topics, list)
                assert len(top_topics) <= 2
                for topic in top_topics:
                    assert isinstance(topic, str)
