import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import AdminDashboard from './AdminDashboard.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {['/admin', '/admin/'].includes(window.location.pathname) ? <AdminDashboard /> : <App />}
  </StrictMode>,
)
