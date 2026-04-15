import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="h-screen flex items-center justify-center bg-slate-50 text-slate-600 flex-col gap-4">
          <div className="text-5xl">⚠</div>
          <div className="text-lg font-semibold text-red-500">Rendering error</div>
          <pre className="text-xs bg-white border border-red-200 rounded p-4 max-w-xl overflow-auto text-red-600">
            {this.state.error.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg text-sm shadow-sm"
          >
            Reload app
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
