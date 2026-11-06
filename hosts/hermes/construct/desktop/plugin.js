// Construct for Hermes Desktop: each built construct live in the chat; glTF models turnable, CAD files read back and
// model kits stepped through in their own viewers; a Constructs page (projects, examples to start from, tutorials);
// a NetLogo run's construct that grows while it runs; job progress in the status bar.
//
// A construct's page is several megabytes of self-contained HTML, more than a frame's address can carry. The agent
// half writes a small loader page beside it and hands the loader to the chat as the MEDIA file. This half shows the
// loader in a sandboxed frame, fetches the full page from the plugin's own backend (dashboard/plugin_api.py) and posts
// it to the loader, which replaces itself with it. The toolbar talks to the page the same way: a few validated
// messages that become the viewer's own keys. A kit's pages (its steps in 3D and its booklet) travel the same road.
//
// glTF models are drawn here with three.js (r180, MIT), bundled into this file at the marker below by
// scripts/hermes_plugin.py: it defines THREE_BUNDLE. Nothing is fetched from the network.
import * as sdk from '@hermes/plugin-sdk'
import * as React from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

// three.js, bundled in here by scripts/hermes_plugin.py (it defines THREE_BUNDLE; see hosts/hermes/three/)
/*__THREE_BUNDLE__*/

const { useCallback, useEffect, useRef, useState } = React

const ID = 'construct'
const HUB = '/constructs'
const SLUG = /^[a-z0-9][a-z0-9-]{0,62}$/
const BUILD = /^\d{8}-\d{6}-[0-9a-f]{4}$/
const SHOWN = /[\\/]shown[\\/]([a-z0-9][a-z0-9-]{0,62})[\\/](\d{8}-\d{6}-[0-9a-f]{4})[\\/](loader|construct)\.html$/
const SHOWN_KIT = /[\\/]shown[\\/]([a-z0-9][a-z0-9-]{0,62})[\\/]kits[\\/](\d{8}-\d{6}-[0-9a-f]{4})[\\/]loader\.html$/
const PAGE_MAX = 64 * 1024 * 1024
const LOADER_MAX = 256 * 1024
const MODEL_MAX = 48 * 1024 * 1024
const KEYS = new Set(['p', 's', 'r', 'm', 'l', 't', 'h', ' ', '1', '2', '3', '4', '5', '6', 'ArrowLeft', 'ArrowRight'])
const FRAME_BG = '#050205' // the construct's own night: the frame shows it before the page arrives
const CAD = /\.(step|stp|fcstd|stl|3mf|obj)$/i

let CTX = null

// ---------------------------------------------------------------------------- small helpers

function parsed(value) {
  if (value && typeof value === 'object') return value
  if (typeof value !== 'string' || value.length > 2_000_000) return null
  try {
    const v = JSON.parse(value)
    return v && typeof v === 'object' ? v : null
  } catch {
    return null
  }
}

function str(v, n) {
  return typeof v === 'string' ? v.slice(0, n || 200) : ''
}

function num(v) {
  return typeof v === 'number' && isFinite(v) ? v : null
}

// The build a media file belongs to: from the producing call's result, else from the file's own path.
function buildOf(file, result) {
  const r = parsed(result)
  const m = SHOWN.exec(String((file && file.path) || ''))
  if (m) {
    const same = r && r.project === m[1] && r.build === m[2]
    return { project: m[1], build: m[2], title: same ? str(r.title, 160) : '', parts: same ? num(r.parts) : null,
      jobId: r && /^[0-9a-f]{12}$/.test(String(r.job_id || '')) ? r.job_id : null }
  }
  return null
}

function rest(path, opts) {
  if (!CTX || typeof CTX.rest !== 'function') return Promise.reject(new Error('the plugin backend is not available'))
  return CTX.rest(path, opts)
}

function query(params) {
  return Object.keys(params).filter(k => params[k] !== undefined && params[k] !== null)
    .map(k => k + '=' + encodeURIComponent(params[k])).join('&')
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
  if (/404/.test(text)) return 'This is no longer kept (only the newest builds of a project are).'
  if (/not found|unavailable|refused|enabled/i.test(text)) return 'The Construct plugin backend is not running: enable the plugin and restart the gateway.'
  return text.slice(0, 240)
}

function plural(n, one) {
  return n === 1 ? '1 ' + one : String(n) + ' ' + one + 's'
}

function when(iso) {
  const d = new Date(String(iso || '').replace(/([+-]\d{2})(\d{2})$/, '$1:$2'))
  if (isNaN(d.getTime())) return ''
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(d)
  } catch {
    return d.toLocaleString()
  }
}

function sizeText(n) {
  if (typeof n !== 'number') return ''
  if (n < 1024) return n + ' bytes'
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1048576).toFixed(1) + ' MB'
}

function sleep(ms) {
  return new Promise(resolve => (CTX ? CTX.setTimeout(resolve, ms) : resolve()))
}

function useBusy(sessionId) {
  const atom = sdk.host && sdk.host.state && sdk.host.state.busyBySession
  const busy = typeof sdk.useValue === 'function' && atom ? sdk.useValue(atom) : null
  return !!(sessionId && busy && busy[sessionId])
}

function dataUrlBuffer(url) {
  const comma = url.indexOf(',')
  if (!url.startsWith('data:') || comma < 0) throw new Error('not a data address')
  const head = url.slice(0, comma)
  const body = url.slice(comma + 1)
  if (!/;base64$/i.test(head)) return new TextEncoder().encode(decodeURIComponent(body)).buffer
  const bin = atob(body)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out.buffer
}

async function openPath(path) {
  if (!path || !CTX || !CTX.os) return
  const opened = typeof CTX.os.openExternal === 'function' ? await CTX.os.openExternal('file://' + encodeURI(path)) : false
  if (!opened && typeof CTX.os.revealPath === 'function') await CTX.os.revealPath(path)
}

async function revealPath(path) {
  if (path && CTX && CTX.os && typeof CTX.os.revealPath === 'function') await CTX.os.revealPath(path)
}

