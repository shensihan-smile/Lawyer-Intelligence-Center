"""初始化数据库种子数据 — 创建默认管理员账号"""
from app.core.database import SessionLocal, engine, Base
from app.core.auth import hash_password
from app.models.user import User


def seed_database():
    """创建默认数据"""
    # 确保表已创建
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 检查是否已有管理员
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("管理员账号已存在，跳过初始化。")
            return

        # 创建管理员
        admin = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            real_name="系统管理员",
            role="admin",
            department="管理部",
            phone="13800000000",
            email="admin@lawyer-center.com",
            is_active=True,
        )
        db.add(admin)

        # 创建演示用户
        demo_users = [
            User(username="partner01", hashed_password=hash_password("123456"), real_name="张律师", role="partner", department="诉讼部", phone="13800000001"),
            User(username="lawyer01", hashed_password=hash_password("123456"), real_name="李律师", role="lawyer", department="诉讼部", phone="13800000002"),
            User(username="lawyer02", hashed_password=hash_password("123456"), real_name="王律师", role="lawyer", department="非诉部", phone="13800000003"),
            User(username="assist01", hashed_password=hash_password("123456"), real_name="赵助理", role="assistant", department="诉讼部", phone="13800000004"),
            User(username="intern01", hashed_password=hash_password("123456"), real_name="小陈", role="intern", department="非诉部", phone="13800000005"),
        ]
        for user in demo_users:
            db.add(user)

        db.commit()
        print("数据库初始化完成！")
        print("=" * 50)
        print("默认管理员账号：")
        print("  用户名: admin")
        print("  密码: admin123")
        print("=" * 50)
        print("演示账号（密码均为 123456）：")
        for u in demo_users:
            print(f"  {u.username} ({u.real_name}) - {u.role}")
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
