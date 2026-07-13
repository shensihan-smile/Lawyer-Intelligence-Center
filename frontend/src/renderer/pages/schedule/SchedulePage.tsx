import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Tabs, Button, Space, Modal, Form, Input, Select,
  DatePicker, TimePicker, Tag, message, Segmented,
  Alert, Empty, Divider, Descriptions, Table, List,
} from 'antd';
import {
  PlusOutlined, CalendarOutlined, MessageOutlined,
  EditOutlined, DeleteOutlined, ExportOutlined, ThunderboltOutlined,
  ClockCircleOutlined, EnvironmentOutlined, UserOutlined,
} from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import apiClient from '../../utils/api';
import { SCHEDULE_TYPE_LABELS, ScheduleType } from '../../types';

const { Title, Text } = Typography;
const { TextArea } = Input;

// ==================== 常量 ====================

const TYPE_COLORS: Record<string, string> = {
  hearing: 'red', meeting: 'blue', consultation: 'green',
  deadline: 'orange', other: 'default',
};

const HOURS = Array.from({ length: 16 }, (_, i) => i + 6); // 6:00 - 21:00

// ==================== 日程类型（本地） ====================

interface ScheduleItem {
  id: number;
  title: string;
  schedule_type: string;
  case_id: number | null;
  case_number: string | null;
  case_reason: string | null;
  start_time: string;
  end_time: string;
  location: string;
  judge: string;
  notes: string;
  is_parsed_from_sms: boolean;
  created_at: string;
}

interface ClientSimple {
  id: number;
  name: string;
  contact_person: string;
}

interface CaseSimple {
  id: number;
  case_number: string;
  case_reason: string;
}

// ==================== 日程表单弹窗 ====================