// A message to the agent in a fresh chat (the Start buttons). Falls back to the draft, then to the clipboard.
async function startChat(text) {
  const host = sdk.host
  const composer = host && host.composer
  try {
    if (host && typeof host.newChat === 'function') host.newChat()
    else if (CTX && typeof CTX.runAction === 'function') await CTX.runAction('session.new')
  } catch {
    /* the composer below still answers, or the clipboard does */
  }
  if (composer && typeof composer.submit === 'function') {
    for (let i = 0; i < 10; i++) {
      await sleep(120 + 60 * i)
      try {
        if (composer.submit('new', text)) return true
      } catch {
        break
      }
    }
    try {
      if ((await composer.setDraft('new', text)) || (await composer.setDraft(null, text))) {
        notify('info', 'The message is in the composer: press Enter to start.')
        return true
      }
    } catch {
      /* no composer answered */
    }
  }
  const copied = CTX && CTX.os && typeof CTX.os.writeClipboard === 'function' ? await CTX.os.writeClipboard(text) : false
  notify('info', copied ? 'Copied the message: paste it into a new chat.' : 'Open a new chat and ask: ' + text.slice(0, 160))
  return false
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
  text: { fontSize: 12, color: 'var(--ui-text-secondary)', lineHeight: 1.45 },
  grow: { flex: '1 1 auto' },
  bar: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, padding: '7px 10px',
    borderTop: '1px solid var(--ui-stroke-secondary)' },
  sep: { width: 1, alignSelf: 'stretch', margin: '2px 4px', background: 'var(--ui-stroke-secondary)' },
  frameBox: { position: 'relative', width: '100%', background: FRAME_BG },
  frame: { display: 'block', width: '100%', height: '100%', border: 0, background: FRAME_BG },
  wait: { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
    textAlign: 'center', fontSize: 12, color: 'var(--ui-text-tertiary)', pointerEvents: 'none' },
  tip: { position: 'absolute', left: 10, top: 10, padding: '3px 8px', borderRadius: 6, fontSize: 11, pointerEvents: 'none',
    background: 'var(--ui-surface-primary, rgba(0,0,0,.6))', color: 'var(--ui-text-primary)', border: '1px solid var(--ui-stroke-secondary)' },
  rows: { display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '3px 12px', padding: '10px 12px', fontSize: 12 },
  key: { color: 'var(--ui-text-tertiary)', whiteSpace: 'nowrap' },
  value: { color: 'var(--ui-text-secondary)', minWidth: 0, overflowWrap: 'anywhere' },
  chip: { display: 'inline-block', padding: '1px 7px', borderRadius: 10, fontSize: 10.5, border: '1px solid var(--ui-stroke-secondary)',
    color: 'var(--ui-text-secondary)', whiteSpace: 'nowrap' }
}

function button(active, disabled) {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 5, height: 24, padding: '0 9px', fontSize: 12, lineHeight: '22px',
    borderRadius: 6, cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.45 : 1, background: 'transparent',
    border: '1px solid ' + (active ? 'var(--ui-accent)' : 'var(--ui-stroke-secondary)'),
    color: active ? 'var(--ui-accent)' : 'var(--ui-text-secondary)', whiteSpace: 'nowrap'
  }
}

function Icon({ name }) {
  return typeof sdk.Codicon === 'function' ? jsx(sdk.Codicon, { name, 'aria-hidden': true, style: { fontSize: 13 } }) : null
}

function Button({ label, icon, title, active, disabled, onClick }) {
  return jsxs('button', {
    type: 'button', title: title || label, disabled: !!disabled, 'aria-pressed': active === undefined ? undefined : !!active,
    style: button(!!active, !!disabled), onClick,
    children: [icon ? jsx(Icon, { name: icon }) : null, label ? jsx('span', { children: label }) : null]
  })
}

function Head({ icon, title, meta, children }) {
  return jsxs('div', {
    style: S.head,
    children: [
      jsx(Icon, { name: icon || 'symbol-structure' }),
      jsx('div', { style: S.title, title, children: title }),
      ...(meta || []).filter(Boolean).map((m, i) => jsx('div', { style: S.meta, children: m }, 'm' + i)),
      jsx('div', { style: S.grow }),
      children || null
    ]
  })
}

// ---------------------------------------------------------------------------- a page in a frame (constructs, kits)

// Shows one page: the loader in a sandboxed frame, the page posted to it once both are there. `route` is the backend
// route that answers {html, loader, card}; `kind` is what the loader checks it as (construct, assembly, booklet).
function PageFrame({ route, kind, loaderUrl, height, onCard, onState, control, onOpenSteps }) {
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
    if (!readyRef.current || !htmlRef.current) return
    post({ type: 'construct:page', html: htmlRef.current, kind })
    setShown(true)
  }, [post, kind])

  useEffect(() => {
    let live = true
    htmlRef.current = null
    readyRef.current = false
    setFailed('')
    setShown(false)
    if (!loaderUrl) setSrc(null)
    rest(route, { timeoutMs: 120000 }).then(
      view => {
        if (!live) return
        const html = view && view.html
        if (typeof html !== 'string' || html.length > PAGE_MAX || !/^\s*<!doctype html>/i.test(html.slice(0, 64))) {
          setFailed('The page could not be read.')
          return
        }
        htmlRef.current = html
        if (view.card && onCard) onCard(view.card)
        if (!loaderUrl) {
          const loader = view.loader
          if (typeof loader !== 'string' || loader.length > LOADER_MAX) {
            setFailed('The page could not be read.')
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
  }, [route, loaderUrl, deliver, post, onCard])

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
          hasSolid: d.hasSolid === true, step: typeof d.step === 'number' && d.step >= 0 && d.step < 1000 ? d.step : 0 })
      } else if (d.type === 'construct:open-steps' && onOpenSteps) {
        onOpenSteps(typeof d.step === 'number' && d.step >= 1 && d.step < 1000 ? Math.floor(d.step) : 1)
      }
    })
  }, [deliver, onState, onOpenSteps])

  useEffect(() => {
    if (control) {
      control.current = {
        key: key => typeof key === 'string' && KEYS.has(key) && post({ type: 'construct:key', key }),
        step: n => typeof n === 'number' && n >= 1 && n < 1000 && post({ type: 'construct:step', step: Math.floor(n) })
      }
    }
  }, [control, post])

  return jsxs('div', {
    style: Object.assign({}, S.frameBox, { height }),
    children: [
      src && typeof sdk.SandboxedFrame === 'function'
        ? jsx(sdk.SandboxedFrame, { ref: frameRef, src, title: 'Construct', sandbox: 'allow-scripts allow-pointer-lock', style: S.frame }, src.length)
        : null,
      failed || !shown ? jsx('div', { style: S.wait, children: failed || 'Opening…' }) : null
    ]
  })
}

// ---------------------------------------------------------------------------- the live construct

// Follows a NetLogo run's previews: while its job runs, each newer drawing of the run replaces the shown build.
function useRunPreview(project, jobId) {
  const [latest, setLatest] = useState(null)
  useEffect(() => {
    if (!CTX || !jobId) return undefined
    return CTX.onEvent('plugin.construct.run.preview', ev => {
      const p = ev && ev.payload
      if (!p || p.project !== project || p.job_id !== jobId || !BUILD.test(String(p.build || ''))) return
      setLatest({ build: p.build, ticks: num(p.ticks), final: p.final === true })
    })
  }, [project, jobId])
  return latest
}

