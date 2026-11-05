// Construct for Hermes Desktop: each built construct live in the chat, a gallery of them, and job progress.
//
// A construct's page is several megabytes of self-contained HTML, more than a frame's address can carry. The
// agent half writes a small loader page beside it and hands the loader to the chat as the MEDIA file. This
// half shows the loader in a sandboxed frame, fetches the full page from the plugin's own backend
// (dashboard/plugin_api.py) and posts it to the loader, which replaces itself with it. The toolbar talks to
// the page the same way: a few validated messages that become the viewer's own keys.
import * as sdk from '@hermes/plugin-sdk'
import * as React from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const { useCallback, useEffect, useRef, useState } = React

const ID = 'construct'
const GALLERY = '/constructs'
const SLUG = /^[a-z0-9][a-z0-9-]{0,62}$/
const BUILD = /^\d{8}-\d{6}-[0-9a-f]{4}$/
const SHOWN = /[\\/]shown[\\/]([a-z0-9][a-z0-9-]{0,62})[\\/](\d{8}-\d{6}-[0-9a-f]{4})[\\/](loader|construct)\.html$/
const PAGE_MAX = 64 * 1024 * 1024
const LOADER_MAX = 256 * 1024
const KEYS = new Set(['p', 's', 'r', 'm', 'l', 't', ' ', '1', '2', '3', '4', '5', '6'])
const FRAME_BG = '#050205' // the construct's own night: the frame shows it before the page arrives

let CTX = null

// ---------------------------------------------------------------------------- small helpers

function parsed(value) {
  if (value && typeof value === 'object') return value
  if (typeof value !== 'string' || value.length > 1_000_000) return null
  try {
    const v = JSON.parse(value)
    return v && typeof v === 'object' ? v : null
  } catch {
    return null
  }
}

// The build a media file belongs to: from the producing call's result, else from the file's own path.
function buildOf(file, result) {
  const r = parsed(result)
  if (r && SLUG.test(String(r.project || '')) && BUILD.test(String(r.build || ''))) {
    return { project: r.project, build: r.build, title: typeof r.title === 'string' ? r.title : '', parts: r.parts }
  }
  const m = SHOWN.exec(String((file && file.path) || ''))
  return m ? { project: m[1], build: m[2], title: '', parts: null } : null
}

function rest(path, opts) {
  if (!CTX || typeof CTX.rest !== 'function') return Promise.reject(new Error('the plugin backend is not available'))
  return CTX.rest(path, opts)
}

function query(project, build) {
  return 'project=' + encodeURIComponent(project) + (build ? '&build=' + encodeURIComponent(build) : '')
}

function notify(kind, message) {
  try {
    if (sdk.host && typeof sdk.host.notify === 'function') sdk.host.notify({ kind, message })
  } catch {
    /* a host without toasts */
  }
}

function errorText(err) {
  const text = String((err && (err.message || err.detail)) || err || 'unknown error')
  if (/404/.test(text)) return 'This construct is no longer kept (only the newest builds of a project are).'
  if (/not found|unavailable|refused|enabled/i.test(text)) return 'The Construct plugin backend is not running: enable the plugin and restart the gateway.'
  return text.slice(0, 240)
}

function plural(n, one) {
  return n === 1 ? '1 ' + one : String(n) + ' ' + one + 's'
}

function when(iso) {
  const d = new Date(String(iso || ''))
  if (isNaN(d.getTime())) return ''
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(d)
  } catch {
    return d.toLocaleString()
  }
}

function useBusy(sessionId) {
  const atom = sdk.host && sdk.host.state && sdk.host.state.busyBySession
  const busy = typeof sdk.useValue === 'function' && atom ? sdk.useValue(atom) : null
  return !!(sessionId && busy && busy[sessionId])
}

// ---------------------------------------------------------------------------- styles (theme variables only)

