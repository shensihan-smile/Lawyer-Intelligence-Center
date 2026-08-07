"""数据库初始化：首次启动时自动创建默认账号 + 轻量迁移"""
import os
import secrets
from app.core.database import SessionLocal, engine
from app.models.user import User
from app.core.auth import hash_password
from sqlalchemy import text


def init_database():
    """初始化数据库，确保默认账号存在"""
    db = SessionLocal()

    try:
        # 1. 管理员账号
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                real_name="管理员",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            print("[INIT] 管理员账号已创建: admin / admin123")

        # 2. 测试体验账号
        demo = db.query(User).filter(User.username == "demo").first()
        if not demo:
            demo = User(
                username="demo",
                hashed_password=hash_password("demo123"),
                real_name="体验用户",
                role="lawyer",
                is_active=True,
            )
            db.add(demo)
            print("[INIT] 测试账号已创建: demo / demo123")

        db.commit()
    finally:
        db.close()


def ensure_jwt_secret():
    """确保 JWT 密钥存在（首次运行随机生成，写入 .env 文件）"""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "SECRET_KEY" in content and "lawyer-center-secret-key-change-in-production" not in content:
            return  # 已有自定义密钥，不覆盖

    # 生成随机密钥
    new_secret = secrets.token_hex(32)

    # 保留已有其他配置，只更新/添加 SECRET_KEY
    existing = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    existing[key.strip()] = val.strip()

    existing["SECRET_KEY"] = new_secret

    with open(env_path, "w", encoding="utf-8") as f:
        for key, val in existing.items():
            f.write(f"{key}={val}\n")
        f.write(f"# 以下可选配置\n")
        f.write(f"# --- AI 大模型（OpenAI 兼容 API）---\n")
        f.write(f"# 智谱 AI（免费，推荐）：\n")
        f.write(f"#   OPENAI_API_KEY=your-zhipu-api-key\n")
        f.write(f"#   OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/\n")
        f.write(f"#   OPENAI_MODEL=glm-4.6v-flash\n")
        f.write(f"# OpenAI 官方：\n")
        f.write(f"#   OPENAI_API_KEY=sk-xxxx\n")
        f.write(f"#   OPENAI_MODEL=gpt-4o-mini\n")

    # 更新运行时配置
    from app.core.config import settings
    settings.SECRET_KEY = new_secret

    print(f"[INIT] JWT 密钥已随机生成")


def ensure_columns():
    """轻量迁移：为已有表补充缺失字段（幂等，SQLite ALTER TABLE）"""
    from sqlalchemy import text as sql_text
    db = SessionLocal()
    try:
        # —— 辅助函数：获取表已有字段 ——
        def _get_existing(table_name: str) -> set:
            try:
                rows = db.execute(sql_text(f"PRAGMA table_info('{table_name}')")).fetchall()
                return {r[1] for r in rows}
            except Exception:
                return set()

        existing_clients = _get_existing("clients")
        existing_docs = _get_existing("documents")
        existing_ccl = _get_existing("case_clients")
        existing_sched = _get_existing("schedules")
        existing_bills = _get_existing("bills")
        existing_bill_items = _get_existing("bill_items")

        # 所有迁移：(表名, 字段名, 类型定义, 已有字段集)
        all_migrations = [
            # clients 表
            ("clients", "client_type", "VARCHAR(10) DEFAULT '个人'", existing_clients),
            ("clients", "id_number", "VARCHAR(50) DEFAULT ''", existing_clients),
            # documents 表
            ("documents", "is_draft", "INTEGER DEFAULT 0", existing_docs),
            ("documents", "template_id", "INTEGER", existing_docs),
            ("documents", "editor_content", "TEXT DEFAULT ''", existing_docs),
            # case_clients 表
            ("case_clients", "role", "VARCHAR(20) DEFAULT ''", existing_ccl),
            # schedules 表
            ("schedules", "is_all_day", "INTEGER DEFAULT 0", existing_sched),
            ("schedules", "reminder_setting", "VARCHAR(20) DEFAULT '3d'", existing_sched),
            ("schedules", "color", "VARCHAR(20) DEFAULT ''", existing_sched),
            ("schedules", "source_deadline", "VARCHAR(50) DEFAULT ''", existing_sched),
            # bills 表
            ("bills", "firm_name", "VARCHAR(200) DEFAULT ''", existing_bills),
            ("bills", "firm_address", "VARCHAR(200) DEFAULT ''", existing_bills),
            ("bills", "firm_phone", "VARCHAR(50) DEFAULT ''", existing_bills),
            ("bills", "lawyer_name", "VARCHAR(50) DEFAULT ''", existing_bills),
            ("bills", "bank_info", "VARCHAR(200) DEFAULT ''", existing_bills),
            ("bills", "amount_paid", "FLOAT DEFAULT 0", existing_bills),
            ("bills", "paid_date", "DATETIME", existing_bills),
            # bill_items 表
            ("bill_items", "item_type", "VARCHAR(20) DEFAULT 'legal_fee'", existing_bill_items),
        ]

        for table, col, typedef, target in all_migrations:
            if col not in target:
                try:
                    sql = f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"
                    db.execute(sql_text(sql))
                    db.commit()
                    print(f"[MIGRATE] {table}.{col} 已添加")
                except Exception as e:
                    db.rollback()
                    print(f"[MIGRATE] {table}.{col} 添加失败（可能已存在）: {e}")
    finally:
        db.close()


def seed_templates():
    """种子数据：模板中心默认模板（委托给 core.seed）"""
    from app.core.seed import seed_templates as _seed
    _seed()
