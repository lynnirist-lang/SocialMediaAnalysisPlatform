import pytest


class TestDataTierAPI:
    """数据分层管理接口测试"""

    def test_tier_stats_status_code(self, client):
        """测试分层统计接口返回 200"""
        response = client.get("/api/data/tier-stats")
        assert response.status_code == 200

    def test_tier_stats_response_structure_redis_unavailable(self, client):
        """测试 Redis 不可用时的响应结构"""
        response = client.get("/api/data/tier-stats")
        data = response.json()

        # 必须包含 tier_distribution 或 error 之一
        assert ("tier_distribution" in data) or ("error" in data)

    def test_tier_stats_error_fallback_fields(self, client):
        """测试 Redis 不可用时的降级字段"""
        response = client.get("/api/data/tier-stats")
        data = response.json()

        if "error" in data:
            assert "hot" in data
            assert "warm" in data
            assert "cold" in data
            assert isinstance(data["hot"], int)
            assert isinstance(data["warm"], int)
            assert isinstance(data["cold"], int)

    def test_tier_stats_distribution_structure(self, client):
        """测试 Redis 可用时 tier_distribution 的字段结构"""
        response = client.get("/api/data/tier-stats")
        data = response.json()

        if "tier_distribution" in data:
            dist = data["tier_distribution"]
            assert "hot" in dist
            assert "warm" in dist
            assert "cold" in dist
            assert "total" in dist
            assert isinstance(dist["hot"], int)
            assert isinstance(dist["warm"], int)
            assert isinstance(dist["cold"], int)
            assert isinstance(dist["total"], int)

    def test_tier_stats_tier_config_present(self, client):
        """测试 Redis 可用时包含 tier_config 字段"""
        response = client.get("/api/data/tier-stats")
        data = response.json()

        if "tier_distribution" in data:
            assert "tier_config" in data

    def test_tier_stats_total_equals_sum(self, client):
        """测试 total 等于各层数量之和"""
        response = client.get("/api/data/tier-stats")
        data = response.json()

        if "tier_distribution" in data:
            dist = data["tier_distribution"]
            assert dist["total"] == dist["hot"] + dist["warm"] + dist["cold"]

    def test_migrate_cold_status_code(self, client):
        """测试冷数据迁移接口返回 200"""
        response = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        assert response.status_code == 200

    def test_migrate_cold_response_structure(self, client):
        """测试冷数据迁移接口的响应结构"""
        response = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        data = response.json()

        # 必须包含 status（成功）或 error（Redis 不可用）之一
        assert ("status" in data) or ("error" in data)

    def test_migrate_cold_success_fields(self, client):
        """测试 Redis 可用时迁移成功的响应字段"""
        response = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        data = response.json()

        if "status" in data:
            assert data["status"] == "ok"
            assert "result" in data
            result = data["result"]
            assert "archived_posts" in result
            assert "archived_comments" in result
            assert "dry_run" in result

    def test_migrate_cold_dry_run_flag(self, client):
        """测试 dry_run=true 时结果中标记正确"""
        response = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        data = response.json()

        if "status" in data:
            assert data["result"]["dry_run"] is True

    def test_migrate_cold_archived_counts_are_int(self, client):
        """测试归档计数字段为整数"""
        response = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        data = response.json()

        if "status" in data:
            result = data["result"]
            assert isinstance(result["archived_posts"], int)
            assert isinstance(result["archived_comments"], int)

    def test_migrate_cold_redis_unavailable_error(self, client):
        """测试 Redis 不可用时返回明确的 error 字段"""
        response = client.post("/api/data/migrate-cold?cutoff_days=60&dry_run=true")
        data = response.json()

        if "error" in data:
            assert isinstance(data["error"], str)
            assert len(data["error"]) > 0

    def test_migrate_cold_default_cutoff(self, client):
        """测试不传 cutoff_days 时使用默认值也能正常响应"""
        response = client.post("/api/data/migrate-cold?dry_run=true")
        assert response.status_code == 200
        data = response.json()
        assert ("status" in data) or ("error" in data)
