import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Button, Input, Space, Modal, Form, Tag, Popconfirm,
  message, Card,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import apiClient from '../../utils/api';
import { Client } from '../../types';

const { Title } = Typography;

const CommunicationPage: React.FC = () => {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [form] = Form.useForm();

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (searchText) params.search = searchText;
      const res = await apiClient.get('/clients/', { params });
      setClients(res.data);
    } catch {
      message.error('获取客户列表失败');
    } finally {
      setLoading(false);
    }
  }, [searchText]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const handleAdd = () => {
    setEditingClient(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: Client) => {
    setEditingClient(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/clients/${id}`);
      message.success('客户删除成功');
      fetchClients();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingClient) {
        await apiClient.put(`/clients/${editingClient.id}`, values);
        message.success('客户更新成功');
      } else {
        await apiClient.post('/clients/', values);
        message.success('客户创建成功');
      }
      setModalOpen(false);
      fetchClients();
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    }
  };

  const columns: ColumnsType<Client> = [
    {
      title: '客户名称',
      dataIndex: 'name',
      width: 180,
      sorter: (a, b) => a.name.localeCompare(b.name, 'zh'),
      render: (text: string) => <a style={{ fontWeight: 500 }}>{text}</a>,
    },
    {
      title: '联系人',
      dataIndex: 'contact_person',
      width: 100,
    },
    {
      title: '电话',
      dataIndex: 'phone',
      width: 130,
    },
    {
      title: '微信',
      dataIndex: 'wechat',
      width: 130,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      width: 180,
      ellipsis: true,
    },
    {
      title: '地址',
      dataIndex: 'address',
      width: 200,
      ellipsis: true,
    },
    {
      title: '关联案件',
      dataIndex: 'case_count',
      width: 90,
      align: 'center',
      render: (count: number) => <Tag color={count > 0 ? 'blue' : 'default'}>{count}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: Client) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确定删除此客户？"
            description="删除后不可恢复，关联的案件将解除关联。"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>客户管理</Title>
        <Space>
          <Input
            placeholder="搜索客户名称、联系人、电话..."
            prefix={<SearchOutlined />}
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onPressEnter={() => fetchClients()}
            style={{ width: 280 }}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchClients}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新建客户</Button>
        </Space>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={clients}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 位客户` }}
          size="middle"
        />
      </Card>

      <Modal
        title={editingClient ? '编辑客户' : '新建客户'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
            <Input placeholder="如：XX科技有限公司" />
          </Form.Item>
          <Space size="middle" style={{ display: 'flex' }} wrap>
            <Form.Item name="contact_person" label="联系人">
              <Input placeholder="对方对接人姓名" style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="phone" label="电话">
              <Input placeholder="手机号或座机" style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="wechat" label="微信">
              <Input placeholder="微信号" style={{ width: 180 }} />
            </Form.Item>
          </Space>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="电子邮箱地址" />
          </Form.Item>
          <Form.Item name="address" label="地址">
            <Input placeholder="通信地址" />
          </Form.Item>
          <Form.Item name="legal_contacts" label="法务对接人">
            <Input.TextArea rows={2} placeholder="对方当事人、对方律师、法官等信息" />
          </Form.Item>
          <Form.Item name="cooperation_history" label="合作历史">
            <Input.TextArea rows={3} placeholder="过往委托记录..." />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} placeholder="其他需要记录的信息" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default CommunicationPage;
