import { useEffect, useState } from 'react'
import { Button } from './ui'

export type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

function isStandalone(): boolean {
  return (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) || Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
}

export function InstallExperience() {
  const [promptEvent, setPromptEvent] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(isStandalone)
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem('academic-assistant-install-dismissed') === 'true')

  useEffect(() => {
    const beforeInstall = (event: Event) => { event.preventDefault(); setPromptEvent(event as BeforeInstallPromptEvent) }
    const appInstalled = () => { setInstalled(true); setPromptEvent(null); sessionStorage.removeItem('academic-assistant-install-dismissed') }
    window.addEventListener('beforeinstallprompt', beforeInstall)
    window.addEventListener('appinstalled', appInstalled)
    return () => { window.removeEventListener('beforeinstallprompt', beforeInstall); window.removeEventListener('appinstalled', appInstalled) }
  }, [])

  async function install() {
    if (!promptEvent) return
    await promptEvent.prompt()
    const choice = await promptEvent.userChoice
    setPromptEvent(null)
    if (choice.outcome === 'dismissed') { sessionStorage.setItem('academic-assistant-install-dismissed', 'true'); setDismissed(true) }
  }
  function dismiss() { sessionStorage.setItem('academic-assistant-install-dismissed', 'true'); setDismissed(true) }

  if (installed || dismissed || !promptEvent) return null
  return <aside className="install-experience" aria-labelledby="install-title"><img src="/icon.svg" alt="" width="48" height="48" /><div><strong id="install-title">Install Academic Assistant</strong><p>Open faster and use your last synchronized snapshot when this device is offline.</p></div><div><Button size="sm" onClick={() => void install()}>Install app</Button><Button size="sm" variant="ghost" onClick={dismiss}>Not now</Button></div></aside>
}

