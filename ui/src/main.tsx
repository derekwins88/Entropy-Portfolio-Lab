import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import Live from './pages/Live'
import Backtests from './pages/Backtests'
import Analytics from './pages/Analytics'
import Proofs from './pages/Proofs'
import Settings from './pages/Settings'
const qc = new QueryClient()
const router = createBrowserRouter([
  { path: '/', element: <App/>, children: [
    { path: '/', element: <Live/> },
    { path: '/live', element: <Live/> },
    { path: '/backtests', element: <Backtests/> },
    { path: '/analytics', element: <Analytics/> },
    { path: '/proofs', element: <Proofs/> },
    { path: '/settings', element: <Settings/> },
  ] }
])
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router}/>
    </QueryClientProvider>
  </React.StrictMode>
)
