import React, { useState, useEffect, useCallback } from 'react';
import {
  Typography, Card, Tabs, Upload, Button, Radio, Input,
  Slider, Space, message, Spin, Alert, Table, Modal,
} from 'antd';
import {
  InboxOutlined, DownloadOutlined, FilePdfOutlined,
  FileWordOutlined, SwapOutlined, PictureOutlined, EyeOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload';
import apiClient from '../../utils/api';
import { Document } from '../../types';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;

// ==================== 格式转换 Tab ====================

const FormatConvert: React.FC = () => {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [targetFormat, setTargetFormat] = useState<'pdf' | 'docx'>('pdf');
  const [converting, setConverting] = useState(false);

  const handleConvert = async () => {
    if (fileList.length === 0) {
      message.warning('请先上传文件');
      return;
    }
    const file = fileList[0].originFileObj;
    if (!file) {
      message.warning('文件无效');
      return;
    }

    setConverting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('target_format', targetFormat);

      const res = await apiClient.post('/documents/convert', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
      });

      // 触发浏览器下载
      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = targetFormat === 'pdf' ? '.pdf' : '.docx';
      const originalName = file.name.replace(/\.[^.]+$/, '');
      a.download = `${originalName}_转换${ext}`;
      a.click();
      URL.revokeObjectURL(url);

      message.success('转换完成，文件已开始下载');
    } catch (e: any) {
      if (e?.response?.data instanceof Blob) {
        // 尝试读取 blob 中的错误信息
        try {
          const text = await e.response.data.text();
          const detail = JSON.parse(text);
          message.error(detail?.detail || '转换失败');
        } catch {
          message.error('转换失败，请确认文件格式正确');
        }
      } else {
        message.error('转换失败');
      }
    } finally {
      setConverting(false);
    }
  };

  const isPdf = fileList[0]?.name?.toLowerCase().endsWith('.pdf');
  const isWord = fileList[0]?.name?.toLowerCase().match(/\.(doc|docx|docm)$/);
  const canConvert = fileList.length > 0 && (
    (targetFormat === 'docx' && isPdf) ||
    (targetFormat === 'pdf' && isWord)
  );
  const showWarning = fileList.length > 0 && !canConvert;

  return (
    <div>
      <Alert
        message="支持 PDF ↔ Word 互转"
        description="上传 PDF 可转为 Word 编辑；上传 Word 可转为 PDF 固化排版。转换在本地完成，文件不会上传到云端。"
        type="info"
        showIcon
        style={{ marginBottom: 20 }}
      />

      <Dragger
        maxCount={1}
        fileList={fileList}
        beforeUpload={(file) => {
          setFileList([{ uid: '-1', name: file.name, status: 'done', originFileObj: file }]);
          return false; // 阻止自动上传
        }}
        onRemove={() => setFileList([])}
        style={{ marginBottom: 20 }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ fontSize: 40, color: '#1677ff' }} />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域</p>
        <p className="ant-upload-hint">
          支持 PDF（.pdf）和 Word（.doc / .docx）文件
        </p>
      </Dragger>

      {fileList.length > 0 && (
        <Card size="small" style={{ marginBottom: 20 }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Text strong>转换方向：</Text>
              <Radio.Group
                value={targetFormat}
                onChange={(e) => setTargetFormat(e.target.value)}
                style={{ marginLeft: 16 }}
              >
                <Radio.Button value="pdf">
                  <FileWordOutlined /> Word → <SwapOutlined /> → <FilePdfOutlined /> PDF
                </Radio.Button>
                <Radio.Button value="docx">
                  <FilePdfOutlined /> PDF → <SwapOutlined /> → <FileWordOutlined /> Word
                </Radio.Button>
              </Radio.Group>
            </div>

            {showWarning && (
              <Alert
                type="warning"
                message={
                  targetFormat === 'docx'
                    ? '请上传 PDF 文件以转换为 Word'
                    : '请上传 Word 文件以转换为 PDF'
                }
                showIcon
              />
            )}

            <Button
              type="primary"
              icon={<SwapOutlined />}
              onClick={handleConvert}
              loading={converting}
              disabled={!canConvert}
              size="large"
            >
              {converting ? '转换中...' : '开始转换'}
            </Button>
          </Space>
        </Card>
      )}
    </div>
  );
};

