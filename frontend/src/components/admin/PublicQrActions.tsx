import { useRef, useState } from 'react'
import { Copy, Download, ExternalLink, QrCode, X } from 'lucide-react'
import { QRCodeCanvas } from 'qrcode.react'
import { PUBLIC_APP_URL } from '../../config/api'

export function albumUrl(slug: string) { return `${PUBLIC_APP_URL}/a/${encodeURIComponent(slug)}` }
export function eventUrl(albumSlug: string, eventSlug: string) { return `${albumUrl(albumSlug)}/e/${encodeURIComponent(eventSlug)}` }

export default function PublicQrActions({ url, label, disabled = false }: { url: string; label: string; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const canvasRef = useRef<HTMLDivElement>(null)
  async function copy() {
    try { await navigator.clipboard.writeText(url); setCopied(true); window.setTimeout(() => setCopied(false), 1800) } catch { setCopied(false) }
  }
  function download() {
    const canvas = canvasRef.current?.querySelector('canvas')
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-qr.png`
    link.href = canvas.toDataURL('image/png'); link.click()
  }
  return <>
    <div className="flex flex-wrap items-center gap-2">
      <button disabled={disabled} onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 rounded-lg border border-[#e5ddd1] px-3 py-2 text-sm text-[#6e5939] disabled:opacity-40"><QrCode size={15} /> QR & link</button>
      {!disabled && <a href={url} target="_blank" rel="noreferrer" aria-label={`Open public page for ${label}`} className="inline-flex items-center gap-1 rounded-lg px-2 py-2 text-sm text-[#766f67]"><ExternalLink size={15} /> Open</a>}
    </div>
    {open && <div role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false) }} className="fixed inset-0 z-50 flex items-center justify-center bg-[#27231f]/55 p-4">
      <section role="dialog" aria-modal="true" aria-label={`${label} QR code`} className="w-full max-w-sm rounded-3xl bg-[#fffdf9] p-6 text-center shadow-2xl">
        <button onClick={() => setOpen(false)} aria-label="Close QR code" className="ml-auto flex rounded-full p-2 text-[#766f67]"><X size={18} /></button>
        <p className="font-serif text-2xl">{label}</p><p className="mt-1 break-all text-xs text-[#82796f]">{url}</p>
        <div ref={canvasRef} className="mx-auto mt-5 inline-block rounded-xl bg-white p-4"><QRCodeCanvas value={url} size={224} level="H" includeMargin bgColor="#ffffff" fgColor="#201b16" /></div>
        <div className="mt-5 flex justify-center gap-2"><button onClick={download} className="inline-flex items-center gap-2 rounded-full bg-[#9b7b49] px-4 py-2.5 text-sm font-semibold text-white"><Download size={15} /> Download PNG</button><button onClick={() => void copy()} className="inline-flex items-center gap-2 rounded-full border border-[#ded4c4] px-4 py-2.5 text-sm font-semibold text-[#655337]"><Copy size={15} /> {copied ? 'Copied' : 'Copy URL'}</button></div>
      </section>
    </div>}
  </>
}
