import { useEffect, useState } from 'react'
import { typeColor } from '@/utils/constants'

/**
 * 宝可梦头像。
 *
 * 官方图鉴图片托管在 raw.githubusercontent.com，国内网络常不可达。
 * 加载失败时降级为「属性主色 + 首字母」的圆形占位，避免出现裂图或空白格。
 */
export default function PokemonAvatar({ src, name, alt, type, size = 40, ring = false }) {
  const [failed, setFailed] = useState(false)

  // 换条目时重置失败状态
  useEffect(() => setFailed(false), [src])

  const bg = typeColor(type)
  const initial = (name || '?').trim().charAt(0).toUpperCase()

  const placeholder = (
    <span
      title={alt || name}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        flex: '0 0 auto',
        borderRadius: '50%',
        background: `radial-gradient(circle at 30% 30%, ${bg}, ${bg} 70%, rgba(0,0,0,0.25))`,
        color: '#fff',
        fontWeight: 700,
        fontSize: Math.max(12, Math.round(size * 0.42)),
        lineHeight: 1,
        boxShadow: `0 2px 8px ${bg}55, inset 0 2px 4px rgba(255,255,255,0.35), inset 0 -2px 4px rgba(0,0,0,0.18)`,
        userSelect: 'none',
        textShadow: '0 1px 2px rgba(0,0,0,0.35)',
      }}
    >
      {initial}
    </span>
  )

  const img = failed || !src ? null : (
    <img
      src={src}
      alt={alt || name}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{
        objectFit: 'contain',
        display: 'block',
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #f7f9fc, #eef1f8)',
        boxShadow: `0 0 0 2px #fff, 0 0 0 4px ${bg}66, 0 4px 12px rgba(23,30,51,0.15)`,
      }}
    />
  )

  if (ring) {
    return (
      <span className="avatar-ring" style={{ width: size + 12, height: size + 12 }}>
        {img || placeholder}
      </span>
    )
  }
  return img || placeholder
}
