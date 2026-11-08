import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Cloud, HardDrive, RefreshCw } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { apiErrorMessage } from '../../services/albumService'
import { storageService, type StorageStatus, type StorageProvider } from '../../services/storageService'

function dateLabel(value: string | null) {
  if (!value) return 'Not checked yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Not checked yet' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export default function AdminStoragePage() {
  const [status, setStatus] = useState<StorageStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()

  const loadStatus = useCallback(async () => {
    setLoading(true)
    setError('')
    try { setStatus(await storageService.status()) }
    catch (requestError) { setError(apiErrorMessage(requestError, 'Storage status could not be loaded.')) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void loadStatus() }, [loadStatus])
  useEffect(() => {
    const result = searchParams.get('drive')
    if (!result) return
    const messages: Record<string, string> = {
      connected: 'Google Drive connected and ready.',
      cancelled: 'Google Drive connection was cancelled.',
      invalid_state: 'The Google authorization expired or was already used. Please connect again.',
      admin_changed: 'The administrator session changed. Please sign in and connect again.',
      exchange_failed: 'Google could not complete authorization. Please try again.',
      credential_error: 'Google credentials could not be stored. Check the backend token-encryption key.',
      connected_check_failed: 'Authorization was saved, but Google Drive could not be verified. Check the folder and connection status.',
      connection_failed: 'Google Drive could not be connected. Check backend logs for a safe diagnostic message.',
    }
    setNotice(messages[result] || 'Google Drive returned an unrecognized connection result.')
    setSearchParams({}, { replace: true })
    void loadStatus()
  }, [loadStatus, searchParams, setSearchParams])

  async function connect() {
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await storageService.connect()
      window.location.assign(response.authorization_url)
    } catch (requestError) { setError(apiErrorMessage(requestError, 'Google Drive authorization could not be started.')) }
    finally { setBusy(false) }
  }

  async function disconnect() {
    if (!window.confirm('Disconnect Google Drive? Existing Drive photos will no longer be available until the account is reconnected. New uploads will use local storage.')) return
    setBusy(true); setError(''); setNotice('')
    try {
      await storageService.disconnect()
      setNotice('Google Drive disconnected. New uploads will use local storage.')
      await loadStatus()
    } catch (requestError) { setError(apiErrorMessage(requestError, 'Google Drive could not be disconnected.')) }
    finally { setBusy(false) }
  }

  async function chooseProvider(provider: StorageProvider) {
    if (provider === status?.provider) return
    const label = provider === 'google_drive' ? 'Google Drive' : 'local storage'
    if (!window.confirm(`Use ${label} for new uploads? Existing photos will continue to use their current storage provider.`)) return
    setBusy(true); setError(''); setNotice('')
    try {
      await storageService.selectProvider(provider)
      setNotice(`New uploads will use ${label}.`)
      await loadStatus()
    } catch (requestError) { setError(apiErrorMessage(requestError, `Could not select ${label}.`)) }
    finally { setBusy(false) }
  }

  const drive = status?.google_drive
  return <main className="mx-auto max-w-5xl px-5 py-9 sm:px-8 sm:py-12">
    <p className="text-xs font-semibold uppercase tracking-[.23em] text-[#9b7b49]">Application preferences</p>
    <div className="mt-2 flex flex-wrap items-end justify-between gap-4"><div><h1 className="font-serif text-4xl">Storage &amp; Google Drive</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[#766f67]">Choose where new guest uploads are stored. Previously uploaded photographs stay with their original provider.</p></div>
      <button disabled={loading || busy} onClick={() => void loadStatus()} className="inline-flex items-center gap-2 rounded-full border border-[#ded4c4] bg-white px-4 py-2.5 text-sm text-[#655337] disabled:opacity-50"><RefreshCw size={15}/> Refresh status</button></div>
    {notice && <p role="status" className="mt-5 rounded-xl bg-[#f3f6ef] px-4 py-3 text-sm text-[#55704a]">{notice}</p>}
    {error && <p role="alert" className="mt-5 rounded-xl bg-[#fff4ef] px-4 py-3 text-sm text-[#914e3a]">{error}</p>}
    {loading ? <p role="status" className="py-16 text-center text-sm text-[#766f67]">Checking storage status…</p> : status && <>
      <section className="mt-7 rounded-3xl border border-[#e9e1d4] bg-white/80 p-5 sm:p-7">
        <div className="flex items-center gap-3"><span className="rounded-2xl bg-[#f5f1e9] p-3 text-[#9b7b49]"><HardDrive size={21}/></span><div><p className="text-xs uppercase tracking-[.2em] text-[#9b7b49]">Current provider</p><h2 className="mt-1 font-serif text-2xl">{status.provider === 'local' ? 'Local filesystem' : 'Google Drive'}</h2></div></div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <button aria-label="Use local storage for new uploads" disabled={busy || status.provider === 'local'} onClick={() => void chooseProvider('local')} aria-pressed={status.provider === 'local'} className={`rounded-2xl border p-4 text-left disabled:opacity-60 ${status.provider === 'local' ? 'border-[#b7c7ae] bg-[#f3f6ef]' : 'border-[#e9e1d4] bg-white'}`}><span className="font-semibold">Local storage</span><span className="mt-1 block text-sm text-[#766f67]">Keep new photos on this backend’s configured filesystem.</span></button>
          <button aria-label="Use Google Drive for new uploads" disabled={busy || !drive?.operational || status.provider === 'google_drive'} onClick={() => void chooseProvider('google_drive')} aria-pressed={status.provider === 'google_drive'} className={`rounded-2xl border p-4 text-left disabled:opacity-60 ${status.provider === 'google_drive' ? 'border-[#b7c7ae] bg-[#f3f6ef]' : 'border-[#e9e1d4] bg-white'}`}><span className="font-semibold">Google Drive</span><span className="mt-1 block text-sm text-[#766f67]">Store new photos privately in the connected account’s app folder.</span></button>
        </div>
      </section>
      <section className="mt-5 rounded-3xl border border-[#e9e1d4] bg-white/80 p-5 sm:p-7" aria-label="Google Drive connection">
        <div className="flex flex-wrap items-start justify-between gap-4"><div className="flex items-center gap-3"><span className="rounded-2xl bg-[#f5f1e9] p-3 text-[#9b7b49]"><Cloud size={21}/></span><div><p className="text-xs uppercase tracking-[.2em] text-[#9b7b49]">Google Drive connection</p><h2 className="mt-1 font-serif text-2xl">{drive?.operational ? 'Connected and ready' : drive?.connected ? 'Connected, needs attention' : 'Not connected'}</h2></div></div>
          {drive?.operational && <CheckCircle2 className="text-[#55704a]" aria-label="Google Drive operational"/>}</div>
        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2"><div><dt className="text-[#968b7d]">Account</dt><dd className="mt-1 text-[#3b352e]">{drive?.connected_email || 'Not available'}</dd></div><div><dt className="text-[#968b7d]">Application folder</dt><dd className="mt-1 capitalize text-[#3b352e]">{drive?.folder_status.replaceAll('_', ' ') || 'Unknown'}</dd></div><div><dt className="text-[#968b7d]">Last successful check</dt><dd className="mt-1 text-[#3b352e]">{dateLabel(drive?.last_successful_check || null)}</dd></div><div><dt className="text-[#968b7d]">OAuth setup</dt><dd className="mt-1 text-[#3b352e]">{drive?.configured ? 'Configured' : 'Backend environment setup required'}</dd></div></dl>
        {!drive?.configured && <p className="mt-5 rounded-xl bg-[#faf5e9] p-4 text-sm leading-6 text-[#766f67]">Add the Google Drive OAuth client values and Fernet encryption key to the backend environment, then restart the backend before connecting.</p>}
        <div className="mt-6 flex flex-wrap gap-3"><button disabled={busy || !drive?.configured} onClick={() => void connect()} className="inline-flex items-center gap-2 rounded-full bg-[#9b7b49] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"><Cloud size={16}/>{busy ? 'Working…' : drive?.connected ? 'Reconnect Google Drive' : 'Connect Google Drive'}</button>
          {drive?.connected && <button disabled={busy} onClick={() => void disconnect()} className="rounded-full border border-[#dfc5b9] px-5 py-3 text-sm font-semibold text-[#965540] disabled:opacity-50">Disconnect</button>}</div>
      </section>
    </>}
  </main>
}
