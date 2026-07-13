import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message, Divider } from 'antd';
import { UserOutlined, LockOutlined, ExperimentOutlined } from '@ant-design/icons';
import apiClient from '../../utils/api';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const doLogin = async (username: string, password: string) => {
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const res = await apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      localStorage.setItem('auth_token', res.data.access_token);
      localStorage.setItem('login_role', res.data.role);
      message.success(`欢迎，${res.data.real_name}`);
      navigate('/dashboard');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (values: { username: string; password: string }) => {
    await doLogin(values.username, values.password);
  };

  // 一键体验：填入 demo 账号直接登录
  const handleDemoLogin = async () => {
    form.setFieldsValue({ username: 'demo', password: 'demo123' });
    await doLogin('demo', 'demo123');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card
        style={{
          width: 420,
          boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
          borderRadius: 8,
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ marginBottom: 4, color: '#667eea' }}>
            律师智能中心
          </Title>
          <Text type="secondary">智能化律师工作平台</Text>
        </div>

        {/* 一键体验按钮 */}
        <Button
          type="primary"
          icon={<ExperimentOutlined />}
          onClick={handleDemoLogin}
          loading={loading}
          block
          size="large"
          style={{
            height: 48,
            background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
            border: 'none',
            fontSize: 16,
            fontWeight: 600,
          }}
        >
          一键体验（免输账号）
        </Button>

        <Divider plain>
          <Text type="secondary" style={{ fontSize: 12 }}>或使用账号密码登录</Text>
        </Divider>

        <Form
          form={form}
          name="login"
          onFinish={handleLogin}
          size="large"
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登 录
            </Button>
          </Form.Item>
        </Form>

        <div style={{
          marginTop: 20, padding: '12px 16px',
          background: '#f6f8fa', borderRadius: 6,
        }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            📋 可用账号：
          </Text>
          <Text code style={{ fontSize: 12 }}>demo / demo123</Text>
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>— 体验账号，可试用全部功能</Text>
          <br />
          <Text code style={{ fontSize: 12 }}>admin / admin123</Text>
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>— 管理员，正式使用时修改密码</Text>
        </div>
      </Card>
    </div>
  );
};

export default LoginPage;
