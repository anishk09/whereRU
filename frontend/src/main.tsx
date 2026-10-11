import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ReportProvider } from './reports'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ReportProvider><App /></ReportProvider>
  </React.StrictMode>,
)
