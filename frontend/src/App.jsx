import { Routes, Route, Navigate } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Progress from './pages/Progress.jsx'
import Results from './pages/Results.jsx'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/progress/:jobId" element={<Progress />} />
        <Route path="/results/:jobId" element={<Results />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
