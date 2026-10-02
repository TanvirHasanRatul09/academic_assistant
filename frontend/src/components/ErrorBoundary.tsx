import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { hasError: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch() {
    // Production reporting will be connected without sending private content.
  }

  render() {
    if (this.state.hasError) {
      return (
        <section className="centered-message" role="alert">
          <h1>Something went wrong</h1>
          <p>Reload the page. Your academic data has not been changed.</p>
          <button type="button" onClick={() => window.location.reload()}>Reload</button>
        </section>
      )
    }
    return this.props.children
  }
}

