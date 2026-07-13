import axios from 'axios';

// 自动检测 API 地址：
// - Electron 环境：始终用 127.0.0.1
// - 浏览器访问：用当前页面的主机名 + 8000 端口（支持局域网分享）
const getBaseUrl = (): string => {
  // Electron 环境检测
  if (typeof window !== 'undefined' && (window as any).electronAPI) {
    return 'http://127.0.0.1:8000/api';
  }
  // 浏览器环境：使用当前主机名
  const hostname = window.location.hostname;
  return `http://${hostname}:8000/api`;
};

const API_BASE_URL = getBaseUrl();

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加认证 token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.hash = '#/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
