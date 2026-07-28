import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App as AntApp, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'

// Ant Design 全局主题 —— Flowbase 浅色风格:
// 深靛蓝墨色文字 + 紫罗兰强调 + 白卡大圆角;主按钮用 Flowbase 标志性的
// 深靛蓝底 + 内侧紫光晕。与 theme.css 变量保持对齐。
const antdTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#8247ff',
    colorInfo: '#3e63dd',
    colorSuccess: '#00a05a',
    colorError: '#e5484d',
    colorWarning: '#d97706',
    colorBgBase: '#ffffff',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f5f4fb',
    colorBorder: '#d9d6ec',
    colorBorderSecondary: '#eae8f4',
    colorText: '#11023b',
    colorTextSecondary: '#45446b',
    colorTextTertiary: '#8b89a6',
    borderRadius: 10,
    fontSize: 13,
    fontFamily: "'Inter', 'Noto Sans SC', sans-serif",
    boxShadowSecondary:
      '0 8px 20px rgba(34, 6, 109, 0.08), 0 24px 56px -16px rgba(34, 6, 109, 0.22)',
  },
  components: {
    Button: {
      colorPrimary: '#11023b',
      colorPrimaryHover: '#241457',
      colorPrimaryActive: '#0b0129',
      primaryShadow: 'inset 0 -6px 20px rgba(130, 71, 255, 0.32)',
      defaultShadow: '0 1px 2px rgba(18, 43, 105, 0.08), 0 2px 6px rgba(18, 43, 105, 0.04)',
    },
    Card: { paddingLG: 14, headerHeight: 40 },
    Tabs: { horizontalMargin: '0' },
    Segmented: { trackBg: '#f1f0f9' },
    Drawer: { colorBgElevated: '#ffffff' },
    Table: { headerBg: '#fbfbfe', cellPaddingBlockSM: 6, cellPaddingInlineSM: 8 },
  },
} as const

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
)
