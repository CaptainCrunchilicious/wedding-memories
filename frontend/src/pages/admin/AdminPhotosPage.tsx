import { useEffect, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, ImageOff, Search, ShieldCheck, Trash2, X } from 'lucide-react'
import { albumService, type Album, type Event } from '../../services/albumService'
import { apiErrorMessage } from '../../services/albumService'
import { photoService, type AdminPhoto, type PhotoQuery, type PhotoStatus } from '../../services/photoService'

function dateLabel(value: string | null) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function bytesLabel(value: number | null) {
  if (value === null) return 'Size unavailable'
  return value < 1024 * 1024 ? `${Math.round(value / 1024)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`
}

function AdminPhotoImage({ photoId, alt, className }: { photoId: string; alt: string; className: string }) {
  const [source, setSource] = useState('')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let active = true
    let objectUrl = ''
    setSource(''); setFailed(false)
    photoService.preview(photoId).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      if (active) setSource(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    }).catch(() => { if (active) setFailed(true) })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [photoId])
  if (failed) return <div className={`flex items-center justify-center bg-[#f1ece3] text-[#978c7c] ${className}`}><ImageOff size={24} /><span className="sr-only">Photo preview unavailable</span></div>
  if (!source) return <div role="status" aria-label="Loading photo preview" className={`animate-pulse bg-[#eee7dc] ${className}`} />
  return <img src={source} alt={alt} loading="lazy" className={className} />
}

const PAGE_SIZE = 24