const S = {
  card: { display: 'flex', flexDirection: 'column', width: '100%', maxWidth: 760, border: '1px solid var(--ui-stroke-secondary)',
    borderRadius: 10, overflow: 'hidden' },
  head: { display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', minHeight: 34,
    borderBottom: '1px solid var(--ui-stroke-secondary)' },
  title: { fontSize: 13, fontWeight: 600, color: 'var(--ui-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis',
    whiteSpace: 'nowrap', minWidth: 0 },
  meta: { fontSize: 11, color: 'var(--ui-text-tertiary)', whiteSpace: 'nowrap' },
  grow: { flex: '1 1 auto' },
  bar: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, padding: '7px 10px',
    borderTop: '1px solid var(--ui-stroke-secondary)' },
  sep: { width: 1, alignSelf: 'stretch', margin: '2px 4px', background: 'var(--ui-stroke-secondary)' },
  frameBox: { position: 'relative', width: '100%', background: FRAME_BG },
  frame: { display: 'block', width: '100%', height: '100%', border: 0, background: FRAME_BG },
  wait: { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
    textAlign: 'center', fontSize: 12, color: 'var(--ui-text-tertiary)', pointerEvents: 'none' }
}

function button(active, disabled) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 5, height: 24, padding: '0 9px', fontSize: 12, lineHeight: '22px',
    borderRadius: 6, cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.45 : 1, background: 'transparent',
    border: '1px solid ' + (active ? 'var(--ui-accent)' : 'var(--ui-stroke-secondary)'),
    color: active ? 'var(--ui-accent)' : 'var(--ui-text-secondary)'
  }
}

function Icon({ name }) {
  return typeof sdk.Codicon === 'function' ? jsx(sdk.Codicon, { name, 'aria-hidden': true, style: { fontSize: 13 } }) : null
}

function Button({ label, icon, title, active, disabled, onClick }) {
  return jsxs('button', {
    type: 'button', title: title || label, disabled: !!disabled, 'aria-pressed': active === undefined ? undefined : !!active,
    style: button(!!active, !!disabled), onClick,
    children: [icon ? jsx(Icon, { name: icon }) : null, jsx('span', { children: label })]
  })
}

// ---------------------------------------------------------------------------- the live construct

// Shows one build: the loader in a sandboxed frame, the full page posted to it once both are there.
function Hologram({ project, build, loaderUrl, height, onCard, onState, control }) {
  const frameRef = useRef(null)
  const htmlRef = useRef(null)
  const readyRef = useRef(false)
  const [src, setSrc] = useState(loaderUrl || null)
  const [failed, setFailed] = useState('')
  const [shown, setShown] = useState(false)

  const post = useCallback(message => {
    const frame = frameRef.current
    if (frame && frame.contentWindow) frame.contentWindow.postMessage(message, '*')
  }, [])

  const deliver = useCallback(() => {
    if (!readyRef.current) return
    if (htmlRef.current) {
      post({ type: 'construct:page', html: htmlRef.current })
      setShown(true)
    }
  }, [post])

  useEffect(() => {
    let live = true
    htmlRef.current = null
    setFailed('')
    setShown(false)
    rest('/view?' + query(project, build), { timeoutMs: 120000 }).then(
      view => {
        if (!live) return
        const html = view && view.html
        if (typeof html !== 'string' || html.length > PAGE_MAX || !/^\s*<!doctype html>/i.test(html.slice(0, 64))) {
          setFailed('The construct page could not be read.')
          return
        }
        htmlRef.current = html
        if (view.card && onCard) onCard(view.card)
        if (!loaderUrl) {
          const loader = view.loader
          if (typeof loader !== 'string' || loader.length > LOADER_MAX) {
            setFailed('The construct page could not be read.')
            return
          }
          setSrc('data:text/html;charset=utf-8,' + encodeURIComponent(loader))
        }
        deliver()
      },
      err => {
        if (!live) return
        const reason = errorText(err)
        setFailed(reason)
        post({ type: 'construct:failed', reason })
      }
    )
    return () => {
      live = false
    }
  }, [project, build, loaderUrl, deliver, post, onCard])

  useEffect(() => {
    if (loaderUrl) setSrc(loaderUrl)
  }, [loaderUrl])

  useEffect(() => {
    if (!CTX) return undefined
    return CTX.addEventListener(window, 'message', event => {
      const frame = frameRef.current
      if (!frame || event.source !== frame.contentWindow) return
      const d = event.data
      if (!d || typeof d !== 'object' || typeof d.type !== 'string') return
      if (d.type === 'construct:loader-ready') {
        readyRef.current = true
        deliver()
      } else if (d.type === 'construct:state' && onState) {
        onState({ ready: d.ready === true, mode: d.mode === 'provenance' ? 'provenance' : 'light', solid: d.solid === true,
          hasSolid: d.hasSolid === true })
      }
    })
  }, [deliver, onState])

  useEffect(() => {
    if (control) {
      control.current = key => {
        if (typeof key === 'string' && KEYS.has(key)) post({ type: 'construct:key', key })
      }
    }
  }, [control, post])

  const box = Object.assign({}, S.frameBox, { height })
  return jsxs('div', {
    style: box,
    children: [
      src && typeof sdk.SandboxedFrame === 'function'
        ? jsx(sdk.SandboxedFrame, {
            ref: frameRef, src, title: 'Construct', sandbox: 'allow-scripts allow-pointer-lock', style: S.frame
          })
        : null,
      failed || !shown ? jsx('div', { style: S.wait, children: failed || 'Opening the construct…' }) : null
    ]
  })
}

