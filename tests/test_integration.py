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

    def test_full_new_features_workflow(self, client):
        """测试所有新增接口的联合工作流程"""
        # 1. 主题演化接口
        evolution_resp = client.get("/api/topic/evolution?interval=week&top_n=6")
        assert evolution_resp.status_code == 200
        evolution_data = evolution_resp.json()
        assert evolution_data["code"] == 200
        assert "series" in evolution_data["data"]
        assert "legend" in evolution_data["data"]

        # 2. 用户列表接口（含新增字段）
        user_list_resp = client.get("/api/user/list?page=1&page_size=5")
        assert user_list_resp.status_code == 200
        user_list_data = user_list_resp.json()
        assert user_list_data["code"] == 200
        assert "users" in user_list_data["data"]
        if user_list_data["data"]["users"]:
            user = user_list_data["data"]["users"][0]
            assert "activity_score" in user
            assert "influence_score" in user
            assert "sentiment_tendency" in user
            assert "top_topics" in user

        # 3. 数据分层统计接口
        tier_stats_resp = client.get("/api/data/tier-stats")
        assert tier_stats_resp.status_code == 200
        tier_stats_data = tier_stats_resp.json()
        # 响应包含 tier_distribution（Redis 可用）或 error（Redis 不可用）
        assert ("tier_distribution" in tier_stats_data) or ("error" in tier_stats_data)

        # 4. 冷数据迁移接口（dry_run 模式，不产生实际变更）
        migrate_resp = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        assert migrate_resp.status_code == 200
        migrate_data = migrate_resp.json()
        # Redis 不可用时返回 error，可用时返回 status/result
        assert ("status" in migrate_data) or ("error" in migrate_data)
        if "status" in migrate_data:
            assert migrate_data["status"] == "ok"
            assert "result" in migrate_data
            result = migrate_data["result"]
            assert "archived_posts" in result
            assert "archived_comments" in result
            assert result.get("dry_run") is True
