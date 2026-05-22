import pytest
from datetime import datetime


class TestReportExport:
    """PDF报告导出接口测试"""

    def test_export_report_success(self, client, report_test_data):
        """测试成功导出PDF报告（无筛选）"""
        response = client.post("/api/export/report", json=report_test_data)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "report_" in response.headers.get("content-disposition", "")
        assert len(response.content) > 0

    # def test_export_report_with_filter(self, client, report_test_data_with_filter):
    #     """测试带筛选条件导出PDF报告"""
    #     response = client.post("/api/export/report", json=report_test_data_with_filter)
    #
    #     assert response.status_code == 200
    #     assert response.headers["content-type"] == "application/pdf"
    #     assert len(response.content) > 0
    #
    #     # 保存测试文件
    #     with open(f"tests/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", "wb") as f:
    #         f.write(response.content)

    def test_export_report_empty_date_range(self, client):
        """测试空日期范围导出"""
        data = {
            "date_range": [],
            "search_keyword": ""
        }

        response = client.post("/api/export/report", json=data)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    def test_export_report_with_keyword_only(self, client):
        """测试仅关键词搜索导出"""
        data = {
            "date_range": [],
            "search_keyword": "舆情"
        }

        response = client.post("/api/export/report", json=data)

        assert response.status_code == 200
        assert len(response.content) > 0

    def test_export_report_invalid_method(self, client):
        """测试错误的请求方法"""
        response = client.get("/api/export/report")

        assert response.status_code == 405  # Method Not Allowed

    def test_export_report_missing_body(self, client):
        """测试缺少请求体"""
        response = client.post("/api/export/report")

        # FastAPI 会返回 422 验证错误
        assert response.status_code in [422, 200]
