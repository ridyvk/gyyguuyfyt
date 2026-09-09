import assert from 'node:assert/strict'
import { test } from 'node:test'
import { disclosureDocumentUrl } from '../src/lib/disclosureLinks.ts'
import { getMarketBreadth } from '../src/lib/marketBreadth.ts'
import { swipeDestination } from '../src/lib/swipeNavigation.ts'

test('the 3D summary counts only comparable quotes from the selected trading day', () => {
  const stock = (changePercent: number | undefined, date = '2026-09-08', stale = false) => ({
    stockPrice: { code: '0000', close: 100, changePercent, date, stale, source: 'Yahoo Finance' },
  })
  const input = [stock(2), stock(-3), stock(0), stock(undefined), stock(NaN), stock(Infinity), stock(1, '2026-09-07'), stock(-1, '2026-09-08', true), {}]
  assert.deepEqual(getMarketBreadth(input, '2026-09-08'), { up: 1, down: 1, flat: 1 })
  assert.equal(input[0].stockPrice?.changePercent, 2)
})
test('missing trading dates show no inferred zero-change quotes', () => {
  assert.deepEqual(getMarketBreadth([]), { up: 0, down: 0, flat: 0 })
})
test('both legacy EDINET viewer query formats resolve to the matching public PDF', () => {
  for (const suffix of ['S100XS9W', 'S100XS9W=']) {
    assert.equal(disclosureDocumentUrl(`https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?${suffix}`), 'https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/S100XS9W.pdf')
  }
})
test('TDnet PDFs and other source links keep their original identity', () => {
  for (const link of ['https://www.release.tdnet.info/inbs/140120260908123456.pdf', 'https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/S100XS9W.pdf', 'https://example.com/WZEK0040.aspx?S100XS9W']) {
    assert.equal(disclosureDocumentUrl(link), link)
  }
})
test('unrecognized viewer links are not rewritten to invented documents', () => {
  for (const link of ['', 'not-a-url', 'https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?missing']) assert.equal(disclosureDocumentUrl(link), link)
})
test('a horizontal swipe follows the same six destinations as the bottom navigation', () => {
  assert.deepEqual(swipeDestination('/', -110, 9, 240), { path: '/map', direction: 1 })
  assert.deepEqual(swipeDestination('/universe', 110, 9, 240), { path: '/map', direction: -1 })
})
test('scrolling, small drags, long presses and detail pages do not navigate', () => {
  assert.equal(swipeDestination('/map', -100, 70, 240), null)
  assert.equal(swipeDestination('/map', -20, 0, 240), null)
  assert.equal(swipeDestination('/map', -120, 0, 900), null)
  assert.equal(swipeDestination('/company/7203', -120, 0, 240), null)
  assert.equal(swipeDestination('/', 120, 0, 240), null)
  assert.equal(swipeDestination('/compare', -120, 0, 240), null)
})
