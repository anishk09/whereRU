import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import {ConnectedProvider} from './connected'
import './index.css'
import './local-fonts.css'
import './demo-tools.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConnectedProvider><App /></ConnectedProvider>
  </React.StrictMode>,
)
