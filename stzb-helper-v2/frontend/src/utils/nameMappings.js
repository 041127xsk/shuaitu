const validKinds = new Set(['hero', 'skill', 'gear'])

export const normalizeMappingKind = (kind) => {
  const value = String(kind ?? '').trim().toLowerCase()
  if (value === '武将') return 'hero'
  if (value === '战法') return 'skill'
  if (value === '宝物') return 'gear'
  return value
}

export const buildNameMappingIndex = (rows = []) => {
  const index = { hero: {}, skill: {}, gear: {} }
  rows.forEach((row) => {
    const kind = normalizeMappingKind(row?.kind)
    const id = Number(row?.id ?? row?.ref_id ?? 0)
    const name = String(row?.name ?? '').trim()
    if (!validKinds.has(kind) || !id || !name) return
    index[kind][String(id)] = {
      ...row,
      kind,
      id,
      name
    }
  })
  return index
}

export const getMappedName = (index, kind, id) => {
  const normalizedKind = normalizeMappingKind(kind)
  if (!validKinds.has(normalizedKind) || !id) return ''
  return index?.[normalizedKind]?.[String(Number(id))]?.name || ''
}

export const mergeHeroMapWithMappings = (heroMap = {}, index = {}) => {
  const merged = { ...heroMap }
  Object.values(index.hero || {}).forEach((row) => {
    const old = merged[String(row.id)] || {}
    merged[String(row.id)] = {
      ...old,
      name: row.name,
      uniqueName: row.name,
      country: old.country || '',
      type: old.type || ''
    }
  })
  return merged
}

export const mergeSkillMapWithMappings = (skillMap = {}, index = {}) => {
  const merged = { ...skillMap }
  Object.values(index.skill || {}).forEach((row) => {
    const old = merged[String(row.id)] || {}
    merged[String(row.id)] = {
      ...old,
      name: row.name,
      type: old.type || '',
      zfQuality: old.zfQuality || ''
    }
  })
  return merged
}