// The toolbar and title around a live construct; `sessionId` enables the actions that ask the agent.
function ConstructCard({ project, build, loaderUrl, title, parts, sessionId, height, extra, jobId }) {
  const control = useRef(null)
  const [card, setCard] = useState(null)
  const [view, setView] = useState({ ready: false, mode: 'light', solid: false, hasSolid: false })
  const busy = useBusy(sessionId)
  const run = useRunPreview(project, jobId)
  const shownBuild = run ? run.build : build
  const composer = sdk.host && sdk.host.composer
  const canAsk = !!(sessionId && composer && typeof composer.submit === 'function')
  const name = (card && card.title) || title || project
  const count = card && typeof card.parts === 'number' ? card.parts : typeof parts === 'number' ? parts : null

  const press = key => control.current && control.current.key(key)
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
  const growing = run && !run.final ? 'growing' + (run.ticks !== null ? ': tick ' + run.ticks : '') : null

  return jsxs('div', {
    style: S.card,
    children: [
      jsx(Head, {
        title: name,
        meta: [count !== null ? plural(count, 'part') : null, card && card.audit_ok === false ? '· audit has errors' : null,
          card && card.changed_since ? '· scene changed since' : null, growing ? '· ' + growing : null],
        children: [extra ? jsx(React.Fragment, { children: extra }, 'extra') : null,
          jsx(Button, { label: 'Open in browser', icon: 'link-external', disabled: !(card && card.page), onClick: () => openPath(card.page),
            title: 'Open the page in your browser' }, 'open')]
      }),
      jsx(PageFrame, { route: '/view?' + query({ project, build: shownBuild }), kind: 'construct',
        loaderUrl: shownBuild === build ? loaderUrl : null, height: height || 420, onCard: setCard, onState: setView, control }),
      jsxs('div', {
        style: S.bar,
        children: [
          jsx(Button, { label: 'Provenance', icon: 'eye', active: view.mode === 'provenance', disabled: !view.ready,
            title: 'How each part is known (P)', onClick: () => press('p') }),
          jsx(Button, { label: 'Solid', icon: 'circle-filled', active: view.solid, disabled: !view.ready || !view.hasSolid,
            title: 'The surfaces as a solid (S)', onClick: () => press('s') }),
          jsx(Button, { label: 'Replay', icon: 'debug-restart', disabled: !view.ready, title: 'Build it again (R)',
            onClick: () => press('r') }),
          jsx(Button, { label: 'How to read it', icon: 'info', disabled: !view.ready, title: 'The reading panel, where the construct has one (H)',
            onClick: () => press('h') }),
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

// ---------------------------------------------------------------------------- a model kit

function KitCard({ project, kit, loaderUrl, sessionId, height }) {
  const control = useRef(null)
  const [card, setCard] = useState(null)
  const [tab, setTab] = useState('assembly')
  const [view, setView] = useState({ ready: false, step: 0 })
  const [goTo, setGoTo] = useState(0)
  const steps = card && typeof card.steps === 'number' ? card.steps : 0
  const has3d = !card || card.has_3d !== false
  const page = has3d ? tab : 'booklet'
  const step = view.step || (view.ready ? 1 : 0)
  useEffect(() => {
    if (goTo && page === 'assembly' && view.ready && control.current) {
      control.current.step(goTo)
      setGoTo(0)
    }
  }, [goTo, page, view.ready])
  const openSteps = useCallback(n => {
    setTab('assembly')
    setGoTo(n)
  }, [])
  const title = (card && card.title) || project
  return jsxs('div', {
    style: S.card,
    children: [
      jsx(Head, {
        icon: 'extensions', title: title + ' · model kit',
        meta: [card ? plural(card.pieces || 0, 'piece') : null, card ? plural(card.plates || 0, 'plate') : null,
          steps ? plural(steps, 'step') : null],
        children: [
          has3d ? jsx(Button, { label: 'Steps in 3D', icon: 'symbol-structure', active: page === 'assembly', onClick: () => setTab('assembly') }, 'a') : null,
          jsx(Button, { label: 'Booklet', icon: 'book', active: page === 'booklet', onClick: () => setTab('booklet') }, 'b'),
          jsx(Button, { label: '', icon: 'folder-opened', title: 'Show the kit’s files (plates, pieces, booklet)', disabled: !(card && card.folder),
            onClick: () => revealPath(card.folder) }, 'f')
        ]
      }),
      jsx(PageFrame, { route: '/kit?' + query({ project, kit, page }), kind: page,
        loaderUrl: page === 'assembly' || !has3d ? loaderUrl : null, height: height || 460, onCard: setCard,
        onState: s => setView({ ready: s.ready, step: s.step }), control, onOpenSteps: openSteps }, page),
      page === 'assembly' ? jsxs('div', {
        style: S.bar,
        children: [
          jsx(Button, { label: 'Back', icon: 'arrow-left', disabled: !view.ready || step <= 1, onClick: () => control.current && control.current.key('ArrowLeft') }),
          jsx(Button, { label: 'Next', icon: 'arrow-right', disabled: !view.ready || (steps && step >= steps), onClick: () => control.current && control.current.key('ArrowRight') }),
          jsx('div', { style: S.meta, children: view.ready && steps ? 'step ' + Math.max(1, step) + ' of ' + steps : '' }),
          jsx('div', { style: S.grow }),
          jsx(Button, { label: 'First step', icon: 'debug-restart', disabled: !view.ready, onClick: () => control.current && control.current.step(1) }),
          jsx(Button, { label: 'Open the booklet', icon: 'link-external', disabled: !(card && card.booklet), onClick: () => openPath(card.booklet),
            title: 'The booklet in your browser, to print' })
        ]
      }) : null
    ]
  })
}

// ---------------------------------------------------------------------------- glTF: a turnable model

const live3d = new Set() // the viewers holding a WebGL context, so a long chat never holds too many
const LIVE_MAX = 6

// The part a mesh belongs to, by id: Construct's glTF marks each part's node with its record (userData.construct:
// id, label, role, certainty) and the nodes under it (its mesh, its piece of a physics body) with the part's id;
// another glTF falls back to the nearest named node.
function partOf(object) {
  let named = ''
  for (let o = object; o && o.type !== 'Scene'; o = o.parent) {
    const c = o.userData && o.userData.construct
    if (c && typeof c.part === 'string') return c.part
    if (c && typeof c.id === 'string' && !c.format) return c.id
    if (!named && o.name && !o.isMesh && !/^stage-\d+$/.test(o.name) && !(c && c.format)) named = o.name
  }
  return named || (object && object.name) || ''
}

function partName(id, records) {
  if (!id) return ''
  const c = (records && records.get(id)) || {}
  const label = typeof c.label === 'string' && c.label !== id ? c.label + ' (' + id + ')' : str(id, 120)
  return [label, typeof c.certainty === 'string' ? c.certainty.replace('_', ' ') : '', typeof c.role === 'string' ? c.role : ''].filter(Boolean).join(' · ')
}

function ModelViewer({ load, height, onInfo }) {
  const boxRef = useRef(null)
  const canvasRef = useRef(null)
  // a canvas whose WebGL context was given up (off screen, or dropped by the browser) never gets it back: the
  // next time the view opens it gets a new canvas
  const [canvasKey, setCanvasKey] = useState(0)
  const api = useRef({})
  const [state, setState] = useState({ phase: 'waiting', error: '' })
  const [hover, setHover] = useState('')
  const [picked, setPicked] = useState('')
  const [clips, setClips] = useState([])
  const [playing, setPlaying] = useState('')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const box = boxRef.current
    if (!box || typeof IntersectionObserver !== 'function') {
      setVisible(true)
      return undefined
    }
    const io = new IntersectionObserver(entries => entries.forEach(e => setVisible(e.isIntersecting)), { rootMargin: '200px' })
    io.observe(box)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    if (!visible) return undefined
    if (typeof THREE_BUNDLE === 'undefined') {
      setState({ phase: 'failed', error: 'The 3D viewer is not in this build of the plugin.' })
      return undefined
    }
    const T = THREE_BUNDLE
    const canvas = canvasRef.current
    if (canvas && canvas.dataset.spent) {
      setCanvasKey(k => k + 1)
      return undefined
    }
    const dropped = () => {
      canvas.dataset.spent = '1'
      if (!disposed) setCanvasKey(k => k + 1)
    }
    canvas.addEventListener('webglcontextlost', dropped)
    let disposed = false
    let renderer = null
    let frame = 0
    let controls = null
    let mixer = null
    let root = null
    const me = {}
    live3d.add(me)
    if (live3d.size > LIVE_MAX) {
      setState({ phase: 'paused', error: '' })
      live3d.delete(me)
      return undefined
    }
    setState({ phase: 'loading', error: '' })
    Promise.resolve(load()).then(buffer => {
      if (disposed) return
      try {
        renderer = new T.WebGLRenderer({ canvas, antialias: true })
      } catch (e) {
        setState({ phase: 'failed', error: 'WebGL is not available here (' + String(e && e.message || e).slice(0, 80) + ').' })
        return
      }
      renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
      renderer.outputColorSpace = T.SRGBColorSpace
      const scene = new T.Scene()
      scene.background = new T.Color(FRAME_BG)
      scene.add(new T.HemisphereLight(0xffffff, 0x30283a, 1.6))
      const sun = new T.DirectionalLight(0xffffff, 1.8)
      sun.position.set(3, 5, 4)
      scene.add(sun)
      const camera = new T.PerspectiveCamera(38, 1, 0.001, 100000)
      new T.GLTFLoader().parse(buffer, '', gltf => {
        if (disposed) return
        root = gltf.scene
        root.traverse(o => {
          if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(m => m.clone()) : o.material.clone()
        })
        scene.add(root)
        const bounds = new T.Box3().setFromObject(root)
        const size = bounds.getSize(new T.Vector3())
        const centre = bounds.getCenter(new T.Vector3())
        const radius = Math.max(size.length() / 2, 0.001)
        camera.position.copy(centre).add(new T.Vector3(radius * 1.5, radius * 0.9, radius * 2.1))
        camera.near = radius / 200
        camera.far = radius * 200
        camera.updateProjectionMatrix()
        controls = new T.OrbitControls(camera, canvas)
        controls.target.copy(centre)
        controls.enableDamping = true
        controls.update()
        const grid = new T.GridHelper(radius * 4, 20, 0x5a4a6a, 0x2a2232)
        grid.position.set(centre.x, bounds.min.y, centre.z)
        scene.add(grid)
        mixer = new T.AnimationMixer(root)
        const names = gltf.animations.map(a => a.name)
        setClips(names)
        const records = new Map()
        const meshesOf = new Map()
        root.traverse(o => {
          const c = o.userData && o.userData.construct
          if (c && typeof c.id === 'string' && !c.format) records.set(c.id, c)
          if (o.isMesh) {
            const id = partOf(o)
            if (id) meshesOf.set(id, (meshesOf.get(id) || []).concat([o]))
          }
        })
        api.current.records = records
        const parts = meshesOf
        if (onInfo) onInfo({ parts: records.size || parts.size, size: [size.x, size.y, size.z], animations: names })   // named parts, as the facts below count them (some are lines only)
        api.current.play = name => {
          const clip = gltf.animations.find(a => a.name === name)
          if (!clip || !mixer) return
          mixer.stopAllAction()
          const action = mixer.clipAction(clip)
          action.reset()
          action.setLoop(/^idle/.test(name) ? T.LoopRepeat : T.LoopOnce, Infinity)
          action.clampWhenFinished = true
          action.play()
          setPlaying(name)
        }
        api.current.stop = () => {
          if (mixer) mixer.stopAllAction()
          setPlaying('')
        }
        api.current.reset = () => {
          camera.position.copy(centre).add(new T.Vector3(radius * 1.5, radius * 0.9, radius * 2.1))
          controls.target.copy(centre)
          controls.update()
        }
        let lit = null
        const light = (id, on) => {
          (meshesOf.get(id) || []).forEach(o => {
            (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => m && m.emissive && m.emissive.setHex(on ? 0x553366 : 0x000000))
          })
        }
        api.current.select = part => {
          light(lit, false)
          lit = part
          light(lit, true)
        }
        setState({ phase: 'ready', error: '' })
      }, err => setState({ phase: 'failed', error: 'The model could not be read: ' + String(err && err.message || err).slice(0, 120) }))
      const ray = new T.Raycaster()
      const at = new T.Vector2()
      const pick = event => {
        if (!root) return null
        const r = canvas.getBoundingClientRect()
        at.set(((event.clientX - r.left) / r.width) * 2 - 1, -((event.clientY - r.top) / r.height) * 2 + 1)
        ray.setFromCamera(at, camera)
        const hit = ray.intersectObject(root, true).find(h => h.object.isMesh && h.object.visible)
        return hit ? partOf(hit.object) : null
      }
      let last = 0
      const move = event => {
        const now = performance.now()
        if (now - last < 50) return
        last = now
        const p = pick(event)
        setHover(partName(p, api.current.records))
      }
      let down = null
      const press = event => {
        down = [event.clientX, event.clientY]
      }
      const click = event => {
        if (!down || Math.abs(event.clientX - down[0]) + Math.abs(event.clientY - down[1]) > 4) return
        const p = pick(event)
        if (api.current.select) api.current.select(p)
        setPicked(partName(p, api.current.records))
      }
      canvas.addEventListener('pointermove', move)
      canvas.addEventListener('pointerdown', press)
      canvas.addEventListener('pointerup', click)
      const fit = () => {
        const w = Math.max(1, canvas.clientWidth)
        const h = Math.max(1, canvas.clientHeight)
        if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) {
          renderer.setSize(w, h, false)
          camera.aspect = w / h
          camera.updateProjectionMatrix()
        }
      }
      const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(fit) : null
      if (ro) ro.observe(canvas)
      const clock = new T.Clock()
      const tick = () => {
        if (disposed) return
        fit()
        const dt = clock.getDelta()
        if (mixer) mixer.update(dt)
        if (controls) controls.update()
        renderer.render(scene, camera)
        frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
      me.stop = () => {
        canvas.removeEventListener('pointermove', move)
        canvas.removeEventListener('pointerdown', press)
        canvas.removeEventListener('pointerup', click)
        if (ro) ro.disconnect()
      }
    }, err => !disposed && setState({ phase: 'failed', error: errorText(err) }))
    return () => {
      disposed = true
      live3d.delete(me)
      cancelAnimationFrame(frame)
      if (me.stop) me.stop()
      if (controls) controls.dispose()
      if (root) {
        root.traverse(o => {
          if (o.geometry) o.geometry.dispose()
          if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => m.dispose())
        })
      }
      canvas.removeEventListener('webglcontextlost', dropped)
      if (renderer) {
        renderer.dispose()
        if (typeof renderer.forceContextLoss === 'function') renderer.forceContextLoss()
        canvas.dataset.spent = '1'
      }
      api.current = {}
      setClips([])
      setPlaying('')
    }
  }, [visible, load, canvasKey])

  const ready = state.phase === 'ready'
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column' },
    children: [
      jsxs('div', {
        ref: boxRef,
        style: Object.assign({}, S.frameBox, { height: height || 420 }),
        children: [
          jsx('canvas', { key: canvasKey, ref: canvasRef, style: { display: 'block', width: '100%', height: '100%', cursor: hover ? 'pointer' : 'grab', touchAction: 'none' } }),
          hover || picked ? jsx('div', { style: S.tip, children: hover || picked }) : null,
          !ready ? jsx('div', { style: S.wait, children: state.error || (state.phase === 'paused' ? 'Scroll here again to turn it (a few other 3D views are open).' : 'Opening the model…') }) : null
        ]
      }),
      jsxs('div', {
        style: S.bar,
        children: [
          jsx(Button, { label: 'Reset view', icon: 'screen-full', disabled: !ready, onClick: () => api.current.reset && api.current.reset() }),
          ...clips.slice(0, 8).map(name => jsx(Button, { label: name.replace(/^open:/, '').replace(/-open$/, ''), icon: 'play',
            active: playing === name, disabled: !ready, title: 'Play the ' + name + ' animation',
            onClick: () => api.current.play && api.current.play(name) }, name)),
          clips.length > 8 ? jsx('div', { style: S.meta, children: '+' + (clips.length - 8) + ' more animations' }) : null,
          playing ? jsx(Button, { label: 'Stop', icon: 'debug-stop', onClick: () => api.current.stop && api.current.stop() }) : null,
          jsx('div', { style: S.grow }),
          jsx('div', { style: S.meta, children: picked ? 'selected: ' + picked : 'hover a part for its name; click to select' })
        ]
      })
    ]
  })
}

function Facts({ rows }) {
  return jsx('div', {
    style: S.rows,
    children: rows.filter(r => r && r[1]).flatMap((r, i) => [
      jsx('div', { style: S.key, children: r[0] }, 'k' + i),
      jsx('div', { style: S.value, children: r[1] }, 'v' + i)
    ])
  })
}

function boundsText(b) {
  if (!b || !Array.isArray(b.m) || !Array.isArray(b.mm)) return ''
  return b.m.map(v => String(v)).join(' × ') + ' m (' + b.mm.map(v => String(v)).join(' × ') + ' mm)'
}

function Names({ names, total }) {
  const [open, setOpen] = useState(false)
  if (!Array.isArray(names) || !names.length) return null
  const list = names.filter(n => typeof n === 'string').slice(0, 60)
  return jsxs('div', {
    style: { padding: '0 12px 10px' },
    children: [
      jsx(Button, { label: (open ? 'Hide' : 'Show') + ' the parts (' + (total || list.length) + ')', icon: open ? 'chevron-up' : 'chevron-down',
        onClick: () => setOpen(!open) }),
      open ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 },
        children: list.map((n, i) => jsx('span', { style: S.chip, children: n }, i)) }) : null
    ]
  })
}

