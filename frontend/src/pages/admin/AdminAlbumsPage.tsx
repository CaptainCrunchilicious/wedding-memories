import { useEffect, useState } from 'react'
import { Archive, CalendarDays, MapPin, Plus, Search, RotateCcw, Trash2, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { albumService, apiErrorMessage, type Album, type ResourceStatus } from '../../services/albumService'
import PublicQrActions, { albumUrl } from '../../components/admin/PublicQrActions'

type StatusFilter = 'all' | ResourceStatus

function displayDate(value: string | null) {
  if (!value) return 'Date not set'
  const dateOnly = value.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date not set' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

export default function AdminAlbumsPage() {
  const [albums, setAlbums] = useState<Album[]>([])
  const [status, setStatus] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    albumService.listAlbums({
      page,
      page_size: pageSize,
      ...(status === 'all' ? {} : { status }),
      ...(debouncedSearch ? { search: debouncedSearch } : {}),
    })
      .then((result) => {
        if (!active) return
        setAlbums(result.items)
        setTotal(result.total)
      })
      .catch((requestError: unknown) => {
        if (active) setError(apiErrorMessage(requestError, 'Albums could not be loaded. Please try again.'))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, pageSize, status, debouncedSearch])

  async function changeStatus(album: Album) {
    setError('')
    setNotice('')
    try {
      if (album.status === 'active') await albumService.archiveAlbum(album.id)
      else await albumService.restoreAlbum(album.id)
      setNotice(`“${album.name}” ${album.status === 'active' ? 'archived' : 'restored'}.`)
      setAlbums((current) => current.filter((item) => status === 'all' || item.id !== album.id))
      setTotal((current) => Math.max(0, current - (status === 'all' ? 0 : 1)))
      if (status === 'all') {
        albumService.listAlbums({ page, page_size: pageSize, ...(debouncedSearch ? { search: debouncedSearch } : {}) })
          .then((result) => { setAlbums(result.items); setTotal(result.total) })
          .catch(() => undefined)
      }
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album status could not be changed.'))
    }
  }

  async function deleteAlbum(album: Album) {
    if (!window.confirm(`Permanently delete “${album.name}”? Albums with events, photos, or contributors cannot be deleted.`)) return
    setError('')
    setNotice('')
    try {
      await albumService.deleteAlbum(album.id)
      setAlbums((current) => current.filter((item) => item.id !== album.id))
      setTotal((current) => Math.max(0, current - 1))
      setNotice(`“${album.name}” deleted.`)
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album could not be deleted. Archive it instead.'))
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  return (
    <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
      <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#9b7b49]">Your celebrations</p>
          <h1 className="mt-3 font-serif text-4xl font-normal sm:text-5xl">Albums</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[#766f67]">Create an album for each wedding and keep every event together.</p>
        </div>
        <Link to="/admin/albums/new" className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#9b7b49] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#85683c]"><Plus size={17} /> Create album</Link>
      </div>

      <div className="mt-8 flex flex-col gap-3 sm:flex-row">
        <label className="relative block flex-1">
          <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#a29a90]" />
          <input aria-label="Search albums" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Search by album name" className="w-full rounded-xl border border-[#e5ddd1] bg-white/80 py-3 pl-11 pr-4 text-sm outline-none focus:border-[#b89b69] focus:ring-4 focus:ring-[#b89b69]/10" />
        </label>
        <label>
          <span className="sr-only">Filter album status</span>
          <select aria-label="Filter album status" value={status} onChange={(event) => { setStatus(event.target.value as StatusFilter); setPage(1) }} className="w-full rounded-xl border border-[#e5ddd1] bg-white/80 px-4 py-3 text-sm text-[#5d554b] outline-none focus:border-[#b89b69] sm:w-48">
            <option value="all">All albums</option><option value="active">Active</option><option value="archived">Archived</option>
          </select>
        </label>
      </div>

      {notice && <p role="status" className="mt-5 rounded-xl border border-[#dce5d7] bg-[#f7fbf5] px-4 py-3 text-sm text-[#4f6d48]">{notice}</p>}
      {error && <p role="alert" className="mt-5 rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{error}</p>}
      {loading ? (
        <p className="py-16 text-center text-sm text-[#766f67]" role="status">Loading albums…</p>
      ) : albums.length === 0 ? (
        <section className="mt-8 rounded-3xl border border-dashed border-[#d9cdb8] bg-white/40 px-6 py-16 text-center">
          <p className="font-serif text-2xl text-[#4d463e]">{search || status !== 'all' ? 'No matching albums' : 'Your first album starts here'}</p>
          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#82796f]">{search || status !== 'all' ? 'Try another search or status filter.' : 'Create an album to bring the celebration and its events together.'}</p>
          {!search && status === 'all' && <Link className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#9b7b49] px-5 py-3 text-sm font-semibold text-white" to="/admin/albums/new"><Plus size={16} /> Create album</Link>}
        </section>
      ) : (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {albums.map((album) => (
            <article key={album.id} className="rounded-3xl border border-[#e9e1d4] bg-white/75 p-6 shadow-sm transition hover:shadow-md sm:p-7">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="truncate font-serif text-2xl text-[#332e29]">{album.name}</h2>
                  {album.couple_names && <p className="mt-1 inline-flex items-center gap-1.5 text-sm text-[#766f67]"><Users size={14} />{album.couple_names}</p>}
                </div>
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${album.status === 'active' ? 'bg-[#edf3e9] text-[#55704a]' : 'bg-[#f0ece6] text-[#776b5e]'}`}>{album.status === 'active' ? 'Active' : 'Archived'}</span>
              </div>
              <div className="mt-5 grid gap-2 text-sm text-[#766f67] sm:grid-cols-2">
                <p className="inline-flex items-center gap-2"><CalendarDays size={15} className="text-[#a18a62]" />{displayDate(album.event_date)}</p>
                {album.location && <p className="inline-flex items-center gap-2"><MapPin size={15} className="text-[#a18a62]" />{album.location}</p>}
                <p>{album.event_count} {album.event_count === 1 ? 'event' : 'events'}</p>
                <p>Created {displayDate(album.created_at.slice(0, 10))}</p>
              </div>
              {album.description && <p className="mt-4 line-clamp-2 text-sm leading-6 text-[#82796f]">{album.description}</p>}
              <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-[#eee8df] pt-4">
                <PublicQrActions url={albumUrl(album.slug)} label={album.name} disabled={album.status !== 'active'} />
                <Link to={`/admin/albums/${album.id}`} className="rounded-lg bg-[#f5f1e9] px-3.5 py-2 text-sm font-medium text-[#6e5939] hover:bg-[#eee5d5]">View details</Link>
                <Link to={`/admin/albums/${album.id}/edit`} className="rounded-lg px-3.5 py-2 text-sm font-medium text-[#766f67] hover:bg-[#faf8f3]">Edit</Link>
                <button onClick={() => void changeStatus(album)} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-[#766f67] hover:bg-[#faf8f3]">
                  {album.status === 'active' ? <Archive size={14} /> : <RotateCcw size={14} />}{album.status === 'active' ? 'Archive' : 'Restore'}
                </button>
                <button onClick={() => void deleteAlbum(album)} aria-label={`Delete ${album.name}`} className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-[#9a6250] hover:bg-[#fff7f4]"><Trash2 size={14} /> Delete</button>
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && total > pageSize && <div className="mt-7 flex items-center justify-between text-sm text-[#766f67]">
        <span>{total} albums</span>
        <div className="flex items-center gap-2"><button disabled={page <= 1} onClick={() => setPage((current) => current - 1)} className="rounded-lg border border-[#e5ddd1] px-3 py-2 disabled:opacity-40">Previous</button><span>Page {page} of {pageCount}</span><button disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)} className="rounded-lg border border-[#e5ddd1] px-3 py-2 disabled:opacity-40">Next</button></div>
      </div>}
    </main>
  )
}
