import React from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Unhandled frontend error:', error, errorInfo);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex flex-col items-center justify-center gap-md p-xl text-center" role="alert">
        <h1 className="text-xl">Something went wrong</h1>
        <p className="text-muted">Please refresh the page and try again. Your claim data is still safe.</p>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>Refresh page</button>
      </div>
    );
  }
}
