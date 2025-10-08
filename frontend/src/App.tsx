import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import CostDashboard from './pages/CostDashboard';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/costs" element={<CostDashboard />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
