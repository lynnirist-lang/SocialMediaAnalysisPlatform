import io
import re
from contextlib import asynccontextmanager
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.api import auth, dashboard, sentiment, topic, user
from backend.database import init_db
from config.config import ensure_dirs_exist
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from backend.services.data_loader import DataLoader
from backend.services.report_exporter import build_report_data


FONT_NAME = 'Helvetica'  # 默认字体
_CHINESE_FONT_CANDIDATES = [
    ('SimSun', 'C:/Windows/Fonts/simsun.ttc'),           # Windows
    ('SimHei', 'C:/Windows/Fonts/simhei.ttf'),            # Windows 备选
    ('NotoSansCJK', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),  # Linux
    ('WenQuanYi', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'),              # Linux 备选
    ('PingFang', '/System/Library/Fonts/PingFang.ttc'),   # macOS
]
for _font_name, _font_path in _CHINESE_FONT_CANDIDATES:
    try:
        pdfmetrics.registerFont(TTFont(_font_name, _font_path))
        FONT_NAME = _font_name
        break
    except Exception:
        continue
if FONT_NAME == 'Helvetica':
    print("[WARNING] 未找到中文字体，PDF 中文字符将显示为乱码")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    ensure_dirs_exist()
    init_db()
    print("[INFO] 数据库表已就绪")
    print("[INFO] 应用启动，检查 Redis 连接...")
    yield
    print("[INFO] 应用关闭")


app = FastAPI(
    title="微博舆情分析系统 API",
    description="社交媒体数据分析平台",
    version="1.0.0",
    lifespan=lifespan
)
data_loader = DataLoader()
# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # 添加 5174
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["数据看板"])
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["情感分析"])
app.include_router(topic.router, prefix="/api/topic", tags=["主题分析"])
app.include_router(user.router, prefix="/api/user", tags=["用户画像"])
app.include_router(auth.router, prefix="/api/auth", tags=["用户认证"])




