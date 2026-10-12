import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import Showcase from './Showcase'
import { ReportProvider } from './reports'
import { showcase } from './embed'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {showcase ? <Showcase /> : <ReportProvider><App /></ReportProvider>}
  </React.StrictMode>,
)
