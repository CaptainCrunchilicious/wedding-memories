import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, Save } from 'lucide-react'
import type { Album, AlbumInput, CoverImageReference } from '../../services/albumService'

type AlbumFormProps = {
  initial?: Album
  submitting?: boolean
  serverError?: string
  onSubmit: (input: AlbumInput) => Promise<void>
  onCancel: () => void
}

function makeSlug(value: string) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120)
}

const inputClass = 'w-full rounded-xl border border-[#e5ddd1] bg-white px-4 py-3 text-sm text-[#332e29] outline-none transition placeholder:text-[#aaa198] focus:border-[#b89b69] focus:ring-4 focus:ring-[#b89b69]/10'
const labelClass = 'mb-2 block text-sm font-medium text-[#4d463e]'

export default function AlbumForm({ initial, submitting = false, serverError, onSubmit, onCancel }: AlbumFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [slug, setSlug] = useState(initial?.slug ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [coupleNames, setCoupleNames] = useState(initial?.couple_names ?? '')
  const [eventDate, setEventDate] = useState(initial?.event_date ?? '')
  const [location, setLocation] = useState(initial?.location ?? '')
  const [coverUrl, setCoverUrl] = useState(initial?.cover_image?.url ?? '')
  const [coverReference, setCoverReference] = useState(initial?.cover_image?.reference ?? '')
  const [coverAlt, setCoverAlt] = useState(initial?.cover_image?.alt_text ?? '')
  const [localError, setLocalError] = useState('')
  const slugPreview = useMemo(() => makeSlug(slug || name), [slug, name])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLocalError('')
    if (!name.trim()) {
      setLocalError('Album name is required.')
      return
    }
    if ((slug.trim() || name.trim()) && !slugPreview) {
      setLocalError('Add a URL-friendly slug for this album name.')
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
      couple_names: coupleNames.trim() || null,
      event_date: eventDate || null,
      location: location.trim() || null,
      cover_image: coverImage,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-[#e9e1d4] bg-white/80 p-6 shadow-sm sm:p-8">
      <div className="mb-7 flex items-start justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.23em] text-[#9b7b49]">Album details</p>
          <h2 className="mt-2 font-serif text-2xl text-[#332e29]">{initial ? 'Edit album' : 'Create an album'}</h2>
        </div>
        <button type="button" onClick={onCancel} className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm text-[#766f67] hover:bg-[#faf8f3]">
          <ArrowLeft size={15} /> Cancel
        </button>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor="album-name">Album name <span className="text-[#a86a55]">*</span></label>
          <input id="album-name" required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} placeholder="Sharma Wedding 2026" />
        </div>
        <div>
          <label className={labelClass} htmlFor="album-couple">Couple names</label>
          <input id="album-couple" maxLength={200} value={coupleNames} onChange={(event) => setCoupleNames(event.target.value)} className={inputClass} placeholder="Anika & Rohan" />
        </div>
        <div>
          <label className={labelClass} htmlFor="album-date">Event date</label>
          <input id="album-date" type="date" value={eventDate} onChange={(event) => setEventDate(event.target.value)} className={inputClass} />
        </div>
        <div>
          <label className={labelClass} htmlFor="album-location">Location</label>
          <input id="album-location" maxLength={200} value={location} onChange={(event) => setLocation(event.target.value)} className={inputClass} placeholder="Jaipur, Rajasthan" />
        </div>
        <div>
          <label className={labelClass} htmlFor="album-slug">URL slug <span className="font-normal text-[#aaa198]">(optional)</span></label>
          <input id="album-slug" maxLength={120} value={slug} onChange={(event) => setSlug(event.target.value)} className={inputClass} placeholder={makeSlug(name) || 'wedding-album'} />
          <p className="mt-2 text-xs text-[#958b7f]">Preview: <span className="font-medium text-[#766f67]">/a/{slugPreview || 'your-album'}</span></p>
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor="album-description">Description</label>
          <textarea id="album-description" maxLength={2000} rows={3} value={description} onChange={(event) => setDescription(event.target.value)} className={`${inputClass} resize-y`} placeholder="A little about the celebration" />
        </div>
        <div>
          <label className={labelClass} htmlFor="album-cover-url">Cover image URL <span className="font-normal text-[#aaa198]">(reference only)</span></label>
          <input id="album-cover-url" type="url" maxLength={2048} value={coverUrl} onChange={(event) => setCoverUrl(event.target.value)} className={inputClass} placeholder="https://example.com/cover.jpg" />
        </div>
        <div>
          <label className={labelClass} htmlFor="album-cover-ref">Cover image reference</label>
          <input id="album-cover-ref" maxLength={500} value={coverReference} onChange={(event) => setCoverReference(event.target.value)} className={inputClass} placeholder="Optional external reference" />
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor="album-cover-alt">Cover image description</label>
          <input id="album-cover-alt" maxLength={200} value={coverAlt} onChange={(event) => setCoverAlt(event.target.value)} className={inputClass} placeholder="A brief accessible description" />
        </div>
      </div>

      {(localError || serverError) && <p role="alert" className="mt-5 rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{localError || serverError}</p>}
      <div className="mt-7 flex justify-end">
        <button type="submit" disabled={submitting} className="inline-flex items-center gap-2 rounded-xl bg-[#9b7b49] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#85683c] disabled:cursor-wait disabled:opacity-60">
          <Save size={16} /> {submitting ? 'Saving…' : initial ? 'Save changes' : 'Create album'}
        </button>
      </div>
    </form>
  )
}
