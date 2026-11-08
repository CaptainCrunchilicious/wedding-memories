import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CalendarDays, MapPin, ArrowUpRight } from 'lucide-react'
import { publicService, type AlbumGuestData, type PublicEvent } from '../../services/publicService'
import { PhotoGallery } from '../../components/guest/PhotoGallery'

type EventCardData = { name: string; slug: string; event?: PublicEvent; photoCount?: number }

export default function GuestAlbumPage() {
  const { albumSlug = '' } = useParams()
  const [data, setData] = useState<AlbumGuestData | null>(null)
  const [events, setEvents] = useState<EventCardData[]>([])
  const [error, setError] = useState(false)
  const [photoCount, setPhotoCount] = useState<number | null>(null)

  useEffect(() => {
    let live = true
    setData(null)
    setError(false)
    publicService.album(albumSlug).then((value) => {
      if (!live) return
      setData(value)
      setEvents(value.events.map((event) => ({ ...event })))
    }).catch(() => live && setError(true))
    return () => { live = false }
  }, [albumSlug])

  useEffect(() => {
    if (!data) return
    let live = true
    Promise.all(data.events.map(async (item) => {
      const [detail, photos] = await Promise.allSettled([
        publicService.event(data.album.slug, item.slug),
        publicService.eventPhotos(data.album.slug, item.slug, 1),
      ])
      return {
        ...item,
        ...(detail.status === 'fulfilled' && detail.value ? { event: detail.value.event } : {}),
        ...(photos.status === 'fulfilled' && photos.value ? { photoCount: photos.value.total } : {}),
      }
    })).then((items) => { if (live) setEvents(items) })
    return () => { live = false }
  }, [data])

  if (error) return <main className="guest-shell"><GuestMessage title="Album unavailable" text="This album may have been archived or the link may be incorrect." /></main>
  if (!data) return <main className="guest-shell"><p role="status" className="px-6 py-20 text-center text-[#766f67]">Opening your wedding album…</p></main>
  const { album } = data
  const date = album.event_date ? new Date(album.event_date).toLocaleDateString(undefined, { dateStyle: 'long' }) : null
  return <main className="guest-shell">
    <div className="mx-auto max-w-[1440px] px-5 pb-16 pt-7 sm:px-8 sm:pb-24 lg:px-12">
      <header className={`min-w-0 overflow-hidden border border-[#e8dece] bg-[#f5f0e7] shadow-[0_24px_70px_-50px_rgba(69,54,32,.5)] ${album.cover_image?.url ? 'grid rounded-[1.75rem] sm:rounded-[2rem] lg:min-h-[490px] lg:grid-cols-[minmax(0,1.05fr)_minmax(0,.95fr)]' : 'rounded-[1.5rem] px-5 py-8 sm:rounded-[2rem] sm:px-12 sm:py-12 lg:px-16 lg:py-14'}`}>
        <div className={`flex min-w-0 flex-col justify-center break-words ${album.cover_image?.url ? 'px-5 py-8 sm:px-12 sm:py-16 lg:px-16' : ''}`}>
          <p className="guest-kicker">A celebration of love</p>
          {album.cover_image?.url && <p className="mt-4 text-xs uppercase tracking-[.18em] text-[#a88d62] sm:mt-5">Wedding memories</p>}
          <h1 className="mt-3 max-w-2xl break-words font-serif text-4xl leading-[1.08] tracking-[-.035em] sm:mt-4 sm:text-6xl lg:text-7xl">{album.name}</h1>
          {album.couple_names && <p className="mt-4 break-words font-serif text-xl text-[#94764b] sm:mt-5 sm:text-3xl">{album.couple_names}</p>}
          {album.description && <p className="mt-4 max-w-xl break-words text-sm leading-6 text-[#766f67] sm:mt-6 sm:text-[15px] sm:leading-7">{album.description}</p>}
          <div className="mt-5 flex min-w-0 flex-wrap gap-x-5 gap-y-2 text-sm text-[#766f67] sm:mt-7 sm:gap-x-6 sm:gap-y-3">
            {date && <span className="inline-flex items-center gap-2"><CalendarDays size={16} strokeWidth={1.5} />{date}</span>}
            {album.location && <span className="inline-flex items-center gap-2"><MapPin size={16} strokeWidth={1.5} />{album.location}</span>}
          </div>
          <div className="mt-6 flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 border-t border-[#ded2c0] pt-4 text-sm text-[#766f67] sm:mt-9 sm:gap-5 sm:pt-5">
            <span>{data.events.length} {data.events.length === 1 ? 'celebration' : 'celebrations'}</span>
            <span aria-hidden="true" className="h-1 w-1 rounded-full bg-[#b49b72]" />
            <span>{photoCount === null ? 'Approved memories' : `${photoCount} approved ${photoCount === 1 ? 'photograph' : 'photographs'}`}</span>
          </div>
        </div>
        {album.cover_image?.url && <div className="relative aspect-[16/10] min-w-0 overflow-hidden border-t border-[#e8dece] bg-[#e9dfd0] lg:aspect-auto lg:min-h-full lg:border-l lg:border-t-0"><img src={album.cover_image.url} alt={album.cover_image.alt_text || album.name} loading="eager" decoding="async" className="absolute inset-0 h-full w-full max-w-full object-cover" /></div>}
      </header>

      <section className="mt-16 sm:mt-24" aria-labelledby="celebrations-heading">
        <div className="flex flex-col justify-between gap-3 border-b border-[#e3d9c9] pb-5 sm:flex-row sm:items-end">
          <div><p className="guest-kicker">The celebrations</p><h2 id="celebrations-heading" className="mt-2 font-serif text-3xl sm:text-4xl">Explore each moment</h2></div>
          <p className="max-w-sm text-sm leading-6 text-[#82796f]">Step into each gathering and share the photographs you love.</p>
        </div>
        {events.length ? <div className="mt-6 grid min-w-0 gap-4 sm:mt-7 sm:gap-5 md:grid-cols-2 xl:grid-cols-3">{events.map((item, index) => <Link key={item.slug} to={`/a/${encodeURIComponent(album.slug)}/e/${encodeURIComponent(item.slug)}`} className="group min-w-0 overflow-hidden rounded-[1.5rem] border border-[#e8dece] bg-[#fffefa] shadow-[0_12px_35px_-30px_rgba(69,54,32,.45)] transition duration-300 hover:-translate-y-1 hover:shadow-[0_22px_42px_-30px_rgba(69,54,32,.48)]">
          <div className="relative aspect-[16/9] overflow-hidden bg-[#eee7dc]">
            {item.event?.cover_image?.url ? <img src={item.event.cover_image.url} alt={item.event.cover_image.alt_text || item.name} loading="lazy" decoding="async" className="h-full w-full max-w-full object-cover transition duration-700 group-hover:scale-[1.025]" /> : <div className="flex h-full items-center justify-center bg-[radial-gradient(ellipse_at_50%_42%,#faf7f0_0,#e9dfd0_100%)]"><span aria-hidden="true" className="font-serif text-6xl italic text-[#c2ad8b]">{String(index + 1).padStart(2, '0')}</span></div>}
            <span className="absolute left-5 top-5 rounded-full border border-white/70 bg-[#faf8f3]/90 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[.18em] text-[#76674d]">Celebration {String(index + 1).padStart(2, '0')}</span>
          </div>
          <div className="p-6 sm:p-7">
            <div className="flex min-w-0 items-start justify-between gap-3"><h3 className="min-w-0 break-words font-serif text-2xl leading-tight sm:text-3xl">{item.name}</h3><ArrowUpRight size={19} strokeWidth={1.5} className="mt-1 shrink-0 text-[#a88d62] transition-transform group-hover:translate-x-1 group-hover:-translate-y-1" /></div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#82796f]">{item.event?.event_date && <span className="inline-flex items-center gap-1.5"><CalendarDays size={14} />{new Date(item.event.event_date).toLocaleDateString(undefined, { dateStyle: 'long' })}</span>}{typeof item.photoCount === 'number' && <span>{item.photoCount} {item.photoCount === 1 ? 'photograph' : 'photographs'}</span>}</div>
            <span className="mt-5 inline-block border-b border-[#c7ad82] pb-1 text-xs font-semibold uppercase tracking-[.14em] text-[#8d7044]">Open celebration</span>
          </div>
        </Link>)}</div> : <p className="mt-7 rounded-3xl border border-dashed border-[#d9cdb8] p-8 text-sm text-[#766f67]">Events will appear here when they’re ready to share.</p>}
      </section>
      <div className="mt-16 border-t border-[#e3d9c9] pt-8 sm:mt-24 sm:pt-12"><PhotoGallery key={album.slug} albumSlug={album.slug} onCountChange={setPhotoCount} /></div>
    </div>
  </main>
}

export function GuestMessage({ title, text }: { title: string; text: string }) { return <section className="mx-auto my-16 w-[calc(100%-2.5rem)] max-w-lg rounded-3xl border border-[#e7dcc8] bg-white/80 p-8 text-center"><p className="guest-kicker">Wedding Memories</p><h1 className="mt-3 font-serif text-3xl">{title}</h1><p className="mt-3 text-sm leading-6 text-[#766f67]">{text}</p><Link className="mt-6 inline-block rounded-full bg-[#9b7b49] px-5 py-3 text-sm font-semibold text-white" to="/">Return home</Link></section> }
