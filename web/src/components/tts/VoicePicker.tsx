import { useMemo, useRef, useState } from 'react'
import { Badge, CloseIcon, Input, Slider, cn } from '../../ui'

/** A selected voice with its relative blend weight (server normalizes ratios). */
export interface VoiceSelection {
  id: string
  weight: number
}

/**
 * Serialize selections into the API `voice` parameter: `a+b` when all weights
 * are equal (weights are redundant), `a(1)+b(0.5)` otherwise.
 */
export function serializeVoices(selected: VoiceSelection[]): string {
  if (selected.length === 0) return ''
  const equal = selected.every((s) => s.weight === selected[0].weight)
  if (selected.length === 1 || equal) return selected.map((s) => s.id).join('+')
  return selected.map((s) => `${s.id}(${s.weight})`).join('+')
}

/** Kokoro voice ids are `<lang><gender>_<name>`, e.g. af_heart, bm_george. */
const LANGUAGES: Record<string, string> = {
  a: 'English (US)',
  b: 'English (GB)',
  e: 'Spanish',
  f: 'French',
  h: 'Hindi',
  i: 'Italian',
  j: 'Japanese',
  p: 'Portuguese (BR)',
  z: 'Chinese (Mandarin)',
}

function voiceGroup(v: string): string {
  const lang = LANGUAGES[v[0]] ?? 'Other'
  const gender = v[1] === 'f' ? 'female' : v[1] === 'm' ? 'male' : ''
  return gender ? `${lang} · ${gender}` : lang
}

/**
 * Multi-select voice picker: a searchable input with a dropdown of available
 * voices grouped by language, selected voices shown as removable chips.
 * With two or more voices selected, a blend panel exposes one slider per
 * voice; the mix is shown as each voice's percentage share, which is what the
 * server's ratio normalization actually produces.
 */
export function VoicePicker({
  voices,
  selected,
  onChange,
  disabled,
}: {
  voices: string[]
  selected: VoiceSelection[]
  onChange: (next: VoiceSelection[]) => void
  disabled?: boolean
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  const selectedIds = useMemo(() => selected.map((s) => s.id), [selected])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return voices
      .filter((v) => !selectedIds.includes(v))
      .filter(
        (v) =>
          !q ||
          v.toLowerCase().includes(q) ||
          voiceGroup(v).toLowerCase().includes(q),
      )
      .slice(0, 120)
  }, [voices, selectedIds, query])

  const grouped = useMemo(() => {
    const groups = new Map<string, string[]>()
    for (const v of filtered) {
      const g = voiceGroup(v)
      const list = groups.get(g)
      if (list) list.push(v)
      else groups.set(g, [v])
    }
    return [...groups.entries()]
  }, [filtered])

  const totalWeight = useMemo(
    () => selected.reduce((sum, s) => sum + s.weight, 0),
    [selected],
  )

  const add = (v: string) => {
    if (!selectedIds.includes(v)) onChange([...selected, { id: v, weight: 1 }])
    setQuery('')
  }
  const remove = (v: string) => onChange(selected.filter((s) => s.id !== v))
  const setWeight = (v: string, weight: number) =>
    onChange(selected.map((s) => (s.id === v ? { ...s, weight } : s)))

  return (
    <div className="flex flex-col gap-2" ref={wrapRef}>
      <div className="relative">
        <Input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls="voice-listbox"
          placeholder={
            voices.length ? 'Search voices…' : 'Loading voices…'
          }
          value={query}
          disabled={disabled || voices.length === 0}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && filtered[0]) {
              e.preventDefault()
              add(filtered[0])
            }
          }}
        />
        {open && filtered.length > 0 && (
          <ul
            id="voice-listbox"
            role="listbox"
            className="absolute z-20 mt-1 max-h-72 w-full animate-fade-in overflow-auto rounded-xl border border-border bg-elevated p-1 shadow-elevated"
          >
            {grouped.map(([group, groupVoices]) => (
              <li key={group}>
                <div className="sticky top-0 bg-elevated px-3 pb-1 pt-2 text-[0.65rem] font-semibold uppercase tracking-wide text-faint">
                  {group}
                </div>
                <ul>
                  {groupVoices.map((v) => (
                    <li key={v}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={false}
                        onMouseDown={(e) => {
                          e.preventDefault()
                          add(v)
                        }}
                        className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-fg hover:bg-accent-soft hover:text-accent"
                      >
                        <span className="font-mono">{v}</span>
                        <span className="text-xs text-faint">add</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((s, i) => (
            <span key={s.id} className="inline-flex items-center gap-1">
              {i > 0 && (
                <span className="text-xs font-semibold text-faint">+</span>
              )}
              <Badge variant="accent" className="gap-1.5 py-1 pl-2.5 pr-1.5">
                <span className="font-mono">{s.id}</span>
                <button
                  type="button"
                  aria-label={`Remove ${s.id}`}
                  onClick={() => remove(s.id)}
                  className={cn(
                    'flex h-4 w-4 items-center justify-center rounded-sm text-[0.85rem]',
                    'text-accent/70 hover:bg-accent/20 hover:text-accent',
                  )}
                >
                  <CloseIcon />
                </button>
              </Badge>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-faint">
          Select one or more voices. Multiple voices are blended together.
        </p>
      )}

      {selected.length >= 2 && (
        <div className="mt-1 flex flex-col gap-2 border-t border-border pt-3">
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-faint">
              Blend
            </span>
            <button
              type="button"
              className="text-[0.7rem] text-muted hover:text-accent"
              onClick={() =>
                onChange(selected.map((s) => ({ ...s, weight: 1 })))
              }
            >
              reset to equal
            </button>
          </div>
          {selected.map((s) => (
            <div key={s.id} className="flex items-center gap-2">
              <span
                className="w-24 shrink-0 truncate font-mono text-xs text-muted"
                title={s.id}
              >
                {s.id}
              </span>
              <Slider
                aria-label={`Blend weight for ${s.id}`}
                min={0.1}
                max={2}
                step={0.05}
                value={s.weight}
                disabled={disabled}
                onChange={(e) => setWeight(s.id, parseFloat(e.target.value))}
              />
              <span className="w-10 shrink-0 text-right text-xs tabular-nums text-muted">
                {totalWeight > 0
                  ? `${Math.round((s.weight / totalWeight) * 100)}%`
                  : '–'}
              </span>
            </div>
          ))}
          <p className="text-[0.7rem] leading-snug text-faint">
            Percentages are each voice&apos;s share of the final blend.
          </p>
        </div>
      )}
    </div>
  )
}