export default function AdminPhotosPage() {
  const [photos, setPhotos] = useState<AdminPhoto[]>([])
  const [counts, setCounts] = useState({ all: 0, pending: 0, approved: 0, rejected: 0, deletion_pending: 0 })
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<'all' | PhotoStatus | 'deletion_pending'>('pending')
  const [albums, setAlbums] = useState<Album[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [albumId, setAlbumId] = useState('')
  const [eventId, setEventId] = useState('')
  const [search, setSearch] = useState('')
  const [searchValue, setSearchValue] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [preview, setPreview] = useState<AdminPhoto | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    albumService.listAlbums({ page: 1, page_size: 100 })
      .then((result) => setAlbums(result.items))
      .catch(() => setError('Album filters could not be loaded.'))
  }, [])

  useEffect(() => {
    if (!albumId) { setEvents([]); setEventId(''); return }
    let active = true
    albumService.listEvents(albumId, { page: 1, page_size: 100 })
      .then((result) => { if (active) setEvents(result.items) })
      .catch(() => { if (active) setEvents([]) })
    return () => { active = false }
  }, [albumId])

  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    const query: PhotoQuery = { page, page_size: PAGE_SIZE,
      ...(status === 'deletion_pending' ? { deletion_state: 'pending' as const } : status === 'all' ? {} : { status }),
      ...(albumId ? { album_id: albumId } : {}), ...(eventId ? { event_id: eventId } : {}), ...(search ? { search } : {}) }
    photoService.list(query).then((result) => {
      if (!active) return
      setPhotos(result.items); setTotal(result.total); setCounts(result.counts)
    }).catch((requestError: unknown) => { if (active) setError(apiErrorMessage(requestError, 'Photos could not be loaded.')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, status, albumId, eventId, search, refresh])

  function changeFilter(update: () => void) {
    setPage(1); setSelected(new Set()); setNotice(''); setError(''); update()
  }

  async function moderate(photo: AdminPhoto, action: 'approve' | 'reject') {
    setBusy(true); setError(''); setNotice('')
    try {
      await photoService[action](photo.id)
      setNotice(`${photo.original_filename} ${action === 'approve' ? 'approved' : 'rejected'}.`)
      setSelected((current) => { const next = new Set(current); next.delete(photo.id); return next })
      if (preview?.id === photo.id) setPreview(null)
      setRefresh((value) => value + 1)
    } catch (requestError) { setError(apiErrorMessage(requestError, `Photo could not be ${action === 'approve' ? 'approved' : 'rejected'}.`)) }
    finally { setBusy(false) }
  }

  async function bulkApprove() {
    if (!selected.size || busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await photoService.bulkApprove([...selected])
      const failures = new Set(result.results.filter((item) => !item.success).map((item) => item.photo_id))
      setSelected(failures)
      setNotice(`${result.succeeded} photo${result.succeeded === 1 ? '' : 's'} approved${result.failed ? `; ${result.failed} could not be approved` : ''}.`)
      setRefresh((value) => value + 1)
    } catch (requestError) { setError(apiErrorMessage(requestError, 'Bulk approval could not be completed.')) }
    finally { setBusy(false) }
  }

  async function permanentlyDelete(photo: AdminPhoto) {
    const retrying = photo.deletion_state === 'pending'
    if (!retrying && !window.confirm(`Permanently delete ${photo.original_filename} and its stored image? This cannot be undone.`)) return
    setBusy(true); setError(''); setNotice('')
    try {
      await photoService.remove(photo.id)
      setSelected((current) => { const next = new Set(current); next.delete(photo.id); return next })
      if (preview?.id === photo.id) setPreview(null)
      setNotice(retrying ? `${photo.original_filename} deletion completed.` : `${photo.original_filename} was permanently deleted.`)
      setRefresh((value) => value + 1)
    } catch (requestError) { setError(apiErrorMessage(requestError, 'Photo could not be deleted. The record was retained if its image could not be removed.')) }
    finally { setBusy(false) }
  }

  const pendingOnPage = photos.filter((photo) => photo.status === 'pending' && photo.deletion_state !== 'pending')
  const allPageSelected = pendingOnPage.length > 0 && pendingOnPage.every((photo) => selected.has(photo.id))
  function toggleAllPending() {
    setSelected((current) => {
      const next = new Set(current)
      if (allPageSelected) pendingOnPage.forEach((photo) => next.delete(photo.id))
      else pendingOnPage.forEach((photo) => next.add(photo.id))
      return next
    })
  }
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return <main className="mx-auto max-w-7xl px-5 py-9 sm:px-8 sm:py-12">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-semibold uppercase tracking-[.23em] text-[#9b7b49]">Care for every memory</p><h1 className="mt-2 font-serif text-4xl">Photo Moderation</h1><p className="mt-2 text-sm text-[#766f67]">Review guest uploads before they join the shared galleries.</p></div>
      {pendingOnPage.length > 0 && <button onClick={toggleAllPending} className="rounded-full border border-[#ded4c4] bg-white px-4 py-2.5 text-sm font-semibold text-[#655337]">{allPageSelected ? 'Clear page selection' : 'Select pending on page'}</button>}</div>
    <div className="mt-7 grid grid-cols-2 gap-3 lg:grid-cols-5">{([['All photos', counts.all], ['Pending', counts.pending], ['Approved', counts.approved], ['Rejected', counts.rejected], ['Deletion retry', counts.deletion_pending]] as const).map(([label, count]) => <article key={label} className="rounded-2xl border border-[#e9e1d4] bg-white/70 p-4"><p className="text-xs text-[#82796f]">{label}</p><p className="mt-1 font-serif text-3xl">{count}</p></article>)}</div>
    <section className="mt-6 rounded-2xl border border-[#e9e1d4] bg-white/75 p-4 sm:p-5" aria-label="Photo filters"><div className="flex flex-col gap-3 lg:flex-row">
      <label className="relative min-w-52 flex-1"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9a9186]"/><input value={searchValue} onChange={(event) => setSearchValue(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') changeFilter(() => setSearch(searchValue.trim())) }} placeholder="Search filename" aria-label="Search filename" className="w-full rounded-xl border border-[#e5ddd1] bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-[#b89b69]"/></label>
      <select aria-label="Filter by album" value={albumId} onChange={(event) => changeFilter(() => { setAlbumId(event.target.value); setEventId('') })} className="rounded-xl border border-[#e5ddd1] bg-white px-3 py-2.5 text-sm"><option value="">All albums</option>{albums.map((album) => <option key={album.id} value={album.id}>{album.name}</option>)}</select>
      <select aria-label="Filter by event" value={eventId} disabled={!albumId} onChange={(event) => changeFilter(() => setEventId(event.target.value))} className="rounded-xl border border-[#e5ddd1] bg-white px-3 py-2.5 text-sm disabled:opacity-50"><option value="">All events</option>{events.map((event) => <option key={event.id} value={event.id}>{event.name}</option>)}</select>
    </div><div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter by photo status">{(['all', 'pending', 'approved', 'rejected', 'deletion_pending'] as const).map((item) => <button key={item} aria-pressed={status === item} onClick={() => changeFilter(() => setStatus(item))} className={`rounded-full px-4 py-2 text-sm capitalize ${status === item ? 'bg-[#9b7b49] text-white' : 'bg-[#f4efe6] text-[#655337]'}`}>{item === 'deletion_pending' ? 'Deletion retry' : item}</button>)}</div></section>
    {selected.size > 0 && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#d8e1d2] bg-[#f5f8f2] p-4"><p className="text-sm text-[#536b4d]">{selected.size} pending photo{selected.size === 1 ? '' : 's'} selected</p><div className="flex gap-2"><button disabled={busy} onClick={() => void bulkApprove()} className="inline-flex items-center gap-2 rounded-full bg-[#456346] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Check size={16}/>{busy ? 'Approving…' : 'Approve selected'}</button><button onClick={() => setSelected(new Set())} className="rounded-full border border-[#cfd9c9] px-4 py-2.5 text-sm">Clear selection</button></div></div>}
    {notice && <p role="status" className="mt-4 rounded-xl bg-[#f3f6ef] px-4 py-3 text-sm text-[#55704a]">{notice}</p>}
    {error && <p role="alert" className="mt-4 rounded-xl bg-[#fff4ef] px-4 py-3 text-sm text-[#914e3a]">{error}</p>}
    {loading ? <p role="status" className="py-16 text-center text-sm text-[#766f67]">Loading photos…</p>
      : photos.length === 0 ? <section className="mt-6 rounded-3xl border border-dashed border-[#d9cdb8] bg-white/50 px-6 py-16 text-center"><ShieldCheck className="mx-auto text-[#9b7b49]"/><h2 className="mt-3 font-serif text-2xl">No photos in this view</h2><p className="mt-2 text-sm text-[#82796f]">Try another status or filter.</p></section>
      : <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{photos.map((photo) => <article key={photo.id} className="overflow-hidden rounded-3xl border border-[#e9e1d4] bg-white/80 shadow-sm">
        <button onClick={() => setPreview(photo)} aria-label={`Preview ${photo.original_filename}`} className="relative block aspect-[4/3] w-full bg-[#f1ece3]"><AdminPhotoImage photoId={photo.id} alt={photo.original_filename} className="h-full w-full object-cover" /><span className={`absolute left-3 top-3 rounded-full px-3 py-1 text-xs font-semibold capitalize ${photo.deletion_state === 'pending' ? 'bg-[#f8e9e3] text-[#965540]' : photo.status === 'approved' ? 'bg-[#eaf1e6] text-[#4d6b45]' : photo.status === 'rejected' ? 'bg-[#f8e9e3] text-[#965540]' : 'bg-[#fff5de] text-[#8b6b2f]'}`}>{photo.deletion_state === 'pending' ? 'Deletion retry' : photo.status}</span></button>
        <div className="p-4"><h2 className="truncate font-medium text-[#3b352e]" title={photo.original_filename}>{photo.original_filename}</h2><p className="mt-2 text-sm text-[#766f67]">{photo.album.name} · {photo.event.name}</p><p className="mt-1 text-xs text-[#968b7d]">{dateLabel(photo.uploaded_at)} · {bytesLabel(photo.file_size)} · {photo.storage_provider === 'google_drive' ? 'Google Drive' : 'Local storage'}</p>
          {photo.deletion_state === 'pending' && <p className="mt-3 rounded-lg bg-[#fff4ef] p-3 text-sm text-[#914e3a]">This image is hidden from guests. Retry deletion when storage is available.</p>}<div className="mt-4 flex flex-wrap gap-2">{photo.deletion_state !== 'pending' && (photo.status === 'pending' || photo.status === 'rejected') && <button disabled={busy} onClick={() => void moderate(photo, 'approve')} className="inline-flex items-center gap-1.5 rounded-lg bg-[#edf3e9] px-3 py-2 text-sm font-medium text-[#55704a] disabled:opacity-50"><Check size={14}/>{photo.status === 'rejected' ? 'Restore to approved' : 'Approve'}</button>}{photo.deletion_state !== 'pending' && (photo.status === 'pending' || photo.status === 'approved') && <button disabled={busy} onClick={() => void moderate(photo, 'reject')} className="rounded-lg bg-[#fff4ef] px-3 py-2 text-sm font-medium text-[#965540] disabled:opacity-50">Reject</button>}
            {photo.deletion_state !== 'pending' && <button onClick={() => setPreview(photo)} className="rounded-lg border border-[#e5ddd1] px-3 py-2 text-sm text-[#655337]">Preview</button>}<button disabled={busy} onClick={() => void permanentlyDelete(photo)} aria-label={photo.deletion_state === 'pending' ? `Retry deletion of ${photo.original_filename}` : `Permanently delete ${photo.original_filename}`} className="ml-auto inline-flex items-center gap-2 rounded-lg p-2 text-[#965540] hover:bg-[#fff4ef] disabled:opacity-50">{photo.deletion_state === 'pending' ? 'Retry deletion' : <Trash2 size={16}/>}</button>
          </div>
          {photo.moderated_by && <p className="mt-3 text-xs text-[#968b7d]">Reviewed by {photo.moderated_by}{photo.moderated_at ? ` · ${dateLabel(photo.moderated_at)}` : ''}</p>}
        </div>
        {photo.status === 'pending' && <label className="flex items-center gap-2 border-t border-[#eee8df] px-4 py-3 text-sm text-[#766f67]"><input type="checkbox" checked={selected.has(photo.id)} onChange={(event) => setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(photo.id); else next.delete(photo.id); return next })} aria-label={`Select ${photo.original_filename} for bulk approval`}/>Select for bulk approval</label>}
      </article>)}</div>}
    {!loading && total > PAGE_SIZE && <div className="mt-6 flex items-center justify-between text-sm text-[#766f67]"><button disabled={page <= 1} onClick={() => { setSelected(new Set()); setPage((current) => current - 1) }} className="inline-flex items-center gap-1 rounded-lg border border-[#e5ddd1] px-3 py-2 disabled:opacity-40"><ChevronLeft size={16}/> Previous</button><span>Page {page} of {pageCount} · {total} photos</span><button disabled={page >= pageCount} onClick={() => { setSelected(new Set()); setPage((current) => current + 1) }} className="inline-flex items-center gap-1 rounded-lg border border-[#e5ddd1] px-3 py-2 disabled:opacity-40">Next <ChevronRight size={16}/></button></div>}
    {preview && <div role="dialog" aria-modal="true" aria-label={`Preview ${preview.original_filename}`} onClick={(event) => { if (event.target === event.currentTarget) setPreview(null) }} className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#211e1a]/90 p-4 sm:p-8"><button onClick={() => setPreview(null)} aria-label="Close preview" className="absolute right-5 top-5 rounded-full bg-white/10 p-3 text-white"><X size={22}/></button><section className="my-auto grid w-full max-w-6xl overflow-hidden rounded-3xl bg-[#fffdf9] shadow-2xl lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,.8fr)]"><div className="flex min-h-64 items-center justify-center bg-[#201d19] p-3"><AdminPhotoImage photoId={preview.id} alt={preview.original_filename} className="max-h-[75vh] max-w-full object-contain"/></div><div className="p-6 sm:p-8"><p className="text-xs font-semibold uppercase tracking-[.22em] text-[#9b7b49]">{preview.status} review</p><h2 className="mt-2 break-words font-serif text-2xl">{preview.original_filename}</h2><p className="mt-4 text-sm text-[#766f67]">{preview.album.name} · {preview.event.name}</p><p className="mt-2 text-sm text-[#968b7d]">{dateLabel(preview.uploaded_at)} · {bytesLabel(preview.file_size)}</p><p className="mt-4 text-xs text-[#968b7d]">{preview.width} × {preview.height} · {preview.mime_type}</p>
      <div className="mt-7 flex flex-wrap gap-2">{(preview.status === 'pending' || preview.status === 'rejected') && <button disabled={busy} onClick={() => void moderate(preview, 'approve')} className="rounded-full bg-[#456346] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{preview.status === 'rejected' ? 'Restore to approved' : 'Approve'}</button>}{(preview.status === 'pending' || preview.status === 'approved') && <button disabled={busy} onClick={() => void moderate(preview, 'reject')} className="rounded-full border border-[#dfc5b9] px-4 py-2.5 text-sm text-[#965540] disabled:opacity-50">Reject</button>}<button disabled={busy} onClick={() => void permanentlyDelete(preview)} className="rounded-full border border-[#dfc5b9] px-4 py-2.5 text-sm text-[#965540] disabled:opacity-50">Permanently delete</button></div>
    </div></section></div>}
  </main>
}
