import { typeColor, typeZh } from '@/utils/constants'

export default function TypeTag({ name }) {
  if (!name) return <span style={{ color: '#bfbfbf' }}>—</span>
  return (
    <span className="type-tag" style={{ background: typeColor(name) }}>
      {typeZh(name)}
    </span>
  )
}
