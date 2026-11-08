import { useEffect, useRef, useState } from 'react'
import { Camera, ImagePlus, RotateCcw, Trash2, Upload, X } from 'lucide-react'
import { publicService, type PhotoResult } from '../../services/publicService'

type QueuedPhoto = { id: string; file: File; url: string; source: 'camera' | 'gallery'; result?: PhotoResult }
const MAX_FILES = 10
const MAX_FILE_BYTES = 12 * 1024 * 1024
const MAX_TOTAL_BYTES = 50 * 1024 * 1024
const allowed = ['image/jpeg', 'image/png', 'image/webp']

function prettyBytes(size: number) { return `${(size / 1024 / 1024).toFixed(1)} MB` }

export function PhotoUploader({ albumSlug, eventSlug }: { albumSlug: string; eventSlug: string }) {
  const [photos, setPhotos] = useState<QueuedPhoto[]>([])
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [photoProgress, setPhotoProgress] = useState<Record<string, number>>({})
  const [error, setError] = useState('')
  const [facing, setFacing] = useState<'environment' | 'user'>('environment')
  const [cameraSupported, setCameraSupported] = useState(true)
  const [uploadSummary, setUploadSummary] = useState<{ succeeded: number; failed: number } | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const galleryRef = useRef<HTMLInputElement>(null)
  const fallbackRef = useRef<HTMLInputElement>(null)
  const objectUrls = useRef(new Set<string>())
  const uploading = useRef(false)

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }

  useEffect(() => {
    if (!cameraOpen) { stopCamera(); return }
    let cancelled = false
    async function start() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported')
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: facing } }, audio: false })
        if (cancelled) { stream.getTracks().forEach((track) => track.stop()); return }
        streamRef.current = stream
        if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play() }
        setCameraError('')
      } catch {
        setCameraSupported(false)
        setCameraError('Camera access is unavailable. Allow camera permission on this secure connection, or use the camera picker or gallery below.')
      }
    }
    void start()
    return () => { cancelled = true; stopCamera() }
  }, [cameraOpen, facing])

  useEffect(() => () => objectUrls.current.forEach((url) => URL.revokeObjectURL(url)), [])

  function addFiles(files: File[], source: QueuedPhoto['source']) {
    if (uploading.current) return
    setError('')
    setUploadSummary(null)
    setPhotos((current) => {
      const next = [...current]
      for (const file of files) {
        if (!allowed.includes(file.type)) { setError(`${file.name}: choose a JPEG, PNG, or WebP image.`); continue }
        if (file.size <= 0 || file.size > MAX_FILE_BYTES) { setError(`${file.name}: each photo must be 12 MB or smaller.`); continue }
        if (next.length >= MAX_FILES) { setError(`You can select up to ${MAX_FILES} photos per upload.`); break }
        if (next.reduce((sum, photo) => sum + photo.file.size, 0) + file.size > MAX_TOTAL_BYTES) { setError('Selected photos must total 50 MB or less.'); break }
        const duplicate = next.some((photo) => photo.file.name === file.name && photo.file.size === file.size && photo.file.lastModified === file.lastModified)
        if (!duplicate) {
          const url = URL.createObjectURL(file)
          objectUrls.current.add(url)
          next.push({ id: crypto.randomUUID(), file, url, source })
        }
      }
      return next
    })
  }

  function removePhoto(id: string) {
    if (uploading.current) return
    setPhotos((current) => {
      const item = current.find((photo) => photo.id === id)
      if (item) { URL.revokeObjectURL(item.url); objectUrls.current.delete(item.url) }
      return current.filter((photo) => photo.id !== id)
    })
  }

  function capture() {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth; canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    context?.drawImage(video, 0, 0)
    canvas.toBlob((blob) => {
      if (blob) addFiles([new File([blob], `capture-${new Date().toISOString().replace(/[:.]/g, '-')}.jpg`, { type: 'image/jpeg' })], 'camera')
    }, 'image/jpeg', 0.92)
  }

  async function upload(selection = photos.filter((photo) => !photo.result?.success)) {
    if (!selection.length || uploading.current) return
    uploading.current = true
    setBusy(true); setError(''); setProgress(0)
    setUploadSummary(null)
    try {
      const response = await publicService.upload(albumSlug, eventSlug, selection.map(({ id, file }) => ({ id, file })), (loaded, total) => {
        setProgress(Math.min(100, Math.round((loaded / total) * 100)))
        let preceding = 0
        const next: Record<string, number> = {}
        selection.forEach((photo) => {
          next[photo.id] = Math.min(100, Math.max(0, Math.round(((loaded - preceding) / photo.file.size) * 100)))
          preceding += photo.file.size
        })
        setPhotoProgress(next)
      })
      const results = selection.map((photo, index) => response.results[index] ?? {
        success: false,
        filename: photo.file.name,
        error: 'No result was returned for this photo. Please retry it.',
      })
      const succeededIds = new Set(selection.filter((_, index) => results[index].success).map((photo) => photo.id))
      const failedById = new Map(selection.flatMap((photo, index) =>
        results[index].success ? [] : [[photo.id, results[index]] as const],
      ))

      for (const photo of selection) {
        if (succeededIds.has(photo.id)) {
          URL.revokeObjectURL(photo.url)
          objectUrls.current.delete(photo.url)
        }
      }
      setPhotos((current) => current.flatMap((photo) => {
        if (succeededIds.has(photo.id)) return []
        const result = failedById.get(photo.id)
        return result ? [{ ...photo, result }] : [photo]
      }))
      const succeeded = succeededIds.size
      const failedCount = results.length - succeeded
      setUploadSummary({ succeeded, failed: failedCount })
      if (succeeded > 0) {
        if (galleryRef.current) galleryRef.current.value = ''
        if (fallbackRef.current) fallbackRef.current.value = ''
      }
      setPhotoProgress({})
    } catch {
      setError('The upload was interrupted. Check your connection and retry the photos that did not finish.')
    } finally { uploading.current = false; setBusy(false) }
  }

  const totalBytes = photos.reduce((sum, photo) => sum + photo.file.size, 0)
  const failed = photos.filter((photo) => photo.result && !photo.result.success)
  const successes = photos.filter((photo) => photo.result?.success).length

  return <section className="mt-6 min-w-0 rounded-3xl border border-[#eadfcd] bg-white/85 p-4 shadow-sm sm:mt-8 sm:rounded-[2rem] sm:p-7" aria-label="Share your photos">
    <div className="min-w-0"><p className="text-[.65rem] font-semibold uppercase tracking-[.2em] text-[#9b7b49] sm:text-xs">Add to the memories</p><h2 className="mt-1.5 font-serif text-2xl sm:mt-2 sm:text-3xl">Share your photos</h2><p className="mt-1.5 max-w-prose text-[.8125rem] leading-5 text-[#766f67] sm:mt-2 sm:text-sm sm:leading-6">Choose a few favorite moments, review them, then upload when you’re ready.</p></div>
    <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 sm:mt-5 sm:flex sm:flex-wrap sm:gap-3">
      <button disabled={busy} onClick={() => { setCameraOpen(true); setCameraSupported(true); setCameraError('') }} className="inline-flex min-h-12 min-w-0 items-center justify-center gap-2 rounded-full bg-[#9b7b49] px-2.5 py-3 text-[.8125rem] font-semibold text-white disabled:opacity-50 sm:px-5 sm:text-sm"><Camera size={17} className="shrink-0" /> <span>Take photos</span></button>
      <button disabled={busy} onClick={() => { stopCamera(); setCameraOpen(false); galleryRef.current?.click() }} className="inline-flex min-h-12 min-w-0 items-center justify-center gap-2 rounded-full border border-[#d9cdb8] px-2.5 py-3 text-[.8125rem] font-semibold text-[#655337] disabled:opacity-50 sm:px-5 sm:text-sm"><ImagePlus size={17} className="shrink-0" /> <span>Choose from gallery</span></button>
      <input ref={galleryRef} type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={busy} className="sr-only" onChange={(event) => { addFiles(Array.from(event.target.files || []), 'gallery'); event.target.value = '' }} />
      <input ref={fallbackRef} type="file" accept="image/*" capture="environment" multiple disabled={busy} className="sr-only" onChange={(event) => { addFiles(Array.from(event.target.files || []), 'camera'); event.target.value = '' }} />
    </div>
    {cameraOpen && <div className="mt-5 rounded-3xl bg-[#2c2925] p-3 text-white">
      <div className="flex items-center justify-between px-2 py-1"><span className="text-sm">Camera capture</span><button onClick={() => { setCameraOpen(false); stopCamera() }} aria-label="Close camera" className="rounded-full p-2 hover:bg-white/10"><X size={18} /></button></div>
      <video ref={videoRef} autoPlay playsInline muted className="mt-2 max-h-[55vh] w-full rounded-2xl bg-black object-contain" aria-label="Camera preview" />
      {cameraError && <p role="alert" className="px-2 py-3 text-sm text-[#f4d9a6]">{cameraError}</p>}
      <div className="flex justify-center gap-3 py-3">
        {cameraSupported && !cameraError && <><button disabled={busy} onClick={capture} className="rounded-full bg-white px-6 py-3 font-semibold text-[#332e29] disabled:opacity-50">Capture photo</button><button disabled={busy} onClick={() => setFacing((value) => value === 'environment' ? 'user' : 'environment')} aria-label="Switch camera" className="rounded-full border border-white/40 p-3 disabled:opacity-50"><RotateCcw size={18} /></button></>}
        <button disabled={busy} onClick={() => { stopCamera(); setCameraOpen(false); fallbackRef.current?.click() }} className="rounded-full border border-white/40 px-4 py-3 text-sm disabled:opacity-50">Use camera picker</button>
      </div>
    </div>}
    {error && <p role="alert" className="mt-4 rounded-xl bg-[#fff4ef] p-3 text-sm text-[#914e3a]">{error}</p>}
    {uploadSummary && <div role="status" className="mt-5 rounded-2xl border border-[#d8e1d2] bg-[#f3f6ef] px-5 py-4 text-sm leading-6 text-[#55704a]">
      <p className="font-semibold">{uploadSummary.failed === 0 ? 'Your photos have been submitted successfully!' : uploadSummary.succeeded > 0 ? `${uploadSummary.succeeded} photo${uploadSummary.succeeded === 1 ? '' : 's'} uploaded successfully, ${uploadSummary.failed} failed.` : `No photos uploaded successfully; ${uploadSummary.failed} failed.`}</p>
      <p>{uploadSummary.failed === 0 ? 'Your photos are now awaiting approval. Once approved, they will appear in the wedding gallery.' : uploadSummary.succeeded > 0 ? 'Successful photos are now awaiting approval. Once approved, they will appear in the wedding gallery.' : 'Failed photos remain selected so you can retry them.'}</p>
    </div>}
    {photos.length > 0 && <>
      <div className="mt-6 flex min-w-0 flex-wrap items-end justify-between gap-3 sm:mt-7"><div className="min-w-0"><h3 className="font-serif text-xl">Your selection <span className="font-sans text-sm text-[#8c8172]">({photos.length})</span></h3><p className="mt-1 text-xs text-[#8c8172]">Total {prettyBytes(totalBytes)} · up to 10 photos, 50 MB</p></div>
      </div>
      <div className="mt-4 grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{photos.map((photo) => <article key={photo.id} className="min-w-0 overflow-hidden rounded-2xl border border-[#eee5d8] bg-[#faf8f3]">
        <div className="relative aspect-square"><img src={photo.url} alt={`Selected ${photo.file.name}`} className="h-full w-full object-cover" /><button disabled={busy} onClick={() => removePhoto(photo.id)} aria-label={`Remove ${photo.file.name}`} className="absolute right-2 top-2 rounded-full bg-white/90 p-2 text-[#776b5e] disabled:opacity-40"><Trash2 size={15} /></button></div>
        <div className="p-3"><p className="truncate text-xs font-medium">{photo.file.name}</p><p className="mt-1 text-[.7rem] text-[#887e72]">{prettyBytes(photo.file.size)} · {photo.source}</p>
          {busy && <progress aria-label={`Upload progress for ${photo.file.name}`} className="mt-2 h-1.5 w-full accent-[#9b7b49]" value={photoProgress[photo.id] || 0} max={100} />}
          {photo.result && <p className={`mt-2 text-xs ${photo.result.success ? 'text-[#55704a]' : 'text-[#a34f3f]'}`}>{photo.result.success ? 'Uploaded · pending review' : photo.result.error}</p>}</div>
      </article>)}</div>
      {busy && <div className="mt-5"><div className="flex justify-between text-sm"><span>Uploading photos…</span><span>{progress}%</span></div><progress className="mt-2 h-2 w-full accent-[#9b7b49]" value={progress} max={100} /></div>}
      <div className="mt-5 flex flex-wrap gap-3">{failed.length > 0 ? <button disabled={busy} onClick={() => void upload(failed)} className="inline-flex items-center gap-2 rounded-full border border-[#d9cdb8] px-5 py-3 text-sm font-semibold disabled:opacity-50"><RotateCcw size={16} /> Retry failed ({failed.length})</button> : <button disabled={busy || successes === photos.length} onClick={() => void upload()} className="inline-flex items-center gap-2 rounded-full bg-[#3d5140] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"><Upload size={16} /> {busy ? 'Uploading…' : 'Upload photos'}</button>}</div>
    </>}
  </section>
}
