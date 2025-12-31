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
    // SECURITY FIX: Use DOM APIs instead of innerHTML to prevent XSS
    // Error messages could contain malicious HTML/JS if from user input
    rootElement.textContent = ''; // Clear existing content safely

    const container = document.createElement('div');
    container.style.cssText = 'padding: 20px; font-family: sans-serif; max-width: 600px; margin: 50px auto;';

    const heading = document.createElement('h1');
    heading.style.color = '#dc2626';
    heading.textContent = 'Application Error';

    const message = document.createElement('p');
    message.style.cssText = 'color: #374151; margin: 16px 0;';
    message.textContent = errorObj.message; // textContent escapes HTML

    const details = document.createElement('details');
    details.style.marginTop = '16px';

    const summary = document.createElement('summary');
    summary.style.cssText = 'cursor: pointer; color: #6b7280;';
    summary.textContent = 'Error Details';

    const pre = document.createElement('pre');
    pre.style.cssText = 'background: #f3f4f6; padding: 12px; border-radius: 4px; overflow: auto; margin-top: 8px; font-size: 12px;';
    pre.textContent = errorObj.stack || JSON.stringify(error, null, 2); // textContent escapes HTML

    details.appendChild(summary);
    details.appendChild(pre);
    container.appendChild(heading);
    container.appendChild(message);
    container.appendChild(details);
    rootElement.appendChild(container);
  }
}
