import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AdminApp } from './AdminApp'
import { initAuth } from '../lib/auth'
import '../styles/global.css' // Import Tailwind
import './styles/theme.css' // Import Admin Theme

initAuth().finally(() =>
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <AdminApp />
    </StrictMode>,
  ),
)