// ==================== 图片导出 Tab ====================

const ImageExport: React.FC = () => {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [mode, setMode] = useState<'long' | 'pages'>('pages');
  const [dpi, setDpi] = useState(150);
  const [watermark, setWatermark] = useState('');
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    if (fileList.length === 0) {
      message.warning('请先上传文件');
      return;
    }
    const file = fileList[0].originFileObj;
    if (!file) {
      message.warning('文件无效');
      return;
    }

    setExporting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('mode', mode);
      formData.append('dpi', String(dpi));
      formData.append('watermark', watermark);

      const res = await apiClient.post('/documents/export-images', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
      });

      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const originalName = file.name.replace(/\.[^.]+$/, '');
      a.download = mode === 'long'
        ? `${originalName}_长图.png`
        : `${originalName}_图片.zip`;
      a.click();
      URL.revokeObjectURL(url);

      message.success('导出完成，文件已开始下载');
    } catch (e: any) {
      if (e?.response?.data instanceof Blob) {
        try {
          const text = await e.response.data.text();
          const detail = JSON.parse(text);
          message.error(detail?.detail || '导出失败');
        } catch {
          message.error('导出失败，请确认文件格式正确');
        }
      } else {
        message.error('导出失败');
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <Alert
        message="将文档导出为高清图片"
        description="支持生成长图（适合微信分享）或分页图（每页一张）。可选添加律所水印。"
        type="info"
        showIcon
        style={{ marginBottom: 20 }}
      />

      <Dragger
        maxCount={1}
        fileList={fileList}
        beforeUpload={(file) => {
          setFileList([{ uid: '-1', name: file.name, status: 'done', originFileObj: file }]);
          return false;
        }}
        onRemove={() => setFileList([])}
        style={{ marginBottom: 20 }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ fontSize: 40, color: '#1677ff' }} />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域</p>
        <p className="ant-upload-hint">
          支持 PDF（.pdf）和 Word（.doc / .docx）文件
        </p>
      </Dragger>

      {fileList.length > 0 && (
        <Card size="small" style={{ marginBottom: 20 }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Text strong>导出模式：</Text>
              <Radio.Group
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                style={{ marginLeft: 16 }}
              >
                <Radio.Button value="long">
                  <PictureOutlined /> 连续长图（适合手机阅读和分享）
                </Radio.Button>
                <Radio.Button value="pages">
                  <PictureOutlined /> 分页图片（每页一张，打包下载）
                </Radio.Button>
              </Radio.Group>
            </div>

            <div>
              <Text strong>图片清晰度（DPI）：</Text>
              <span style={{ marginLeft: 16 }}>{dpi} DPI</span>
              <Slider
                min={72}
                max={300}
                value={dpi}
                onChange={setDpi}
                style={{ width: 300, marginLeft: 16 }}
                marks={{ 72: '72', 150: '150', 200: '200', 300: '300' }}
              />
            </div>

            <div>
              <Text strong>水印文字（可选）：</Text>
              <Input
                placeholder="如：XX律师事务所 · 张三律师"
                value={watermark}
                onChange={(e) => setWatermark(e.target.value)}
                style={{ width: 320, marginLeft: 16 }}
                allowClear
              />
            </div>

            <Button
              type="primary"
              icon={<PictureOutlined />}
              onClick={handleExport}
              loading={exporting}
              size="large"
            >
              {exporting ? '导出中...' : '开始导出'}
            </Button>
          </Space>
        </Card>
      )}
    </div>
  );
};

// ==================== 预览内容组件（独立组件，管理加载状态） ====================

interface PreviewContentProps {
  doc: Document;
  page: number;
  onPageChange: (page: number) => void;
}

