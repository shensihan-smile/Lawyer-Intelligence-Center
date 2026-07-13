import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Typography, Card, Tabs, Button, Space, Modal, Form, Input, Select,
  DatePicker, TimePicker, Tag, message, Table, Popconfirm, Statistic,
  InputNumber, Radio, Alert, Empty, Descriptions, Divider, List,
} from 'antd';
import {
  PlusOutlined, PlayCircleOutlined, PauseCircleOutlined,
  EditOutlined, DeleteOutlined, DollarOutlined,
  FilePdfOutlined, ClockCircleOutlined, SettingOutlined,
  FileTextOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import apiClient from '../../utils/api';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Countdown } = Statistic;

// ==================== 类型 ====================

interface TimeRecord {
  id: number;
  case_id: number | null;
  case_number: string | null;
  work_category: string;
  description: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  is_billed: boolean;
  created_at: string;
}

interface BillingConfigItem {
  id: number;
  name: string;
  billing_method: string;
  unit_price: number;
  is_default: boolean;
  notes: string;
}

interface CaseSimple { id: number; case_number: string; case_reason: string; }

interface ClientSimple { id: number; name: string; }

interface BillItem {
  id: number; case_id: number | null; case_number: string | null;
  description: string; billing_method: string;
  unit_price: number; quantity: number; amount: number;
}

interface Bill {
  id: number; bill_number: string; client_id: number;
  client_name: string;
  billing_period_start: string; billing_period_end: string;
  total_amount: number; status: string;
  notes: string; generated_at: string; exported_at: string | null;
  items: BillItem[];
}

const WORK_LABELS: Record<string, string> = {
  legal_research: '法律研究', drafting: '文书起草',
  hearing: '庭审出庭', consultation: '客户咨询', other: '其他',
};

const METHOD_LABELS: Record<string, string> = {
  hourly: '按小时', fixed: '按件', percentage: '按比例',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'default', generated: 'blue', exported: 'orange', paid: 'green',
};

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿', generated: '已生成', exported: '已导出', paid: '已收款',
};

// ==================== 工时记录 Tab ====================

