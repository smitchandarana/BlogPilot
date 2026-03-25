import { useState, useCallback } from 'react'
import IdeaPoolPanel from '../components/IdeaPoolPanel'
import MixBoard from '../components/MixBoard'

export default function IdeasLab({ onSendToGenerator }) {
  const [pinnedItems, setPinnedItems] = useState([])

  const handlePin = useCallback((item) => {
    setPinnedItems(prev => {
      if (prev.length >= 5) return prev
      if (prev.some(p => p.id === item.id)) return prev
      return [...prev, { ...item, highlights: [] }]
    })
  }, [])

  const handleUnpin = useCallback((itemId) => {
    setPinnedItems(prev => prev.filter(p => p.id !== itemId))
  }, [])

  const handleHighlight = useCallback((itemId, highlights) => {
    setPinnedItems(prev =>
      prev.map(p => p.id === itemId ? { ...p, highlights } : p)
    )
  }, [])

  return (
    <div className="flex gap-0 h-full min-h-[600px]">
      <div className="w-[45%] pr-4 border-r border-slate-700/40 overflow-y-auto">
        <IdeaPoolPanel
          pinnedItems={pinnedItems}
          onPin={handlePin}
        />
      </div>
      <div className="flex-1 pl-4 overflow-y-auto">
        <MixBoard
          pinnedItems={pinnedItems}
          onUnpin={handleUnpin}
          onHighlight={handleHighlight}
          onSendToGenerator={onSendToGenerator}
        />
      </div>
    </div>
  )
}
