import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import DashboardPage from '@/pages/DashboardPage'
import PokemonListPage from '@/pages/PokemonListPage'
import ChartsPage from '@/pages/ChartsPage'
import CrawlPage from '@/pages/CrawlPage'
import ComparePage from '@/pages/ComparePage'
import MoveDexPage from '@/pages/MoveDexPage'

export default createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'pokemon', element: <PokemonListPage /> },
      { path: 'moves', element: <MoveDexPage /> },
      { path: 'charts', element: <ChartsPage /> },
      { path: 'compare', element: <ComparePage /> },
      { path: 'crawl', element: <CrawlPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
