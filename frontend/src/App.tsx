import { useState } from 'react'
import { ReactFlowProvider } from '@xyflow/react'
import { Toolbar } from './components/Toolbar'
import { Sidebar } from './components/Sidebar'
import { NetworkCanvas } from './components/NetworkCanvas'
import { PropertiesPanel } from './components/PropertiesPanel'
import { ErrorBoundary } from './components/ErrorBoundary'
import { BuilderPage } from './pages/Builder'
import { ImportPage } from './pages/Import'
import { CadImportPage } from './pages/CadImport'

export type Tab = 'simulator' | 'builder' | 'import' | 'cad'

function SimulatorContent() {
  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar />
      <NetworkCanvas />
      <PropertiesPanel />
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('simulator')

  return (
    <ErrorBoundary>
      <ReactFlowProvider>
        <div className="flex flex-col h-screen bg-slate-50">
          <Toolbar activeTab={activeTab} onTabChange={setActiveTab} />
          {/* All tabs stay mounted to preserve state */}
          <div className={activeTab === 'simulator' ? 'flex flex-1 overflow-hidden' : 'hidden'}>
            <SimulatorContent />
          </div>
          <div className={activeTab === 'builder' ? 'flex flex-1 overflow-hidden flex-col' : 'hidden'}>
            <BuilderPage />
          </div>
          <div className={activeTab === 'import' ? 'flex flex-1 overflow-hidden flex-col' : 'hidden'}>
            <ImportPage />
          </div>
          <div className={activeTab === 'cad' ? 'flex flex-1 overflow-hidden flex-col' : 'hidden'}>
            <CadImportPage />
          </div>
        </div>
      </ReactFlowProvider>
    </ErrorBoundary>
  )
}
