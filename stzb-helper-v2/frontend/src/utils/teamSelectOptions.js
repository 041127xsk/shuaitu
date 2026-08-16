const normalizeSearchText = (value) => String(value ?? '').trim().toLowerCase()

const sortByLabel = (a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN')

export const buildHeroOptions = (heroMap) => Object.entries(heroMap || {})
  .map(([id, hero]) => {
    const name = hero?.name || `ID:${id}`
    const country = hero?.country || hero?.contory || ''
    const type = hero?.type || ''
    const uniqueName = hero?.uniqueName || ''
    return {
      label: `${name}${country || type ? ` · ${country}${type}` : ''} · ID ${id}`,
      value: Number(id),
      search: [id, name, uniqueName, country, type].filter(Boolean).join(' ')
    }
  })
  .sort(sortByLabel)

export const buildSkillOptions = (skillMap) => Object.entries(skillMap || {})
  .map(([id, skill]) => {
    const name = skill?.name || `ID:${id}`
    const type = skill?.type || ''
    const quality = skill?.zfQuality || ''
    return {
      label: `${name}${type ? ` · ${type}` : ''}${quality ? ` · ${quality}` : ''} · ID ${id}`,
      value: Number(id),
      search: [id, name, type, quality].filter(Boolean).join(' ')
    }
  })
  .sort(sortByLabel)

export const filterSelectOption = (pattern, option) => {
  const keyword = normalizeSearchText(pattern)
  if (!keyword) return true
  return normalizeSearchText(`${option?.search || ''} ${option?.label || ''}`).includes(keyword)
}

export const selectIdValue = (value) => {
  const num = Number(value || 0)
  return num > 0 ? num : null
}

export const toNumericSelectValue = (value) => {
  if (value === null || value === undefined || value === '') return 0
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? num : 0
}