@app.get("/")
async def root():
    return {"message": "欢迎使用微博舆情分析系统 API", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/cache/clear")
async def clear_cache():
    """手动清除所有缓存"""
    data_loader.invalidate_all_cache()
    return {"status": "success", "message": "缓存已清除"}


@app.get("/api/cache/stats")
async def cache_stats():
    """获取缓存统计信息"""
    if data_loader.redis_client:
        try:
            info = data_loader.redis_client.info('memory')
            keys_count = data_loader.redis_client.dbsize()
            return {
                "cache_enabled": True,
                "keys_count": keys_count,
                "used_memory_human": info.get('used_memory_human', 'N/A'),
                "used_memory_peak_human": info.get('used_memory_peak_human', 'N/A')
            }
        except Exception as e:
            return {"cache_enabled": False, "error": str(e)}
    return {"cache_enabled": False}


def _truncate_text(text: str, max_len: int = 36) -> str:
    text = str(text or "")
    return text if len(text) <= max_len else text[: max_len - 1] + "..."


def _pdf_safe_text(text: str) -> str:
    """避免 PDF 段落解析器把 <>& 误当成 HTML 标签"""
    return xml_escape(str(text or ""))


@app.post("/api/export/report")
async def export_report(request: dict):
    """导出专业 PDF 报告 - 支持全量分日展示与条件筛选"""
    date_range = request.get("date_range") or []
    keyword = (request.get("search_keyword") or "").strip()

    try:
        is_full_report, summary, report_data = build_report_data(
            data_loader, date_range=date_range, keyword=keyword
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"报告数据组装失败: {e}") from e

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1f77b4"),
        spaceAfter=30,
        fontName=FONT_NAME,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#2c3e50"),
        spaceBefore=20,
        spaceAfter=10,
        fontName=FONT_NAME,
    )
    sub_heading_style = ParagraphStyle(
        "SmallHeading", parent=styles["Heading3"], fontName=FONT_NAME, fontSize=12
    )
    normal_style = ParagraphStyle(
        "CustomNormal", parent=styles["Normal"], fontSize=11, fontName=FONT_NAME, leading=18
    )
    muted_style = ParagraphStyle(
        "Muted", parent=styles["Normal"], fontName=FONT_NAME, textColor=colors.grey, fontSize=10
    )
    table_style = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ])

    elements.append(Paragraph("社交媒体舆情分析报告", title_style))
    elements.append(Spacer(1, 0.3 * cm))

    date_range_label = (
        f"{date_range[0]} 至 {date_range[1]}" if len(date_range) >= 2 else "全部"
    )
    info_data = [
        ["报告生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["分析模式", "全量历史数据（按日）" if is_full_report else "条件筛选"],
        ["日期范围", date_range_label],
        ["搜索关键词", keyword or "无"],
    ]
    info_table = Table(info_data, colWidths=[4 * cm, 10 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph("数据总览", heading_style))
    summary_rows = [
        ["指标", "数值"],
        ["帖子总数", str(summary["total_posts"])],
        ["评论总数", str(summary["total_comments"])],
        ["参与用户数", str(summary["total_users"])],
        ["覆盖日期", f"{summary['date_from']} ~ {summary['date_to']}（{summary['day_count']} 天）"],
        ["整体积极占比", f"{summary['sent_dist']['positive']:.1f}%"],
        ["整体消极占比", f"{summary['sent_dist']['negative']:.1f}%"],
        ["整体中性占比", f"{summary['sent_dist']['neutral']:.1f}%"],
    ]
    summary_table = Table(summary_rows, colWidths=[4 * cm, 10 * cm])
    summary_table.setStyle(table_style)
    elements.append(summary_table)
    elements.append(Spacer(1, 0.8 * cm))

    for day_data in report_data:
        elements.append(Paragraph(f"日期: {_pdf_safe_text(day_data['date'])}", heading_style))
        elements.append(Paragraph(
            f"本段共 <b>{day_data['total_posts']}</b> 条帖子，<b>{day_data['total_comments']}</b> 条评论。",
            normal_style,
        ))

        elements.append(Paragraph("情感分析", sub_heading_style))
        sent_table_data = [["类型", "占比", "数量"]]
        for en_key, cn_key in [("positive", "积极"), ("negative", "消极"), ("neutral", "中性")]:
            sent_table_data.append([
                cn_key,
                f"{day_data['sent_dist'].get(en_key, 0):.1f}%",
                day_data["sent_counts"].get(cn_key, 0),
            ])
        elements.append(Table(sent_table_data, colWidths=[3 * cm, 3 * cm, 3 * cm], style=table_style))
        elements.append(Spacer(1, 0.4 * cm))

        elements.append(Paragraph("热门话题 Top 5", sub_heading_style))
        if day_data.get("topics"):
            topic_table_data = [["排名", "名称", "帖子数"]]
            for idx, tp in enumerate(day_data["topics"], 1):
                topic_table_data.append([
                    idx,
                    _truncate_text(tp["name"], 40),
                    tp["post_count"],
                ])
            elements.append(Table(topic_table_data, colWidths=[1.5 * cm, 9 * cm, 3 * cm], style=table_style))
        else:
            elements.append(Paragraph("暂无话题数据", muted_style))
        elements.append(Spacer(1, 0.4 * cm))

        elements.append(Paragraph("活跃用户 Top 5", sub_heading_style))
        if day_data.get("users"):
            user_table_data = [["排名", "昵称", "发帖数", "粉丝数"]]
            for idx, usr in enumerate(day_data["users"], 1):
                user_table_data.append([
                    idx,
                    _truncate_text(usr.get("nickname", "未知"), 20),
                    usr.get("post_count", 0),
                    usr.get("followers", 0),
                ])
            elements.append(Table(user_table_data, colWidths=[1.5 * cm, 6 * cm, 3 * cm, 3 * cm], style=table_style))
        else:
            elements.append(Paragraph("暂无活跃用户数据", muted_style))
        elements.append(Spacer(1, 0.8 * cm))

    try:
        doc.build(elements)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {e}") from e

    pdf_bytes = buffer.getvalue()
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=500, detail="PDF 生成结果无效")

    buffer = io.BytesIO(pdf_bytes)
    filename = f"weibo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


if __name__ == "__main__":
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)