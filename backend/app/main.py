"""FastAPI 应用主文件"""
import os
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件中的环境变量（必须在其他 import 之前）
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, users, cases, clients, documents, schedules, billing, dockets, lightweight, local_cases, preservations, retainer, dashboard, ai_assistant
from app.models.docket import DocketRecord  # 确保表被创建
from app.models.lightweight import StoredMessage, StoredTask, StoredTimeRecord, StoredBillingConfig, StoredBill
from app.models.local_case import LocalCase  # 本地判例库
from app.models.preservation import PreservationRecord, PreservationRenewal  # 保全记录
from app.models.communication import CommunicationRecord  # 沟通记录
from app.models.template import Template  # 文档模板
from app.models.retainer import RetainerClient, WorkRecord, PaymentRecord, RetainerReport  # 常法客户

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 首次启动初始化（默认账号 + JWT 密钥 + 轻量迁移 + 种子数据）
from app.core.init_db import init_database, ensure_jwt_secret, ensure_columns, seed_templates
ensure_jwt_secret()
init_database()
ensure_columns()
seed_templates()

app = FastAPI(
    title="律师智能中心 API",
    description="律师智能中心后端服务",
    version="1.0.0",
)

# CORS 中间件（开发模式允许所有来源，生产模式应限制）
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(cases.router, prefix="/api/cases", tags=["案件管理"])
app.include_router(clients.router, prefix="/api/clients", tags=["客户管理"])
app.include_router(documents.router, prefix="/api/documents", tags=["文档管理"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["日程管理"])
app.include_router(billing.router, prefix="/api/billing", tags=["财务管理"])
app.include_router(dockets.router, prefix="/api/dockets", tags=["卷宗管理"])
app.include_router(lightweight.router, prefix="/api/lw", tags=["轻量数据"])
app.include_router(local_cases.router, prefix="/api/local-cases", tags=["本地判例库"])
app.include_router(preservations.router, prefix="/api/preservations", tags=["保全管理"])
app.include_router(retainer.router, prefix="/api/retainer", tags=["常法客户"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(ai_assistant.router, prefix="/api/ai", tags=["AI助手"])

# 延迟导入 templates（避免循环引用）
from app.api.templates import router as templates_router
app.include_router(templates_router, prefix="/api/templates", tags=["模板管理"])

@app.get("/api/health")
def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "1.0.0"}


# 前端页面路由（必须在所有 API 路由之后注册，否则兜底路由会拦截 API 请求）
try:
    from app.routes_pages import router as pages_router
    from fastapi.staticfiles import StaticFiles
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(pages_router)
except ImportError:
    pass  # 纯 API 模式，不加载页面