// The toolbar and title around a live construct; `sessionId` enables the actions that ask the agent.
function ConstructCard({ project, build, loaderUrl, title, parts, sessionId, height, extra }) {
  const control = useRef(null)
  const [card, setCard] = useState(null)
  const [view, setView] = useState({ ready: false, mode: 'light', solid: false, hasSolid: false })
  const busy = useBusy(sessionId)
  const composer = sdk.host && sdk.host.composer
  const canAsk = !!(sessionId && composer && typeof composer.submit === 'function')
  const name = (card && card.title) || title || project
  const count = card && typeof card.parts === 'number' ? card.parts : typeof parts === 'number' ? parts : null

  const press = key => control.current && control.current(key)
  const ask = text => {
    if (!canAsk || busy) return
    let ok = false
    try {
      ok = composer.submit(sessionId, text)
    } catch {
      ok = false
    }
    if (!ok) notify('info', 'Open this chat to ask for that.')
  }
  const subject = '"' + name + '" (construct project ' + project + ')'
  const openPage = async () => {
    const page = card && card.page
    if (!page || !CTX || !CTX.os) return
    const opened = typeof CTX.os.openExternal === 'function' ? await CTX.os.openExternal(page) : false
    if (!opened && typeof CTX.os.revealPath === 'function') await CTX.os.revealPath(page)
  }

  return jsxs('div', {
    style: S.card,
    children: [
      jsxs('div', {
        style: S.head,
        children: [
          jsx(Icon, { name: 'symbol-structure' }),
          jsx('div', { style: S.title, title: name, children: name }),
          count !== null ? jsx('div', { style: S.meta, children: plural(count, 'part') }) : null,
          card && card.audit_ok === false ? jsx('div', { style: S.meta, children: '· audit has errors' }) : null,
          jsx('div', { style: S.grow }),
          extra || null,
          jsx(Button, { label: 'Open in browser', icon: 'link-external', disabled: !(card && card.page), onClick: openPage,
            title: 'Open the page in your browser' })
        ]
      }),
      jsx(Hologram, { project, build, loaderUrl, height: height || 420, onCard: setCard, onState: setView, control }),
      jsxs('div', {
        style: S.bar,
        children: [
          jsx(Button, { label: 'Provenance', icon: 'eye', active: view.mode === 'provenance', disabled: !view.ready,
            title: 'How each part is known (P)', onClick: () => press('p') }),
          jsx(Button, { label: 'Solid', icon: 'circle-filled', active: view.solid, disabled: !view.ready || !view.hasSolid,
            title: 'The surfaces as a solid (S)', onClick: () => press('s') }),
          jsx(Button, { label: 'Replay', icon: 'debug-restart', disabled: !view.ready, title: 'Build it again (R)',
            onClick: () => press('r') }),
          canAsk ? jsx('div', { style: S.sep }) : null,
          canAsk ? jsx(Button, { label: 'Export a glTF', icon: 'package', disabled: busy,
            onClick: () => ask('Export the construct ' + subject + ' as a glTF (.glb) with construct_export and show me the file.') }) : null,
          canAsk ? jsx(Button, { label: 'More detail', icon: 'sparkle', disabled: busy, title: 'Make it more detailed, keep every part',
            onClick: () => ask('Make the construct ' + subject + ' more detailed: keep every part, add true detail where its identity lives, then check, build and show it.') }) : null,
          canAsk ? jsx(Button, { label: 'Review it', icon: 'search', disabled: busy,
            onClick: () => ask('Review the construct ' + subject + ' as an art director with construct_review: show me the hero and the sheets, and say what to improve first.') }) : null
        ]
      })
    ]
  })
}

