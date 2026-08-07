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


def seed_templates():
    """种子数据：模板中心默认模板（仅当 templates 表为空时插入）"""
    from app.models.template import Template
    db = SessionLocal()
    try:
        if db.query(Template).count() > 0:
            return

        templates = [
            ("起诉状", "民事起诉状", "标准民事起诉状模板，适用于一般合同纠纷、侵权纠纷等",
             '<h2>民事起诉状</h2>'
             '<p><strong>原告：</strong>{委托人}</p>'
             '<p><strong>被告：</strong>{对方当事人}</p>'
             '<p><strong>受理法院：</strong>{受理法院}</p>'
             '<h3>诉讼请求</h3>'
             '<ol><li>请求判令被告……</li>'
             '<li>请求判令被告承担本案全部诉讼费用。</li></ol>'
             '<h3>事实与理由</h3>'
             '<p>（请在此详细陈述案件事实和法律依据）</p>'
             '<p>综上所述，原告的合法权益受到严重侵害，为维护自身合法权益，'
             '特依据《中华人民共和国民事诉讼法》之相关规定，向贵院提起诉讼，'
             '恳请贵院依法支持原告的全部诉讼请求。</p>'
             '<p style="text-align:right">具状人：{委托人}</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("答辩状", "民事答辩状", "标准民事答辩状模板，用于对原告诉讼请求进行答辩",
             '<h2>民事答辩状</h2>'
             '<p><strong>答辩人：</strong>{委托人}</p>'
             '<p><strong>被答辩人：</strong>{对方当事人}</p>'
             '<p>答辩人因{案由}一案，现就起诉状内容答辩如下：</p>'
             '<h3>答辩意见</h3>'
             '<ol><li>关于原告第一项诉讼请求……</li>'
             '<li>关于原告第二项诉讼请求……</li></ol>'
             '<h3>事实与理由</h3>'
             '<p>（请在此详细陈述答辩理由）</p>'
             '<p>综上所述，原告的诉讼请求缺乏事实和法律依据，'
             '恳请贵院依法驳回原告的全部诉讼请求。</p>'
             '<p style="text-align:right">答辩人：{委托人}</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("代理词", "诉讼代理词", "庭审代理词模板，用于开庭时发表代理意见",
             '<h2>代 理 词</h2>'
             '<p><strong>审判长、审判员：</strong></p>'
             '<p>{委托人}与{对方当事人}{案由}纠纷一案，'
             '我受{委托人}的委托，担任其诉讼代理人，'
             '现根据本案事实和相关法律规定，发表如下代理意见：</p>'
             '<h3>一、关于案件事实</h3>'
             '<p>（请在此陈述案件基本事实）</p>'
             '<h3>二、关于法律适用</h3>'
             '<p>（请在此阐述法律依据）</p>'
             '<h3>三、综合意见</h3>'
             '<p>综上所述，恳请贵院依法……</p>'
             '<p style="text-align:right">委托代理人：</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("上诉状", "民事上诉状", "标准民事上诉状模板，用于对一审判决提起上诉",
             '<h2>民事上诉状</h2>'
             '<p><strong>上诉人（原审原告/被告）：</strong>{委托人}</p>'
             '<p><strong>被上诉人（原审被告/原告）：</strong>{对方当事人}</p>'
             '<p>上诉人因{案由}一案，不服{受理法院}作出的（案号）民事判决/裁定书，现提起上诉。</p>'
             '<h3>上诉请求</h3>'
             '<ol><li>请求撤销原审判决，依法改判……</li>'
             '<li>请求判令被上诉人承担本案全部诉讼费用。</li></ol>'
             '<h3>上诉理由</h3>'
             '<p>（请在此详细陈述上诉理由）</p>'
             '<p style="text-align:right">上诉人：{委托人}</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("律师函", "律师函", "标准律师函模板，用于发送正式法律函告",
             '<h2>律 师 函</h2>'
             '<p><strong>致：</strong>{对方当事人}</p>'
             '<p>{委托人}（以下称委托人）委托本所就其与贵方之间的相关事宜，出具本律师函。</p>'
             '<h3>一、基本事实</h3>'
             '<p>（请在此陈述委托事项的基本事实）</p>'
             '<h3>二、法律分析</h3>'
             '<p>（请在此进行法律分析）</p>'
             '<h3>三、律师意见</h3>'
             '<p>基于上述事实和法律分析，本律师提出以下意见：</p>'
             '<ol><li>……</li></ol>'
             '<p>请在收到本函后 日内予以书面答复。如逾期未获回复，'
             '委托人将依法采取进一步法律措施，以维护自身合法权益。</p>'
             '<p style="text-align:right">特此函告。</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("法律意见书", "法律意见书", "标准法律意见书模板，向客户出具法律分析和建议",
             '<h2>法 律 意 见 书</h2>'
             '<p><strong>致：</strong>{委托人}</p>'
             '<p>贵方就{案由}相关事宜向本所征询法律意见。'
             '本所在审阅贵方提供的相关材料后，依据现行法律法规，出具如下法律意见：</p>'
             '<h3>一、案件基本情况</h3>'
             '<p>（请在此概述案件情况）</p>'
             '<h3>二、法律分析</h3>'
             '<p>（请在此进行法律分析）</p>'
             '<h3>三、风险评估</h3>'
             '<p>（请在此进行风险评估）</p>'
             '<h3>四、法律建议</h3>'
             '<p>（请在此提出具体建议）</p>'
             '<h3>五、声明</h3>'
             '<p>本法律意见书仅供贵方参考，不构成具有法律约束力的承诺或保证。</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("财产保全申请书", "财产保全申请书", "诉前/诉中财产保全申请书模板",
             '<h2>财产保全申请书</h2>'
             '<p><strong>申请人：</strong>{委托人}</p>'
             '<p><strong>被申请人：</strong>{对方当事人}</p>'
             '<p><strong>受理法院：</strong>{受理法院}</p>'
             '<h3>申请事项</h3>'
             '<p>请求贵院依法对被申请人名下的以下财产采取保全措施：</p>'
             '<ol><li>查封/冻结被申请人银行存款人民币 元；</li>'
             '<li>查封被申请人名下的……</li></ol>'
             '<h3>事实与理由</h3>'
             '<p>申请人因与被申请人{案由}纠纷一案，已向贵院提起诉讼/拟向贵院提起诉讼。'
             '现因……（请陈述申请财产保全的理由和紧迫性）</p>'
             '<p>为防止被申请人转移、隐匿财产，保障将来生效法律文书能够得到顺利执行，'
             '申请人依据《中华人民共和国民事诉讼法》第一百零三条、第一百零四条的规定，'
             '特向贵院提出财产保全申请。</p>'
             '<p>申请人愿提供如下担保：</p><p>（担保方式及说明）</p>'
             '<p style="text-align:right">申请人：{委托人}</p>'
             '<p style="text-align:right">{当前日期}</p>'),
            ("证据目录", "证据目录", "标准证据目录模板，用于提交证据时系统整理",
             '<h2>证 据 目 录</h2>'
             '<p><strong>案由：</strong>{案由}</p>'
             '<p><strong>提交人：</strong>{委托人}</p>'
             '<p><strong>提交日期：</strong>{当前日期}</p>'
             '<table style="width:100%;border-collapse:collapse">'
             '<thead><tr>'
             '<th style="border:1px solid #ccc;padding:8px">序号</th>'
             '<th style="border:1px solid #ccc;padding:8px">证据名称</th>'
             '<th style="border:1px solid #ccc;padding:8px">证据来源</th>'
             '<th style="border:1px solid #ccc;padding:8px">页码</th>'
             '<th style="border:1px solid #ccc;padding:8px">证明内容</th>'
             '</tr></thead><tbody>'
             '<tr><td style="border:1px solid #ccc;padding:8px">1</td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td></tr>'
             '<tr><td style="border:1px solid #ccc;padding:8px">2</td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td></tr>'
             '<tr><td style="border:1px solid #ccc;padding:8px">3</td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td>'
             '<td style="border:1px solid #ccc;padding:8px"></td></tr>'
             '</tbody></table>'
             '<p style="text-align:right">提交人：{委托人}</p>'),
        ]

        for cat, name, desc, content in templates:
            t = Template(category=cat, name=name, description=desc, content=content)
            db.add(t)

        db.commit()
        print(f"[SEED] 已填充 {len(templates)} 个文档模板")
    except Exception as e:
        db.rollback()
        print(f"[SEED] 模板种子数据填充失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
