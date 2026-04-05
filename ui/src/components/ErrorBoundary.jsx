import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('Uncaught error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-slate-950 text-slate-100">
          <div className="text-2xl font-semibold text-red-400">Something went wrong</div>
          <div className="max-w-md text-center text-sm text-slate-400">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button
            className="rounded bg-violet-600 px-4 py-2 text-sm hover:bg-violet-700"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
