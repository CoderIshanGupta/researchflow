import { checkBackendHealth } from '@/lib/api'

export default async function Home() {
  const backendStatus = await checkBackendHealth()
  
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-center font-mono text-sm">
        <h1 className="text-4xl font-bold mb-8 text-center">
          ResearchFlow
        </h1>
        <div className="bg-slate-100 dark:bg-slate-800 p-6 rounded-lg">
          <h2 className="text-xl font-semibold mb-4">System Status</h2>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span>Frontend: Running</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${backendStatus ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span>Backend: {backendStatus ? 'Connected' : 'Disconnected'}</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}