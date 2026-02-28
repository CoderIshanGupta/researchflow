'use client'

import React, { useEffect, useState, useRef, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FiArrowLeft,
  FiSearch,
  FiMessageSquare,
  FiFileText,
  FiPlus,
  FiExternalLink,
  FiBookOpen,
  FiCheck,
  FiRefreshCw,
  FiFilter,
  FiTrash2,
  FiUpload,
  FiShare2,
} from 'react-icons/fi'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/store/auth'
import { api } from '@/lib/api'
import Link from 'next/link'
import {
  ResponsiveContainer,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Bar,
} from 'recharts'

interface ResearchSession {
  id: string
  title: string
  topic: string
  description: string | null
  created_at: string
  updated_at: string
}

interface Author {
  name: string
}

interface Paper {
  id: string
  title: string
  authors: Author[]
  abstract: string | null
  year: number | null
  citation_count: number
  url: string | null
  pdf_url: string | null
  source_type: string
  venue: string | null
}

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

type DraftStyle = 'summary' | 'literature_review'
type BibliographyStyle = 'bibtex' | 'apa' | 'mla' | 'ieee'
type MetricsView = 'relevance' | 'citations' | 'keywords'

type MetricsChartItem = {
  id: string
  idx: number
  title: string
  shortTitle: string
  citations: number
  relevance: number
  relevanceScore: number
  keywordHits: number
}

