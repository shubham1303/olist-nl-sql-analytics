// A small PostgreSQL tokenizer for highlighting only: it never decides what runs.
// Joining every token's text gives back the input exactly.

export type TokenKind = 'keyword' | 'function' | 'string' | 'number' | 'comment' | 'identifier' | 'punct' | 'space'

export interface Token {
  kind: TokenKind
  text: string
}

const KEYWORDS = new Set(
  `select from where group by order having limit offset join inner left right full outer cross on
  as and or not in is null true false case when then else end with distinct union all intersect
  except between like ilike exists any asc desc nulls first last over partition filter within
  interval date timestamp cast using lateral rows range preceding following current row unbounded`
    .split(/\s+/)
    .filter(Boolean),
)

const PATTERNS: [TokenKind, RegExp][] = [
  ['space', /^\s+/],
  ['comment', /^--[^\n]*/],
  ['comment', /^\/\*[\s\S]*?(?:\*\/|$)/],
  ['string', /^[eE]?'(?:[^']|'')*(?:'|$)/],
  ['string', /^\$\$[\s\S]*?(?:\$\$|$)/],
  ['identifier', /^"(?:[^"]|"")*(?:"|$)/],
  ['number', /^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/],
  ['identifier', /^[A-Za-z_][A-Za-z0-9_$]*/],
  ['punct', /^(?:::|<=|>=|<>|!=|\|\||[^\sA-Za-z0-9_])/],
]

export function tokenize(sql: string): Token[] {
  const tokens: Token[] = []
  let rest = sql
  while (rest.length > 0) {
    let matched = false
    for (const [kind, pattern] of PATTERNS) {
      const m = pattern.exec(rest)
      if (!m) continue
      let tokenKind = kind
      const text = m[0]
      if (kind === 'identifier' && !text.startsWith('"')) {
        const lower = text.toLowerCase()
        if (KEYWORDS.has(lower)) tokenKind = 'keyword'
        else if (/^\s*\(/.test(rest.slice(text.length))) tokenKind = 'function'
      }
      tokens.push({ kind: tokenKind, text })
      rest = rest.slice(text.length)
      matched = true
      break
    }
    if (!matched) {
      tokens.push({ kind: 'punct', text: rest[0]! })
      rest = rest.slice(1)
    }
  }
  return tokens
}
