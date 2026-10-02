import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="centered-message">
      <h1>Page not found</h1>
      <p>The requested page does not exist.</p>
      <Link to="/">Return home</Link>
    </section>
  )
}