// The tool media renderer: the loader a construct_build (or a construct_job that finished one) produced.
function ToolMedia({ file, result, sessionId, fallback }) {
  const [url, setUrl] = useState(null)
  const ids = buildOf(file, result)
  const isLoader = !!(file && /(^|[\\/])loader\.html$/.test(String(file.path || '')))
  useEffect(() => {
    let live = true
    if (!isLoader || !file || typeof file.resolveUrl !== 'function') return undefined
    Promise.resolve(file.resolveUrl()).then(
      u => live && setUrl(typeof u === 'string' && u.startsWith('data:') ? u.replace(/^data:[^;,]*/, 'data:text/html') : ''),
      () => live && setUrl('')
    )
    return () => {
      live = false
    }
  }, [file && file.path, isLoader])
  if (!ids || !isLoader || typeof sdk.SandboxedFrame !== 'function') return fallback || null
  if (url === null) return jsx('div', { style: Object.assign({}, S.card, { height: 120 }) }) // the loader's address is on its way
  // without the host's address for the loader (''), the card reads the loader from the plugin's backend instead
  return jsx(ConstructCard, { project: ids.project, build: ids.build, title: ids.title, parts: ids.parts, sessionId,
    loaderUrl: url || null })
}

// ---------------------------------------------------------------------------- the gallery

function Thumb({ project, build, has }) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    let live = true
    if (!has) return undefined
    rest('/thumb?' + query(project, build)).then(
      t => live && typeof t.data_url === 'string' && t.data_url.startsWith('data:image/png;base64,') && setSrc(t.data_url),
      () => {}
    )
    return () => {
      live = false
    }
  }, [project, build, has])
  return jsx('div', {
    style: { aspectRatio: '16 / 10', width: '100%', background: FRAME_BG, display: 'flex', alignItems: 'center',
      justifyContent: 'center', overflow: 'hidden' },
    children: src ? jsx('img', { src, alt: '', style: { width: '100%', height: '100%', objectFit: 'cover' } })
      : jsx(Icon, { name: 'symbol-structure' })
  })
}

function Tile({ item, onOpen }) {
  return jsxs('button', {
    type: 'button', onClick: () => onOpen(item), title: item.title || item.project,
    style: { display: 'flex', flexDirection: 'column', textAlign: 'left', padding: 0, borderRadius: 10, overflow: 'hidden',
      cursor: 'pointer', background: 'transparent', border: '1px solid var(--ui-stroke-secondary)' },
    children: [
      jsx(Thumb, { project: item.project, build: item.build, has: !!item.has_thumb }),
      jsxs('div', {
        style: { padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 },
        children: [
          jsx('div', { style: S.title, children: item.title || item.project }),
          jsx('div', { style: S.meta, children: [typeof item.parts === 'number' ? plural(item.parts, 'part') : null,
            when(item.created)].filter(Boolean).join(' · ') })
        ]
      })
    ]
  })
}

function Gallery() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(null)
  const load = useCallback(() => {
    rest('/projects').then(
      r => {
        setItems(Array.isArray(r && r.projects) ? r.projects.filter(p => SLUG.test(String(p.project)) && BUILD.test(String(p.build))) : [])
        setError('')
      },
      err => setError(errorText(err))
    )
  }, [])
  useEffect(() => {
    load()
    if (!CTX) return undefined
    return CTX.onEvent('plugin.construct.job.progress', ev => {
      const p = ev && ev.payload
      if (p && p.state === 'done') load()
    })
  }, [load])

  const header = jsxs('div', {
    style: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 },
    children: [
      jsx('div', { style: { fontSize: 18, fontWeight: 600, color: 'var(--ui-text-primary)' }, children: 'Constructs' }),
      items ? jsx('div', { style: S.meta, children: plural(items.length, 'construct') }) : null,
      jsx('div', { style: S.grow }),
      open ? jsx(Button, { label: 'All constructs', icon: 'arrow-left', onClick: () => setOpen(null) }) : null,
      jsx(Button, { label: 'Refresh', icon: 'refresh', onClick: load })
    ]
  })
  let body
  if (error) body = jsx('div', { style: { color: 'var(--ui-text-secondary)', fontSize: 13 }, children: error })
  else if (!items) body = jsx('div', { style: S.meta, children: 'Loading…' })
  else if (open) {
    body = jsx(ConstructCard, { project: open.project, build: open.build, title: open.title, parts: open.parts,
      sessionId: null, height: 560, extra: jsx('div', { style: S.meta, children: when(open.created) }) })
  } else if (!items.length) {
    body = jsxs('div', {
      style: { padding: '48px 0', textAlign: 'center', color: 'var(--ui-text-tertiary)', fontSize: 13 },
      children: [
        jsx('div', { style: { fontSize: 15, color: 'var(--ui-text-secondary)', marginBottom: 6 }, children: 'No constructs yet' }),
        jsx('div', { children: 'Ask Hermes for one: "Make a construct of a lighthouse."' })
      ]
    })
  } else {
    body = jsx('div', {
      style: { display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' },
      children: items.map(item => jsx(Tile, { item, onOpen: setOpen }, item.project + '/' + item.build))
    })
  }
  return jsxs('div', {
    style: { height: '100%', overflow: 'auto', padding: '20px 24px', boxSizing: 'border-box' },
    children: [header, body]
  })
}

