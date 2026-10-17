import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { ConfigProvider, App as AntApp, theme as antTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'antd/dist/reset.css'
import './styles/global.css'
import router from './router'
import { useThemeStore } from './store/themeStore'

dayjs.locale('zh-cn')

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

function ThemedApp() {
  const mode = useThemeStore((s) => s.mode)
  const dark = mode === 'dark'

  // 同步 HTML 主题标记：global.css 的暗色变量与 antd 暗色算法都以此为准
  React.useEffect(() => {
    document.documentElement.dataset.theme = mode
  }, [mode])

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: dark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#e3350d',
          colorInfo: '#e3350d',
          colorLink: '#e3350d',
          borderRadius: 10,
          colorBgLayout: 'transparent',
          colorText: dark ? '#e8ebf2' : '#2a3040',
          colorTextSecondary: dark ? '#9aa3b8' : '#5a6478',
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'HarmonyOS Sans SC', 'MiSans', 'Microsoft YaHei', sans-serif",
        },
        components: {
          Layout: { headerBg: 'transparent', siderBg: '#171d2e', bodyBg: 'transparent' },
          Card: { paddingLG: 20 },
          Table: { headerBg: 'transparent' },
        },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemedApp />
  </React.StrictMode>,
)