const TimeTrackingTab: React.FC = () => {
  const [records, setRecords] = useState<TimeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTimer, setActiveTimer] = useState<any>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<TimeRecord | null>(null);
  const [cases, setCases] = useState<CaseSimple[]>([]);
  const [form] = Form.useForm();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/billing/time-records');
      setRecords(res.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  const checkActiveTimer = useCallback(async () => {
    try {
      const res = await apiClient.get('/billing/time-records/active');
      setActiveTimer(res.data?.active ? res.data : null);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchRecords(); checkActiveTimer(); }, [fetchRecords, checkActiveTimer]);
  useEffect(() => {
    apiClient.get('/cases/').then(r => setCases(r.data)).catch(() => {});
  }, []);

  // 实时刷新计时器
  useEffect(() => {
    if (activeTimer?.active) {
      timerRef.current = setInterval(checkActiveTimer, 10000);
      return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }
  }, [activeTimer?.active]);

  const handleStart = async () => {
    try {
      const values = await form.validateFields();
      const res = await apiClient.post('/billing/time-records/start', {
        case_id: values.case_id || null,
        work_category: values.work_category || 'other',
        description: values.description || '',
      });
      setActiveTimer({ active: true, record: res.data, elapsed_minutes: 0 });
      setModalOpen(false);
      form.resetFields();
    } catch (e: any) {
      if (e?.response?.data?.detail) message.error(e.response.data.detail);
    }
  };

  const handleStop = async () => {
    if (!activeTimer?.record?.id) return;
    try {
      await apiClient.post(`/billing/time-records/${activeTimer.record.id}/stop`);
      message.success(`计时结束，${activeTimer.elapsed_minutes || 0} 分钟`);
      setActiveTimer(null);
      fetchRecords();
    } catch { message.error('停止失败'); }
  };

  const handleManualAdd = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        case_id: values.case_id || null,
        work_category: values.work_category || 'other',
        description: values.description || '',
        start_time: values.time_range[0].toISOString(),
        end_time: values.time_range[1].toISOString(),
      };
      await apiClient.post('/billing/time-records', payload);
      message.success('工时记录已添加');
      setModalOpen(false);
      form.resetFields();
      fetchRecords();
    } catch (e: any) {
      if (e?.response?.data?.detail) message.error(e.response.data.detail);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/billing/time-records/${id}`);
      message.success('已删除');
      fetchRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const formatDuration = (mins: number) => {
    if (mins < 60) return `${mins} 分钟`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m > 0 ? `${h}小时${m}分钟` : `${h} 小时`;
  };

  const columns = [
    { title: '案件', dataIndex: 'case_number', width: 160, render: (v: string | null) => v || '-' },
    {
      title: '分类', dataIndex: 'work_category', width: 100,
      render: (v: string) => <Tag>{WORK_LABELS[v] || v}</Tag>,
    },
    { title: '描述', dataIndex: 'description', ellipsis: true },
    {
      title: '开始', dataIndex: 'start_time', width: 130,
      render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '结束', dataIndex: 'end_time', width: 130,
      render: (v: string, r: TimeRecord) =>
        r.duration_minutes === 0 && v ? '计时中...' : v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '时长', dataIndex: 'duration_minutes', width: 100,
      render: (v: number) => v > 0 ? formatDuration(v) : <Tag color="processing">计时中</Tag>,
    },
    {
      title: '状态', dataIndex: 'is_billed', width: 80,
      render: (v: boolean) => v ? <Tag color="green">已计费</Tag> : <Tag>未计费</Tag>,
    },
    {
      title: '操作', key: 'action', width: 100,
      render: (_: unknown, r: TimeRecord) => (
        <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)} disabled={r.is_billed}>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} disabled={r.is_billed}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      {/* 计时器区域 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space size="large">
            <Title level={5} style={{ margin: 0 }}>⌛ 工时计时器</Title>
            {activeTimer?.active ? (
              <Space>
                <Tag color="processing">计时中</Tag>
                <Text strong>
                  {activeTimer.record?.case_number || '未关联案件'}
                  {activeTimer.record?.description ? ` - ${activeTimer.record.description}` : ''}
                </Text>
                <Text type="secondary">
                  已过 {formatDuration(activeTimer.elapsed_minutes || 0)}
                </Text>
              </Space>
            ) : (
              <Text type="secondary">点击下方按钮开始计时</Text>
            )}
          </Space>
          <Space>
            {activeTimer?.active ? (
              <Button type="primary" danger icon={<PauseCircleOutlined />} onClick={handleStop} size="large">
                停止计时
              </Button>
            ) : (
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => setModalOpen(true)} size="large">
                开始计时
              </Button>
            )}
            <Button icon={<PlusOutlined />} onClick={() => {
              setEditRecord(null);
              form.resetFields();
              setModalOpen(true);
            }}>
              手动补录
            </Button>
          </Space>
        </div>
      </Card>

      {/* 工时列表 */}
      <Table columns={columns} dataSource={records} rowKey="id" loading={loading}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条记录` }} size="middle"
      />

      {/* 计时/补录弹窗 */}
      <Modal
        title={activeTimer?.active ? '开始计时' : '添加工时记录'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        onOk={activeTimer?.active ? undefined : handleManualAdd}
        footer={activeTimer?.active ? [
          <Button key="cancel" onClick={() => { setModalOpen(false); form.resetFields(); }}>取消</Button>,
          <Button key="start" type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>开始计时</Button>,
        ] : undefined}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="case_id" label="关联案件">
            <Select allowClear placeholder="选择案件（可选）" showSearch
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
              options={cases.map(c => ({ value: c.id, label: `${c.case_number} ${c.case_reason || ''}` }))}
            />
          </Form.Item>
          <Form.Item name="work_category" label="工作分类" initialValue="other">
            <Select style={{ width: 160 }}
              options={Object.entries(WORK_LABELS).map(([v, l]) => ({ value: v, label: l }))}
            />
          </Form.Item>
          {!activeTimer?.active && (
            <Form.Item name="time_range" label="时间范围" rules={[{ required: true, message: '请选择' }]}>
              <DatePicker.RangePicker
                showTime={{ format: 'HH:mm' }}
                format="YYYY-MM-DD HH:mm"
                style={{ width: '100%' }}
              />
            </Form.Item>
          )}
          <Form.Item name="description" label="工作描述">
            <TextArea rows={2} placeholder="简述工作内容" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// ==================== 计费配置 Tab ====================

const BillingConfigTab: React.FC = () => {
  const [configs, setConfigs] = useState<BillingConfigItem[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editData, setEditData] = useState<BillingConfigItem | null>(null);
  const [form] = Form.useForm();

  const fetchConfigs = useCallback(async () => {
    try {
      const res = await apiClient.get('/billing/config');
      setConfigs(res.data || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editData) {
        await apiClient.put(`/billing/config/${editData.id}`, values);
      } else {
        await apiClient.post('/billing/config', values);
      }
      message.success(editData ? '已更新' : '已创建');
      setModalOpen(false);
      fetchConfigs();
    } catch (e: any) {
      if (e?.response?.data?.detail) message.error(e.response.data.detail);
    }
  };

  const handleDelete = async (id: number) => {
    await apiClient.delete(`/billing/config/${id}`);
    message.success('已删除');
    fetchConfigs();
  };

  const columns = [
    { title: '名称', dataIndex: 'name', width: 200 },
    {
      title: '计费方式', dataIndex: 'billing_method', width: 100,
      render: (v: string) => <Tag color="blue">{METHOD_LABELS[v] || v}</Tag>,
    },
    {
      title: '费率', dataIndex: 'unit_price', width: 150,
      render: (v: number, r: BillingConfigItem) => {
        if (r.billing_method === 'percentage') return `${v}%`;
        if (r.billing_method === 'fixed') return `${v.toLocaleString()} 元/件`;
        return `${v.toLocaleString()} 元/小时`;
      },
    },
    {
      title: '默认', dataIndex: 'is_default', width: 80,
      render: (v: boolean) => v ? <Tag color="green">默认</Tag> : '',
    },
    { title: '备注', dataIndex: 'notes', ellipsis: true },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, r: BillingConfigItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
            setEditData(r);
            form.setFieldsValue(r);
            setModalOpen(true);
          }}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Alert message="计费配置说明" type="info" showIcon style={{ marginBottom: 16 }}
        description={
          <span>
            <strong>默认配置</strong>应用于所有案件；可以在案件编辑中单独设置<strong>案件级特殊费率</strong>（覆盖默认）。
            <br />计费方式：「按小时」= 时长×费率、「按件」= 固定费用、「按比例」= 案件标的额×百分比。
          </span>
        }
      />

      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditData(null);
          form.resetFields();
          form.setFieldsValue({ billing_method: 'hourly', unit_price: 2000, is_default: false });
          setModalOpen(true);
        }}>新增配置</Button>
      </div>

      <Table columns={columns} dataSource={configs} rowKey="id" pagination={false} size="middle" />

      <Modal title={editData ? '编辑配置' : '新增配置'} open={modalOpen}
        onCancel={() => setModalOpen(false)} onOk={handleSave} width={480} destroyOnClose>
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：默认小时费率、老客户优惠价" />
          </Form.Item>
          <Form.Item name="billing_method" label="计费方式">
            <Radio.Group>
              <Radio.Button value="hourly">按小时</Radio.Button>
              <Radio.Button value="fixed">按件</Radio.Button>
              <Radio.Button value="percentage">按比例</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="unit_price" label="费率" rules={[{ required: true, message: '请输入费率' }]}>
            <InputNumber min={0} step={100} style={{ width: 200 }} addonAfter={
              Form.useWatch('billing_method', form) === 'percentage' ? '%' :
              Form.useWatch('billing_method', form) === 'fixed' ? '元/件' : '元/小时'
            } />
          </Form.Item>
          <Form.Item name="is_default" label="设为默认" valuePropName="checked">
            <Select options={[{ value: true, label: '是（其他配置的默认标记将被取消）' }, { value: false, label: '否' }]} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input placeholder="可选备注" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// ==================== 账单管理 Tab ====================

