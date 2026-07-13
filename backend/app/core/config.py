"""应用配置"""
import os


class Settings:
    """应用全局配置"""
    # 服务配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lawyer_center.db"),
    )

    # JWT 认证配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "lawyer-center-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # 文件存储路径
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")


settings = Settings()

# 确保数据目录存在
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
