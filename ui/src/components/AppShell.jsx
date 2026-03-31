import { Outlet } from 'react-router-dom'
import Layout from './Layout'

export default function AppShell() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  )
}
