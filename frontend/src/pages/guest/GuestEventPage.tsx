import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CalendarDays, MapPin } from 'lucide-react'
import { publicService, type EventGuestData } from '../../services/publicService'
import { GuestMessage } from './GuestAlbumPage'
import { PhotoUploader } from '../../components/guest/PhotoUploader'
import { PhotoGallery } from '../../components/guest/PhotoGallery'

export default function GuestEventPage() {
  const { albumSlug = '', eventSlug = '' } = useParams()
  const [data, setData] = useState<EventGuestData | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { let live = true; setData(null); setError(false); publicService.event(albumSlug, eventSlug).then((value) => live && setData(value)).catch(() => live && setError(true)); return () => { live = false } }, [albumSlug, eventSlug])
  if (error) return <main className="guest-shell"><GuestMessage title="Event unavailable" text="This event may have been archived, or the link doesn’t match this album." /></main>
  if (!data) return <main className="guest-shell"><p role="status" className="px-6 py-20 text-center text-[#766f67]">Opening this celebration…</p></main>
  const { album, event, events } = data
  return <main className="guest-shell">
    <div className="mx-auto max-w-[1440px] px-5 pb-16 pt-7 sm:px-8 sm:pb-24 lg:px-12">
      <nav aria-label="Breadcrumb" className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm text-[#8d7044]"><Link to={`/a/${encodeURIComponent(album.slug)}`} title={album.name} className="min-w-0 max-w-[45%] truncate transition hover:text-[#5f4d30]">{album.name}</Link><span aria-hidden="true" className="shrink-0">/</span><span aria-current="page" className="min-w-0 break-words text-[#766f67]">{event.name}</span></nav>
      {event.cover_image?.url ? <header className="mt-6 grid min-w-0 overflow-hidden rounded-[1.75rem] border border-[#e8dece] bg-[#f5f0e7] lg:min-h-[420px] lg:grid-cols-[minmax(0,1fr)_minmax(0,.9fr)]">
        <div className="flex min-w-0 flex-col justify-center px-5 py-8 sm:px-12 sm:py-14 lg:px-16">
          <p className="guest-kicker">{album.couple_names || album.name}</p><h1 className="mt-3 break-words font-serif text-4xl leading-[1.08] tracking-[-.035em] sm:mt-4 sm:text-6xl">{event.name}</h1>
          {event.description && <p className="mt-4 max-w-2xl text-sm leading-6 text-[#766f67] sm:mt-5 sm:text-[15px] sm:leading-7">{event.description}</p>}
          <div className="mt-5 flex min-w-0 flex-wrap gap-x-5 gap-y-2 text-sm text-[#766f67] sm:mt-6 sm:gap-x-6">{event.event_date && <span className="inline-flex min-w-0 items-center gap-2"><CalendarDays size={16} strokeWidth={1.5} />{new Date(event.event_date).toLocaleDateString(undefined, { dateStyle: 'long' })}</span>}{event.location && <span className="inline-flex min-w-0 items-center gap-2"><MapPin size={16} strokeWidth={1.5} />{event.location}</span>}</div>
        </div>
        <div className="relative aspect-[16/10] min-w-0 overflow-hidden border-t border-[#e8dece] bg-[#e9dfd0] lg:aspect-auto lg:min-h-full lg:border-l lg:border-t-0">
          <img src={event.cover_image.url} alt={event.cover_image.alt_text || event.name} className="absolute inset-0 h-full w-full object-cover" />
        </div>
      </header> : <header className="mt-6 min-w-0 rounded-[1.5rem] border border-[#e8dece] bg-[#f5f0e7] px-5 py-7 sm:rounded-[1.75rem] sm:px-12 sm:py-11 lg:px-16">
        <p className="guest-kicker">{album.couple_names || album.name}</p>
        <h1 className="mt-3 max-w-4xl break-words font-serif text-4xl leading-[1.08] tracking-[-.035em] sm:mt-4 sm:text-6xl">{event.name}</h1>
        {event.description && <p className="mt-4 max-w-2xl text-sm leading-6 text-[#766f67] sm:mt-5 sm:text-[15px] sm:leading-7">{event.description}</p>}
        <span aria-hidden="true" className="mt-5 block h-px w-12 bg-[#b49b72] sm:mt-6" />
        <div className="mt-4 flex min-w-0 flex-wrap gap-x-5 gap-y-2 text-sm text-[#766f67]">{event.event_date && <span className="inline-flex min-w-0 items-center gap-2"><CalendarDays size={16} strokeWidth={1.5} />{new Date(event.event_date).toLocaleDateString(undefined, { dateStyle: 'long' })}</span>}{event.location && <span className="inline-flex min-w-0 items-center gap-2"><MapPin size={16} strokeWidth={1.5} />{event.location}</span>}</div>
      </header>}
      <div className="mx-auto mt-9 max-w-3xl"><PhotoUploader albumSlug={album.slug} eventSlug={event.slug} /></div>
      <div className="mt-14 border-t border-[#e3d9c9] pt-8 sm:mt-20 sm:pt-12"><PhotoGallery key={`${album.slug}/${event.slug}`} albumSlug={album.slug} eventSlug={event.slug} /></div>
      {events.length > 1 && <nav aria-label="Other wedding events" className="mt-12 border-t border-[#e3d9c9] pt-8"><p className="guest-kicker">Move through the celebration</p><div className="mt-4 flex flex-wrap gap-2">{events.map((item) => <Link key={item.slug} aria-current={item.slug === event.slug ? 'page' : undefined} to={`/a/${encodeURIComponent(album.slug)}/e/${encodeURIComponent(item.slug)}`} className={`rounded-full border px-4 py-2 text-sm transition ${item.slug === event.slug ? 'border-[#9b7b49] bg-[#9b7b49] text-white' : 'border-[#e3d9c9] bg-white/70 text-[#655337] hover:border-[#bda77f]'}`}>{item.name}</Link>)}</div></nav>}
    </div>
  </main>
}
