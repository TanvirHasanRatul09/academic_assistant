type AmbientBackgroundProps = {
  variant?: 'hero' | 'onboarding' | 'assistant'
}

export function AmbientBackground({ variant = 'hero' }: AmbientBackgroundProps) {
  return <div className={`ambient-background ambient-background-${variant}`} aria-hidden="true">
    <span className="ambient-mesh" />
    <span className="ambient-orb ambient-orb-primary" />
    <span className="ambient-orb ambient-orb-secondary" />
    <span className="ambient-orbit" />
    <span className="ambient-grid" />
  </div>
}