// What a verified export holds (construct_export's read-back): for every format; the CAD formats show only this.
function ExportFacts({ verified, format }) {
  const v = verified || {}
  const made = v.construct || {}
  const surfaces = v.surfaces && typeof v.surfaces === 'object' ? Object.keys(v.surfaces).map(k => k + ' ' + v.surfaces[k]).join(', ') : ''
  const rows = [
    ['file', [str(v.file, 120), str(v.size, 20)].filter(Boolean).join(' · ')],
    ['size', boundsText(v.bounds)],
    format === 'step' ? ['products', num(v.products) !== null ? v.products + ' (solids ' + (v.solids || 0) + ', faces ' + (v.faces || 0) + ')' : ''] : null,
    format === 'step' && surfaces ? ['surfaces', surfaces] : null,
    (format === 'step' || format === 'fcstd') && num(made.exact) !== null ? ['CAD shapes', made.exact + ' exact, ' + (made.faceted || 0) + ' faceted'] : null,
    format === 'fcstd' && num(v.solids) !== null ? ['solids', v.solids + ' named, in ' + (v.objects || 0) + ' objects'] : null,
    num(made.joints) !== null ? ['joints', String(made.joints)] : null,
    (format === 'stl' || format === '3mf') && num(v.triangles) !== null ? ['triangles', String(v.triangles)] : null,
    format === 'obj' && num(v.objects) !== null ? ['objects', v.objects + ' named, ' + (v.faces || 0) + ' faces'] : null,
    format === 'glb' && num(v.named_parts) !== null ? ['parts', v.named_parts + ' named, ' + (v.nodes || 0) + ' nodes, ' + (v.meshes || 0) + ' meshes'] : null,
    format === 'glb' && Array.isArray(v.animations) ? ['animations', v.animations.length ? v.animations.map(a => str(a.name, 60) + ' ' + a.seconds + ' s').join(', ') : 'none'] : null,
    made.left_out ? ['left out', str(made.left_out, 300)] : null,
    made.invalid ? ['invalid', str(made.invalid, 300)] : null,
    v.error ? ['read-back', str(v.error, 300)] : null
  ]
  return jsxs('div', { children: [jsx(Facts, { rows }),
    jsx(Names, { names: v.part_names, total: num(v.named_parts) || num(v.products) || num(v.solids) || num(v.objects) })] })
}

