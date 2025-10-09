import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';

// Eager load: Dashboard (home page)
import { Dashboard } from './pages/Dashboard';

// Lazy load: Other pages for better performance
const Leads = lazy(() => import('./pages/Leads').then(m => ({ default: m.Leads })));
const Research = lazy(() => import('./pages/Research').then(m => ({ default: m.Research })));
const Campaigns = lazy(() => import('./pages/Campaigns').then(m => ({ default: m.Campaigns })));
const Conversations = lazy(() => import('./pages/Conversations').then(m => ({ default: m.Conversations })));
const CostDashboard = lazy(() => import('./pages/CostDashboard'));
const CSVImport = lazy(() => import('./pages/CSVImport').then(m => ({ default: m.CSVImport })));
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase').then(m => ({ default: m.KnowledgeBase })));
const ContactDiscovery = lazy(() => import('./pages/ContactDiscovery').then(m => ({ default: m.ContactDiscovery })));
const AgentTeams = lazy(() => import('./pages/AgentTeams').then(m => ({ default: m.AgentTeams })));

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route
            path="leads"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <Leads />
              </Suspense>
            }
          />
          <Route
            path="research"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <Research />
              </Suspense>
            }
          />
          <Route
            path="campaigns"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <Campaigns />
              </Suspense>
            }
          />
          <Route
            path="conversations"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <Conversations />
              </Suspense>
            }
          />
          <Route
            path="costs"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <CostDashboard />
              </Suspense>
            }
          />
          <Route
            path="csv-import"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <CSVImport />
              </Suspense>
            }
          />
          <Route
            path="knowledge"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <KnowledgeBase />
              </Suspense>
            }
          />
          <Route
            path="contacts"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <ContactDiscovery />
              </Suspense>
            }
          />
          <Route
            path="agents"
            element={
              <Suspense fallback={<LoadingFallback />}>
                <AgentTeams />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </Router>
  );
}

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="text-sm text-gray-500">Loading...</p>
      </div>
    </div>
  );
}

export default App;
