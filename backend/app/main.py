"""FastAPI 应用主文件"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, users, cases, clients, documents, schedules, billing, dockets, lightweight
from app.models.docket import DocketRecord  # 确保表被创建
from app.models.lightweight import StoredMessage, StoredTask, StoredTimeRecord, StoredBillingConfig, StoredBill

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 首次启动初始化（默认账号 + JWT 密钥）
from app.core.init_db import init_database, ensure_jwt_secret
ensure_jwt_secret()
init_database()

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

# 前端页面路由（如果模板存在则加载）
try:
    from app.routes_pages import router as pages_router
    from fastapi.staticfiles import StaticFiles
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(pages_router)
except ImportError:
    pass  # 纯 API 模式，不加载页面


@app.get("/api/health")
def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "1.0.0"}
