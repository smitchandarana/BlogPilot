import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import EngineControl from './pages/EngineControl'
import Topics from './pages/Topics'
import FeedEngagement from './pages/FeedEngagement'
import ContentStudio from './pages/ContentStudio'
import Campaigns from './pages/Campaigns'
import Leads from './pages/Leads'
import Analytics from './pages/Analytics'
import PromptEditor from './pages/PromptEditor'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/control" element={<EngineControl />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/feed" element={<FeedEngagement />} />
          <Route path="/content" element={<ContentStudio />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/prompts" element={<PromptEditor />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