const BillManagementTab: React.FC = () => {
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(false);
  const [genModalOpen, setGenModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
  const [clients, setClients] = useState<ClientSimple[]>([]);
  const [genForm] = Form.useForm();
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchResult, setBatchResult] = useState<any>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchForm] = Form.useForm();

  const fetchBills = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/billing/bills');
      setBills(res.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchBills(); }, [fetchBills]);
  useEffect(() => {
    apiClient.get('/clients/simple').then(r => setClients(r.data)).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    try {
      const values = await genForm.validateFields();
      const res = await apiClient.post('/billing/bills/generate', {
        client_id: values.client_id,
        period_start: values.period[0].format('YYYY-MM-DD'),
        period_end: values.period[1].format('YYYY-MM-DD'),
        case_id: values.case_id || null,
        firm_name: values.firm_name || '',
        firm_address: values.firm_address || '',
        firm_phone: values.firm_phone || '',
        lawyer_name: values.lawyer_name || '',
        notes: values.notes || '',
        bank_info: values.bank_info || '',
      });
      message.success(`账单 ${res.data.bill_number} 已生成`);
      setGenModalOpen(false);
      fetchBills();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '生成失败');
    }
  };

  const handleBatchGenerate = async () => {
    try {
      const values = await batchForm.validateFields();
      setBatchLoading(true);
      const res = await apiClient.post('/billing/bills/batch-generate', {
        client_id: 0,  // 批量模式不需要 client_id，后端会遍历所有客户
        period_start: values.period[0].format('YYYY-MM-DD'),
        period_end: values.period[1].format('YYYY-MM-DD'),
        firm_name: values.firm_name || '',
        firm_address: values.firm_address || '',
        firm_phone: values.firm_phone || '',
        lawyer_name: values.lawyer_name || '',
        notes: values.notes || '',
        bank_info: values.bank_info || '',
      });
      setBatchResult(res.data);
      setBatchModalOpen(false);
      fetchBills();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '批量出账失败');
    } finally {
      setBatchLoading(false);
    }
  };

  const handleExportPdf = async (bill: Bill) => {
    try {
      const res = await apiClient.get(`/billing/bills/${bill.id}/pdf`, {
        params: {
          firm_name: 'XX律师事务所',
          firm_address: '请在实际使用时填写地址',
          firm_phone: '请填写电话',
          lawyer_name: '请填写律师姓名',
        },
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${bill.bill_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('PDF 已下载');
      fetchBills();
    } catch { message.error('导出失败'); }
  };

  const handleMarkPaid = async (bill: Bill) => {
    await apiClient.put(`/billing/bills/${bill.id}/status`, { status: 'paid' });
    message.success('已标记为已收款');
    fetchBills();
  };

  const handleDelete = async (id: number) => {
    await apiClient.delete(`/billing/bills/${id}`);
    message.success('已删除');
    fetchBills();
  };

  const columns = [
    { title: '账单编号', dataIndex: 'bill_number', width: 200, render: (v: string) => <a onClick={() => {
      const bill = bills.find(b => b.bill_number === v);
      if (bill) { setSelectedBill(bill); setDetailModalOpen(true); }
    }}>{v}</a> },
    { title: '客户', dataIndex: 'client_name', width: 150 },
    {
      title: '计费期间', key: 'period', width: 200,
      render: (_: unknown, r: Bill) =>
        `${r.billing_period_start ? dayjs(r.billing_period_start).format('YYYY-MM-DD') : ''} ~ ${r.billing_period_end ? dayjs(r.billing_period_end).format('YYYY-MM-DD') : ''}`,
    },
    {
      title: '金额', dataIndex: 'total_amount', width: 120, align: 'right' as const,
      render: (v: number) => <Text strong>{v.toLocaleString()} 元</Text>,
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (v: string) => <Tag color={STATUS_COLORS[v]}>{STATUS_LABELS[v]}</Tag>,
    },
    {
      title: '生成时间', dataIndex: 'generated_at', width: 120,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : '-',
    },
    {
      title: '操作', key: 'action', width: 180,
      render: (_: unknown, r: Bill) => (
        <Space size="small">
          <Button type="link" size="small" icon={<FilePdfOutlined />} onClick={() => handleExportPdf(r)}>PDF</Button>
          {r.status !== 'paid' && (
            <Button type="link" size="small" icon={<CheckCircleOutlined />}
              onClick={() => handleMarkPaid(r)}>收款</Button>
          )}
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Alert message="从工时记录自动生成对账单，支持 PDF 导出。请先在「工时记录」中录入工作时长，然后在此生成账单。"
          type="info" showIcon style={{ flex: 1 }} />
        <Button type="primary" icon={<FileTextOutlined />} size="large"
          style={{ marginLeft: 16 }} onClick={() => {
            genForm.resetFields();
            setGenModalOpen(true);
          }}>生成账单</Button>
        <Button icon={<FileTextOutlined />} size="large"
          style={{ marginLeft: 8 }} onClick={() => {
            batchForm.resetFields();
            setBatchModalOpen(true);
          }}>周期出账</Button>
      </div>

      <Table columns={columns} dataSource={bills} rowKey="id" loading={loading}
        pagination={{ pageSize: 20 }} size="middle"
      />

      {/* 生成账单弹窗 */}
      <Modal title="生成账单" open={genModalOpen} onCancel={() => setGenModalOpen(false)}
        onOk={handleGenerate} width={600} destroyOnClose>
        <Form form={genForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="client_id" label="选择客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select placeholder="选择要出账的客户" showSearch
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
              options={clients.map(c => ({ value: c.id, label: c.name }))}
            />
          </Form.Item>
          <Form.Item name="period" label="计费期间" rules={[{ required: true, message: '请选择期间' }]}>
            <DatePicker.RangePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="case_id" label="限定案件（可选）">
            <Select allowClear placeholder="不选则包含该客户所有案件" />
          </Form.Item>
          <Divider>律所信息（用于账单抬头）</Divider>
          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="firm_name" label="律所名称"><Input placeholder="XX律师事务所" style={{ width: 200 }} /></Form.Item>
            <Form.Item name="lawyer_name" label="律师姓名"><Input placeholder="律师姓名" style={{ width: 150 }} /></Form.Item>
            <Form.Item name="firm_phone" label="电话"><Input placeholder="电话" style={{ width: 150 }} /></Form.Item>
          </Space>
          <Form.Item name="firm_address" label="地址"><Input placeholder="律所地址" /></Form.Item>
          <Form.Item name="bank_info" label="银行账户"><Input placeholder="开户行及账号" /></Form.Item>
          <Form.Item name="notes" label="备注"><TextArea rows={2} placeholder="账单备注，如付款方式等" /></Form.Item>
        </Form>
      </Modal>

      {/* 周期出账弹窗 */}
      <Modal title="周期出账" open={batchModalOpen}
        onCancel={() => setBatchModalOpen(false)}
        onOk={handleBatchGenerate}
        confirmLoading={batchLoading}
        width={600} destroyOnClose>
        <Alert message="系统将自动为所有有未计费工时的客户各生成一份账单，无需逐个选择客户。"
          type="info" showIcon style={{ marginBottom: 16 }} />
        <Form form={batchForm} layout="vertical">
          <Form.Item name="period" label="计费期间" rules={[{ required: true, message: '请选择期间' }]}>
            <DatePicker.RangePicker
              style={{ width: '100%' }}
              presets={[
                { label: '本月', value: [dayjs().startOf('month'), dayjs().endOf('month')] },
                { label: '上个月', value: [dayjs().subtract(1, 'month').startOf('month'), dayjs().subtract(1, 'month').endOf('month')] },
                { label: '本季度', value: [dayjs().startOf('quarter'), dayjs().endOf('quarter')] },
                { label: '本年', value: [dayjs().startOf('year'), dayjs().endOf('year')] },
              ]}
            />
          </Form.Item>
          <Divider>律所信息（用于账单抬头）</Divider>
          <Space size="middle" style={{ display: 'flex' }}>
            <Form.Item name="firm_name" label="律所名称"><Input placeholder="XX律师事务所" style={{ width: 200 }} /></Form.Item>
            <Form.Item name="lawyer_name" label="律师姓名"><Input placeholder="律师姓名" style={{ width: 150 }} /></Form.Item>
            <Form.Item name="firm_phone" label="电话"><Input placeholder="电话" style={{ width: 150 }} /></Form.Item>
          </Space>
          <Form.Item name="firm_address" label="地址"><Input placeholder="律所地址" /></Form.Item>
          <Form.Item name="bank_info" label="银行账户"><Input placeholder="开户行及账号" /></Form.Item>
          <Form.Item name="notes" label="备注"><TextArea rows={2} placeholder="如：2026年6月法律服务费" /></Form.Item>
        </Form>
      </Modal>

      {/* 批量出账结果弹窗 */}
      <Modal title="出账结果" open={!!batchResult}
        onCancel={() => setBatchResult(null)}
        footer={[
          <Button key="close" onClick={() => setBatchResult(null)}>关闭</Button>,
          <Button key="export" type="primary" icon={<FilePdfOutlined />}
            onClick={async () => {
              if (!batchResult?.bills) return;
              for (const bill of batchResult.bills) {
                try {
                  const res = await apiClient.get(`/billing/bills/${bill.id}/pdf`, {
                    params: { firm_name: '律师事务所' },
                    responseType: 'blob',
                  });
                  const blob = new Blob([res.data], { type: 'application/pdf' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${bill.bill_number}.pdf`;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch { /* skip */ }
              }
              message.success('所有 PDF 已开始下载');
            }}>
            批量导出全部 PDF
          </Button>,
        ]}
        width={700}>
        {batchResult && (
          <>
            <Descriptions column={3} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="出账周期">{batchResult.period}</Descriptions.Item>
              <Descriptions.Item label="生成账单">{batchResult.bills?.length || 0} 份</Descriptions.Item>
              <Descriptions.Item label="总金额">
                <Text strong>¥ {(batchResult.total_amount || 0).toLocaleString()}</Text>
              </Descriptions.Item>
            </Descriptions>
            {batchResult.errors && batchResult.errors.length > 0 && (
              <Alert type="warning" message={`${batchResult.errors.length} 个客户出账失败`}
                description={batchResult.errors.join('；')} showIcon style={{ marginBottom: 12 }} />
            )}
            <Table dataSource={batchResult.bills || []} rowKey="id" pagination={false} size="small"
              columns={[
                { title: '账单编号', dataIndex: 'bill_number', width: 180 },
                { title: '客户', dataIndex: 'client_name' },
                { title: '金额', dataIndex: 'total_amount', align: 'right' as const,
                  render: (v: number) => `${v.toLocaleString()} 元` },
                { title: '状态', dataIndex: 'status', width: 80,
                  render: (v: string) => <Tag color={STATUS_COLORS[v]}>{STATUS_LABELS[v]}</Tag> },
              ]}
            />
          </>
        )}
      </Modal>

      {/* 账单详情弹窗 */}
      <Modal title={`账单详情 - ${selectedBill?.bill_number || ''}`} open={detailModalOpen}
        onCancel={() => setDetailModalOpen(false)} width={700} footer={null}>
        {selectedBill && (
          <>
            <Descriptions column={3} size="small" bordered>
              <Descriptions.Item label="客户">{selectedBill.client_name}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLORS[selectedBill.status]}>{STATUS_LABELS[selectedBill.status]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="金额"><Text strong>{selectedBill.total_amount.toLocaleString()} 元</Text></Descriptions.Item>
              <Descriptions.Item label="期间" span={3}>
                {selectedBill.billing_period_start ? dayjs(selectedBill.billing_period_start).format('YYYY-MM-DD') : ''}
                ~{selectedBill.billing_period_end ? dayjs(selectedBill.billing_period_end).format('YYYY-MM-DD') : ''}
              </Descriptions.Item>
            </Descriptions>
            <Divider>明细</Divider>
            <Table dataSource={selectedBill.items || []} rowKey="id" pagination={false} size="small"
              columns={[
                { title: '描述', dataIndex: 'description' },
                { title: '方式', dataIndex: 'billing_method', width: 80, render: (v: string) => METHOD_LABELS[v] },
                { title: '数量', dataIndex: 'quantity', width: 80, align: 'right' as const, render: (v: number) => v.toFixed(1) },
                { title: '单价', dataIndex: 'unit_price', width: 100, align: 'right' as const, render: (v: number) => v.toLocaleString() },
                { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const,
                  render: (v: number) => <Text strong>{v.toLocaleString()} 元</Text> },
              ]}
            />
            <div style={{ textAlign: 'right', marginTop: 16 }}>
              <Text strong style={{ fontSize: 16 }}>
                合计：¥ {selectedBill.total_amount.toLocaleString()}
              </Text>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
};

// ==================== 主页面 ====================

const BillingPage: React.FC = () => {
  const tabItems = [
    { key: 'time', label: '工时记录', children: <TimeTrackingTab /> },
    { key: 'config', label: '计费配置', children: <BillingConfigTab /> },
    { key: 'bills', label: '账单管理', children: <BillManagementTab /> },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>财务账单管理</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
};

export default BillingPage;
