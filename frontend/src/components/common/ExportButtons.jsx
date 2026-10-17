import { Button, Space, App as AntApp } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { downloadExport } from '@/api/export'

export default function ExportButtons({ filters }) {
  const { message } = AntApp.useApp()
  const run = async (format) => {
    try {
      await downloadExport(filters, format)
      message.success(`已导出 ${format.toUpperCase()} 文件`)
    } catch (err) {
      message.error(`导出失败：${err.message}`)
    }
  }
  return (
    <Space>
      <Button icon={<DownloadOutlined />} onClick={() => run('csv')}>
        导出 CSV
      </Button>
      <Button icon={<DownloadOutlined />} onClick={() => run('json')}>
        导出 JSON
      </Button>
    </Space>
  )
}
