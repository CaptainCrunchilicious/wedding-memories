import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, Save } from 'lucide-react'
import type { CoverImageReference, Event, EventInput } from '../../services/albumService'

type EventFormProps = {
  initial?: Event
  submitting?: boolean
  serverError?: string
  onSubmit: (input: EventInput) => Promise<void>
  onCancel: () => void
}

function makeSlug(value: string) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120)
}

function toLocalDateTime(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

const inputClass = 'w-full rounded-xl border border-[#e5ddd1] bg-white px-4 py-3 text-sm text-[#332e29] outline-none transition placeholder:text-[#aaa198] focus:border-[#b89b69] focus:ring-4 focus:ring-[#b89b69]/10'
const labelClass = 'mb-2 block text-sm font-medium text-[#4d463e]'

export default function EventForm({ initial, submitting = false, serverError, onSubmit, onCancel }: EventFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [slug, setSlug] = useState(initial?.slug ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [eventDate, setEventDate] = useState(toLocalDateTime(initial?.event_date))
  const [location, setLocation] = useState(initial?.location ?? '')
  const [displayOrder, setDisplayOrder] = useState(initial?.display_order ?? 0)
  const [coverUrl, setCoverUrl] = useState(initial?.cover_image?.url ?? '')
  const [coverReference, setCoverReference] = useState(initial?.cover_image?.reference ?? '')
  const [coverAlt, setCoverAlt] = useState(initial?.cover_image?.alt_text ?? '')
  const [localError, setLocalError] = useState('')
  const slugPreview = useMemo(() => makeSlug(slug || name), [slug, name])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLocalError('')
    if (!name.trim()) {
      setLocalError('Event name is required.')
      return
    }
    if (!slugPreview) {
      setLocalError('Add a URL-friendly slug for this event name.')
      return
    }
    const coverImage: CoverImageReference | null = coverUrl.trim() || coverReference.trim()
      ? {
          ...(coverUrl.trim() ? { url: coverUrl.trim() } : {}),
          ...(coverReference.trim() ? { reference: coverReference.trim() } : {}),
          ...(coverAlt.trim() ? { alt_text: coverAlt.trim() } : {}),
        }
      : null
    await onSubmit({
      name: name.trim(),
      slug: slug.trim() ? slugPreview : null,
      description: description.trim() || null,
      event_date: eventDate ? new Date(eventDate).toISOString() : null,
      location: location.trim() || null,
      display_order: displayOrder,
      cover_image: coverImage,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-[#e9e1d4] bg-white/80 p-6 shadow-sm sm:p-8">
      <div className="mb-7 flex items-start justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.23em] text-[#9b7b49]">Event details</p>
          <h2 className="mt-2 font-serif text-2xl text-[#332e29]">{initial ? 'Edit event' : 'Create an event'}</h2>
        </div>
        <button type="button" onClick={onCancel} className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm text-[#766f67] hover:bg-[#faf8f3]"><ArrowLeft size={15} /> Cancel</button>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor="event-name">Event name <span className="text-[#a86a55]">*</span></label>
          <input id="event-name" required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} placeholder="Mehendi" />
        </div>
        <div>
          <label className={labelClass} htmlFor="event-date">Date and time</label>
          <input id="event-date" type="datetime-local" value={eventDate} onChange={(event) => setEventDate(event.target.value)} className={inputClass} />
        </div>
        <div>
          <label className={labelClass} htmlFor="event-location">Location</label>
          <input id="event-location" maxLength={200} value={location} onChange={(event) => setLocation(event.target.value)} className={inputClass} placeholder="Garden courtyard" />
        </div>
        <div>
          <label className={labelClass} htmlFor="event-order">Display order</label>
          <input id="event-order" type="number" min={0} max={100000} value={displayOrder} onChange={(event) => setDisplayOrder(Number(event.target.value))} className={inputClass} />
        </div>
        <div>
          <label className={labelClass} htmlFor="event-slug">URL slug <span className="font-normal text-[#aaa198]">(optional)</span></label>
          <input id="event-slug" maxLength={120} value={slug} onChange={(event) => setSlug(event.target.value)} className={inputClass} placeholder={makeSlug(name) || 'wedding-event'} />
          <p className="mt-2 text-xs text-[#958b7f]">Preview: <span className="font-medium text-[#766f67]">/a/album/e/{slugPreview || 'your-event'}</span></p>
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor="event-description">Description</label>
          <textarea id="event-description" maxLength={2000} rows={3} value={description} onChange={(event) => setDescription(event.target.value)} className={`${inputClass} resize-y`} placeholder="A little about this moment" />
        </div>
        <div>
          <label className={labelClass} htmlFor="event-cover-url">Cover image URL <span className="font-normal text-[#aaa198]">(reference only)</span></label>
          <input id="event-cover-url" type="url" maxLength={2048} value={coverUrl} onChange={(event) => setCoverUrl(event.target.value)} className={inputClass} placeholder="https://example.com/cover.jpg" />
        </div>
        <div>
          <label className={labelClass} htmlFor="event-cover-ref">Cover image reference</label>
          <input id="event-cover-ref" maxLength={500} value={coverReference} onChange={(event) => setCoverReference(event.target.value)} className={inputClass} placeholder="Optional external reference" />
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor="event-cover-alt">Cover image description</label>
          <input id="event-cover-alt" maxLength={200} value={coverAlt} onChange={(event) => setCoverAlt(event.target.value)} className={inputClass} placeholder="A brief accessible description" />
        </div>
      </div>
      {(localError || serverError) && <p role="alert" className="mt-5 rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{localError || serverError}</p>}
      <div className="mt-7 flex justify-end">
        <button type="submit" disabled={submitting} className="inline-flex items-center gap-2 rounded-xl bg-[#9b7b49] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#85683c] disabled:cursor-wait disabled:opacity-60">
          <Save size={16} /> {submitting ? 'Saving…' : initial ? 'Save changes' : 'Create event'}
        </button>
      </div>
    </form>
  )
}