function formatOf(name) {
  const m = /\.([a-z0-9]+)$/i.exec(String(name || ''))
  const ext = m ? m[1].toLowerCase() : ''
  return ext === 'stp' ? 'step' : ext
}

function ExportCard({ name, path, format, verified, load, project, height }) {
  const [info, setInfo] = useState(null)
  const glb = format === 'glb'
  const meta = glb && info ? [plural(info.parts, 'part'), info.animations.length ? plural(info.animations.length, 'animation') : null]
    : [str(verified && verified.size, 20)]
  return jsxs('div', {
    style: S.card,
    children: [
      jsx(Head, {
        icon: glb ? 'symbol-structure' : 'file-binary', title: name || (format.toUpperCase() + ' export'), meta,
        children: [jsx(Button, { label: 'Show in folder', icon: 'folder-opened', disabled: !path, onClick: () => revealPath(path) }, 'r'),
          jsx(Button, { label: 'Open', icon: 'link-external', disabled: !path, title: 'Open it in the program your computer uses for ' + format.toUpperCase(),
            onClick: () => openPath(path) }, 'o')]
      }),
      glb && load ? jsx(ModelViewer, { load, height, onInfo: setInfo }) : null,
      verified ? jsxs('div', {
        children: [jsx('div', { style: Object.assign({}, S.meta, { padding: '8px 12px 0' }), children: 'Verified from the written file' + (project ? ' · ' + project : '') }, 'h'),
          jsx(ExportFacts, { verified, format }, 'f')] }) : null
    ]
  })
}

// ---------------------------------------------------------------------------- the tool media renderer

