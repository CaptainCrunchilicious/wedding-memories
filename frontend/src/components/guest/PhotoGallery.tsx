import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Download, X } from 'lucide-react'
import { publicService, type PublicPhoto } from '../../services/publicService'

export function PhotoGallery({ albumSlug, eventSlug, onCountChange }: { albumSlug: string; eventSlug?: string; onCountChange?: (count: number) => void }) {
  const [photos, setPhotos] = useState<PublicPhoto[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const touchStartX = useRef<number | null>(null)

  useEffect(() => {
    let active = true
    if (page === 1) { setLoading(true); setPhotos([]); setSelectedIndex(null) }
    else setLoadingMore(true)
    setError(false)
    const request = eventSlug ? publicService.eventPhotos(albumSlug, eventSlug, page) : publicService.albumPhotos(albumSlug, page)
    request.then((result) => {
      if (!active) return
      setPhotos((current) => page === 1 ? result.items : [...current, ...result.items])
      setTotal(result.total)
      onCountChange?.(result.total)
    }).catch(() => { if (active) setError(true) })
      .finally(() => { if (active) { setLoading(false); setLoadingMore(false) } })
    return () => { active = false }
  }, [albumSlug, eventSlug, page, onCountChange])

  useEffect(() => {
    if (selectedIndex === null) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setSelectedIndex(null)
      if (event.key === 'ArrowRight') setSelectedIndex((current) => current === null ? null : (current + 1) % photos.length)
      if (event.key === 'ArrowLeft') setSelectedIndex((current) => current === null ? null : (current - 1 + photos.length) % photos.length)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedIndex, photos.length])

  useEffect(() => {
    if (selectedIndex === null) return
    const rootOverflow = document.documentElement.style.overflow
    const bodyOverflow = document.body.style.overflow
    document.documentElement.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
    return () => {
      document.documentElement.style.overflow = rootOverflow
      document.body.style.overflow = bodyOverflow
    }
  }, [selectedIndex])

  const selected = selectedIndex === null ? null : photos[selectedIndex]
  const downloadUrl = selected ? (() => { const url = new URL(selected.image_url); url.searchParams.set('download', 'true'); return url.toString() })() : undefined
  const previous = () => setSelectedIndex((current) => current === null ? null : (current - 1 + photos.length) % photos.length)
  const next = () => setSelectedIndex((current) => current === null ? null : (current + 1) % photos.length)

  return <section className="w-full min-w-0 max-w-full" aria-label={eventSlug ? 'Event photo gallery' : 'Wedding album gallery'}>
    <p className="guest-kicker">Shared memories</p><div className="mt-2 flex min-w-0 flex-col gap-1.5 sm:flex-row sm:items-end sm:justify-between sm:gap-4"><h2 className="min-w-0 break-words font-serif text-3xl leading-tight sm:text-4xl">{eventSlug ? 'Moments from this day' : 'Every celebration'}</h2>{total > 0 && <span className="min-w-0 text-xs text-[#82796f] sm:shrink-0 sm:text-sm">{total} {total === 1 ? 'photograph' : 'photographs'}</span>}</div>
    {loading ? <p role="status" className="mt-7 rounded-3xl bg-white/60 p-8 text-center text-sm text-[#766f67]">Gathering the approved memories…</p>
      : error ? <div role="alert" className="mt-7 rounded-3xl bg-white/70 p-8 text-center text-sm text-[#914e3a]">The gallery could not be loaded. Please try again.</div>
      : photos.length === 0 ? <div className="mt-7 rounded-3xl border border-dashed border-[#d9cdb8] bg-white/50 p-10 text-center"><p className="font-serif text-xl">The memories are gathering</p><p className="mt-2 text-sm text-[#82796f]">Approved photographs will appear here.</p></div>
      : <>
        <div className="mt-6 w-full min-w-0 max-w-full columns-2 gap-3 sm:mt-7 sm:columns-3 sm:gap-4 lg:columns-4 xl:columns-4">{photos.map((photo, index) => <button key={photo.id} onClick={() => setSelectedIndex(index)} aria-label={`Open wedding photo ${index + 1}`} className="group mb-3 block max-w-full break-inside-avoid overflow-hidden rounded-xl bg-[#eee5d8] text-left shadow-[0_5px_20px_-15px_rgba(69,54,32,.4)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9b7b49] sm:mb-4 sm:rounded-2xl">
          <img src={photo.image_url} alt={`Wedding memory ${index + 1}`} width={photo.width || undefined} height={photo.height || undefined} loading="lazy" decoding="async" className="block h-auto w-full max-w-full transition duration-700 ease-out group-hover:scale-[1.025]" />
        </button>)}</div>
        {photos.length < total && <div className="mt-7 text-center"><button disabled={loadingMore} onClick={() => setPage((current) => current + 1)} className="rounded-full border border-[#d9cdb8] bg-white/75 px-6 py-3 text-sm font-semibold text-[#655337] transition hover:border-[#bda77f] disabled:opacity-50">{loadingMore ? 'Gathering more…' : 'Load more photographs'}</button></div>}
      </>}
    {selected && <div role="dialog" aria-modal="true" aria-label="Photo preview" className="fixed inset-0 z-50 flex h-[100dvh] min-h-[100svh] w-full items-center justify-center overscroll-none bg-[#f6f1e9]/[.97] pl-[max(.5rem,env(safe-area-inset-left))] pr-[max(.5rem,env(safe-area-inset-right))] pt-[max(.75rem,env(safe-area-inset-top))] pb-[max(.75rem,env(safe-area-inset-bottom))] backdrop-blur-sm sm:px-8 sm:py-8" onClick={(event) => { if (event.target === event.currentTarget) setSelectedIndex(null) }} onTouchStart={(event) => { touchStartX.current = event.touches[0]?.clientX ?? null }} onTouchEnd={(event) => { const start = touchStartX.current; const end = event.changedTouches[0]?.clientX; if (start !== null && end !== undefined && Math.abs(end - start) > 48) (end < start ? next : previous)(); touchStartX.current = null }}>
      <button onClick={() => setSelectedIndex(null)} aria-label="Close photo preview" className="absolute right-[max(.75rem,env(safe-area-inset-right))] top-[max(.75rem,env(safe-area-inset-top))] z-10 min-h-12 min-w-12 rounded-full border border-[#ded2c0] bg-white/90 p-3 text-[#51483a] transition hover:bg-white"><X size={21} /></button>
      {photos.length > 1 && <button onClick={previous} aria-label="Previous photo" className="absolute left-[max(.5rem,env(safe-area-inset-left))] z-10 min-h-12 min-w-12 rounded-full border border-[#ded2c0] bg-white/90 p-3 text-[#51483a] transition hover:bg-white sm:left-6"><ChevronLeft size={24} /></button>}
      <div className="flex max-h-full min-w-0 max-w-full flex-col items-center justify-center gap-3 px-10 pb-14 pt-14 sm:gap-4 sm:px-16 sm:pb-16 sm:pt-8">
        <img src={selected.image_url} alt="Wedding memory full-size preview" decoding="async" className="block max-h-[calc(100dvh_-_10rem_-_env(safe-area-inset-top)_-_env(safe-area-inset-bottom))] max-w-[min(88vw,1280px)] rounded-md object-contain shadow-[0_25px_70px_-32px_rgba(51,46,41,.38)]" />
        <p className="text-xs tracking-[.12em] text-[#766f67]">{selectedIndex! + 1} <span className="px-1 text-[#b49b72]">/</span> {photos.length}</p>
      </div>
      {photos.length > 1 && <button onClick={next} aria-label="Next photo" className="absolute right-[max(.5rem,env(safe-area-inset-right))] z-10 min-h-12 min-w-12 rounded-full border border-[#ded2c0] bg-white/90 p-3 text-[#51483a] transition hover:bg-white sm:right-6"><ChevronRight size={24} /></button>}
      <a href={downloadUrl} download className="absolute bottom-[max(.75rem,env(safe-area-inset-bottom))] z-10 inline-flex min-h-12 items-center gap-2 rounded-full border border-[#d9cdb8] bg-white/95 px-5 py-3 text-sm font-semibold text-[#51483a] shadow-sm transition hover:bg-white"><Download size={16} /> Download photo</a>
    </div>}
  </section>
}
