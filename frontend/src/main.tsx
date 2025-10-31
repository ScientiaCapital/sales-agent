import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { QueryProvider } from './components/providers/QueryProvider';
import { ErrorTracker, logger } from './lib/debug';

try {
  const rootElement = document.getElementById('root');
  if (!rootElement) {
    throw new Error('Root element not found');
  }

  const root = createRoot(rootElement);
  root.render(
    <StrictMode>
      <QueryProvider>
        <App />
      </QueryProvider>
    </StrictMode>
  );

  logger.info('Application started successfully');
} catch (error) {
  const errorObj = error instanceof Error ? error : new Error(String(error));
  ErrorTracker.captureException(errorObj, { context: 'application_startup' });

  const rootElement = document.getElementById('root');
  if (rootElement) {
    rootElement.innerHTML = `
      <div style="padding: 20px; font-family: sans-serif; max-width: 600px; margin: 50px auto;">
        <h1 style="color: #dc2626;">Application Error</h1>
        <p style="color: #374151; margin: 16px 0;">${errorObj.message}</p>
        <details style="margin-top: 16px;">
          <summary style="cursor: pointer; color: #6b7280;">Error Details</summary>
          <pre style="background: #f3f4f6; padding: 12px; border-radius: 4px; overflow: auto; margin-top: 8px; font-size: 12px;">${errorObj.stack || JSON.stringify(error, null, 2)}</pre>
        </details>
      </div>
    `;
  }
}
