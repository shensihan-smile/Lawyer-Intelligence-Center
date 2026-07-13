import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Table, Button, Modal, Form, Input, Select, Space, Tag,
  message, Popconfirm, Switch, Alert, Descriptions,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SettingOutlined,
  UserOutlined, StopOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import apiClient from '../../utils/api';

const { Title, Text } = Typography;

// ==================== 类型 ====================

interface UserRecord {
  id: number;
  username: string;
  real_name: string;
  role: string;
  phone: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员', lawyer: '律师', assistant: '助理',
};
const ROLE_COLORS: Record<string, string> = {
  admin: 'red', lawyer: 'blue', assistant: 'green',
};

// ==================== 当前用户信息 ====================

const CurrentUserCard: React.FC<{ onRefresh: () => void }> = ({ onRefresh }) => {
  const [me, setMe] = useState<UserRecord | null>(null);

  useEffect(() => {
    apiClient.get('/users/me').then(r => setMe(r.data)).catch(() => {});
  }, []);

  if (!me) return null;
  const isAdmin = me.role === 'admin';

  return (
    <Alert
      type={isAdmin ? 'success' : 'info'}
      message={
        <Space>
          <UserOutlined />
          <span>当前登录：{me.real_name}</span>
          <Tag color={ROLE_COLORS[me.role]}>{ROLE_LABELS[me.role]}</Tag>
          {isAdmin && <Text type="success">— 您拥有管理员权限，可管理所有成员账号</Text>}
          {!isAdmin && <Text type="secondary">— 如需修改账号权限，请联系管理员</Text>}
        </Space>
      }
      style={{ marginBottom: 16 }}
    />
  );
};

// ==================== 主页面 ====================

const SystemPage: React.FC = () => {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editUser, setEditUser] = useState<UserRecord | null>(null);
  const [me, setMe] = useState<UserRecord | null>(null);
  const [form] = Form.useForm();

  const isAdmin = me?.role === 'admin';

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/users/');
      setUsers(res.data || []);
    } catch { message.error('获取用户列表失败'); }
    finally { setLoading(false); }
  }, []);

  const fetchMe = useCallback(async () => {
    try {
      const res = await apiClient.get('/users/me');
      setMe(res.data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchUsers(); fetchMe(); }, [fetchUsers, fetchMe]);

  // 打开新增弹窗
  const handleAdd = () => {
    if (!isAdmin) { message.error('仅管理员可添加用户'); return; }
    setEditUser(null);
    form.resetFields();
    form.setFieldsValue({ role: 'lawyer' });
    setModalOpen(true);
  };

  // 打开编辑弹窗
  const handleEdit = (user: UserRecord) => {
    if (!isAdmin) { message.error('仅管理员可编辑用户'); return; }
    setEditUser(user);
    form.setFieldsValue({
      real_name: user.real_name,
      role: user.role,
      phone: user.phone || '',
      email: user.email || '',
    });
    setModalOpen(true);
  };

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editUser) {
        await apiClient.put(`/users/${editUser.id}`, values);
        message.success(`${values.real_name} 信息已更新`);
      } else {
        await apiClient.post('/users/', values);
        message.success(`用户 ${values.real_name} 已创建`);
      }
      setModalOpen(false);
      fetchUsers();
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    }
  };

  // 一键启停
  const handleToggleActive = async (user: UserRecord) => {
    if (!isAdmin) { message.error('仅管理员可操作'); return; }
    try {
      const res = await apiClient.put(`/users/${user.id}/toggle-active`);
      message.success(res.data.message);
      fetchUsers();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  // 删除
  const handleDelete = async (user: UserRecord) => {
    if (!isAdmin) { message.error('仅管理员可删除用户'); return; }
    try {
      await apiClient.delete(`/users/${user.id}`);
      message.success(`${user.real_name} 已删除`);
      fetchUsers();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const columns: ColumnsType<UserRecord> = [
    { title: '用户名', dataIndex: 'username', width: 120 },
    { title: '姓名', dataIndex: 'real_name', width: 100 },
    {
      title: '角色', dataIndex: 'role', width: 90,
      render: (role: string) => <Tag color={ROLE_COLORS[role]}>{ROLE_LABELS[role] || role}</Tag>,
    },
    { title: '电话', dataIndex: 'phone', width: 130, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', ellipsis: true, render: (v: string) => v || '-' },
    {
      title: '状态', dataIndex: 'is_active', width: 70,
      render: (active: boolean, record: UserRecord) => (
        isAdmin ? (
          <Switch
            checked={active}
            size="small"
            onChange={() => handleToggleActive(record)}
            checkedChildren={<CheckCircleOutlined />}
            unCheckedChildren={<StopOutlined />}
          />
        ) : (
          <Tag color={active ? 'green' : 'red'}>{active ? '正常' : '已停用'}</Tag>
        )
      ),
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 120,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, record: UserRecord) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            disabled={!isAdmin}>编辑</Button>
          <Popconfirm
            title="确定删除此用户？此操作不可恢复"
            onConfirm={() => handleDelete(record)}
            okText="确定" cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}
              disabled={!isAdmin || record.id === me?.id}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}><SettingOutlined /> 系统管理 — 账号与权限</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd} disabled={!isAdmin}>
          添加成员
        </Button>
      </div>

      <CurrentUserCard onRefresh={fetchMe} />

      <Card title={<span><UserOutlined /> 团队成员（{users.length} 人）</span>}>
        {!isAdmin && (
          <Alert
            message="您当前不是管理员，只能查看成员列表。如需修改，请联系管理员。"
            type="warning" showIcon style={{ marginBottom: 16 }}
          />
        )}

        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: t => `共 ${t} 人` }}
          size="middle"
        />

        {/* 角色权限说明 */}
        <div style={{ marginTop: 16, background: '#fafafa', padding: 16, borderRadius: 8 }}>
          <Text strong>角色权限说明：</Text>
          <Descriptions column={3} size="small" style={{ marginTop: 8 }}>
            <Descriptions.Item label={<Tag color="red">管理员</Tag>}>
              全部数据可见可改 + 管理成员账号
            </Descriptions.Item>
            <Descriptions.Item label={<Tag color="blue">律师</Tag>}>
              查看/修改自己的案件和客户
            </Descriptions.Item>
            <Descriptions.Item label={<Tag color="green">助理</Tag>}>
              查看/修改自己被分配的案件
            </Descriptions.Item>
          </Descriptions>
        </div>
      </Card>

      {/* 添加/编辑用户弹窗 */}
      <Modal
        title={editUser ? `编辑成员 — ${editUser.real_name}` : '添加新成员'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={480}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          {!editUser && (
            <>
              <Form.Item name="username" label="登录用户名" rules={[{ required: true, message: '请输入' }]}>
                <Input placeholder="英文或拼音，如 zhangwei" />
              </Form.Item>
              <Form.Item name="password" label="登录密码" rules={[{ required: true, message: '请输入密码' }]}>
                <Input.Password placeholder="至少6位" />
              </Form.Item>
            </>
          )}

          <Form.Item name="real_name" label="真实姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="如：张伟" />
          </Form.Item>

          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select
              options={Object.entries(ROLE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
            />
          </Form.Item>

          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="phone" label="电话">
              <Input placeholder="手机号" style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="email" label="邮箱">
              <Input placeholder="邮箱地址" style={{ width: 200 }} />
            </Form.Item>
          </Space>

          {editUser && (
            <Form.Item name="password" label="新密码（留空则不修改）">
              <Input.Password placeholder="留空则保持原密码" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default SystemPage;
