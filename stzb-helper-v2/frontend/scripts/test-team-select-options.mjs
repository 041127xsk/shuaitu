import assert from 'node:assert/strict'
import { buildNameMappingIndex, getMappedName, mergeHeroMapWithMappings, mergeSkillMapWithMappings } from '../src/utils/nameMappings.js'
import { buildHeroOptions, buildSkillOptions, filterSelectOption, selectIdValue, toNumericSelectValue } from '../src/utils/teamSelectOptions.js'

const heroOptions = buildHeroOptions({
  1001: { name: '群吕布', uniqueName: '神吕', country: '群', type: '骑' },
  2002: { name: '张机', uniqueName: '', country: '汉', type: '弓' }
})

assert.equal(heroOptions.length, 2)
assert.equal(heroOptions[0].value, 1001)
assert.match(heroOptions[0].label, /群吕布/)
assert.equal(filterSelectOption('神吕', heroOptions[0]), true)
assert.equal(filterSelectOption('1001', heroOptions[0]), true)
assert.equal(filterSelectOption('不存在', heroOptions[0]), false)

const skillOptions = buildSkillOptions({
  3001: { name: '天下无双', type: '主动', zfQuality: 'S' },
  3002: { name: '垒实迎击', type: '被动', zfQuality: 'S' }
})

assert.equal(skillOptions.length, 2)
const primarySkill = skillOptions.find((option) => option.value === 3001)
const secondSkill = skillOptions.find((option) => option.value === 3002)
assert.match(primarySkill.label, /天下无双/)
assert.equal(filterSelectOption('主动', primarySkill), true)
assert.equal(filterSelectOption('3002', secondSkill), true)

assert.equal(selectIdValue(0), null)
assert.equal(selectIdValue(''), null)
assert.equal(selectIdValue('1001'), 1001)
assert.equal(toNumericSelectValue(null), 0)
assert.equal(toNumericSelectValue(''), 0)
assert.equal(toNumericSelectValue('1001'), 1001)
assert.equal(toNumericSelectValue('abc'), 0)

const mappingIndex = buildNameMappingIndex([
  { kind: 'hero', id: 1001, name: '手填吕布' },
  { kind: 'hero', id: 9999, name: '新武将' },
  { kind: 'skill', id: 8888, name: '新战法' },
  { kind: 'gear', id: 7777, name: '新宝物' }
])

assert.equal(getMappedName(mappingIndex, 'hero', 1001), '手填吕布')
assert.equal(getMappedName(mappingIndex, 'gear', 7777), '新宝物')
assert.equal(getMappedName(mappingIndex, 'gear', 1), '')

const mappedHeroOptions = buildHeroOptions(mergeHeroMapWithMappings({ 1001: { name: '群吕布', country: '群', type: '骑' } }, mappingIndex))
assert.equal(mappedHeroOptions.find((option) => option.value === 1001).label.includes('手填吕布'), true)
assert.equal(mappedHeroOptions.find((option) => option.value === 9999).label.includes('新武将'), true)

const mappedSkillOptions = buildSkillOptions(mergeSkillMapWithMappings({ 3001: { name: '天下无双', type: '主动', zfQuality: 'S' } }, mappingIndex))
assert.equal(mappedSkillOptions.find((option) => option.value === 8888).label.includes('新战法'), true)