function ToolMedia({ file, result, sessionId, fallback }) {
  const path = String((file && file.path) || '')
  const r = parsed(result)
  const kitMatch = SHOWN_KIT.exec(path)
  const isLoader = /(^|[\\/])loader\.html$/.test(path)
  const format = formatOf(path)
  const [url, setUrl] = useState(null)
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
  }, [path, isLoader])
  const loadModel = useCallback(async () => {
    let u = null
    try {
      u = file && typeof file.resolveUrl === 'function' ? await file.resolveUrl() : null
    } catch {
      u = null
    }
    if (typeof u === 'string' && u.startsWith('data:')) return dataUrlBuffer(u)
    // a model larger than the host's data-address cap comes from the plugin's backend, by its id
    const item = r && BUILD.test(String(r.item || '')) && SLUG.test(String(r.project || '')) ? r.item : null
    if (!item) throw new Error('the model is too large to show here; open it from its folder')
    const got = await rest('/item?' + query({ project: r.project, item }), { timeoutMs: 120000 })
    if (!got || typeof got.data_url !== 'string' || got.data_url.length > MODEL_MAX * 1.4) throw new Error('the model could not be read')
    return dataUrlBuffer(got.data_url)
  }, [path])

  if (typeof sdk.SandboxedFrame !== 'function' && isLoader) return fallback || null
  if (isLoader && kitMatch) {
    if (url === null) return jsx('div', { style: Object.assign({}, S.card, { height: 120 }) })
    return jsx(KitCard, { project: kitMatch[1], kit: kitMatch[2], loaderUrl: url || null, sessionId })
  }
  if (isLoader) {
    const ids = buildOf(file, result)
    if (!ids) return fallback || null
    if (url === null) return jsx('div', { style: Object.assign({}, S.card, { height: 120 }) }) // the loader's address is on its way
    // without the host's address for the loader (''), the card reads the loader from the plugin's backend instead
    return jsx(ConstructCard, { project: ids.project, build: ids.build, title: ids.title, parts: ids.parts, sessionId,
      loaderUrl: url || null, jobId: ids.jobId })
  }
  if (format === 'glb' || CAD.test(path)) {
    const verified = r && r.file_path === path ? r.verified : r && r.verified_step && /\.(step|stp)$/i.test(path) ? r.verified_step : null
    return jsx(ExportCard, { name: path.split(/[\\/]/).pop(), path, format, verified: verified && typeof verified === 'object' ? verified : null,
      load: format === 'glb' ? loadModel : null, project: r && SLUG.test(String(r.project || '')) ? r.project : '' })
  }
  return fallback || null
}

// ---------------------------------------------------------------------------- the Constructs page

let pending = { tab: null, project: null }
const hubListeners = new Set()

function openHub(tab, project) {
  pending = { tab: tab || null, project: project || null }
  hubListeners.forEach(fn => fn())
  if (sdk.host && typeof sdk.host.navigate === 'function') sdk.host.navigate(HUB)
}

function Img({ load, deps, icon }) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    let live = true
    if (!load) return undefined
    load().then(
      t => live && t && typeof t.data_url === 'string' && /^data:image\/(png|jpeg);base64,/.test(t.data_url) && setSrc(t.data_url),
      () => {}
    )
    return () => {
      live = false
    }
  }, deps)
  return jsx('div', {
    style: { aspectRatio: '16 / 10', width: '100%', background: FRAME_BG, display: 'flex', alignItems: 'center',
      justifyContent: 'center', overflow: 'hidden' },
    children: src ? jsx('img', { src, alt: '', style: { width: '100%', height: '100%', objectFit: 'cover' } }) : jsx(Icon, { name: icon || 'symbol-structure' })
  })
}

function Tile({ title, lines, badge, image, onOpen, actions }) {
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', borderRadius: 10, overflow: 'hidden', border: '1px solid var(--ui-stroke-secondary)', minWidth: 0 },
    children: [
      jsxs('button', {
        type: 'button', onClick: onOpen, title,
        style: { display: 'flex', flexDirection: 'column', textAlign: 'left', padding: 0, cursor: onOpen ? 'pointer' : 'default',
          background: 'transparent', border: 0, minWidth: 0 },
        children: [
          image,
          jsxs('div', {
            style: { padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 },
            children: [
              jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 },
                children: [jsx('div', { style: S.title, children: title }), badge ? jsx('span', { style: S.chip, children: badge }) : null] }),
              ...(lines || []).filter(Boolean).map((l, i) => jsx('div', { style: Object.assign({}, S.meta, { whiteSpace: 'normal' }), children: l }, i))
            ]
          })
        ]
      }),
      actions ? jsx('div', { style: { display: 'flex', gap: 6, padding: '0 10px 10px', flexWrap: 'wrap' }, children: actions }) : null
    ]
  })
}

const GRID = { display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))' }

function itemIcon(item) {
  return { film: 'device-camera-video', kit: 'extensions', run: 'graph-line', compare: 'graph', plates: 'layers', export: 'package' }[item.kind] || 'file'
}

function ItemRow({ project, item, onShow }) {
  const format = formatOf(item.name)
  const viewable = item.exists && (format === 'glb' || format === 'mp4' || CAD.test(item.name || ''))
  return jsxs('div', {
    style: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderTop: '1px solid var(--ui-stroke-secondary)' },
    children: [
      jsx(Icon, { name: itemIcon(item) }),
      jsxs('div', { style: { display: 'flex', flexDirection: 'column', minWidth: 0, flex: '1 1 auto' },
        children: [jsx('div', { style: S.title, children: str(item.title, 80) || item.name }),
          jsx('div', { style: Object.assign({}, S.meta, { whiteSpace: 'normal' }),
            children: [item.name, sizeText(item.bytes), when(item.created), item.exists ? '' : 'no longer there'].filter(Boolean).join(' · ') }),
          item.summary ? jsx('div', { style: Object.assign({}, S.text, { fontSize: 11 }), children: str(item.summary, 400) }) : null] }),
      viewable ? jsx(Button, { label: format === 'mp4' ? 'Play' : format === 'glb' ? 'Turn it' : 'Details', icon: format === 'mp4' ? 'play' : 'eye',
        onClick: () => onShow(item) }) : null,
      jsx(Button, { label: '', icon: 'folder-opened', title: 'Show in its folder', disabled: !item.exists, onClick: () => revealPath(item.path) })
    ]
  })
}

function ItemView({ project, item }) {
  const format = formatOf(item.name)
  const [video, setVideo] = useState(null)
  const [verified, setVerified] = useState(null)
  const [error, setError] = useState('')
  const fetchItem = useCallback(() => rest('/item?' + query({ project, item: item.id }), { timeoutMs: 120000 }), [project, item.id])
  const load = useCallback(async () => {
    const got = await fetchItem()
    if (got && got.summary) setVerified(got.summary)
    return dataUrlBuffer(got.data_url)
  }, [fetchItem])
  useEffect(() => {
    let live = true
    if (format === 'mp4') fetchItem().then(g => live && setVideo(g.data_url), e => live && setError(errorText(e)))
    else if (format !== 'glb') fetchItem().then(g => live && setVerified(g.summary || {}), e => live && setError(errorText(e)))
    return () => {
      live = false
    }
  }, [format, fetchItem])
  if (format === 'mp4') {
    return jsx('div', { style: S.card, children: error ? jsx('div', { style: Object.assign({}, S.text, { padding: 12 }), children: error })
      : video ? jsx('video', { src: video, controls: true, style: { width: '100%', background: FRAME_BG, display: 'block' } })
      : jsx('div', { style: Object.assign({}, S.meta, { padding: 12 }), children: 'Opening the film…' }) })
  }
  return jsx(ExportCard, { name: item.name, path: item.path, format, verified, load: format === 'glb' ? load : null, project, height: 480 })
}

