import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Avatar, Dropdown, theme } from 'antd';
import {
  DashboardOutlined,
  MessageOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  CalendarOutlined,
  DollarOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/dashboard',      icon: <DashboardOutlined />,  label: '工作台' },
  { key: '/communication',  icon: <MessageOutlined />,     label: '智能通信' },
  { key: '/cases',          icon: <FolderOpenOutlined />,  label: '案件与文档' },
  { key: '/documents',      icon: <FileTextOutlined />,    label: '文档处理' },
  { key: '/schedule',       icon: <CalendarOutlined />,    label: '日程与庭审' },
  { key: '/billing',        icon: <DollarOutlined />,      label: '财务管理' },
  { key: '/system',         icon: <SettingOutlined />,     label: '系统管理' },
];

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();

  const handleMenuClick = (info: { key: string }) => {
    navigate(info.key);
  };

  const userMenuItems = [
    { key: 'profile',  icon: <UserOutlined />,   label: '个人信息' },
    { key: 'logout',   icon: <LogoutOutlined />,  label: '退出登录', danger: true },
  ];

  const handleUserMenuClick = (info: { key: string }) => {
    if (info.key === 'logout') {
      localStorage.removeItem('auth_token');
      navigate('/login');
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 左侧导航 */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <div className={`logo-container ${collapsed ? 'collapsed' : ''}`}
          style={{ color: token.colorPrimary }}>
          {collapsed ? '律师' : '律师智能中心'}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ border: 'none', marginTop: 8 }}
        />
      </Sider>

      <Layout>
        {/* 顶部栏 */}
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenuClick }}>
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} />
              <span>管理员</span>
            </div>
          </Dropdown>
        </Header>

        {/* 内容区域 */}
        <Content
          style={{
            margin: 0,
            padding: 24,
            background: token.colorBgLayout,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