// ---------------------------------------------------------------------------- job progress in the status bar

const jobs = new Map()
const listeners = new Set()

function setJob(payload) {
  if (!payload || typeof payload !== 'object' || typeof payload.job_id !== 'string' || !/^[0-9a-f]{12}$/.test(payload.job_id)) return
  const job = {
    id: payload.job_id, label: typeof payload.label === 'string' ? payload.label.slice(0, 80) : 'construct job',
    state: ['running', 'done', 'failed'].includes(payload.state) ? payload.state : 'running',
    percent: typeof payload.percent === 'number' && isFinite(payload.percent) ? Math.max(0, Math.min(100, payload.percent)) : null
  }
  jobs.set(job.id, job)
  if (job.state !== 'running' && CTX) {
    CTX.setTimeout(() => {
      jobs.delete(job.id)
      listeners.forEach(fn => fn())
    }, 8000)
  }
  listeners.forEach(fn => fn())
}

function JobsChip() {
  const [, tick] = useState(0)
  useEffect(() => {
    const fn = () => tick(n => n + 1)
    listeners.add(fn)
    return () => listeners.delete(fn)
  }, [])
  const list = Array.from(jobs.values())
  if (!list.length) return null
  const job = list[list.length - 1]
  const text = job.state === 'running'
    ? (job.percent === null ? job.label : job.label + ' ' + job.percent + '%')
    : job.label + (job.state === 'done' ? ' finished' : ' failed')
  return jsxs('button', {
    type: 'button', title: list.map(j => j.label + ': ' + j.state).join('\n'),
    onClick: () => sdk.host && typeof sdk.host.navigate === 'function' && sdk.host.navigate(GALLERY),
    style: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '0 6px', fontSize: 11, background: 'transparent',
      border: 0, cursor: 'pointer', color: job.state === 'failed' ? 'var(--ui-text-secondary)' : 'var(--ui-text-tertiary)' },
    children: [jsx(Icon, { name: job.state === 'running' ? 'loading' : 'symbol-structure' }),
      jsx('span', { children: text + (list.length > 1 ? ' (+' + (list.length - 1) + ')' : '') })]
  })
}

// ---------------------------------------------------------------------------- registration

export default {
  id: ID,
  name: 'Construct',
  register(ctx) {
    CTX = ctx
    const parts = []
    if (typeof sdk.TOOL_MEDIA_RENDERER_AREA === 'string') {
      parts.push({ id: 'live', area: sdk.TOOL_MEDIA_RENDERER_AREA,
        data: { tools: ['construct_build', 'construct_job'], render: props => jsx(ToolMedia, props) } })
    }
    if (typeof sdk.ROUTES_AREA === 'string' && typeof sdk.SIDEBAR_NAV_AREA === 'string') {
      parts.push({ id: 'gallery', area: sdk.ROUTES_AREA, data: { path: GALLERY }, render: () => jsx(Gallery, {}) })
      parts.push({ id: 'gallery-nav', area: sdk.SIDEBAR_NAV_AREA, data: { path: GALLERY, label: 'Constructs', codicon: 'symbol-structure' } })
    }
    if (sdk.STATUSBAR_AREAS && typeof sdk.STATUSBAR_AREAS.right === 'string') {
      parts.push({ id: 'jobs', area: sdk.STATUSBAR_AREAS.right, order: 140, render: () => jsx(JobsChip, {}) })
    }
    if (parts.length) ctx.registerMany(parts)
    ctx.onEvent('plugin.construct.job.progress', ev => setJob(ev && ev.payload))
    ctx.onDispose(() => {
      jobs.clear()
      listeners.clear()
      CTX = null
    })
  }
}
