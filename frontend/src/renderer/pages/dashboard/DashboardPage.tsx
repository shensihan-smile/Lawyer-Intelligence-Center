import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, List, Tag, Typography, Spin, Empty } from 'antd';
import {
  FolderOpenOutlined, CalendarOutlined, FileTextOutlined,
  DollarOutlined, ClockCircleOutlined, EnvironmentOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import apiClient from '../../utils/api';

const { Title, Text } = Typography;

// ==================== 类型 ====================

interface DashboardStats {
  activeCases: number;
  weekHearings: number;
  totalDocs: number;
  monthBills: number;
}

interface ScheduleItem {
  id: number;
  title: string;
  schedule_type: string;
  case_number: string | null;
  start_time: string;
  location: string;
  judge: string;
}

interface CaseItem {
  id: number;
  case_number: string;
  case_reason: string;
  case_stage: string;
  updated_at: string;
}

const STAGE_LABELS: Record<string, string> = {
  intake: '接案', filing: '立案', trial: '审理中',
  judgment: '判决', enforcement: '执行', closed: '结案',
};
const STAGE_COLORS: Record<string, string> = {
  intake: 'purple', filing: 'geekblue', trial: 'blue',
  judgment: 'orange', enforcement: 'volcano', closed: 'green',
};

// ==================== 页面 ====================

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats>({ activeCases: 0, weekHearings: 0, totalDocs: 0, monthBills: 0 });
  const [hearings, setHearings] = useState<ScheduleItem[]>([]);
  const [recentCases, setRecentCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const today = dayjs().format('YYYY-MM-DD');
      const weekEnd = dayjs().add(7, 'day').format('YYYY-MM-DD');
      const monthStart = dayjs().startOf('month').format('YYYY-MM-DD');
      const monthEnd = dayjs().endOf('month').format('YYYY-MM-DD');

      const [casesRes, schedulesRes, docsRes, billsRes] = await Promise.all([
        apiClient.get('/cases/'),
        apiClient.get('/schedules/', { params: { start_date: today, end_date: weekEnd } }),
        apiClient.get('/documents/'),
        apiClient.get('/billing/bills').catch(() => ({ data: [] })),
      ]);

      const cases = casesRes.data || [];
      const schedules = schedulesRes.data || [];
      const docs = docsRes.data || [];
      const bills = (billsRes.data || []).filter((b: any) => {
        if (!b.generated_at) return false;
        return dayjs(b.generated_at).format('YYYY-MM') === dayjs().format('YYYY-MM');
      });

      // 统计
      setStats({
        activeCases: cases.filter((c: CaseItem) => c.case_stage !== 'closed').length,
        weekHearings: schedules.filter((s: ScheduleItem) => s.schedule_type === 'hearing').length,
        totalDocs: docs.length,
        monthBills: bills.length,
      });

      // 近期开庭（按时间排序，取前5）
      setHearings(
        schedules
          .filter((s: ScheduleItem) => s.schedule_type === 'hearing')
          .sort((a: ScheduleItem, b: ScheduleItem) => a.start_time.localeCompare(b.start_time))
          .slice(0, 5)
      );

      // 最近更新的案件（取前5）
      setRecentCases(
        cases
          .filter((c: CaseItem) => c.case_stage !== 'closed')
          .sort((a: CaseItem, b: CaseItem) => (b.updated_at || '').localeCompare(a.updated_at || ''))
          .slice(0, 5)
      );
    } catch {
      // 后端可能未启动或数据为空
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>工作台</Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/cases')} style={{ cursor: 'pointer' }}>
            <Statistic title="在办案件" value={stats.activeCases}
              prefix={<FolderOpenOutlined />} valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/schedule')} style={{ cursor: 'pointer' }}>
            <Statistic title="本周开庭" value={stats.weekHearings}
              prefix={<CalendarOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/documents')} style={{ cursor: 'pointer' }}>
            <Statistic title="文档总数" value={stats.totalDocs}
              prefix={<FileTextOutlined />} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/billing')} style={{ cursor: 'pointer' }}>
            <Statistic title="本月账单" value={stats.monthBills}
              prefix={<DollarOutlined />} valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* 近期开庭 */}
        <Col xs={24} lg={12}>
          <Card
            title="📅 近期开庭"
            extra={<a onClick={() => navigate('/schedule')}>全部 →</a>}
            style={{ height: '100%' }}
          >
            {hearings.length === 0 ? (
              <Empty description="暂无近期开庭" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={hearings}
                renderItem={(item) => (
                  <List.Item style={{ cursor: 'pointer' }} onClick={() => navigate('/schedule')}>
                    <List.Item.Meta
                      title={
                        <Text strong>
                          {item.case_number ? `${item.case_number} — ` : ''}{item.title}
                        </Text>
                      }
                      description={
                        <div>
                          <Text type="secondary">
                            <ClockCircleOutlined /> {dayjs(item.start_time).format('MM-DD HH:mm')}
                          </Text>
                          {item.location && (
                            <Text type="secondary" style={{ marginLeft: 16 }}>
                              <EnvironmentOutlined /> {item.location}
                            </Text>
                          )}
                          {item.judge && (
                            <Text type="secondary" style={{ marginLeft: 16 }}>
                              <UserOutlined /> {item.judge}
                            </Text>
                          )}
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* 最近案件 */}
        <Col xs={24} lg={12}>
          <Card
            title="📂 在办案件"
            extra={<a onClick={() => navigate('/cases')}>全部 →</a>}
            style={{ height: '100%' }}
          >
            {recentCases.length === 0 ? (
              <Empty description="暂无在办案件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={recentCases}
                renderItem={(item) => (
                  <List.Item style={{ cursor: 'pointer' }} onClick={() => navigate('/cases')}>
                    <List.Item.Meta
                      title={<Text strong>{item.case_number}</Text>}
                      description={item.case_reason || '未填写案由'}
                    />
                    <Tag color={STAGE_COLORS[item.case_stage]}>
                      {STAGE_LABELS[item.case_stage] || item.case_stage}
                    </Tag>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
