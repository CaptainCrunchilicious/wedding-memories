import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AlbumForm from '../../components/admin/AlbumForm'
import { albumService, apiErrorMessage, type Album, type AlbumInput } from '../../services/albumService'

export default function AlbumEditPage() {
  const { albumId = '' } = useParams()
  const navigate = useNavigate()
  const [album, setAlbum] = useState<Album | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const loadAlbum = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setAlbum(await albumService.getAlbum(albumId))
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [albumId])

  useEffect(() => { void loadAlbum() }, [loadAlbum])

  async function submit(input: AlbumInput) {
    setSubmitting(true)
    setError('')
    try {
      await albumService.updateAlbum(albumId, input)
      navigate(`/admin/albums/${albumId}`, { replace: true, state: { notice: 'Album updated successfully.' } })
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album could not be updated. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
      <p className="mb-6 text-sm text-[#8b8176]"><Link to="/admin/albums" className="hover:text-[#6e5939]">Albums</Link>{album && <> / <Link to={`/admin/albums/${albumId}`} className="hover:text-[#6e5939]">{album.name}</Link></>} / Edit</p>
      {loading ? <p role="status" className="py-12 text-center text-sm text-[#766f67]">Loading album…</p> : album ? (
        <AlbumForm initial={album} onSubmit={submit} onCancel={() => navigate(`/admin/albums/${albumId}`)} submitting={submitting} serverError={error} />
      ) : <p role="alert" className="rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{error || 'Album not found.'}</p>}
    </main>
  )
}