function ProjectView({ row, onBack }) {
  const [open, setOpen] = useState({ kind: 'build', id: row.newest ? row.newest.build : null })
  const pick = (kind, id) => setOpen({ kind, id })
  let body = null
  if (open.kind === 'build' && open.id) {
    const b = row.builds.find(x => x.build === open.id) || row.newest
    body = jsx(ConstructCard, { project: row.project, build: b.build, title: b.title, parts: b.parts, sessionId: null, height: 560,
      extra: jsx('div', { style: S.meta, children: when(b.created) }) }, b.build)
  } else if (open.kind === 'kit') {
    body = jsx(KitCard, { project: row.project, kit: open.id, height: 560 }, open.id)
  } else if (open.kind === 'item') {
    const item = row.items.find(x => x.id === open.id)
    if (item) body = jsx(ItemView, { project: row.project, item }, item.id)
  }
  const list = (label, children) => children.length ? jsxs('div', { style: { marginTop: 18 },
    children: [jsx('div', { style: Object.assign({}, S.meta, { textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }), children: label }), ...children] }) : null
  return jsxs('div', {
    children: [
      jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' },
        children: [jsx(Button, { label: 'All constructs', icon: 'arrow-left', onClick: onBack }),
          jsx('div', { style: { fontSize: 16, fontWeight: 600, color: 'var(--ui-text-primary)' }, children: row.title }),
          jsx('span', { style: S.chip, children: row.project }),
          jsx('div', { style: S.meta, children: 'started ' + when(row.created) + ' · last ' + when(row.updated) }),
          row.changed_since ? jsx('span', { style: S.chip, title: 'The scene was changed after its newest build: build it again to see the change', children: 'scene changed since the last build' }) : null] }),
      body,
      list('Builds', row.builds.map(b => jsx('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderTop: '1px solid var(--ui-stroke-secondary)' },
        children: [jsx(Icon, { name: 'symbol-structure' }),
          jsx('div', { style: Object.assign({}, S.text, { flex: '1 1 auto' }), children: [when(b.created), b.parts ? plural(b.parts, 'part') : '', b.preview ? 'a run still growing' : '',
            b.audit_ok === false ? 'audit has errors' : ''].filter(Boolean).join(' · ') }),
          jsx(Button, { label: 'Show', icon: 'eye', active: open.kind === 'build' && open.id === b.build, onClick: () => pick('build', b.build) })] }, b.build))),
      list('Model kits', row.kits.map(k => jsx('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderTop: '1px solid var(--ui-stroke-secondary)' },
        children: [jsx(Icon, { name: 'extensions' }),
          jsx('div', { style: Object.assign({}, S.text, { flex: '1 1 auto' }), children: [when(k.created), plural(k.pieces || 0, 'piece'), plural(k.plates || 0, 'plate'), plural(k.steps || 0, 'step')].join(' · ') }),
          jsx(Button, { label: 'Step through', icon: 'eye', active: open.kind === 'kit' && open.id === k.kit, onClick: () => pick('kit', k.kit) })] }, k.kit))),
      list('Files', row.items.filter(i => i.kind !== 'kit').map(i => jsx(ItemRow, { project: row.project, item: i, onShow: x => pick('item', x.id) }, i.id)))
    ]
  })
}

function Projects({ focus }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(focus || null)
  const load = useCallback(() => {
    rest('/projects').then(
      r => {
        setRows(Array.isArray(r && r.projects) ? r.projects.filter(p => SLUG.test(String(p.project))) : [])
        setError('')
      },
      err => setError(errorText(err))
    )
  }, [])
  useEffect(() => {
    load()
    if (!CTX) return undefined
    const offs = [CTX.onEvent('plugin.construct.job.progress', ev => ev && ev.payload && ev.payload.state === 'done' && load()),
      CTX.onEvent('plugin.construct.run.preview', ev => ev && ev.payload && ev.payload.final && load())]
    return () => offs.forEach(off => typeof off === 'function' && off())
  }, [load])
  useEffect(() => {
    if (focus) setOpen(focus)
  }, [focus])
  if (error) return jsx('div', { style: S.text, children: error })
  if (!rows) return jsx('div', { style: S.meta, children: 'Loading…' })
  const row = open && rows.find(r => r.project === open)
  if (row) return jsx(ProjectView, { row, onBack: () => setOpen(null) }, row.project)
  if (!rows.length) {
    return jsxs('div', { style: { padding: '40px 0', textAlign: 'center', color: 'var(--ui-text-tertiary)', fontSize: 13 },
      children: [jsx('div', { style: { fontSize: 15, color: 'var(--ui-text-secondary)', marginBottom: 6 }, children: 'No constructs yet' }),
        jsx('div', { children: 'Ask Hermes for one ("Make a construct of a lighthouse"), or start from one under Start from.' })] })
  }
  // the same name twice (two copies of an example) is told apart by its project id and its dates
  const titles = {}
  rows.forEach(r => (titles[r.title] = (titles[r.title] || 0) + 1))
  return jsx('div', {
    style: GRID,
    children: rows.map(r => {
      const n = r.newest
      const counts = [n && n.parts ? plural(n.parts, 'part') : null, r.builds.length ? plural(r.builds.length, 'build') : null,
        r.kits.length ? plural(r.kits.length, 'kit') : null,
        r.items.length ? plural(r.items.length, 'file') : null].filter(Boolean).join(' · ')
      return jsx(Tile, {
        title: r.title, badge: titles[r.title] > 1 ? r.project : null, onOpen: () => setOpen(r.project),
        image: jsx(Img, { load: n && n.has_thumb ? () => rest('/thumb?' + query({ project: r.project, build: n.build })) : null, deps: [r.project, n && n.build] }),
        lines: [counts, 'last ' + when(r.updated) + (titles[r.title] > 1 ? '' : ' · ' + r.project), r.changed_since ? 'scene changed since the last build' : null]
      }, r.project)
    })
  })
}

