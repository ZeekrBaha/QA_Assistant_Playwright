export function analyzeLocatorConfidence(distilledDom = '') {
  if (!distilledDom.trim()) return []

  const parser = new DOMParser()
  const doc = parser.parseFromString(distilledDom, 'text/html')
  const elements = Array.from(doc.body.querySelectorAll('button,a,input,select,textarea,label,[role],[data-testid],[data-test-id],[id],[aria-label]'))

  return elements.map((element) => {
    const selector = selectorForElement(element)
    const strategy = strategyForElement(element)
    return {
      tag: element.tagName.toLowerCase(),
      text: cleanText(element.textContent || element.getAttribute('aria-label') || element.getAttribute('placeholder') || ''),
      selector,
      strategy,
      confidence: confidenceForStrategy(strategy),
      stability: stabilityForStrategy(strategy),
      source: element.outerHTML,
    }
  })
}

function selectorForElement(element) {
  if (element.getAttribute('role')) return `getByRole('${element.getAttribute('role')}')`
  if (element.getAttribute('aria-label')) return `getByLabel('${element.getAttribute('aria-label')}')`
  if (element.getAttribute('data-testid')) return `getByTestId('${element.getAttribute('data-testid')}')`
  if (element.getAttribute('data-test-id')) return `getByTestId('${element.getAttribute('data-test-id')}')`
  if (element.id) return `#${element.id}`
  if (element.getAttribute('name')) return `[name="${element.getAttribute('name')}"]`
  if (cleanText(element.textContent)) return `text=${cleanText(element.textContent)}`
  return element.tagName.toLowerCase()
}

function strategyForElement(element) {
  if (element.getAttribute('role')) return 'role'
  if (element.getAttribute('aria-label')) return 'label'
  if (element.getAttribute('data-testid') || element.getAttribute('data-test-id')) return 'test-id'
  if (element.id) return 'id'
  if (element.getAttribute('name')) return 'name'
  if (cleanText(element.textContent)) return 'text'
  return 'css'
}

function confidenceForStrategy(strategy) {
  return {
    role: 'high',
    label: 'high',
    'test-id': 'high',
    id: 'medium',
    name: 'medium',
    text: 'medium',
    css: 'low',
  }[strategy] || 'low'
}

function stabilityForStrategy(strategy) {
  return ['role', 'label', 'test-id', 'id'].includes(strategy) ? 'stable' : 'brittle'
}

function cleanText(text) {
  return text.replace(/\s+/g, ' ').trim().slice(0, 80)
}
