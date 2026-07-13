import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Button, Input, Space, Modal, Form, Select, Tag, Popconfirm,
  message, Card, Tabs, Upload, DatePicker, Divider,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  InboxOutlined, DownloadOutlined, UploadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import apiClient from '../../utils/api';
import { Case, Document, CASE_STAGE_LABELS, DOC_CATEGORY_LABELS, CaseStage, DocumentCategory } from '../../types';

const { Title } = Typography;
const { Dragger } = Upload;

// ==================== 案件管理 Tab ====================

interface ClientSimple {
  id: number;
  name: string;
  contact_person: string;
}

// 统一第三人标签的编码/解码辅助函数
const CLIENT_TAG_PREFIX = 'c:';
const toClientValue = (id: number) => `${CLIENT_TAG_PREFIX}${id}`;
const isClientValue = (v: string) => v.startsWith(CLIENT_TAG_PREFIX);
const parseClientId = (v: string) => parseInt(v.slice(CLIENT_TAG_PREFIX.length), 10);

const CaseManagement: React.FC = () => {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [stageFilter, setStageFilter] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<Case | null>(null);
  const [clients, setClients] = useState<ClientSimple[]>([]);
  const [clientModalOpen, setClientModalOpen] = useState(false);
  const [clientForm] = Form.useForm();
  const [form] = Form.useForm();

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (searchText) params.search = searchText;
      if (stageFilter) params.stage = stageFilter;
      const res = await apiClient.get('/cases/', { params });
      setCases(res.data);
    } catch {
      message.error('获取案件列表失败');
    } finally {
      setLoading(false);
    }
  }, [searchText, stageFilter]);

  const fetchClients = useCallback(async () => {
    try {
      const res = await apiClient.get('/clients/simple');
      setClients(res.data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchCases(); }, [fetchCases]);
  useEffect(() => { fetchClients(); }, [fetchClients]);

  // 快速新建客户
  const handleQuickCreateClient = async () => {
    try {
      const values = await clientForm.validateFields();
      await apiClient.post('/clients/', values);
      message.success('客户创建成功');
      setClientModalOpen(false);
      clientForm.resetFields();
      fetchClients(); // 刷新下拉列表
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    }
  };

  const handleAdd = () => {
    setEditingCase(null);
    form.resetFields();
    form.setFieldsValue({ case_stage: 'intake', amount_in_dispute: 0, client_ids: [], third_party_tags: [] });
    setModalOpen(true);
  };

  const handleEdit = (record: Case) => {
    setEditingCase(record);
    // 构建统一的第三人标签值（客户库选择 + 手动输入）
    const tags: string[] = [];
    (record.third_party_clients || []).forEach((c) => {
      tags.push(toClientValue(c.id));
    });
    (record.third_party || []).forEach((t) => {
      if (t) tags.push(t);
    });

    form.setFieldsValue({
      ...record,
      client_ids: (record.clients || []).map((c) => c.id),
      third_party_tags: tags,
      acceptance_date: record.acceptance_date ? dayjs(record.acceptance_date) : null,
      filing_date: record.filing_date ? dayjs(record.filing_date) : null,
      trial_date: record.trial_date ? dayjs(record.trial_date) : null,
      judgment_date: record.judgment_date ? dayjs(record.judgment_date) : null,
      closing_date: record.closing_date ? dayjs(record.closing_date) : null,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/cases/${id}`);
      message.success('案件删除成功');
      fetchCases();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      // 日期转为 ISO 字符串
      const dateFields = ['acceptance_date', 'filing_date', 'trial_date', 'judgment_date', 'closing_date'];
      const payload = { ...values };
      dateFields.forEach((k) => {
        if (payload[k]) payload[k] = dayjs(payload[k]).format('YYYY-MM-DDTHH:mm:ss');
        else payload[k] = null;
      });

      // 解析统一第三人标签 → 客户ID列表 + 手动文本列表
      const tags: string[] = payload.third_party_tags || [];
      const thirdPartyClientIds: number[] = [];
      const thirdPartyManual: string[] = [];
      tags.forEach((v: string) => {
        if (isClientValue(v)) {
          const cid = parseClientId(v);
          if (!isNaN(cid)) thirdPartyClientIds.push(cid);
        } else if (v.trim()) {
          thirdPartyManual.push(v.trim());
        }
      });
      payload.third_party_client_ids = thirdPartyClientIds;
      payload.third_party = thirdPartyManual;
      // 清理掉只在前端使用的字段
      delete payload.third_party_tags;
      delete payload.third_party_clients;

      if (editingCase) {
        await apiClient.put(`/cases/${editingCase.id}`, payload);
        message.success('案件更新成功');
      } else {
        await apiClient.post('/cases/', payload);
        message.success('案件创建成功');
      }
      setModalOpen(false);
      fetchCases();
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    }
  };

  const stageOptions = [
    { value: 'intake', label: '接案' },
    { value: 'filing', label: '立案' },
    { value: 'trial', label: '审理中' },
    { value: 'judgment', label: '判决' },
    { value: 'enforcement', label: '执行' },
    { value: 'closed', label: '结案' },
  ];

  const stageColors: Record<string, string> = {
    intake: 'purple', filing: 'geekblue', trial: 'blue',
    judgment: 'orange', enforcement: 'volcano', closed: 'green',
  };

  const columns: ColumnsType<Case> = [
    {
      title: '案号', dataIndex: 'case_number', width: 150, sorter: true,
      render: (text: string) => <a style={{ fontWeight: 500 }}>{text}</a>,
    },
    { title: '案由', dataIndex: 'case_reason', width: 160, ellipsis: true },
    {
      title: '案件阶段', dataIndex: 'case_stage', width: 100,
      render: (v: CaseStage) => <Tag color={stageColors[v]}>{CASE_STAGE_LABELS[v]}</Tag>,
    },
    { title: '受理法院', dataIndex: 'court', width: 160, ellipsis: true },
    {
      title: '标的额', dataIndex: 'amount_in_dispute', width: 120, align: 'right',
      render: (v: number) => v > 0 ? `${v.toLocaleString()} 元` : '-',
    },
    {
      title: '关联客户', dataIndex: 'clients', width: 180,
      render: (clients: Array<{ id: number; name: string; contact_person: string }>) => {
        if (!clients || clients.length === 0) return <span style={{ color: '#ccc' }}>未关联</span>;
        return (
          <Space size={[4, 2]} wrap>
            {clients.map((c) => (
              <Tag key={c.id} color="blue">{c.name}</Tag>
            ))}
          </Space>
        );
      },
    },
    { title: '承办法官', dataIndex: 'judge', width: 100 },
    {
      title: '开庭日期', dataIndex: 'trial_date', width: 120,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : '-',
    },
    {
      title: '操作', key: 'action', width: 120, fixed: 'right',
      render: (_: unknown, record: Case) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除此案件？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>案件列表</Title>
        <Space>
          <Input
            placeholder="搜索案号、案由..."
            prefix={<SearchOutlined />}
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onPressEnter={() => fetchCases()}
            style={{ width: 220 }}
          />
          <Select
            placeholder="按阶段筛选"
            allowClear
            value={stageFilter || undefined}
            onChange={(v) => setStageFilter(v || '')}
            style={{ width: 130 }}
            options={stageOptions}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchCases}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新建案件</Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={cases}
        rowKey="id"
        loading={loading}
        scroll={{ x: 1200 }}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 个案件` }}
        size="middle"
      />

      {/* 案件编辑弹窗（含客户下拉 + 快速新建） */}
      <Modal
        title={editingCase ? '编辑案件' : '新建案件'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={760}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <Space size="middle" style={{ display: 'flex' }} wrap>
            <Form.Item name="case_number" label="案号" rules={[{ required: true, message: '请输入案号' }]}>
              <Input placeholder="如：(2026)京0105民初12345号" style={{ width: 260 }} />
            </Form.Item>
            <Form.Item name="case_stage" label="案件阶段">
              <Select options={stageOptions} style={{ width: 120 }} />
            </Form.Item>
          </Space>

          <Form.Item name="case_reason" label="案由">
            <Input placeholder="如：合同纠纷、劳动争议等" />
          </Form.Item>

          <Space size="middle" style={{ display: 'flex' }} wrap>
            <Form.Item name="court" label="受理法院">
              <Input placeholder="如：北京市朝阳区人民法院" style={{ width: 240 }} />
            </Form.Item>
            <Form.Item name="judge" label="承办法官">
              <Input placeholder="法官姓名" style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="clerk" label="书记员">
              <Input placeholder="书记员姓名" style={{ width: 120 }} />
            </Form.Item>
          </Space>

          {/* 客户多选下拉框 + 快速新建 */}
          <Form.Item label="关联客户">
            <Space>
              <Form.Item name="client_ids" noStyle>
                <Select
                  mode="multiple"
                  placeholder="选择客户（可选，支持多选）"
                  allowClear
                  style={{ minWidth: 320 }}
                  options={clients.map((c) => ({
                    value: c.id,
                    label: `${c.name}${c.contact_person ? ` (${c.contact_person})` : ''}`,
                  }))}
                  showSearch
                  filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                />
              </Form.Item>
              <Button
                type="dashed"
                icon={<PlusOutlined />}
                onClick={() => setClientModalOpen(true)}
              >
                快速新建客户
              </Button>
            </Space>
          </Form.Item>

          <Space size="middle" style={{ display: 'flex' }} wrap>
            <Form.Item name="plaintiff" label="原告">
              <Input placeholder="原告名称" style={{ width: 260 }} />
            </Form.Item>
            <Form.Item name="defendant" label="被告">
              <Input placeholder="被告名称" style={{ width: 260 }} />
            </Form.Item>
          </Space>

          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="amount_in_dispute" label="标的额（元）">
              <Input type="number" placeholder="0" style={{ width: 160 }} />
            </Form.Item>
          </Space>

          {/* 统一第三人输入（方案A：标签式智能搜索） */}
          <Form.Item
            name="third_party_tags"
            label="第三人"
            tooltip="输入文字搜索已有客户，搜不到时按回车直接添加为自定义第三人"
          >
            <Select
              mode="tags"
              placeholder="输入关键词搜索客户，或直接输入第三人名称后按回车..."
              style={{ maxWidth: 600 }}
              options={clients.map((c) => ({
                value: toClientValue(c.id),
                label: `${c.name}${c.contact_person ? ` (${c.contact_person})` : ''}`,
              }))}
              showSearch
              filterOption={(input, option) => {
                const label = (option?.label ?? '').toLowerCase();
                const search = input.toLowerCase();
                return label.includes(search);
              }}
              tagRender={(props) => {
                const { value, closable, onClose } = props;
                const label = isClientValue(value as string)
                  ? (() => {
                      const cid = parseClientId(value as string);
                      const client = clients.find((cl) => cl.id === cid);
                      return client
                        ? `${client.name}${client.contact_person ? ` (${client.contact_person})` : ''}`
                        : String(value);
                    })()
                  : String(value);
                return (
                  <Tag
                    color={isClientValue(value as string) ? 'blue' : 'green'}
                    closable={closable}
                    onClose={onClose}
                    style={{ marginRight: 3 }}
                  >
                    {isClientValue(value as string) ? '📋 ' : '✏️ '}{label}
                  </Tag>
                );
              }}
              dropdownRender={(menu) => (
                <>
                  {menu}
                  <Divider style={{ margin: '8px 0' }} />
                  <div style={{ padding: '0 8px 8px', color: '#999', fontSize: 12 }}>
                    💡 输入文字后按 <strong>回车</strong> 可直接添加，无需从列表中选择
                  </div>
                </>
              )}
            />
          </Form.Item>

          {/* 关键日期 */}
          <Space size="middle" style={{ display: 'flex' }} wrap>
            <Form.Item name="acceptance_date" label="收案日期">
              <DatePicker style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="filing_date" label="立案日期">
              <DatePicker style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="trial_date" label="开庭日期">
              <DatePicker style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="judgment_date" label="判决日期">
              <DatePicker style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="closing_date" label="结案日期">
              <DatePicker style={{ width: 160 }} />
            </Form.Item>
          </Space>

          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} placeholder="案件的补充说明" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 快速新建客户弹窗 */}
      <Modal
        title="快速新建客户"
        open={clientModalOpen}
        onCancel={() => { setClientModalOpen(false); clientForm.resetFields(); }}
        onOk={handleQuickCreateClient}
        width={400}
        destroyOnClose
      >
        <Form form={clientForm} layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
            <Input placeholder="如：XX科技有限公司" />
          </Form.Item>
          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="contact_person" label="联系人">
              <Input placeholder="对接人姓名" style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="phone" label="电话">
              <Input placeholder="手机号" style={{ width: 160 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
};

// ==================== 文件归档 Tab ====================

interface CaseSimple {
  id: number;
  case_number: string;
}

const DocumentArchive: React.FC = () => {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [cases, setCases] = useState<CaseSimple[]>([]);
  const [clients, setClients] = useState<ClientSimple[]>([]);
  const [editDocId, setEditDocId] = useState<number | null>(null);
  const [editForm] = Form.useForm();

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (searchText) params.search = searchText;
      if (categoryFilter) params.category = categoryFilter;
      const res = await apiClient.get('/documents/', { params });
      setDocs(res.data);
    } catch {
      message.error('获取文档列表失败');
    } finally {
      setLoading(false);
    }
  }, [searchText, categoryFilter]);

  const fetchRefs = useCallback(async () => {
    try {
      const [caseRes, clientRes] = await Promise.all([
        apiClient.get('/cases/'),
        apiClient.get('/clients/simple'),
      ]);
      setCases(caseRes.data);
      setClients(clientRes.data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);
  useEffect(() => { fetchRefs(); }, [fetchRefs]);

  const handleUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_category', 'other');

    try {
      const res = await apiClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onSuccess(res.data, file);
      message.success(`${file.name} 上传成功`);
      fetchDocs();
    } catch {
      onError(new Error('上传失败'));
      message.error('上传失败');
    }
  };

  const handleDeleteDoc = async (id: number) => {
    try {
      await apiClient.delete(`/documents/${id}`);
      message.success('文档删除成功');
      fetchDocs();
    } catch {
      message.error('删除失败');
    }
  };

  const handleDownload = (doc: Document) => {
    const token = localStorage.getItem('auth_token');
    const url = `${apiClient.defaults.baseURL}/documents/${doc.id}/download`;
    // 用隐藏的 a 标签触发下载
    const a = document.createElement('a');
    a.href = url;
    a.download = doc.original_name;
    // 携带 token 的方式：用 fetch 下载
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.blob())
      .then((blob) => {
        const blobUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = doc.original_name;
        link.click();
        URL.revokeObjectURL(blobUrl);
      })
      .catch(() => message.error('下载失败'));
  };

  const saveDocMeta = async (docId: number) => {
    try {
      const values = editForm.getFieldsValue();
      const formData = new FormData();
      if (values.doc_category) formData.append('doc_category', values.doc_category);
      if (values.case_id) formData.append('case_id', String(values.case_id));
      if (values.client_id) formData.append('client_id', String(values.client_id));
      if (values.notes) formData.append('notes', values.notes);
      await apiClient.put(`/documents/${docId}`, formData);
      message.success('文档信息更新成功');
      setEditDocId(null);
      fetchDocs();
    } catch {
      message.error('保存失败');
    }
  };

  const catOptions = Object.entries(DOC_CATEGORY_LABELS).map(([value, label]) => ({ value, label }));

  const columns: ColumnsType<Document> = [
    {
      title: '文件名', dataIndex: 'original_name', width: 240, ellipsis: true,
      render: (name: string) => <a onClick={() => {
        const doc = docs.find((d) => d.original_name === name);
        if (doc) handleDownload(doc);
      }}>{name}</a>,
    },
    {
      title: '分类', dataIndex: 'doc_category', width: 130,
      render: (v: DocumentCategory) => {
        if (editDocId !== null) {
          // inline 编辑模式
          return null;
        }
        return <Tag>{DOC_CATEGORY_LABELS[v] || v}</Tag>;
      },
    },
    { title: '大小', dataIndex: 'size_display', width: 90, align: 'right' },
    { title: '关联案件', dataIndex: 'case_number', width: 160, render: (v: string | null) => v || '-' },
    { title: '关联客户', dataIndex: 'client_name', width: 140, render: (v: string | null) => v || '-' },
    { title: '版本', dataIndex: 'version', width: 60, align: 'center' },
    {
      title: '上传时间', dataIndex: 'uploaded_at', width: 120,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : '-',
    },
    {
      title: '操作', key: 'action', width: 160,
      render: (_: unknown, record: Document) => (
        <Space size="small">
          <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleDownload(record)}>
            下载
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
            setEditDocId(record.id);
            editForm.setFieldsValue({
              doc_category: record.doc_category,
              case_id: record.case_id,
              client_id: record.client_id,
              notes: record.notes,
            });
          }}>
            编辑
          </Button>
          <Popconfirm title="确定删除此文件？" onConfirm={() => handleDeleteDoc(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>文件归档</Title>
        <Space>
          <Input
            placeholder="搜索文件名..."
            prefix={<SearchOutlined />}
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onPressEnter={() => fetchDocs()}
            style={{ width: 220 }}
          />
          <Select
            placeholder="按分类筛选"
            allowClear
            value={categoryFilter || undefined}
            onChange={(v) => setCategoryFilter(v || '')}
            style={{ width: 140 }}
            options={catOptions}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchDocs}>刷新</Button>
        </Space>
      </div>

      {/* 拖拽+按钮双模式上传区域（方案三 C） */}
      <Card style={{ marginBottom: 16 }}>
        <Dragger
          multiple
          customRequest={handleUpload}
          showUploadList={false}
          style={{ padding: '16px 0' }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ fontSize: 40, color: '#1677ff' }} />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF、Word、图片等常见文件格式。可以同时上传多个文件。
          </p>
        </Dragger>
      </Card>

      <Table
        columns={columns}
        dataSource={docs}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 个文件` }}
        size="middle"
        expandable={{
          expandedRowRender: (record) => {
            if (record.id !== editDocId) return null;
            return (
              <Form form={editForm} layout="inline" style={{ padding: '12px 0' }}>
                <Form.Item name="doc_category" label="分类">
                  <Select options={catOptions} style={{ width: 150 }} />
                </Form.Item>
                <Form.Item name="case_id" label="关联案件">
                  <Select
                    allowClear
                    placeholder="选择案件"
                    style={{ width: 200 }}
                    options={cases.map((c) => ({ value: c.id, label: `${c.case_number}` }))}
                    showSearch
                    filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                  />
                </Form.Item>
                <Form.Item name="client_id" label="关联客户">
                  <Select
                    allowClear
                    placeholder="选择客户"
                    style={{ width: 200 }}
                    options={clients.map((c) => ({ value: c.id, label: c.name }))}
                    showSearch
                    filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                  />
                </Form.Item>
                <Form.Item name="notes" label="备注">
                  <Input placeholder="备注" style={{ width: 200 }} />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" onClick={() => saveDocMeta(record.id)}>保存</Button>
                  <Button style={{ marginLeft: 8 }} onClick={() => setEditDocId(null)}>取消</Button>
                </Form.Item>
              </Form>
            );
          },
          expandedRowKeys: editDocId ? [editDocId] : [],
        }}
      />
    </div>
  );
};

// ==================== 主页面 ====================

const CasesPage: React.FC = () => {
  const tabItems = [
    { key: 'cases', label: '案件管理', children: <CaseManagement /> },
    { key: 'docs', label: '文件归档', children: <DocumentArchive /> },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>案件与文档中心</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
};

export default CasesPage;