function Examples() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    rest('/examples').then(r => setRows(Array.isArray(r && r.examples) ? r.examples : []), err => setError(errorText(err)))
  }, [])
  if (error) return jsx('div', { style: S.text, children: error })
  if (!rows) return jsx('div', { style: S.meta, children: 'Loading…' })
  const start = (e, how) => startChat(how === 'show'
    ? 'Show me the "' + e.title + '" construct: start a project from the example ' + e.name + ' with construct_start, build it with construct_build and put it in your reply; then tell me in a few lines what it shows and how each part is known (construct_inspect).'
    : 'Start a new construct from the example ' + e.name + ' ("' + e.title + '") with construct_start, build and show it, then ask me what I want to change: we will make it mine.')
  return jsxs('div', {
    children: [jsx('div', { style: Object.assign({}, S.text, { marginBottom: 12 }), children: 'Finished constructs that ship with the plugin. Each opens a new chat: Show builds it there; Start from makes it the first version of your own.' }),
      jsx('div', { style: GRID, children: rows.map(e => jsx(Tile, {
        title: e.title, onOpen: () => start(e, 'show'),
        image: jsx(Img, { load: e.has_thumb ? () => rest('/example-thumb?' + query({ name: e.name })) : null, deps: [e.name] }),
        lines: [plural(e.parts || 0, 'part') + (e.made ? ' · ' + str(e.made, 60) : ''), str(e.use, 120) || str(e.line, 170)],
        actions: [jsx(Button, { label: 'Show', icon: 'eye', onClick: () => start(e, 'show') }, 's'),
          jsx(Button, { label: 'Start from', icon: 'add', onClick: () => start(e, 'start') }, 'f')]
      }, e.name)) })]
  })
}

function Learn() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    rest('/tutorials').then(r => setRows(Array.isArray(r && r.tutorials) ? r.tutorials : []), err => setError(errorText(err)))
  }, [])
  if (error) return jsx('div', { style: S.text, children: error })
  if (!rows) return jsx('div', { style: S.meta, children: 'Loading…' })
  const groups = []
  rows.forEach(t => {
    let g = groups.find(x => x.name === t.group)
    if (!g) groups.push((g = { name: t.group, items: [] }))
    g.items.push(t)
  })
  return jsxs('div', {
    children: [jsx('div', { style: Object.assign({}, S.text, { marginBottom: 12 }), children: 'Each tutorial opens a new chat where Hermes teaches it step by step with the Construct tools, waiting for you between steps. They work from the command line too: /construct learn.' }),
      ...groups.map(g => jsxs('div', { style: { marginBottom: 20 }, children: [
        jsx('div', { style: Object.assign({}, S.meta, { textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }), children: g.name }),
        jsx('div', { style: GRID, children: g.items.map(t => jsx(Tile, {
          title: t.title, badge: t.status === 'placeholder' ? 'soon' : null,
          image: null, lines: [str(t.summary, 200), [t.time, t.needs.length ? 'needs ' + t.needs.join(', ') : ''].filter(Boolean).join(' · ')],
          actions: [jsx(Button, { label: 'Start', icon: 'play', disabled: t.status === 'placeholder', onClick: () => startChat(t.prompt) }, 's')]
        }, t.id)) })] }, g.name))]
  })
}

function Hub() {
  const [tab, setTab] = useState(pending.tab || 'constructs')
  const [focus, setFocus] = useState(pending.project)
  useEffect(() => {
    const fn = () => {
      if (pending.tab) setTab(pending.tab)
      if (pending.project) setFocus(pending.project)
      pending = { tab: null, project: null }
    }
    fn()
    hubListeners.add(fn)
    return () => hubListeners.delete(fn)
  }, [])
  const tabs = [['constructs', 'Constructs', 'symbol-structure'], ['examples', 'Start from', 'add'], ['learn', 'Learn', 'mortar-board']]
  return jsxs('div', {
    style: { height: '100%', overflow: 'auto', padding: '20px 24px', boxSizing: 'border-box' },
    children: [
      jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' },
        children: [jsx('div', { style: { fontSize: 18, fontWeight: 600, color: 'var(--ui-text-primary)', marginRight: 10 }, children: 'Construct' }),
          ...tabs.map(t => jsx(Button, { label: t[1], icon: t[2], active: tab === t[0], onClick: () => { setTab(t[0]); if (t[0] === 'constructs') setFocus(null) } }, t[0]))] }),
      tab === 'examples' ? jsx(Examples, {}) : tab === 'learn' ? jsx(Learn, {}) : jsx(Projects, { focus })
    ]
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
    onClick: () => openHub('constructs'),
    style: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '0 6px', fontSize: 11, background: 'transparent',
      border: 0, cursor: 'pointer', color: job.state === 'failed' ? 'var(--ui-text-secondary)' : 'var(--ui-text-tertiary)' },
    children: [jsx(Icon, { name: job.state === 'running' ? 'loading' : 'symbol-structure' }),
      jsx('span', { children: text + (list.length > 1 ? ' (+' + (list.length - 1) + ')' : '') })]
  })
}

// ---------------------------------------------------------------------------- registration

const MEDIA_TOOLS = ['construct_build', 'construct_job', 'construct_export', 'construct_command', 'construct_netlogo_run',
  'construct_netlogo_draw']

export default {
  id: ID,
  name: 'Construct',
  register(ctx) {
    CTX = ctx
    const parts = []
    if (typeof sdk.TOOL_MEDIA_RENDERER_AREA === 'string') {
      parts.push({ id: 'live', area: sdk.TOOL_MEDIA_RENDERER_AREA, data: { tools: MEDIA_TOOLS, render: props => jsx(ToolMedia, props) } })
    }
    if (typeof sdk.ROUTES_AREA === 'string' && typeof sdk.SIDEBAR_NAV_AREA === 'string') {
      parts.push({ id: 'hub', area: sdk.ROUTES_AREA, data: { path: HUB }, render: () => jsx(Hub, {}) })
      parts.push({ id: 'hub-nav', area: sdk.SIDEBAR_NAV_AREA, data: { path: HUB, label: 'Constructs', codicon: 'symbol-structure' } })
    }
    if (typeof sdk.PALETTE_AREA === 'string') {
      parts.push({ id: 'open-hub', area: sdk.PALETTE_AREA,
        data: { id: 'construct.open', label: 'Construct: Open the Constructs page', keywords: ['construct', 'hologram', 'gallery', 'projects'], run: () => openHub('constructs') } })
      parts.push({ id: 'open-examples', area: sdk.PALETTE_AREA,
        data: { id: 'construct.examples', label: 'Construct: Start from an example', keywords: ['construct', 'example', 'start'], run: () => openHub('examples') } })
      parts.push({ id: 'open-learn', area: sdk.PALETTE_AREA,
        data: { id: 'construct.learn', label: 'Construct: Learn (tutorials)', keywords: ['construct', 'tutorial', 'learn', 'netlogo'], run: () => openHub('learn') } })
    }
    if (sdk.STATUSBAR_AREAS && typeof sdk.STATUSBAR_AREAS.right === 'string') {
      parts.push({ id: 'jobs', area: sdk.STATUSBAR_AREAS.right, order: 140, render: () => jsx(JobsChip, {}) })
    }
    if (parts.length) ctx.registerMany(parts)
    ctx.onEvent('plugin.construct.job.progress', ev => setJob(ev && ev.payload))
    // /construct open <project> (a slash command the user typed) opens it on the Constructs page
    ctx.onEvent('plugin.construct.open', ev => {
      const p = ev && ev.payload
      if (p && SLUG.test(String(p.project || ''))) openHub('constructs', p.project)
    })
    ctx.onDispose(() => {
      jobs.clear()
      listeners.clear()
      hubListeners.clear()
      live3d.clear()
      CTX = null
    })
  }
}
