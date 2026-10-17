import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Form,
  Select,
  InputNumber,
  Button,
  Progress,
  Table,
  Tag,
  Space,
  App as AntApp,
  Descriptions,
  Alert,
  Typography,
} from 'antd'
import { PlayCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { triggerCrawl, listJobs, cancelJob, getScheduler, getRobots, getFetchers, runSchedulerNow } from '@/api/crawl'
import { useCrawlJob } from '@/hooks/useCrawlJob'

const STATUS_COLOR = {
  pending: 'default',
  running: 'processing',
  cancelling: 'warning',
  success: 'success',
  failed: 'error',
  cancelled: 'default',
}

const STATUS_TEXT = {
  pending: '排队中',
  running: '运行中',
  cancelling: '取消中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

export default function CrawlPage() {
  const { message } = AntApp.useApp()
  const queryClient = useQueryClient()
  const [form] = Form.useForm()
  const [jobId, setJobId] = useState(null)

  const { data: fetchers } = useQuery({ queryKey: ['fetchers'], queryFn: getFetchers })
  const { data: robots } = useQuery({ queryKey: ['robots'], queryFn: getRobots })
  const { data: scheduler, refetch: refetchScheduler } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getScheduler,
    refetchInterval: 15000,
  })
  const { data: jobs, refetch: refetchJobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => listJobs({ page: 1, page_size: 20 }),
  })

  const job = useCrawlJob(jobId)

  const triggerMutation = useMutation({
    mutationFn: triggerCrawl,
    onSuccess: (data) => {
      setJobId(data.job_id)
      message.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (err) => message.error(err.message),
  })

  const cancelMutation = useMutation({
    mutationFn: cancelJob,
    onSuccess: () => {
      message.info('已发起取消')
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (err) => message.error(err.message),
  })

  const runNowMutation = useMutation({
    mutationFn: runSchedulerNow,
    onSuccess: (data) => {
      setJobId(data.job_id)
      message.success(data.message)
    },
    onError: (err) => message.error(err.message),
  })

  const active = job.data
  const isRunning = active && ['pending', 'running', 'cancelling'].includes(active.status)

  useEffect(() => {
    if (active && ['success', 'failed', 'cancelled'].includes(active.status)) {
      refetchJobs()
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['pokemon'] })
    }
  }, [active?.status])

  const columns = [
    { title: '#', dataIndex: 'id', width: 60 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s) => <Tag color={STATUS_COLOR[s]}>{STATUS_TEXT[s] || s}</Tag>,
    },
    { title: '模式', dataIndex: 'job_type', width: 90 },
    { title: '抓取器', dataIndex: 'fetcher', width: 90 },
    { title: '进度', dataIndex: 'progress', width: 120, render: (p) => `${(p || 0).toFixed(1)}%` },
    {
      title: '结果',
      key: 'result',
      render: (_, r) =>
        `新增 ${r.inserted} / 更新 ${r.updated} / 未变 ${r.skipped} / 失败 ${r.failed}`,
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      width: 90,
      render: (d) => (d ? `${(d / 1000).toFixed(1)}s` : '—'),
    },
    { title: '说明', dataIndex: 'message', ellipsis: true },
  ]

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <div className="page-banner">
        <div className="crumbs">
          <span>POKÉDEX</span>
          <span className="crumbs-sep">/</span>
          <span className="crumbs-cur">CRAWLER</span>
        </div>
        <h3 className="page-banner-title">
          爬取<span className="grad-text">管理</span>
        </h3>
        <p className="page-banner-sub">CRAWLER CONTROL · 双引擎抓取 · robots 合规 · 定时调度</p>
        <div className="page-banner-badges">
          <span className="pk-badge">httpx <span style={{ color: '#ffd9a0' }}>静态</span> / playwright <span style={{ color: '#ffd9a0' }}>动态</span></span>
          <span className="pk-badge">限速 · 并发控制 · 失败重试</span>
        </div>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card className="list-card" title="触发爬取">
            <Form
              form={form}
              layout="vertical"
              initialValues={{ mode: 'range', fetcher: 'httpx', limit: 100, concurrency: 6 }}
              onFinish={(values) => triggerMutation.mutate(values)}
            >
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="mode" label="模式">
                    <Select
                      options={[
                        { value: 'range', label: '范围抓取（前 N 条）' },
                        { value: 'full', label: '全量抓取（1351 条）' },
                        { value: 'incremental', label: '增量更新' },
                        { value: 'retry_failed', label: '重试失败项' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="fetcher" label="抓取器">
                    <Select
                      options={(fetchers?.available || ['httpx', 'playwright']).map((f) => ({
                        value: f,
                        label: f === 'httpx' ? 'httpx（静态，快）' : 'playwright（动态渲染）',
                      }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="limit" label="数量上限">
                    <InputNumber min={1} max={2000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="concurrency" label="并发数">
                    <InputNumber min={1} max={16} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Space>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  htmlType="submit"
                  loading={triggerMutation.isPending || isRunning}
                >
                  开始抓取
                </Button>
                <Button
                  danger
                  icon={<StopOutlined />}
                  disabled={!isRunning || active?.status === 'cancelling'}
                  onClick={() => cancelMutation.mutate(active.id)}
                >
                  取消任务
                </Button>
                <Button icon={<ReloadOutlined />} onClick={() => refetchJobs()}>
                  刷新历史
                </Button>
              </Space>
            </Form>

            {active && (
              <div style={{ marginTop: 20 }}>
                <Space orientation="vertical" style={{ width: '100%' }} size={4}>
                  <Space>
                    <Typography.Text strong>任务 #{active.id}</Typography.Text>
                    <Tag color={STATUS_COLOR[active.status]}>
                      {STATUS_TEXT[active.status] || active.status}
                    </Tag>
                    {active.eta_seconds != null && isRunning && (
                      <Typography.Text type="secondary">预计还需 {active.eta_seconds}s</Typography.Text>
                    )}
                  </Space>
                  <Progress
                    percent={active.progress || 0}
                    status={
                      active.status === 'failed'
                        ? 'exception'
                        : active.status === 'success'
                          ? 'success'
                          : 'active'
                    }
                  />
                  <Typography.Text type="secondary">
                    {active.message}
                    {active.processed ? `（${active.processed}/${active.total}，请求 ${active.request_count} 次）` : ''}
                  </Typography.Text>
                  {active.error_detail && (
                    <Alert type="error" message={active.error_detail} showIcon />
                  )}
                </Space>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card className="chart-card" title="礼貌爬取状态" size="small">
            {robots ? (
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="robots.txt">
                  <Tag color={robots.allowed ? 'success' : 'error'}>
                    {robots.allowed ? '允许抓取' : '禁止抓取'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Disallow 规则">
                  {robots.has_disallow ? '有' : '无'}
                </Descriptions.Item>
                <Descriptions.Item label="请求间隔">
                  {robots.effective_delay_ms} ms
                </Descriptions.Item>
                <Descriptions.Item label="User-Agent">{robots.user_agent}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{robots.fetched_at || '—'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Typography.Text type="secondary">加载中…</Typography.Text>
            )}
          </Card>

          <Card className="chart-card" title="定时任务" size="small" style={{ marginTop: 16 }}>
            <Space orientation="vertical" style={{ width: '100%' }}>
              {(scheduler?.items || []).length ? (
                scheduler.items.map((s) => (
                  <Card key={s.id} size="small" type="inner" title={s.name}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      下次执行：{s.next_run_at?.slice(0, 19).replace('T', ' ') || '—'}
                    </Typography.Text>
                    <div style={{ marginTop: 8 }}>
                      <Button
                        size="small"
                        onClick={() => runNowMutation.mutate(s.id)}
                        disabled={!!isRunning}
                      >
                        立即执行
                      </Button>
                    </div>
                  </Card>
                ))
              ) : (
                <Typography.Text type="secondary">未启用定时调度</Typography.Text>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      <Card className="list-card" title="任务历史" size="small">
        <Table
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={jobs?.items || []}
          pagination={{ pageSize: 8, size: 'small' }}
        />
      </Card>
    </Space>
  )
}
