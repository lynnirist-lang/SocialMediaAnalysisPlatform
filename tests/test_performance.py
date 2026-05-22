import pytest
import time


class TestPerformance:
    """性能测试"""

    @pytest.mark.parametrize("endpoint,expected_max_time", [
        ("/health", 0.5),
        ("/api/dashboard/summary", 2.0),
        ("/api/dashboard/trend", 2.0),
        ("/api/sentiment/distribution", 2.0),
        ("/api/sentiment/trend", 2.0),
        ("/api/topic/keywords", 2.0),
        ("/api/user/stats", 2.0),
    ])
    def test_endpoint_response_time(self, client, endpoint, expected_max_time):
        """测试各接口响应时间"""
        start_time = time.time()
        response = client.get(endpoint)
        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < expected_max_time, \
            f"{endpoint} 响应时间 {elapsed_time:.2f}s 超过预期 {expected_max_time}s"

    def test_concurrent_requests(self, client):
        """测试并发请求处理能力"""
        import concurrent.futures

        def make_request():
            return client.get("/api/dashboard/summary")

        # 模拟10个并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # 所有请求都应成功
        assert all(r.status_code == 200 for r in responses)

    def test_repeated_requests_stability(self, client):
        """测试重复请求的稳定性"""
        endpoint = "/api/dashboard/summary"
        success_count = 0
        total_requests = 20

        for _ in range(total_requests):
            response = client.get(endpoint)
            if response.status_code == 200:
                success_count += 1

        # 成功率应达到100%
        assert success_count == total_requests, \
            f"成功率: {success_count}/{total_requests}"
