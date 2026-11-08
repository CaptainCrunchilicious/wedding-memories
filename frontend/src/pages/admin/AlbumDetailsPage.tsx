import { useCallback, useEffect, useState } from 'react'
import { Archive, ArrowLeft, CalendarDays, MapPin, Plus, RotateCcw, Trash2, Users } from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import EventForm from '../../components/admin/EventForm'
import PublicQrActions, { albumUrl, eventUrl } from '../../components/admin/PublicQrActions'
import { albumService, apiErrorMessage, type Album, type Event, type EventInput, type ResourceStatus } from '../../services/albumService'

type StatusFilter = 'all' | ResourceStatus

function formatDate(value: string | null, includeTime = false) {
  if (!value) return 'Not set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not set'
  return new Intl.DateTimeFormat(undefined, includeTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { dateStyle: 'medium' }).format(date)
}

export default function AlbumDetailsPage() {
  const { albumId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [album, setAlbum] = useState<Album | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [eventStatus, setEventStatus] = useState<StatusFilter>('all')
  const [loading, setLoading] = useState(true)
  const [formOpen, setFormOpen] = useState(false)
  const [editingEvent, setEditingEvent] = useState<Event | undefined>()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState((location.state as { notice?: string } | null)?.notice ?? '')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [albumResult, eventResult] = await Promise.all([
        albumService.getAlbum(albumId),
        albumService.listEvents(albumId, { page: 1, page_size: 100, ...(eventStatus === 'all' ? {} : { status: eventStatus }) }),
      ])
      setAlbum(albumResult)
      setEvents(eventResult.items)
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album details could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [albumId, eventStatus])

  useEffect(() => { void load() }, [load])

  async function saveEvent(input: EventInput) {
    setSubmitting(true)
    setError('')
    try {
      if (editingEvent) await albumService.updateEvent(albumId, editingEvent.id, input)
      else await albumService.createEvent(albumId, input)
      setNotice(editingEvent ? 'Event updated successfully.' : 'Event created successfully.')
      setEditingEvent(undefined)
      setFormOpen(false)
      await load()
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Event could not be saved. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  async function changeEventStatus(event: Event) {
    setError('')
    try {
      if (event.status === 'active') await albumService.archiveEvent(albumId, event.id)
      else await albumService.restoreEvent(albumId, event.id)
      setNotice(`“${event.name}” ${event.status === 'active' ? 'archived' : 'restored'}.`)
      await load()
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Event status could not be changed.'))
    }
  }

  async function deleteEvent(event: Event) {
    if (!window.confirm(`Permanently delete “${event.name}”? Events with photos cannot be deleted.`)) return
    setError('')
    try {
      await albumService.deleteEvent(albumId, event.id)
      setNotice(`“${event.name}” deleted.`)
      await load()
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Event could not be deleted. Archive it instead.'))
    }
  }

  async function changeAlbumStatus() {
    if (!album) return
    setError('')
    try {
      const updated = album.status === 'active'
        ? await albumService.archiveAlbum(album.id)
        : await albumService.restoreAlbum(album.id)
      setAlbum(updated)
      if (updated.status === 'archived') {
        setFormOpen(false)
        setEditingEvent(undefined)
      }
      setNotice(`Album ${updated.status === 'active' ? 'restored' : 'archived'}.`)
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album status could not be changed.'))
    }
  }

  async function deleteAlbum() {
    if (!album || !window.confirm(`Permanently delete “${album.name}”? Albums with related records cannot be deleted.`)) return
    setError('')
    try {
      await albumService.deleteAlbum(album.id)
      navigate('/admin/albums', { replace: true, state: { notice: 'Album deleted.' } })
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album could not be deleted. Archive it instead.'))
    }
  }

  if (loading) return <main className="mx-auto max-w-6xl px-5 py-16 text-center text-sm text-[#766f67]" role="status">Loading album…</main>
  if (!album) return <main className="mx-auto max-w-6xl px-5 py-12"><p role="alert" className="rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{error || 'Album not found.'}</p><Link to="/admin/albums" className="mt-5 inline-flex items-center gap-2 text-sm text-[#6e5939]"><ArrowLeft size={15} /> Back to albums</Link></main>

  return (
    <main className="mx-auto max-w-6xl px-5 py-9 sm:px-8 sm:py-12">
      <Link to="/admin/albums" className="inline-flex items-center gap-2 text-sm text-[#8b8176] hover:text-[#6e5939]"><ArrowLeft size={15} /> All albums</Link>
      {notice && <p role="status" className="mt-5 rounded-xl border border-[#dce5d7] bg-[#f7fbf5] px-4 py-3 text-sm text-[#4f6d48]">{notice}</p>}
      {error && <p role="alert" className="mt-5 rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{error}</p>}
      <section className="mt-6 rounded-3xl border border-[#e9e1d4] bg-white/75 p-6 shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.23em] text-[#9b7b49]">Album</p>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${album.status === 'active' ? 'bg-[#edf3e9] text-[#55704a]' : 'bg-[#f0ece6] text-[#776b5e]'}`}>{album.status === 'active' ? 'Active' : 'Archived'}</span>
            </div>
            <h1 className="mt-3 font-serif text-4xl font-normal text-[#332e29] sm:text-5xl">{album.name}</h1>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-[#958b7f]">Public URL: <span className="font-medium text-[#766f67]">{albumUrl(album.slug)}</span></p><PublicQrActions url={albumUrl(album.slug)} label={album.name} disabled={album.status !== 'active'} /></div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/admin/albums/${album.id}/edit`} className="rounded-xl border border-[#e5ddd1] px-4 py-2.5 text-sm font-medium text-[#62594f] hover:bg-[#faf8f3]">Edit album</Link>
            <button onClick={() => void changeAlbumStatus()} className="inline-flex items-center gap-2 rounded-xl border border-[#e5ddd1] px-4 py-2.5 text-sm text-[#62594f] hover:bg-[#faf8f3]">{album.status === 'active' ? <Archive size={15} /> : <RotateCcw size={15} />}{album.status === 'active' ? 'Archive' : 'Restore'}</button>
            <button onClick={() => void deleteAlbum()} className="inline-flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-[#9a6250] hover:bg-[#fff7f4]"><Trash2 size={15} /> Delete</button>
          </div>
        </div>
        <div className="mt-7 grid gap-4 border-t border-[#eee8df] pt-6 sm:grid-cols-2 lg:grid-cols-4">
          {album.couple_names && <div className="flex items-start gap-3 text-sm text-[#62594f]"><Users size={16} className="mt-0.5 text-[#a18a62]" /><div><span className="block text-xs text-[#a29a90]">Couple</span>{album.couple_names}</div></div>}
          <div className="flex items-start gap-3 text-sm text-[#62594f]"><CalendarDays size={16} className="mt-0.5 text-[#a18a62]" /><div><span className="block text-xs text-[#a29a90]">Event date</span>{formatDate(album.event_date)}</div></div>
          {album.location && <div className="flex items-start gap-3 text-sm text-[#62594f]"><MapPin size={16} className="mt-0.5 text-[#a18a62]" /><div><span className="block text-xs text-[#a29a90]">Location</span>{album.location}</div></div>}
          <div className="text-sm text-[#62594f]"><span className="block text-xs text-[#a29a90]">Events</span>{album.event_count}</div>
        </div>
        {album.description && <p className="mt-5 max-w-3xl text-sm leading-7 text-[#766f67]">{album.description}</p>}
      </section>

      <section className="mt-10">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div><p className="text-xs font-semibold uppercase tracking-[0.23em] text-[#9b7b49]">Inside this album</p><h2 className="mt-2 font-serif text-3xl text-[#332e29]">Events</h2></div>
          <div className="flex flex-wrap items-center gap-3">
            <label><span className="sr-only">Filter event status</span><select aria-label="Filter event status" value={eventStatus} onChange={(event) => setEventStatus(event.target.value as StatusFilter)} className="rounded-xl border border-[#e5ddd1] bg-white/80 px-4 py-2.5 text-sm text-[#5d554b]"><option value="all">All events</option><option value="active">Active</option><option value="archived">Archived</option></select></label>
            {album.status === 'active' && <button onClick={() => { setEditingEvent(undefined); setFormOpen((value) => !value) }} className="inline-flex items-center gap-2 rounded-xl bg-[#9b7b49] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#85683c]"><Plus size={16} /> New event</button>}
          </div>
        </div>
        {formOpen && <div className="mt-5"><EventForm onSubmit={saveEvent} onCancel={() => { setFormOpen(false); setEditingEvent(undefined); setError('') }} submitting={submitting} serverError={error} /></div>}
        {!formOpen && editingEvent && <div className="mt-5"><EventForm initial={editingEvent} onSubmit={saveEvent} onCancel={() => { setEditingEvent(undefined); setError('') }} submitting={submitting} serverError={error} /></div>}
        {events.length === 0 ? (
          <div className="mt-5 rounded-3xl border border-dashed border-[#d9cdb8] bg-white/40 px-6 py-12 text-center"><p className="font-serif text-xl text-[#4d463e]">No events yet</p><p className="mt-2 text-sm text-[#82796f]">Add events such as Mehendi, Haldi, Wedding, or Reception.</p></div>
        ) : (
          <div className="mt-5 space-y-3">
            {events.map((event) => (
              <article key={event.id} className="rounded-2xl border border-[#e9e1d4] bg-white/75 p-5 sm:flex sm:items-center sm:justify-between sm:gap-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2"><h3 className="font-serif text-xl text-[#332e29]">{event.name}</h3><span className={`rounded-full px-2.5 py-1 text-[0.68rem] font-medium ${event.status === 'active' ? 'bg-[#edf3e9] text-[#55704a]' : 'bg-[#f0ece6] text-[#776b5e]'}`}>{event.status}</span></div>
                  <p className="mt-1 text-xs text-[#a29a90]">{eventUrl(album.slug, event.slug)}</p>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#82796f]">{event.event_date && <span>{formatDate(event.event_date, true)}</span>}{event.location && <span>{event.location}</span>}<span>Order {event.display_order}</span></div>
                  {event.description && <p className="mt-2 line-clamp-2 text-sm text-[#82796f]">{event.description}</p>}
                </div>
                <div className="mt-4 flex shrink-0 flex-wrap items-center gap-1 border-t border-[#eee8df] pt-3 sm:mt-0 sm:border-0 sm:pt-0">
                  <PublicQrActions url={eventUrl(album.slug, event.slug)} label={event.name} disabled={album.status !== 'active' || event.status !== 'active'} />
                  <button onClick={() => { setFormOpen(false); setEditingEvent(event); setError('') }} className="rounded-lg px-3 py-2 text-sm text-[#766f67] hover:bg-[#faf8f3]">Edit</button>
                  <button onClick={() => void changeEventStatus(event)} disabled={event.status === 'archived' && album.status === 'archived'} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-[#766f67] hover:bg-[#faf8f3] disabled:cursor-not-allowed disabled:opacity-40">{event.status === 'active' ? <Archive size={13} /> : <RotateCcw size={13} />}{event.status === 'active' ? 'Archive' : 'Restore'}</button>
                  <button onClick={() => void deleteEvent(event)} aria-label={`Delete ${event.name}`} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-[#9a6250] hover:bg-[#fff7f4]"><Trash2 size={13} /> Delete</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
