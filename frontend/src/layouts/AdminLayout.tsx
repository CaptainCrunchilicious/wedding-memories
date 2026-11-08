import { LogOut } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function AdminLayout() {
  const { admin, logout } = useAuth()

  async function handleLogout() {
    await logout()
  }

  return (
    <div className="min-h-screen bg-[#faf8f3] text-[#332e29]">
      <header className="border-b border-[#e9e1d4] bg-white/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link to="/admin" className="flex items-center gap-3" aria-label="Wedding Memories Admin home">
            <span className="flex h-10 w-10 items-center justify-center rounded-full border border-[#d5bd91] font-serif text-xl text-[#9b7b49]">W</span>
            <span>
              <span className="block font-serif text-lg leading-5">Wedding Memories</span>
              <span className="mt-1 block text-[0.62rem] font-semibold uppercase tracking-[0.2em] text-[#9b7b49]">Admin</span>
            </span>
          </Link>
          <div className="flex items-center gap-3 sm:gap-5">
            <span className="hidden max-w-56 truncate text-sm text-[#766f67] sm:block">{admin?.email}</span>
            <button onClick={() => void handleLogout()} className="inline-flex items-center gap-2 rounded-full border border-[#e5ddd1] px-4 py-2 text-sm text-[#62594f] transition hover:border-[#cbb893] hover:bg-[#faf8f3]">
              <LogOut size={15} /> <span>Log out</span>
            </button>
          </div>
        </div>
        <nav className="mx-auto max-w-6xl px-5 pb-3 sm:px-8" aria-label="Admin navigation">
          <NavLink to="/admin/albums" className={({ isActive }) => `rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-[#f5f1e9] font-medium text-[#6e5939]' : 'text-[#766f67] hover:bg-[#faf8f3]'}`}>Albums</NavLink>
          <NavLink to="/admin/photos" className={({ isActive }) => `ml-1 rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-[#f5f1e9] font-medium text-[#6e5939]' : 'text-[#766f67] hover:bg-[#faf8f3]'}`}>Photo moderation</NavLink>
          <NavLink to="/admin/settings" className={({ isActive }) => `ml-1 rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-[#f5f1e9] font-medium text-[#6e5939]' : 'text-[#766f67] hover:bg-[#faf8f3]'}`}>Storage settings</NavLink>
        </nav>
      </header>
      <Outlet />
    </div>
  )
}
