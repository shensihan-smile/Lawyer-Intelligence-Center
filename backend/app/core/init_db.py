"""数据库初始化：首次启动时自动创建默认账号"""
import os
import secrets
from app.core.database import SessionLocal
from app.models.user import User
from app.core.auth import hash_password


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
        f.write(f"# OPENAI_API_KEY=sk-xxxx\n")

    # 更新运行时配置
    from app.core.config import settings
    settings.SECRET_KEY = new_secret

    print(f"[INIT] JWT 密钥已随机生成")
