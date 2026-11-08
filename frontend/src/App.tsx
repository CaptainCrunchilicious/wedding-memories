import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedAdminRoute } from './components/common/ProtectedAdminRoute'
import AdminLayout from './layouts/AdminLayout'
import AdminLogin from './pages/admin/AdminLogin'
import AdminAlbumsPage from './pages/admin/AdminAlbumsPage'
import AlbumCreatePage from './pages/admin/AlbumCreatePage'
import AlbumDetailsPage from './pages/admin/AlbumDetailsPage'
import AlbumEditPage from './pages/admin/AlbumEditPage'
import AdminPhotosPage from './pages/admin/AdminPhotosPage'
import AdminStoragePage from './pages/admin/AdminStoragePage'
import GuestAlbumPage from './pages/guest/GuestAlbumPage'
import GuestEventPage from './pages/guest/GuestEventPage'

function HomePage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-16">
      <div aria-hidden="true" className="absolute -left-32 -top-36 h-96 w-96 rounded-full bg-[#eadfc8]/35 blur-3xl" />
      <div aria-hidden="true" className="absolute -bottom-44 -right-28 h-[30rem] w-[30rem] rounded-full bg-[#e7d7c4]/30 blur-3xl" />
      <section className="relative w-full max-w-2xl text-center">
        <div className="mx-auto mb-8 flex h-14 w-14 items-center justify-center rounded-full border border-[#d5bd91] text-[#9b7b49]">
          <span className="font-serif text-2xl">W</span>
        </div>
        <p className="mb-5 text-xs font-medium uppercase tracking-[0.32em] text-[#9b7b49]">A place for your forever</p>
        <h1 className="font-serif text-5xl font-normal tracking-tight text-[#332e29] sm:text-7xl">Wedding Memories</h1>
        <p className="mx-auto mt-7 max-w-lg text-lg leading-8 text-[#766f67] sm:text-xl">
          A shared space for capturing and reliving beautiful moments.
        </p>
        <div className="mx-auto mt-10 inline-flex items-center gap-3 rounded-full border border-[#e5dccb] bg-white/60 px-5 py-2.5 text-sm text-[#766f67] shadow-sm shadow-[#756449]/5">
          <span className="h-2 w-2 rounded-full bg-[#b89b69]" />
          Coming Soon
        </div>
        <div className="mx-auto mt-16 h-px w-16 bg-[#d5bd91]" />
        <p className="mt-5 text-xs uppercase tracking-[0.22em] text-[#aaa198]">Made for moments that matter</p>
      </section>
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/a/:albumSlug" element={<GuestAlbumPage />} />
      <Route path="/a/:albumSlug/e/:eventSlug" element={<GuestEventPage />} />
      <Route element={<ProtectedAdminRoute />}>
        <Route element={<AdminLayout />}>
          <Route path="/admin" element={<Navigate to="/admin/albums" replace />} />
          <Route path="/admin/albums" element={<AdminAlbumsPage />} />
          <Route path="/admin/photos" element={<AdminPhotosPage />} />
          <Route path="/admin/settings" element={<AdminStoragePage />} />
          <Route path="/admin/albums/new" element={<AlbumCreatePage />} />
          <Route path="/admin/albums/:albumId" element={<AlbumDetailsPage />} />
          <Route path="/admin/albums/:albumId/edit" element={<AlbumEditPage />} />
        </Route>
      </Route>
      <Route path="*" element={<HomePage />} />
    </Routes>
  )
}
