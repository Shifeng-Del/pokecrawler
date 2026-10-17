import { useEffect, useState } from 'react'
import { Layout, Menu, Typography, Modal, Tooltip } from 'antd'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  BarChartOutlined,
  CloudDownloadOutlined,
  SwapOutlined,
  SearchOutlined,
  BulbOutlined,
  BulbFilled,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useOverview } from '@/hooks/usePokemonStats'
import { useThemeStore } from '@/store/themeStore'
import SearchPalette from '@/components/common/SearchPalette'
import CompareBar from '@/components/common/CompareBar'

const { Header, Sider, Content } = Layout

const MENU = [
  { key: '/', icon: <DashboardOutlined />, label: '总览' },
  { key: '/pokemon', icon: <UnorderedListOutlined />, label: '数据列表' },
  { key: '/moves', icon: <ThunderboltOutlined />, label: '招式图鉴' },
  { key: '/charts', icon: <BarChartOutlined />, label: '图表分析' },
  { key: '/compare', icon: <SwapOutlined />, label: '对比' },
  { key: '/crawl', icon: <CloudDownloadOutlined />, label: '爬取管理' },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { data: overview } = useOverview()
  const dark = useThemeStore((s) => s.mode === 'dark')
  const toggleTheme = useThemeStore((s) => s.toggle)

  // Ctrl+K / Cmd+K 唤起全局搜索
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const selected = MENU.find((m) =>
    m.key === '/' ? location.pathname === '/' : location.pathname.startsWith(m.key),
  )?.key

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={208}
        className="sider-shell"
      >
        <div className="brand-zone">
          <div className="pokeball" aria-hidden="true" />
          <div className="brand-name" style={{ fontSize: collapsed ? 12 : 14 }}>
            {collapsed ? (
              <span className="grad">图鉴</span>
            ) : (
              <>
                宝可梦<span className="grad">图鉴</span>
              </>
            )}
          </div>
        </div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[selected]}
          items={MENU}
          onClick={({ key }) => navigate(key)}
        />
        {!collapsed && (
          <div className="sider-foot">
            POKE&nbsp;DEX&nbsp;·&nbsp;v1.1
            <br />
            1351&nbsp;种收录
          </div>
        )}
      </Sider>
      <Layout>
        <Header className="glass-header">
          <Typography.Title className="header-title" level={5}>
            宝可梦数据采集与可视化
          </Typography.Title>
          <span className="header-deco" aria-hidden="true" />
          <span className="header-actions">
            <Tooltip title="全局搜索（Ctrl+K）">
              <span className="header-icon-btn" onClick={() => setSearchOpen(true)} role="button" tabIndex={0}>
                <SearchOutlined />
              </span>
            </Tooltip>
            <Tooltip title={dark ? '切换到亮色模式' : '切换到暗色模式'}>
              <span
                className="header-icon-btn"
                onClick={toggleTheme}
                role="button"
                tabIndex={0}
                aria-label="切换主题"
              >
                {dark ? <BulbFilled style={{ color: '#f7b733' }} /> : <BulbOutlined />}
              </span>
            </Tooltip>
            <span className="live-chip">
              <span className="dot" aria-hidden="true" />
              {overview?.total ? (
                <>
                  已收录 <b style={{ color: '#e3350d', fontVariantNumeric: 'tabular-nums' }}>{overview.total}</b> 只 ·{' '}
                  {overview.type_count} 种属性
                </>
              ) : (
                '暂无数据，请先执行爬取'
              )}
            </span>
          </span>
        </Header>
        <Content style={{ margin: 24, maxWidth: 1440, width: '100%', marginInline: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>

      <Modal
        open={searchOpen}
        onCancel={() => setSearchOpen(false)}
        footer={null}
        closable={false}
        width={560}
        className="search-modal"
        styles={{ body: { padding: 16 } }}
        destroyOnClose
      >
        <div className="search-modal-head">
          <span className="search-modal-title">全局搜索</span>
          <span className="search-modal-hint">Ctrl+K 随时唤起</span>
        </div>
        <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
      </Modal>

      <CompareBar />
    </Layout>
  )
}
