import ReactECharts from 'echarts-for-react'
import { useThemeStore } from '@/store/themeStore'

/** 统一封装：高度、loading、重渲染策略一致；暗色模式注入浅色文字 */
export default function EChart({ option, height = 320, loading = false, onEvents }) {
  const dark = useThemeStore((s) => s.mode === 'dark')
  const themed = dark
    ? { ...option, textStyle: { ...(option.textStyle || {}), color: '#c6cddb' } }
    : option
  return (
    <ReactECharts
      option={themed}
      notMerge
      lazyUpdate
      style={{ height, width: '100%' }}
      showLoading={loading}
      loadingOption={{
        text: '加载中…',
        color: '#e3350d',
        textColor: dark ? '#c6cddb' : '#595959',
      }}
      onEvents={onEvents}
      opts={{ renderer: 'canvas' }}
    />
  )
}