const ScheduleFormModal: React.FC<{
  open: boolean;
  editData: ScheduleItem | null;
  defaultStart: string | null;
  defaultEnd: string | null;
  onClose: () => void;
  onSuccess: () => void;
}> = ({ open, editData, defaultStart, defaultEnd, onClose, onSuccess }) => {
  const [form] = Form.useForm();
  const [cases, setCases] = useState<CaseSimple[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiClient.get('/cases/').then(r => setCases(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (open) {
      if (editData) {
        form.setFieldsValue({
          title: editData.title,
          schedule_type: editData.schedule_type,
          case_id: editData.case_id,
          date: dayjs(editData.start_time),
          time_range: [dayjs(editData.start_time), dayjs(editData.end_time)],
          location: editData.location,
          judge: editData.judge,
          notes: editData.notes,
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          schedule_type: 'hearing',
          date: defaultStart ? dayjs(defaultStart) : dayjs(),
          time_range: [
            defaultStart ? dayjs(defaultStart) : dayjs().hour(9).minute(0),
            defaultEnd ? dayjs(defaultEnd) : dayjs().hour(12).minute(0),
          ],
        });
      }
    }
  }, [open, editData, defaultStart, defaultEnd, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const payload = {
        title: values.title,
        schedule_type: values.schedule_type,
        case_id: values.case_id || null,
        start_time: values.time_range[0].toISOString(),
        end_time: values.time_range[1].toISOString(),
        location: values.location || '',
        judge: values.judge || '',
        notes: values.notes || '',
      };

      let res;
      if (editData) {
        res = await apiClient.put(`/schedules/${editData.id}`, payload);
      } else {
        res = await apiClient.post('/schedules/', payload);
      }

      if (res.data?.conflicts?.length > 0) {
        message.warning(`检测到 ${res.data.conflicts.length} 个时间冲突，请注意`);
      } else {
        message.success(editData ? '已更新' : '已创建');
      }
      onSuccess();
    } catch (e: any) {
      if (e?.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={editData ? '编辑日程' : '新建日程'}
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      confirmLoading={loading}
      width={560}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
        <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
          <Input placeholder="如：XX案件开庭审理" />
        </Form.Item>

        <Space size="middle" style={{ display: 'flex' }}>
          <Form.Item name="schedule_type" label="类型">
            <Select style={{ width: 120 }}
              options={Object.entries(SCHEDULE_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
            />
          </Form.Item>
          <Form.Item name="case_id" label="关联案件">
            <Select
              allowClear placeholder="选择案件（可选）" style={{ width: 260 }}
              showSearch
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
              options={cases.map(c => ({ value: c.id, label: `${c.case_number} ${c.case_reason || ''}` }))}
            />
          </Form.Item>
        </Space>

        <Space size="middle" style={{ display: 'flex' }}>
          <Form.Item name="date" label="日期">
            <DatePicker style={{ width: 160 }} />
          </Form.Item>
          <Form.Item name="time_range" label="时间范围" rules={[{ required: true, message: '请选择时间' }]}>
            <TimePicker.RangePicker format="HH:mm" minuteStep={15} style={{ width: 240 }} />
          </Form.Item>
        </Space>

        <Space size="middle" style={{ display: 'flex' }}>
          <Form.Item name="location" label="地点">
            <Input placeholder="法院、法庭" style={{ width: 240 }} />
          </Form.Item>
          <Form.Item name="judge" label="法官">
            <Input placeholder="承办法官" style={{ width: 160 }} />
          </Form.Item>
        </Space>

        <Form.Item name="notes" label="备注">
          <TextArea rows={2} placeholder="补充说明" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

// ==================== 日程详情弹窗 ====================

const ScheduleDetailModal: React.FC<{
  schedule: ScheduleItem | null;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}> = ({ schedule, onClose, onEdit, onDelete }) => {
  if (!schedule) return null;
  return (
    <Modal
      title={schedule.title}
      open={!!schedule}
      onCancel={onClose}
      width={500}
      footer={[
        <Button key="delete" danger icon={<DeleteOutlined />} onClick={onDelete}>删除</Button>,
        <Button key="edit" type="primary" icon={<EditOutlined />} onClick={onEdit}>编辑</Button>,
      ]}
    >
      <Descriptions column={2} size="small" style={{ marginTop: 8 }}>
        <Descriptions.Item label="类型">
          <Tag color={TYPE_COLORS[schedule.schedule_type]}>
            {SCHEDULE_TYPE_LABELS[schedule.schedule_type as ScheduleType]}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="关联案件">
          {schedule.case_number || '无'}
        </Descriptions.Item>
        <Descriptions.Item label="开始时间">
          {dayjs(schedule.start_time).format('YYYY-MM-DD HH:mm')}
        </Descriptions.Item>
        <Descriptions.Item label="结束时间">
          {dayjs(schedule.end_time).format('YYYY-MM-DD HH:mm')}
        </Descriptions.Item>
        {schedule.location && (
          <Descriptions.Item label="地点" span={2}>
            <EnvironmentOutlined /> {schedule.location}
          </Descriptions.Item>
        )}
        {schedule.judge && (
          <Descriptions.Item label="法官" span={2}>
            <UserOutlined /> {schedule.judge}
          </Descriptions.Item>
        )}
        {schedule.notes && (
          <Descriptions.Item label="备注" span={2}>{schedule.notes}</Descriptions.Item>
        )}
        {schedule.is_parsed_from_sms && (
          <Descriptions.Item label="来源" span={2}>
            <Tag icon={<MessageOutlined />}>12368 短信解析</Tag>
          </Descriptions.Item>
        )}
      </Descriptions>
    </Modal>
  );
};

// ==================== 日历视图（主视图） ====================

const CalendarViewTab: React.FC = () => {
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [view, setView] = useState<'month' | 'week' | 'day'>('month');
  const [currentDate, setCurrentDate] = useState(dayjs());
  const [formOpen, setFormOpen] = useState(false);
  const [editData, setEditData] = useState<ScheduleItem | null>(null);
  const [defaultStart, setDefaultStart] = useState<string | null>(null);
  const [defaultEnd, setDefaultEnd] = useState<string | null>(null);
  const [detailSchedule, setDetailSchedule] = useState<ScheduleItem | null>(null);

  // 计算日期范围
  const getDateRange = useCallback((): [string, string] => {
    if (view === 'month') {
      return [
        currentDate.startOf('month').format('YYYY-MM-DD'),
        currentDate.endOf('month').format('YYYY-MM-DD'),
      ];
    }
    if (view === 'week') {
      // 简单计算：从当前日期往前推到周一
      const dayOfWeek = currentDate.day(); // 0=Sun
      const monday = currentDate.subtract(dayOfWeek === 0 ? 6 : dayOfWeek - 1, 'day');
      const sunday = monday.add(6, 'day');
      return [monday.format('YYYY-MM-DD'), sunday.format('YYYY-MM-DD')];
    }
    return [currentDate.format('YYYY-MM-DD'), currentDate.format('YYYY-MM-DD')];
  }, [view, currentDate]);

  // 获取日程
  const fetchSchedules = useCallback(async () => {
    try {
      const [start, end] = getDateRange();
      const res = await apiClient.get('/schedules/', {
        params: { start_date: start, end_date: end },
      });
      setSchedules(res.data || []);
    } catch { /* ignore */ }
  }, [getDateRange]);

  useEffect(() => {
    fetchSchedules();
  }, [fetchSchedules]);

  // 冲突检测
  const getConflictingIds = (): Set<number> => {
    const ids = new Set<number>();
    for (let i = 0; i < schedules.length; i++) {
      for (let j = i + 1; j < schedules.length; j++) {
        const a = schedules[i], b = schedules[j];
        if (dayjs(a.start_time) < dayjs(b.end_time) && dayjs(a.end_time) > dayjs(b.start_time)) {
          ids.add(a.id);
          ids.add(b.id);
        }
      }
    }
    return ids;
  };
  const conflictIds = getConflictingIds();

  // 某天的日程
  const getDaySchedules = (date: Dayjs): ScheduleItem[] => {
    const ds = date.format('YYYY-MM-DD');
    return schedules.filter(s => dayjs(s.start_time).format('YYYY-MM-DD') === ds);
  };

  // 操作
  const handleNew = (start?: Dayjs, end?: Dayjs) => {
    setEditData(null);
    setDefaultStart(start ? start.toISOString() : dayjs().hour(9).minute(0).toISOString());
    setDefaultEnd(end ? end.toISOString() : dayjs().hour(12).minute(0).toISOString());
    setFormOpen(true);
  };

  const handleEdit = (s: ScheduleItem) => {
    setEditData(s);
    setDefaultStart(null);
    setDefaultEnd(null);
    setFormOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/schedules/${id}`);
      message.success('已删除');
      setDetailSchedule(null);
      fetchSchedules();
    } catch { message.error('删除失败'); }
  };

  const handleExport = async () => {
    try {
      const [start, end] = getDateRange();
      const res = await apiClient.get('/schedules/export-ical', {
        params: { start_date: start, end_date: end },
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'text/calendar' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'lawyer_schedule.ics';
      a.click();
      URL.revokeObjectURL(url);
      message.success('日历导出成功');
    } catch { message.error('导出失败'); }
  };

  // 导航
  const goPrev = () => {
    const fn: Record<string, () => dayjs.Dayjs> = {
      month: () => currentDate.subtract(1, 'month'),
      week: () => currentDate.subtract(1, 'week'),
      day: () => currentDate.subtract(1, 'day'),
    };
    setCurrentDate(fn[view]());
  };

  const goNext = () => {
    const fn: Record<string, () => dayjs.Dayjs> = {
      month: () => currentDate.add(1, 'month'),
      week: () => currentDate.add(1, 'week'),
      day: () => currentDate.add(1, 'day'),
    };
    setCurrentDate(fn[view]());
  };

  // ====== 月视图表格 ======
  const renderMonthView = () => {
    // 计算当月第一天和最后一天
    const firstDay = currentDate.startOf('month');
    const lastDay = currentDate.endOf('month');
    const daysInMonth = currentDate.daysInMonth();

    // 该月第一天是星期几（0=Sun）
    const startDayOfWeek = firstDay.day();

    // 构建日历网格：6行 x 7列
    const weeks: Dayjs[][] = [];
    let day = firstDay.subtract(startDayOfWeek, 'day'); // 从上周日开始
    for (let w = 0; w < 6; w++) {
      const week: Dayjs[] = [];
      for (let d = 0; d < 7; d++) {
        week.push(day);
        day = day.add(1, 'day');
      }
      weeks.push(week);
      // 如果这周已经覆盖了最后一天，停止
      if (day.isAfter(lastDay, 'day') && week[6].isAfter(lastDay.subtract(1, 'day'))) {
        break;
      }
    }

    const isToday = (d: Dayjs) => d.format('YYYY-MM-DD') === dayjs().format('YYYY-MM-DD');

    return (
      <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, overflow: 'hidden' }}>
        {/* 星期标题 */}
        <div style={{ display: 'flex', background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
          {['日', '一', '二', '三', '四', '五', '六'].map(w => (
            <div key={w} style={{
              flex: 1, textAlign: 'center', padding: '8px 0',
              fontSize: 13, fontWeight: 600, color: '#666',
            }}>{w}</div>
          ))}
        </div>

        {weeks.slice(0, 6).map((week, wi) => (
          <div key={wi} style={{ display: 'flex', borderBottom: wi < weeks.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
            {week.map((d, di) => {
              const isCurrentMonth = d.month() === currentDate.month();
              const today = isToday(d);
              const daySchedules = getDaySchedules(d);
              return (
                <div
                  key={di}
                  onClick={() => handleNew(d.hour(9).minute(0), d.hour(12).minute(0))}
                  style={{
                    flex: 1, minHeight: 80, padding: '4px 6px',
                    background: today ? '#e6f4ff' : isCurrentMonth ? '#fff' : '#fafafa',
                    borderLeft: di > 0 ? '1px solid #f0f0f0' : 'none',
                    cursor: 'pointer',
                    opacity: isCurrentMonth ? 1 : 0.5,
                  }}
                >
                  <div style={{
                    fontSize: 13, fontWeight: today ? 700 : 400,
                    color: today ? '#1677ff' : isCurrentMonth ? '#333' : '#bbb',
                    marginBottom: 4,
                  }}>
                    {d.format('D')}
                  </div>
                  {daySchedules.slice(0, 3).map(s => (
                    <div
                      key={s.id}
                      onClick={(e) => { e.stopPropagation(); setDetailSchedule(s); }}
                      style={{
                        fontSize: 11, padding: '1px 4px', marginBottom: 2, borderRadius: 3,
                        background: conflictIds.has(s.id) ? '#fff2f0' : '#e6f4ff',
                        color: conflictIds.has(s.id) ? '#ff4d4f' : '#1677ff',
                        borderLeft: `3px solid ${conflictIds.has(s.id) ? '#ff4d4f' : '#1677ff'}`,
                        cursor: 'pointer', overflow: 'hidden', whiteSpace: 'nowrap',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {s.title}
                    </div>
                  ))}
                  {daySchedules.length > 3 && (
                    <div style={{ fontSize: 11, color: '#999' }}>+{daySchedules.length - 3}</div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    );
  };

  // ====== 周视图 ======
  const renderWeekView = () => {
    const dayOfWeek = currentDate.day();
    const monday = currentDate.subtract(dayOfWeek === 0 ? 6 : dayOfWeek - 1, 'day');
    const days = Array.from({ length: 7 }, (_, i) => monday.add(i, 'day'));
    const isToday = (d: Dayjs) => d.format('YYYY-MM-DD') === dayjs().format('YYYY-MM-DD');

    return (
      <div style={{ overflow: 'auto', border: '1px solid #f0f0f0', borderRadius: 8 }}>
        {/* Header */}
        <div style={{ display: 'flex', position: 'sticky', top: 0, zIndex: 2, background: '#fff' }}>
          <div style={{ width: 55, flexShrink: 0, borderBottom: '1px solid #f0f0f0' }} />
          {days.map(d => (
            <div key={d.format('D')} style={{
              flex: 1, textAlign: 'center', padding: '6px 2px',
              background: isToday(d) ? '#e6f4ff' : '#fafafa',
              borderBottom: '1px solid #f0f0f0', borderLeft: '1px solid #f0f0f0',
            }}>
              <div style={{ fontSize: 10, color: '#999' }}>
                {['一', '二', '三', '四', '五', '六', '日'][d.day() === 0 ? 6 : d.day() - 1]}
              </div>
              <div style={{
                fontSize: 15, fontWeight: isToday(d) ? 700 : 400,
                color: isToday(d) ? '#1677ff' : '#333',
              }}>{d.format('D')}</div>
            </div>
          ))}
        </div>

        {/* Time slots */}
        {HOURS.map(h => {
          const slotStart = (d: Dayjs) => d.hour(h).minute(0);
          const slotEnd = (d: Dayjs) => d.hour(h + 1).minute(0);
          return (
            <div key={h} style={{ display: 'flex', borderBottom: '1px solid #f5f5f5', minHeight: 48 }}>
              <div style={{
                width: 55, flexShrink: 0, textAlign: 'right',
                paddingRight: 8, fontSize: 11, color: '#999', lineHeight: '48px',
              }}>{`${String(h).padStart(2, '0')}:00`}</div>
              {days.map(d => {
                const ss = slotStart(d);
                const se = slotEnd(d);
                const slotScheds = schedules.filter(s =>
                  dayjs(s.start_time) < se && dayjs(s.end_time) > ss
                );
                return (
                  <div
                    key={d.format('D')}
                    onClick={() => handleNew(ss, se)}
                    style={{
                      flex: 1, borderLeft: '1px solid #f5f5f5',
                      background: isToday(d) ? '#fafcff' : '#fff',
                      padding: 1, cursor: 'pointer', position: 'relative',
                    }}
                  >
                    {slotScheds.map(s => (
                      <div
                        key={s.id}
                        onClick={(e) => { e.stopPropagation(); setDetailSchedule(s); }}
                        style={{
                          background: conflictIds.has(s.id) ? '#fff2f0' : '#e6f4ff',
                          borderLeft: `3px solid ${conflictIds.has(s.id) ? '#ff4d4f' : '#1677ff'}`,
                          borderRadius: 3, padding: '1px 4px', marginBottom: 1,
                          fontSize: 10, cursor: 'pointer', overflow: 'hidden',
                        }}
                      >
                        <span style={{ fontWeight: 600 }}>{s.title}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    );
  };

  // ====== 日视图 ======
  const renderDayView = () => {
    const isToday = currentDate.format('YYYY-MM-DD') === dayjs().format('YYYY-MM-DD');

    return (
      <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, overflow: 'hidden' }}>
        <div style={{
          textAlign: 'center', padding: 12, fontSize: 16, fontWeight: 600,
          background: isToday ? '#e6f4ff' : '#fafafa', borderBottom: '1px solid #f0f0f0',
        }}>
          {currentDate.format('YYYY年M月D日 dddd')}
          {isToday && <Tag color="blue" style={{ marginLeft: 8 }}>今天</Tag>}
        </div>
        {HOURS.map(h => {
          const ss = currentDate.hour(h).minute(0);
          const se = ss.add(1, 'hour');
          const slotScheds = schedules.filter(s =>
            dayjs(s.start_time) < se && dayjs(s.end_time) > ss
          );
          return (
            <div
              key={h}
              onClick={() => handleNew(ss, se)}
              style={{
                display: 'flex', borderBottom: '1px solid #f5f5f5',
                minHeight: 56, cursor: 'pointer',
              }}
            >
              <div style={{
                width: 60, flexShrink: 0, textAlign: 'right',
                paddingRight: 12, fontSize: 12, color: '#999', lineHeight: '56px',
              }}>{`${String(h).padStart(2, '0')}:00`}</div>
              <div style={{ flex: 1, borderLeft: '1px solid #f0f0f0', padding: 4 }}>
                {slotScheds.map(s => (
                  <div
                    key={s.id}
                    onClick={(e) => { e.stopPropagation(); setDetailSchedule(s); }}
                    style={{
                      background: conflictIds.has(s.id) ? '#fff2f0' : '#e6f4ff',
                      border: `1px solid ${conflictIds.has(s.id) ? '#ff4d4f' : '#91caff'}`,
                      borderRadius: 6, padding: '6px 10px', marginBottom: 4, cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 14 }}>
                      <Tag color={TYPE_COLORS[s.schedule_type]} style={{ marginRight: 6 }}>
                        {SCHEDULE_TYPE_LABELS[s.schedule_type as ScheduleType]}
                      </Tag>
                      {s.title}
                      {conflictIds.has(s.id) && <Tag color="error" style={{ marginLeft: 6 }}>冲突</Tag>}
                    </div>
                    <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>
                      <ClockCircleOutlined /> {dayjs(s.start_time).format('HH:mm')} - {dayjs(s.end_time).format('HH:mm')}
                      {s.location && <span> &nbsp;|&nbsp; <EnvironmentOutlined /> {s.location}</span>}
                      {s.judge && <span> &nbsp;|&nbsp; <UserOutlined /> {s.judge}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // ====== 主渲染 ======
  return (
    <div>
      {/* 工具栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Title level={5} style={{ margin: 0 }}>日历视图</Title>
          <Segmented
            value={view}
            onChange={(v) => setView(v as 'month' | 'week' | 'day')}
            options={[
              { value: 'month', label: '月' },
              { value: 'week', label: '周' },
              { value: 'day', label: '日' },
            ]}
          />
          <Button onClick={() => setCurrentDate(dayjs())}>今天</Button>
          <Button onClick={goPrev}>{'<'}</Button>
          <Button onClick={goNext}>{'>'}</Button>
          <Text type="secondary">
            {view === 'month' && currentDate.format('YYYY年M月')}
            {view === 'week' && `${currentDate.startOf('week').format('M/D')} - ${currentDate.endOf('week').format('M/D')}`}
            {view === 'day' && currentDate.format('YYYY年M月D日')}
          </Text>
        </Space>
        <Space>
          <Button icon={<ExportOutlined />} onClick={handleExport}>导出 iCal</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => handleNew()}>新建日程</Button>
        </Space>
      </div>

      {/* 冲突警告 */}
      {conflictIds.size > 0 && (
        <Alert
          type="error"
          message={`检测到 ${schedules.filter(s => conflictIds.has(s.id)).length} 个日程存在时间冲突`}
          showIcon closable style={{ marginBottom: 16 }}
        />
      )}

      {/* 日历内容 */}
      <Card style={{ minHeight: 400 }}>
        {view === 'month' && renderMonthView()}
        {view === 'week' && renderWeekView()}
        {view === 'day' && renderDayView()}
      </Card>

      {/* 日程列表 */}
      <div style={{ marginTop: 16 }}>
        <Title level={5}>日程列表 <Text type="secondary" style={{ fontSize: 13 }}>（{schedules.length} 项）</Text></Title>
        {schedules.length === 0 ? (
          <Empty description="暂无日程" />
        ) : (
          <List
            dataSource={schedules}
            renderItem={(s: ScheduleItem) => (
              <Card
                size="small"
                hoverable
                style={{ marginBottom: 6 }}
                onClick={() => setDetailSchedule(s)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Tag color={TYPE_COLORS[s.schedule_type]}>
                      {SCHEDULE_TYPE_LABELS[s.schedule_type as ScheduleType]}
                    </Tag>
                    <Text strong style={{ color: conflictIds.has(s.id) ? '#ff4d4f' : '#333' }}>
                      {s.title}
                    </Text>
                    {conflictIds.has(s.id) && <Tag color="error">冲突</Tag>}
                    {s.is_parsed_from_sms && <Tag icon={<MessageOutlined />} color="purple">短信</Tag>}
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {dayjs(s.start_time).format('MM-DD HH:mm')} - {dayjs(s.end_time).format('HH:mm')}
                    {s.location ? ` | ${s.location}` : ''}
                  </Text>
                </div>
              </Card>
            )}
          />
        )}
      </div>

      {/* 弹窗 */}
      <ScheduleFormModal
        open={formOpen}
        editData={editData}
        defaultStart={defaultStart}
        defaultEnd={defaultEnd}
        onClose={() => setFormOpen(false)}
        onSuccess={() => { setFormOpen(false); fetchSchedules(); }}
      />
      <ScheduleDetailModal
        schedule={detailSchedule}
        onClose={() => setDetailSchedule(null)}
        onEdit={() => {
          if (detailSchedule) {
            const s = detailSchedule;
            setDetailSchedule(null);
            handleEdit(s);
          }
        }}
        onDelete={() => detailSchedule && handleDelete(detailSchedule.id)}
      />
    </div>
  );
};

// ==================== 短信解析 Tab ====================

const SmsParserTab: React.FC = () => {
  const [text, setText] = useState('');
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [creating, setCreating] = useState(false);

  const handleParse = async () => {
    if (!text.trim()) { message.warning('请先输入短信内容'); return; }
    setParsing(true);
    try {
      const res = await apiClient.post('/schedules/parse-sms', { text: text.trim() });
      setResult(res.data);
      if (!res.data.case_number && !res.data.hearing_datetime) {
        message.warning('未能识别庭审信息，请检查短信格式');
      } else {
        const methodLabel = res.data.method === 'regex' ? '规则匹配' : res.data.method === 'regex+ai' ? '规则+AI' : 'AI';
        message.success(`解析完成（${methodLabel}）`);
      }
    } catch { message.error('解析失败'); }
    finally { setParsing(false); }
  };

  const handleCreateSchedule = async () => {
    if (!result?.hearing_datetime) { message.warning('未识别到开庭时间'); return; }
    setCreating(true);
    try {
      const res = await apiClient.post('/schedules/create-from-sms', {
        sms_text: text.trim(), schedule_type: 'hearing',
      });
      message.success('日程创建成功！');
      if (res.data?.conflicts?.length > 0) message.warning('该时间段已有其他日程，请注意冲突');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '创建失败');
    } finally { setCreating(false); }
  };

  return (
    <div>
      <Alert
        message="12368 法院短信解析"
        description="粘贴法院服务平台（12368）发送的开庭通知短信，系统自动提取开庭时间、地点、案号、法官等信息。"
        type="info" showIcon style={{ marginBottom: 20 }}
      />

      <Card title="短信内容" style={{ marginBottom: 16 }}>
        <TextArea
          rows={6}
          value={text}
          onChange={(e) => { setText(e.target.value); setResult(null); }}
          placeholder="请在此粘贴 12368 法院短信..."
        />
        <div style={{ marginTop: 12 }}>
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleParse} loading={parsing}>
            解析短信
          </Button>
        </div>
      </Card>

      {result && (result.case_number || result.hearing_datetime) && (
        <Card title="解析结果" style={{ marginBottom: 16 }}>
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="案号">
              <Text strong>{result.case_number || '未识别'}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="开庭时间">
              <Text strong>
                {result.hearing_datetime
                  ? dayjs(result.hearing_datetime).format('YYYY年M月D日 HH:mm')
                  : '未识别'}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="法庭地点">{result.location || '未识别'}</Descriptions.Item>
            <Descriptions.Item label="承办法官">{result.judge || '未识别'}</Descriptions.Item>
            <Descriptions.Item label="联系电话">{result.phone || '未识别'}</Descriptions.Item>
            <Descriptions.Item label="解析方式">
              <Tag color={result.method?.includes('ai') ? 'purple' : 'blue'}>
                {result.method === 'regex' ? '规则匹配' : result.method === 'regex+ai' ? '规则+AI' : 'AI'}
              </Tag>
            </Descriptions.Item>
            {result.matched_case_id && (
              <Descriptions.Item label="匹配案件" span={2}>
                <Tag color="green">已自动匹配到已有案件</Tag>
              </Descriptions.Item>
            )}
          </Descriptions>
          <Divider />
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateSchedule} loading={creating} disabled={!result.hearing_datetime}>
              一键创建开庭日程
            </Button>
            <Button onClick={() => { setText(''); setResult(null); }}>清空</Button>
          </Space>
        </Card>
      )}
    </div>
  );
};

// ==================== 主页面 ====================

const SchedulePage: React.FC = () => {
  const tabItems = [
    { key: 'calendar', label: '日历视图', children: <CalendarViewTab /> },
    { key: 'sms', label: '短信解析', children: <SmsParserTab /> },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>日程与庭审中心</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
};

export default SchedulePage;
