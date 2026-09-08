/** Open existing EDINET viewer links as public PDFs, without an API key. */
export function disclosureDocumentUrl(value: string): string {
  try {
    const url = new URL(value)
    if (url.hostname !== 'disclosure2.edinet-fsa.go.jp'
      || !/^\/WZEK0040\.aspx$/i.test(url.pathname)) return value
    const documentId = url.search.slice(1).match(/^(S[0-9A-Z]{7})(?:=)?$/)?.[1]
    return documentId
      ? `https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/${documentId}.pdf`
      : value
  } catch {
    return value
  }
}