export default function SessionDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuthStore()
  const sessionId = params?.id as string

  const initialized = useRef(false)
  const autoSearched = useRef(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [session, setSession] = useState<ResearchSession | null>(null)
  const [papers, setPapers] = useState<Paper[]>([])
  const [searchResults, setSearchResults] = useState<Paper[]>([])
  const [suggestedPapers, setSuggestedPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] =
    useState<'sources' | 'chat' | 'draft' | 'metrics'>('sources')
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [autoSearching, setAutoSearching] = useState(false)
  const [addingPaper, setAddingPaper] = useState<string | null>(null)
  const [removingPaper, setRemovingPaper] = useState<string | null>(null)
  const [addedPaperIds, setAddedPaperIds] = useState<Set<string>>(new Set())
  const [sourcesSearched, setSourcesSearched] = useState<string[]>([])

  // Chat
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatLoading, setChatLoading] = useState(false)

  // Draft
  const [draftContent, setDraftContent] = useState('')
  const [draftLoading, setDraftLoading] = useState(false)
  const [draftStyle, setDraftStyle] = useState<DraftStyle>('literature_review')

  // Bibliography export
  const [bibStyle, setBibStyle] = useState<BibliographyStyle>('bibtex')
  const [bibLoading, setBibLoading] = useState(false)

  // Filters
  const [showFilters, setShowFilters] = useState(false)
  const [sortBy, setSortBy] =
    useState<'relevance' | 'citations' | 'year'>('relevance')
  const [yearFrom, setYearFrom] = useState<number | ''>('')
  const [yearTo, setYearTo] = useState<number | ''>('')

  // Paper overview modal
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null)

  // PDF upload state
  const [uploadingPdf, setUploadingPdf] = useState(false)

  // Metrics view and mobile detection
  const [metricsView, setMetricsView] = useState<MetricsView>('relevance')
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const update = () => setIsMobile(window.innerWidth < 640)
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  // Init session & sources
  useEffect(() => {
    if (!sessionId || !user || initialized.current) return
    initialized.current = true

    const init = async () => {
      setLoading(true)
      let sessionData: ResearchSession | null = null

      try {
        const { data, error } = await supabase
          .from('research_sessions')
          .select('*')
          .eq('id', sessionId)
          .single()

        if (error) throw error
        sessionData = data
        setSession(sessionData)

        await fetchPapers()
      } catch (error) {
        console.error('Error initializing session:', error)
        router.push('/dashboard')
        return
      } finally {
        setLoading(false)
      }

      if (sessionData && !autoSearched.current) {
        autoSearched.current = true
        const searchTerms = (sessionData.title || sessionData.topic || '').trim()
        if (searchTerms) {
          autoSearchPapers(searchTerms)
        }
      }
    }

    init()
  }, [sessionId, user, router])

  // Load chat history
  useEffect(() => {
    if (!sessionId) return

    const loadHistory = async () => {
      try {
        const res = await api.get('/rag/history', {
          params: { session_id: sessionId },
        })
        setChatMessages(res.data)
      } catch (err) {
        console.error('Failed to load chat history:', err)
      }
    }

    loadHistory()
  }, [sessionId])

  const fetchPapers = async () => {
    try {
      const { data, error } = await supabase
        .from('session_papers')
        .select(
          `
          paper_id,
          relevance_score,
          added_at,
          papers (*)
        `
        )
        .eq('session_id', sessionId)
        .order('added_at', { ascending: false })

      if (error) throw error

      const papersList = data?.map((item: any) => item.papers).filter(Boolean) || []
      setPapers(papersList)

      const ids = new Set(papersList.map((p: Paper) => p.id))
      setAddedPaperIds(ids)

      console.log(`Fetched ${papersList.length} papers from session`)
    } catch (error) {
      console.error('Error fetching papers:', error)
    }
  }

  const autoSearchPapers = async (searchTerms: string) => {
    setAutoSearching(true)
    try {
      const res = await api.get('/sources/search', {
        params: {
          query: searchTerms,
          limit: 20,
          sort_by: 'relevance',
        },
      })

      setSuggestedPapers(res.data.papers || [])
      setSourcesSearched(res.data.sources_searched || [])
    } catch (error) {
      console.error('Auto-search error:', error)
    } finally {
      setAutoSearching(false)
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    setSearching(true)
    setSearchResults([])

    try {
      const params: any = {
        query: searchQuery,
        limit: 30,
        sort_by: sortBy,
      }

      if (yearFrom) params.year_from = yearFrom
      if (yearTo) params.year_to = yearTo

      const res = await api.get('/sources/search', { params })

      setSearchResults(res.data.papers || [])
      setSourcesSearched(res.data.sources_searched || [])
    } catch (error) {
      console.error('Search error:', error)
      alert('Failed to search papers. Please try again.')
    } finally {
      setSearching(false)
    }
  }

  const handleAddPaper = async (paper: Paper) => {
    if (addedPaperIds.has(paper.id) || addingPaper === paper.id) return

    setAddingPaper(paper.id)

    try {
      await api.post('/sources/add-to-session', {
        session_id: sessionId,
        paper: paper,
        relevance_score: 0.9,
      })

      setPapers((prev) => {
        if (prev.some((p) => p.id === paper.id)) return prev
        return [paper, ...prev]
      })
      setAddedPaperIds((prev) => new Set(prev).add(paper.id))
    } catch (error: any) {
      console.error('Error adding paper:', error)
      alert(error.response?.data?.detail || 'Failed to add paper')
    } finally {
      setAddingPaper(null)
    }
  }

  const handleRemovePaper = async (paperId: string) => {
    if (!confirm('Remove this paper from My Sources?')) return
    setRemovingPaper(paperId)

    try {
      const { error } = await supabase
        .from('session_papers')
        .delete()
        .eq('session_id', sessionId)
        .eq('paper_id', paperId)

      if (error) throw error

      setPapers((prev) => prev.filter((p) => p.id !== paperId))
      setAddedPaperIds((prev) => {
        const next = new Set(prev)
        next.delete(paperId)
        return next
      })
    } catch (error) {
      console.error('Error removing paper:', error)
      alert('Failed to remove paper from session')
    } finally {
      setRemovingPaper(null)
    }
  }

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim()) return

    const question = chatInput.trim()
    setChatMessages((prev) => [...prev, { role: 'user', content: question }])
    setChatInput('')
    setChatLoading(true)

    try {
      const res = await api.post('/rag/chat', {
        session_id: sessionId,
        question,
      })

      const answer = res.data.answer as string
      setChatMessages((prev) => [...prev, { role: 'assistant', content: answer }])
    } catch (error: any) {
      console.error('Chat error:', error)
      const msg = error.response?.data?.detail || 'Failed to get answer'
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error: ' + msg },
      ])
    } finally {
      setChatLoading(false)
    }
  }

  const handleDownloadChat = async () => {
    try {
      const res = await api.get('/rag/history', {
        params: { session_id: sessionId },
      })

      const history = res.data as {
        role: string
        content: string
        created_at?: string
      }[]

      if (!history.length) {
        alert('No chat history to download yet.')
        return
      }

      const header = `# Chat History for Session: ${session?.title || sessionId
        }\n\n`
      const lines = history.map((m) => {
        const ts = m.created_at ? new Date(m.created_at).toLocaleString() : ''
        const role = m.role.toUpperCase()
        return `### [${role}] ${ts}\n\n${m.content}`
      })

      const content = header + lines.join('\n\n---\n\n')

      const blob = new Blob([content], {
        type: 'text/markdown;charset=utf-8',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const dateStr = new Date().toISOString().slice(0, 10)
      const safeTitle = (session?.title || 'session')
        .replace(/[^a-z0-9\-]+/gi, '-')
        .slice(0, 40)
      a.download = `${safeTitle}-chat-${dateStr}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to download chat:', err)
      alert('Failed to download chat history. Please try again.')
    }
  }

  const handleGenerateDraft = async () => {
    if (!papers.length) {
      alert('Add some sources to this session before generating a draft.')
      return
    }
    setDraftLoading(true)
    try {
      const res = await api.post('/draft/generate', {
        session_id: sessionId,
        style: draftStyle,
      })
      setDraftContent(res.data.content || '')
      setActiveTab('draft')
    } catch (err: any) {
      console.error('Draft generation error:', err)
      alert(
        err.response?.data?.detail ||
        'Failed to generate draft. Please try again.'
      )
    } finally {
      setDraftLoading(false)
    }
  }

  const handleDownloadDraft = async () => {
    if (!draftContent.trim()) {
      alert('No draft to download yet.')
      return
    }
    const header = `# Draft for Session: ${session?.title || sessionId}\n\n`
    const blob = new Blob([header + draftContent], {
      type: 'text/markdown;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const dateStr = new Date().toISOString().slice(0, 10)
    const safeTitle = (session?.title || 'session')
      .replace(/[^a-z0-9\-]+/gi, '-')
      .slice(0, 40)
    a.download = `${safeTitle}-draft-${dateStr}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleExportBibliography = async () => {
    if (!papers.length) {
      alert('Add some sources to this session before exporting references.')
      return
    }
    setBibLoading(true)
    try {
      const res = await api.get('/draft/bibliography', {
        params: {
          session_id: sessionId,
          style: bibStyle,
        },
      })

      const text: string = res.data?.text || ''
      if (!text.trim()) {
        alert('No references available for this session yet.')
        return
      }

      const dateStr = new Date().toISOString().slice(0, 10)
      const safeTitle = (session?.title || 'session')
        .replace(/[^a-z0-9\-]+/gi, '-')
        .slice(0, 40)
      const ext = bibStyle === 'bibtex' ? 'bib' : 'txt'

      const blob = new Blob([text], {
        type: 'text/plain;charset=utf-8',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeTitle}-refs-${dateStr}.${ext}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error('Bibliography export error:', err)
      alert(
        err.response?.data?.detail ||
        'Failed to export references. Please try again.'
      )
    } finally {
      setBibLoading(false)
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleUploadPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = '' // reset input

    if (file.type !== 'application/pdf') {
      alert('Please upload a PDF file.')
      return
    }

    const maxSize = 20 * 1024 * 1024
    if (file.size > maxSize) {
      alert('File too large. Please upload a PDF smaller than 20 MB.')
      return
    }

    setUploadingPdf(true)
    try {
      const filePath = `${sessionId}/${Date.now()}-${file.name}`

      const { error: uploadError } = await supabase.storage
        .from('uploads')
        .upload(filePath, file, {
          cacheControl: '3600',
          upsert: false,
        })

      if (uploadError) {
        console.error('Upload error:', uploadError)
        alert('Failed to upload PDF to storage.')
        return
      }

      const { data: publicData } = supabase.storage
        .from('uploads')
        .getPublicUrl(filePath)

      const pdfUrl = publicData.publicUrl

      await api.post('/sources/add-uploaded', {
        session_id: sessionId,
        pdf_url: pdfUrl,
        filename: file.name,
      })

      await fetchPapers()
      alert('PDF uploaded and added to sources.')
    } catch (err) {
      console.error('Upload PDF error:', err)
      alert('Failed to upload and process PDF.')
    } finally {
      setUploadingPdf(false)
    }
  }

  const getSourceBadgeColor = (source: string) => {
    switch (source) {
      case 'semantic_scholar':
        return 'bg-blue-100 text-blue-700'
      case 'arxiv':
        return 'bg-orange-100 text-orange-700'
      case 'pubmed':
        return 'bg-green-100 text-green-700'
      case 'uploaded':
        return 'bg-purple-100 text-purple-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  const getSourceName = (source: string) => {
    switch (source) {
      case 'semantic_scholar':
        return 'Semantic Scholar'
      case 'arxiv':
        return 'arXiv'
      case 'pubmed':
        return 'PubMed'
      case 'uploaded':
        return 'Uploaded PDF'
      default:
        return source
    }
  }

  const PaperCard = ({
    paper,
    showAddButton = false,
    canRemove = false,
    isRemoving = false,
  }: {
    paper: Paper
    showAddButton?: boolean
    canRemove?: boolean
    isRemoving?: boolean
  }) => {
    const isAdded = addedPaperIds.has(paper.id)
    const isAdding = addingPaper === paper.id

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        onClick={() => setSelectedPaper(paper)}
        className={`p-4 border rounded-lg transition-colors cursor-pointer ${isAdded && !showAddButton
          ? 'border-green-200 bg-green-50/30'
          : 'border-gray-200 hover:border-teal-300'
          }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-gray-900 mb-1 line-clamp-2 text-sm sm:text-base">
              {paper.title}
            </h4>
            <p className="text-xs sm:text-sm text-gray-600 mb-2">
              {paper.authors?.map((a) => a.name).slice(0, 3).join(', ')}
              {paper.authors?.length > 3 && ` +${paper.authors.length - 3}`}
              {paper.year && <span className="font-medium"> • {paper.year}</span>}
              {paper.venue && <span className="text-gray-500"> • {paper.venue}</span>}
            </p>
            {typeof paper.citation_count === 'number' &&
              paper.citation_count > 0 && (
                <p className="text-[11px] text-gray-500 mb-1">
                  Citations: {paper.citation_count.toLocaleString()}
                </p>
              )}
            {paper.abstract && (
              <p className="text-xs sm:text-sm text-gray-500 line-clamp-2 mb-2">
                {paper.abstract}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`text-xs px-2 py-0.5 rounded ${getSourceBadgeColor(
                  paper.source_type
                )}`}
              >
                {getSourceName(paper.source_type)}
              </span>
              {paper.url && (
                <a
                  href={paper.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-teal-600 hover:underline flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  View <FiExternalLink className="w-3 h-3" />
                </a>
              )}
              {paper.pdf_url && (
                <a
                  href={paper.pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-red-600 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  PDF
                </a>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end gap-2">
            {showAddButton && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleAddPaper(paper)
                }}
                disabled={isAdded || isAdding}
                className={`p-2 rounded-lg transition-all ${isAdded
                  ? 'bg-green-100 text-green-600'
                  : isAdding
                    ? 'bg-gray-100 text-gray-400'
                    : 'bg-teal-50 text-teal-600 hover:bg-teal-100'
                  }`}
              >
                {isAdding ? (
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                ) : isAdded ? (
                  <FiCheck className="w-5 h-5" />
                ) : (
                  <FiPlus className="w-5 h-5" />
                )}
              </button>
            )}

            {canRemove && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleRemovePaper(paper.id)
                }}
                disabled={isRemoving}
                className="p-2 rounded-lg text-xs text-red-600 hover:bg-red-50 flex items-center gap-1 disabled:opacity-50"
              >
                {isRemoving ? (
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                ) : (
                  <>
                    <FiTrash2 className="w-4 h-4" />
                    <span>Remove</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </motion.div>
    )
  }

  // ----- Metrics data -----

  const metricsChartData = useMemo<MetricsChartItem[]>(() => {
    if (!session || !papers.length) return []

    const topicText = `${session.title || ''} ${session.topic || ''}`.toLowerCase()

    const tokenize = (text: string | null | undefined): Set<string> => {
      if (!text) return new Set()
      return new Set(
        text
          .toLowerCase()
          .replace(/[^a-z0-9\s-]/g, ' ')
          .split(/\s+/)
          .filter((t) => t.length >= 4)
      )
    }

    const topicTokens = tokenize(topicText)
    const rawPoints: {
      id: string
      title: string
      citations: number
      relevance: number
      keywordHits: number
    }[] = []

    for (const p of papers) {
      const text = `${p.title || ''} ${p.abstract || ''}`.toLowerCase()
      const paperTokens = tokenize(text)

      let relevance = 0
      topicTokens.forEach((t) => {
        if (paperTokens.has(t)) relevance++
      })

      let keywordHits = 0
      topicTokens.forEach((t) => {
        const regex = new RegExp(`\\b${t}\\b`, 'gi')
        const matches = text.match(regex)
        if (matches) keywordHits += matches.length
      })

      const citations =
        typeof p.citation_count === 'number' && p.citation_count > 0
          ? p.citation_count
          : 0

      rawPoints.push({
        id: p.id,
        title: p.title,
        citations,
        relevance,
        keywordHits,
      })
    }

    if (!rawPoints.length) return []

    const maxRelevance = rawPoints.reduce((m, p) => Math.max(m, p.relevance), 0) || 1

    return rawPoints.map((p, index) => {
      const shortTitle =
        p.title.length > 24 ? p.title.slice(0, 21).trimEnd() + '…' : p.title

      return {
        id: p.id,
        idx: index + 1,
        title: p.title,
        shortTitle,
        citations: p.citations,
        relevance: p.relevance,
        keywordHits: p.keywordHits,
        relevanceScore: Math.round((p.relevance / maxRelevance) * 100),
      }
    })
  }, [papers, session])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading session...</p>
        </div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-600">Session not found</p>
        <Link
          href="/dashboard"
          className="text-teal-600 hover:underline mt-2 inline-block"
        >
          Back to Dashboard
        </Link>
      </div>
    )
  }

  return (
    <div className="overflow-x-hidden">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-gray-600 hover:text-teal-600 transition-colors mb-4"
        >
          <FiArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>

        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">
          {session.title}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-teal-600 font-medium">{session.topic}</span>
          {sourcesSearched.length > 0 && (
            <span className="text-xs text-gray-500">
              Searching: {sourcesSearched.join(', ')}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-full sm:w-auto sm:inline-flex overflow-x-auto">
        <button
          onClick={() => setActiveTab('sources')}
          className={`flex-1 sm:flex-none flex items-center justify-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${activeTab === 'sources'
            ? 'bg-white text-teal-600 shadow-sm'
            : 'text-gray-600'
            }`}
        >
          <FiSearch className="w-4 h-4" />
          <span>Sources</span>
          {papers.length > 0 && (
            <span className="bg-teal-100 text-teal-700 text-[10px] sm:text-xs px-2 py-0.5 rounded-full">
              {papers.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 sm:flex-none flex items-center justify-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${activeTab === 'chat'
            ? 'bg-white text-teal-600 shadow-sm'
            : 'text-gray-600'
            }`}
        >
          <FiMessageSquare className="w-4 h-4" />
          <span>Chat</span>
        </button>
        <button
          onClick={() => setActiveTab('draft')}
          className={`flex-1 sm:flex-none flex items-center justify-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${activeTab === 'draft'
            ? 'bg-white text-teal-600 shadow-sm'
            : 'text-gray-600'
            }`}
        >
          <FiFileText className="w-4 h-4" />
          <span>Draft</span>
        </button>
        <button
          onClick={() => setActiveTab('metrics')}
          className={`flex-1 sm:flex-none flex items-center justify-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${activeTab === 'metrics'
            ? 'bg-white text-teal-600 shadow-sm'
            : 'text-gray-600'
            }`}
        >
          <FiShare2 className="w-4 h-4" />
          <span>Metrics</span>
        </button>
      </div>

      {/* Hidden file input for PDF upload */}
      <input
        type="file"
        accept="application/pdf"
        ref={fileInputRef}
        onChange={handleUploadPdf}
        className="hidden"
      />

      {/* Tab Content */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6">
        {/* SOURCES TAB */}
        {activeTab === 'sources' && (
          <div className="space-y-8">
            {/* My Sources + Upload PDF */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    My Sources {papers.length > 0 && `(${papers.length})`}
                  </h3>
                  <p className="text-xs text-gray-500">
                    Add from search, suggestions, or upload your own PDFs.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={fetchPapers}
                    className="text-sm text-gray-500 hover:text-teal-600 flex items-center gap-1"
                  >
                    <FiRefreshCw className="w-4 h-4" />
                    Refresh
                  </button>
                  <button
                    type="button"
                    onClick={handleUploadClick}
                    disabled={uploadingPdf}
                    className="flex items-center gap-1 px-3 py-2 rounded-lg border border-gray-300 text-xs sm:text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                  >
                    <FiUpload className="w-4 h-4" />
                    <span>{uploadingPdf ? 'Uploading...' : 'Upload PDF'}</span>
                  </button>
                </div>
              </div>

              {papers.length === 0 ? (
                <div className="text-center py-6 border-2 border-dashed border-gray-200 rounded-xl">
                  <FiBookOpen className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-gray-600 text-sm">
                    No papers added yet. Add from suggestions, search, or upload a PDF.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[300px] overflow-y-auto">
                  {papers.map((paper) => (
                    <PaperCard
                      key={paper.id}
                      paper={paper}
                      canRemove
                      isRemoving={removingPaper === paper.id}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Suggested Papers */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Suggested Papers
                <span className="text-sm font-normal text-gray-500 ml-2">
                  based on &quot;{session.title}&quot;
                </span>
              </h3>

              {autoSearching ? (
                <div className="text-center py-8">
                  <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                  <p className="text-gray-600">Finding relevant papers...</p>
                </div>
              ) : suggestedPapers.length > 0 ? (
                <div className="space-y-3 max-h-[400px] overflow-y-auto">
                  {suggestedPapers.map((paper) => (
                    <PaperCard key={paper.id} paper={paper} showAddButton />
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-6">
                  No suggestions found
                </p>
              )}
            </div>

            {/* Manual Search */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  Search More Papers
                </h3>
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`text-sm flex items-center gap-1 px-3 py-1.5 rounded-lg transition-colors ${showFilters ? 'bg-teal-100 text-teal-700' : 'text-gray-500 hover:bg-gray-100'
                    }`}
                >
                  <FiFilter className="w-4 h-4" />
                  Filters
                </button>
              </div>

              <AnimatePresence>
                {showFilters && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="mb-4 overflow-hidden"
                  >
                    <div className="p-4 bg-gray-50 rounded-lg flex flex-wrap gap-4">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Sort By
                        </label>
                        <select
                          value={sortBy}
                          onChange={(e) =>
                            setSortBy(
                              e.target.value as 'relevance' | 'citations' | 'year'
                            )
                          }
                          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                        >
                          <option value="relevance">Relevance</option>
                          <option value="citations">Citations</option>
                          <option value="year">Most Recent</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Year From
                        </label>
                        <input
                          type="number"
                          value={yearFrom}
                          onChange={(e) =>
                            setYearFrom(e.target.value ? parseInt(e.target.value) : '')
                          }
                          placeholder="2020"
                          className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Year To
                        </label>
                        <input
                          type="number"
                          value={yearTo}
                          onChange={(e) =>
                            setYearTo(e.target.value ? parseInt(e.target.value) : '')
                          }
                          placeholder="2024"
                          className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                        />
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <form onSubmit={handleSearch} className="mb-4">
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="flex-1 relative">
                    <FiSearch className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search papers..."
                      className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
                    />
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    type="submit"
                    disabled={searching}
                    className="px-6 py-3 bg-gradient-to-r from-teal-600 to-emerald-600 text-white rounded-xl font-semibold shadow-lg disabled:opacity-50"
                  >
                    {searching ? 'Searching...' : 'Search'}
                  </motion.button>
                </div>
              </form>

              {searchResults.length > 0 && (
                <div className="space-y-3 max-h-[400px] overflow-y-auto">
                  <p className="text-sm text-gray-600">
                    Found {searchResults.length} papers
                  </p>
                  {searchResults.map((paper) => (
                    <PaperCard key={paper.id} paper={paper} showAddButton />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* CHAT TAB */}
        {activeTab === 'chat' && (
          <div className="flex flex-col min-h-[60vh]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-base font-semibold text-gray-900">
                AI Chat with Citations
              </h3>
              <button
                type="button"
                onClick={handleDownloadChat}
                className="text-xs sm:text-sm px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100"
              >
                Download Chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 mb-4 border border-gray-200 rounded-xl p-4 bg-gray-50">
              {chatMessages.length === 0 && (
                <div className="text-center text-gray-500 text-sm">
                  {papers.length === 0 ? (
                    <p>Add some papers to this session first, then ask a question.</p>
                  ) : (
                    <p>
                      Ask a question about the papers in this session, for example:{' '}
                      &quot;What EEG features are most predictive for early
                      Alzheimer&apos;s?&quot;
                    </p>
                  )}
                </div>
              )}

              {chatMessages.map((m, idx) => (
                <div
                  key={idx}
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${m.role === 'user'
                    ? 'ml-auto bg-teal-600 text-white'
                    : 'mr-auto bg-white border border-gray-200 text-gray-900'
                    }`}
                >
                  {m.content}
                </div>
              ))}
            </div>

            <form onSubmit={handleChatSubmit} className="flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask something about this session..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none text-sm"
              />
              <button
                type="submit"
                disabled={chatLoading || !chatInput.trim() || papers.length === 0}
                className="px-4 py-2 bg-gradient-to-r from-teal-600 to-emerald-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50"
              >
                {chatLoading ? 'Asking...' : 'Ask'}
              </button>
            </form>
          </div>
        )}

        {/* DRAFT TAB */}
        {activeTab === 'draft' && (
          <div className="flex flex-col min-h-[60vh] gap-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-2">
              <div>
                <h3 className="text-base font-semibold text-gray-900">
                  AI Draft (Experimental)
                </h3>
                <p className="text-xs text-gray-500">
                  Generate a structured draft based on the sources in this session.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={draftStyle}
                  onChange={(e) =>
                    setDraftStyle(e.target.value as DraftStyle)
                  }
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs sm:text-sm"
                >
                  <option value="summary">Summary</option>
                  <option value="literature_review">Literature Review</option>
                </select>
                <button
                  type="button"
                  onClick={handleGenerateDraft}
                  disabled={draftLoading || !papers.length}
                  className="px-4 py-2 bg-gradient-to-r from-teal-600 to-emerald-600 text-white rounded-lg text-xs sm:text-sm font-semibold disabled:opacity-50"
                >
                  {draftLoading ? 'Generating...' : 'Generate Draft'}
                </button>
                <button
                  type="button"
                  onClick={handleDownloadDraft}
                  disabled={!draftContent.trim()}
                  className="px-3 py-2 rounded-lg border border-gray-300 text-xs sm:text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                >
                  Download .md
                </button>
                <select
                  value={bibStyle}
                  onChange={(e) =>
                    setBibStyle(e.target.value as BibliographyStyle)
                  }
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs sm:text-sm"
                >
                  <option value="bibtex">BibTeX</option>
                  <option value="apa">APA</option>
                  <option value="mla">MLA</option>
                  <option value="ieee">IEEE</option>
                </select>
                <button
                  type="button"
                  onClick={handleExportBibliography}
                  disabled={bibLoading || !papers.length}
                  className="px-3 py-2 rounded-lg border border-gray-300 text-xs sm:text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                >
                  {bibLoading ? 'Exporting...' : 'Export refs'}
                </button>
              </div>
            </div>

            <div className="flex-1">
              <textarea
                value={draftContent}
                onChange={(e) => setDraftContent(e.target.value)}
                placeholder={
                  papers.length === 0
                    ? 'Add some sources first, then generate a draft.'
                    : 'Click "Generate Draft" to create a structured summary or literature review.\nYou can edit the draft here.'
                }
                className="
                  w-full
                  min-h-[420px]
                  sm:min-h-[520px]
                  border
                  border-gray-300
                  rounded-lg
                  p-3
                  text-sm
                  font-mono
                  resize-none
                  focus:ring-2
                  focus:ring-teal-500
                  focus:border-transparent
                  outline-none
                  "
              />
            </div>
          </div>
        )}

        {/* METRICS TAB */}
        {activeTab === 'metrics' && (
          <div className="flex flex-col min-h-[60vh] gap-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify_between gap-3 mb-2">
              <div>
                <h3 className="text-base font-semibold text_gray-900">
                  Paper Metrics
                </h3>
                <p className="text-xs text-gray-500">
                  Choose a metric to see how each paper compares: Relevance
                  (0–100), Citations (count), or Keyword hits.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">View:</span>
                <select
                  value={metricsView}
                  onChange={(e) =>
                    setMetricsView(e.target.value as MetricsView)
                  }
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs sm:text-sm"
                >
                  <option value="relevance">Relevance (0–100)</option>
                  <option value="citations">Citations (count)</option>
                  <option value="keywords">Keyword hits (count)</option>
                </select>
              </div>
            </div>

            <div className="flex-1 min-h-[250px] w-full sm:max-w-5xl mx-auto px-1 sm:px-0">
              {metricsChartData.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                  Add some sources to visualize their metrics.
                </div>
              ) : (
                <ResponsiveContainer
                  width="100%"
                  height={isMobile ? 260 : 320}
                >
                  <BarChart
                    data={metricsChartData}
                    margin={{
                      top: 10,
                      right: isMobile ? 8 : 10,
                      bottom: 30,
                      left: isMobile ? 20 : 40,
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="idx"
                      tick={{ fontSize: 10 }}
                      tickLine={false}
                      label={{
                        value: 'Paper # (see tooltip for title)',
                        position: 'bottom',
                        offset: 0,
                        style: { fontSize: 16 },
                      }}
                    />
                    <YAxis
                      domain={
                        metricsView === 'relevance' ? [0, 100] : [0, 'auto']
                      }
                      tick={{ fontSize: 10 }}
                      tickLine={false}
                      label={{
                        value:
                          metricsView === 'relevance'
                            ? 'Relevance score (0–100)'
                            : metricsView === 'citations'
                              ? 'Citations'
                              : 'Keyword hits',
                        angle: -90,
                        position: 'center',
                        style: { fontSize: 13 },
                      }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload || !payload.length) return null
                        const p = payload[0].payload as MetricsChartItem
                        return (
                          <div className="bg-white border border-gray-200 rounded-md p-2 shadow-sm text-xs max-w-xs">
                            <div className="font-semibold mb-1 line-clamp-2">
                              {p.title}
                            </div>
                            {metricsView === 'relevance' && (
                              <>
                                <div>Relevance score: {p.relevanceScore}</div>
                                <div>Raw relevance (overlap): {p.relevance}</div>
                              </>
                            )}
                            {metricsView === 'citations' && (
                              <div>Citations: {p.citations}</div>
                            )}
                            {metricsView === 'keywords' && (
                              <div>Keyword hits: {p.keywordHits}</div>
                            )}
                          </div>
                        )
                      }}
                    />
                    <Legend
                      verticalAlign="top"
                      align="center"
                      height={24}
                      wrapperStyle={{ fontSize: 11 }}
                    />
                    {metricsView === 'relevance' && (
                      <Bar
                        dataKey="relevanceScore"
                        name="Relevance (0–100)"
                        fill="#0d9488"
                        barSize={isMobile ? 34 : 65}
                      />
                    )}
                    {metricsView === 'citations' && (
                      <Bar
                        dataKey="citations"
                        name="Citations (count)"
                        fill="#6366f1"
                        barSize={isMobile ? 34 : 65}
                      />
                    )}
                    {metricsView === 'keywords' && (
                      <Bar
                        dataKey="keywordHits"
                        name="Keyword hits (count)"
                        fill="#f97316"
                        barSize={isMobile ? 34 : 65}
                      />
                    )}
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}