const PreviewContent: React.FC<PreviewContentProps> = ({ doc, page, onPageChange }) => {
  const [blobUrl, setBlobUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const token = localStorage.getItem('auth_token');
  const fileType = doc.file_type?.toLowerCase() || '';
  const apiUrl = `${apiClient.defaults.baseURL}/documents/${doc.id}/preview`;

  const fetchAsBlob = async (url: string): Promise<string> => {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error('加载失败');
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  };

  useEffect(() => {
    setLoading(true);
    setBlobUrl('');
    const loadUrl = fileType === 'pdf' || ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(fileType)
      ? apiUrl
      : `${apiUrl}?page=${page}`;
    fetchAsBlob(loadUrl)
      .then(setBlobUrl)
      .catch(() => message.error('预览加载失败'))
      .finally(() => setLoading(false));
  }, [doc.id, page]);

  if (loading) {
    return <Spin tip="加载中..." style={{ display: 'block', textAlign: 'center', padding: 60 }} />;
  }

  if (!blobUrl) {
    return <Text type="secondary">无法加载预览</Text>;
  }

  // PDF → iframe
  if (fileType === 'pdf') {
    return (
      <iframe
        src={`${blobUrl}#toolbar=1&navpanes=1`}
        style={{ width: '100%', height: '70vh', border: 'none' }}
        title="PDF 预览"
      />
    );
  }

  // 图片
  if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(fileType)) {
    return (
      <div style={{ textAlign: 'center' }}>
        <img src={blobUrl} alt={doc.original_name} style={{ maxWidth: '100%', maxHeight: '70vh' }} />
      </div>
    );
  }

  // Word → 图片
  if (['doc', 'docx', 'docm'].includes(fileType)) {
    return (
      <div style={{ textAlign: 'center' }}>
        <img src={blobUrl} alt={`第 ${page} 页`} style={{ maxWidth: '100%', maxHeight: '65vh' }} />
        <div style={{ marginTop: 12 }}>
          <Space>
            <Button disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</Button>
            <Text>第 {page} 页</Text>
            <Button onClick={() => onPageChange(page + 1)}>下一页</Button>
          </Space>
        </div>
      </div>
    );
  }

  return <Text type="secondary">不支持预览此文件格式</Text>;
};

// ==================== 文件预览 Tab ====================

const FilePreview: React.FC = () => {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewPage, setPreviewPage] = useState(1);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/documents/');
      setDocs(res.data);
    } catch {
      message.error('获取文档列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const handlePreview = (doc: Document) => {
    setPreviewDoc(doc);
    setPreviewPage(1);
    setPreviewOpen(true);
  };

  const columns = [
    { title: '文件名', dataIndex: 'original_name', ellipsis: true },
    { title: '类型', dataIndex: 'file_type', width: 80,
      render: (v: string) => v?.toUpperCase() },
    { title: '大小', dataIndex: 'size_display', width: 90 },
    {
      title: '操作', key: 'action', width: 100,
      render: (_: unknown, record: Document) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => handlePreview(record)}
        >
          预览
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Alert
        message="文件在线预览"
        description="PDF 和图片可直接预览，Word 文档将自动转为图片预览。点击文件名旁的「预览」按钮查看。"
        type="info"
        showIcon
        style={{ marginBottom: 20 }}
      />

      <Table
        columns={columns}
        dataSource={docs}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 个文件` }}
        size="middle"
      />

      <Modal
        title={previewDoc?.original_name || '文件预览'}
        open={previewOpen}
        onCancel={() => { setPreviewOpen(false); setPreviewDoc(null); }}
        footer={null}
        width="90%"
        style={{ top: 20 }}
        destroyOnClose
      >
        {previewDoc && (
          <PreviewContent
            doc={previewDoc}
            page={previewPage}
            onPageChange={setPreviewPage}
          />
        )}
      </Modal>
    </div>
  );
};

// ==================== 主页面 ====================

const DocumentsPage: React.FC = () => {
  const tabItems = [
    { key: 'convert', label: '格式转换', children: <FormatConvert /> },
    { key: 'export', label: '图片导出', children: <ImageExport /> },
    { key: 'preview', label: '文件预览', children: <FilePreview /> },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>智能文档处理</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
};

export default DocumentsPage;
