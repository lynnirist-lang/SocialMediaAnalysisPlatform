import pytest


class TestIntegration:
    """集成测试 - 验证多个接口的协同工作"""

    def test_full_dashboard_workflow(self, client):
        """测试完整的数据看板工作流程"""
        # 1. 获取概览
        summary_resp = client.get("/api/dashboard/summary")
        assert summary_resp.status_code == 200

        # 2. 获取趋势
        trend_resp = client.get("/api/dashboard/trend")
        assert trend_resp.status_code == 200

        # 3. 获取词云
        wordcloud_resp = client.get("/api/dashboard/wordcloud")
        assert wordcloud_resp.status_code == 200

    def test_full_sentiment_workflow(self, client):
        """测试完整的情感分析工作流程"""
        # 1. 获取分布
        dist_resp = client.get("/api/sentiment/distribution")
        assert dist_resp.status_code == 200

        # 2. 获取趋势
        trend_resp = client.get("/api/sentiment/trend")
        assert trend_resp.status_code == 200

        # 3. 获取热力图
        heatmap_resp = client.get("/api/sentiment/heatmap")
        assert heatmap_resp.status_code == 200

        # 4. 获取博文列表
        posts_resp = client.get("/api/sentiment/posts?page_size=5")
        assert posts_resp.status_code == 200

    def test_full_topic_workflow(self, client):
        """测试完整的主题分析工作流程"""
        # 1. 获取关键词
        keywords_resp = client.get("/api/topic/keywords?top_n=10")
        assert keywords_resp.status_code == 200

        # 2. 获取聚类
        clusters_resp = client.get("/api/topic/clusters")
        assert clusters_resp.status_code == 200

        # 3. 获取柱状图
        bar_resp = client.get("/api/topic/bar")
        assert bar_resp.status_code == 200

    def test_full_user_workflow(self, client):
        """测试完整的用户画像工作流程"""
        # 1. 获取统计
        stats_resp = client.get("/api/user/stats")
        assert stats_resp.status_code == 200

        # 2. 获取网络
        network_resp = client.get("/api/user/network?top_n=20")
        assert network_resp.status_code == 200

        # 3. 获取角色分布
        role_resp = client.get("/api/user/role-distribution")
        assert role_resp.status_code == 200

        # 4. 获取用户列表
        list_resp = client.get("/api/user/list?page_size=5")
        assert list_resp.status_code == 200

    def test_api_response_time(self, client):
        """测试API响应时间（应在合理范围内）"""
        import time

        endpoints = [
            "/health",
            "/api/dashboard/summary",
            "/api/sentiment/distribution",
            "/api/topic/keywords",
            "/api/user/stats"
        ]

        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            elapsed_time = time.time() - start_time

            assert response.status_code == 200
            # 响应时间应小于2秒
            assert elapsed_time < 2.0, f"{endpoint} 响应时间过长: {elapsed_time:.2f}s"
