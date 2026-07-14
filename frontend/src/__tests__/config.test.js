import { describe, expect, it } from 'vitest'
import { loadTemperature } from '../lib/config'

function storageWith(value) {
  return {
    getItem(key) {
      return key === 'qa_temperature' ? value : null
    },
  }
}

describe('config helpers', () => {
  it('restores temperature 0 instead of falling back to 0.6', () => {
    expect(loadTemperature(storageWith('0'))).toBe(0)
  })

  it('falls back for missing or invalid temperatures', () => {
    expect(loadTemperature(storageWith(null))).toBe(0.6)
    expect(loadTemperature(storageWith('not-a-number'))).toBe(0.6)
    expect(loadTemperature(storageWith('-1'))).toBe(0.6)
    expect(loadTemperature(storageWith('3'))).toBe(0.6)
  })
})
