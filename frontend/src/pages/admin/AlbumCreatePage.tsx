import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AlbumForm from '../../components/admin/AlbumForm'
import { albumService, apiErrorMessage, type AlbumInput } from '../../services/albumService'

export default function AlbumCreatePage() {
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function submit(input: AlbumInput) {
    setSubmitting(true)
    setError('')
    try {
      const album = await albumService.createAlbum(input)
      navigate(`/admin/albums/${album.id}`, { replace: true, state: { notice: 'Album created successfully.' } })
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'Album could not be created. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
      <p className="mb-6 text-sm text-[#8b8176]"><Link to="/admin/albums" className="hover:text-[#6e5939]">Albums</Link> / New album</p>
      <AlbumForm onSubmit={submit} onCancel={() => navigate('/admin/albums')} submitting={submitting} serverError={error} />
    </main>
  )
}
