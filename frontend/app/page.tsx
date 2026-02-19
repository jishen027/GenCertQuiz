'use client';

import { useState, useEffect } from 'react';
import { 
  Book, 
  Binary, 
  Cpu, 
  Plus, 
  ArrowRight, 
  Layers, 
  Database,
  Search,
  ShieldCheck,
  Zap,
  Target,
  AlertCircle,
  FileText,
  Trash2,
  Download,
  FileJson,
  Tags,
  Check,
  PlusCircle,
  RefreshCw
} from 'lucide-react';

type FileItem = {
  id: string;
  name: string;
  size: string;
};

type TopicItem = {
  id: string;
  name: string;
  source_filename: string;
};

type DistractorReasoning = {
  option: string;
  reason: string;
};

type ProgressEvent = {
  type: 'progress' | 'question' | 'done' | 'error';
  stage?: string;
  message?: string;
  data?: any;
};

type LogEntry = {
  message: string;
  timestamp: string;
  stage: string;
};

type Question = {
  id: number;
  context: string;
  question: string;
  options: { A: string; B: string; C: string; D: string };
  answer: string;
  explanation: string;
  difficulty: string;
  // V2 Multi-Agent metadata
  topic: string;
  cognitive_level: string;
  quality_score: number;
  distractor_reasoning: DistractorReasoning[];
  source_references: string[];
  quality_checks: Record<string, Record<string, boolean | string>>;
};

type FilesResponse = {
  textbooks: Array<{ name: string; chunks: number }>;
  exam_papers: Array<{ name: string; chunks: number }>;
};

type ErrorResponse = {
  detail?: string;
  message?: string;
};

type QuestionResponseData = {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  answer: string;
  explanation: string;
  difficulty: string;
  topic?: string;
  cognitive_level?: string;
  quality_score?: number;
  distractor_reasoning?: DistractorReasoning[];
  source_references?: string[];
  quality_checks?: Record<string, Record<string, boolean | string>>;
};

export default function Home() {
  // Core data state
  const [textbooks, setTextbooks] = useState<FileItem[]>([]);
  const [examPapers, setExamPapers] = useState<FileItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  
  // Progress state
  const [progressLogs, setProgressLogs] = useState<LogEntry[]>([]);
  const [currentStage, setCurrentStage] = useState<string>('');

  // Topics state
  const [availableTopics, setAvailableTopics] = useState<TopicItem[]>([]);
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [customTopic, setCustomTopic] = useState('');
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [regeneratingTopics, setRegeneratingTopics] = useState(false);

  // Form state
  const [complexity, setComplexity] = useState('medium');
  const [quantity, setQuantity] = useState(5);

  // Error state
  const [error, setError] = useState<string | null>(null);
  const [uploadingTextbook, setUploadingTextbook] = useState(false);
  const [uploadingExam, setUploadingExam] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(true);

  // Fetch uploaded files from database
  const fetchFiles = async () => {
    try {
      const response = await fetch('http://localhost:8000/files');
      if (response.ok) {
        const data: FilesResponse = await response.json();
        
        // Map database response to frontend format
        const textbookList = data.textbooks.map((file, idx: number) => ({
          id: `tb-${idx}`,
          name: file.name,
          size: `${file.chunks} chunks`
        }));
        
        const examList = data.exam_papers.map((file, idx: number) => ({
          id: `ex-${idx}`,
          name: file.name,
          size: `${file.chunks} chunks`
        }));
        
        setTextbooks(textbookList);
        setExamPapers(examList);
      }
    } catch (error) {
      console.error('Failed to load files from database');
    } finally {
      setLoadingFiles(false);
    }
  };

  // Fetch available topics from database
  const fetchTopics = async () => {
    setLoadingTopics(true);
    try {
      const response = await fetch('http://localhost:8000/topics');
      if (response.ok) {
        const data: { topics: TopicItem[] } = await response.json();
        setAvailableTopics(data.topics);
      }
    } catch (err) {
      console.error('Failed to load topics from database');
    } finally {
      setLoadingTopics(false);
    }
  };

  // Load files and topics from database on mount
  useEffect(() => {
    fetchFiles();
    fetchTopics();
  }, []);

  // File upload handlers
  const handleTextbookUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingTextbook(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', 'textbook');

    try {
      const response = await fetch('http://localhost:8000/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData: ErrorResponse = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Failed to upload textbook');
      }

      // Refresh file list and topics from database
      await Promise.all([fetchFiles(), fetchTopics()]);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Backend connection failed. Make sure the server is running on port 8000.';
      setError(message);
    } finally {
      setUploadingTextbook(false);
      e.target.value = '';
    }
  };

  const handleExamPaperUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingExam(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', 'exam_paper');

    try {
      const response = await fetch('http://localhost:8000/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData: ErrorResponse = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Failed to upload exam paper');
      }

      // Refresh file list from database
      await fetchFiles();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Backend connection failed. Make sure the server is running on port 8000.';
      setError(message);
    } finally {
      setUploadingExam(false);
      e.target.value = '';
    }
  };

  // Delete file handler — also removes associated topics
  const handleDeleteFile = async (filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

    try {
      const response = await fetch(`http://localhost:8000/files/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete file');
      }

      // Refresh files and topics (backend cascade-deleted topics)
      await Promise.all([fetchFiles(), fetchTopics()]);
      // Remove any selected topics that came from this file
      setSelectedTopics(prev =>
        prev.filter(t => !availableTopics.find(at => at.source_filename === filename && at.name === t))
      );
    } catch (error) {
      console.error('Error deleting file:', error);
      setError('Failed to delete file');
    }
  };

  // Toggle a topic in/out of the selected set
  const toggleTopic = (topicName: string) => {
    setSelectedTopics(prev =>
      prev.includes(topicName) ? prev.filter(t => t !== topicName) : [...prev, topicName]
    );
  };

  // Add a custom topic typed by the user
  const addCustomTopic = () => {
    const trimmed = customTopic.trim();
    if (!trimmed || selectedTopics.includes(trimmed)) return;
    setSelectedTopics(prev => [...prev, trimmed]);
    setCustomTopic('');
  };

  // Remove a topic from the selection
  const removeSelectedTopic = (topicName: string) => {
    setSelectedTopics(prev => prev.filter(t => t !== topicName));
  };

  // Regenerate all topics from uploaded textbooks
  const handleRegenerateTopics = async () => {
    if (regeneratingTopics) return;
    setRegeneratingTopics(true);
    try {
      const res = await fetch('http://localhost:8000/topics/regenerate', { method: 'POST' });
      if (!res.ok) throw new Error('Regeneration failed');
      await fetchTopics();
    } catch (err) {
      console.error('Failed to regenerate topics:', err);
      setError('Failed to regenerate topics. Make sure the backend is running.');
    } finally {
      setRegeneratingTopics(false);
    }
  };

  // Generate questions using Streaming endpoint
  const triggerInference = async () => {
    // Client-side validation
    if (selectedTopics.length === 0) {
      setError('Please select at least one topic (or add a custom topic)');
      return;
    }

    if (quantity < 1 || quantity > 50) {
      setError('Quantity must be between 1 and 50');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setQuestions([]);
    setProgressLogs([]);
    setCurrentStage('init');
    
    try {
      // Use Streaming endpoint
      const response = await fetch('http://localhost:8000/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topics: selectedTopics, difficulty: complexity, count: quantity }),
      });

      if (!response.ok) {
        const errorData: ErrorResponse = await response.json().catch(() => ({ detail: 'Generation failed' }));
        throw new Error(errorData.detail || 'Failed to start generation');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Process buffer for SSE messages
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const dataStr = line.slice(6);
              const event: ProgressEvent = JSON.parse(dataStr);
              
              if (event.type === 'progress') {
                const newLog: LogEntry = {
                  message: event.message || '',
                  timestamp: new Date().toLocaleTimeString(),
                  stage: event.stage || 'info'
                };
                
                setProgressLogs(prev => [...prev, newLog]);
                if (event.stage) setCurrentStage(event.stage);
                
                // Keep logs scrolled to bottom
                const logContainer = document.getElementById('log-container');
                if (logContainer) {
                  logContainer.scrollTop = logContainer.scrollHeight;
                }
              } 
              else if (event.type === 'question' && event.data) {
                // Process individual question
                const q = event.data;
                const newQuestion: Question = {
                  id: questions.length + 1, // Use current length + 1 (closure issue handled by functional update below if needed, but here we can just use setQuestions callback)
                  context: "SOURCE: Multi-Agent RAG",
                  question: q.question,
                  options: q.options,
                  answer: q.answer,
                  explanation: q.explanation,
                  difficulty: q.difficulty,
                  topic: q.topic || selectedTopics.join('; '),
                  cognitive_level: q.cognitive_level || 'application',
                  quality_score: q.quality_score || 7,
                  distractor_reasoning: q.distractor_reasoning || [],
                  source_references: q.source_references || [],
                  quality_checks: q.quality_checks || {}
                };
                
                setQuestions(prev => [...prev, { ...newQuestion, id: prev.length + 1 }]);
              }
              else if (event.type === 'done') {
                 setCurrentStage('complete');
                 setIsProcessing(false);
              }
              else if (event.type === 'error') {
                throw new Error(event.message || 'Unknown error during streaming');
              }
            } catch (e) {
              console.error('Error parsing SSE event:', e);
            }
          }
        }
      }
      
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Backend connection failed';
      setError(message);
      setProgressLogs(prev => [...prev, {
        message: `ERROR: ${message}`,
        timestamp: new Date().toLocaleTimeString(),
        stage: 'error'
      }]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Download handlers
  const handleDownloadJSON = () => {
    if (questions.length === 0) return;
    
    const allTopics = selectedTopics.join('_').replace(/\s+/g, '_') || 'questions';
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(questions, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `${allTopics}_questions.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  // Helper: Convert to Exam System Format
  const convertToExamFormat = (questionsToConvert: Question[]) => {
    return questionsToConvert.map((q, idx) => {
      // Transform options map {"A": "...", "B": "..."} to list of objects
      const optionsList = [];
      const optionMap: Record<string, number> = { "A": 1, "B": 2, "C": 3, "D": 4 };
      
      const sortedKeys = Object.keys(q.options).sort();
      for (const key of sortedKeys) {
        // key is A, B, C, D
        // @ts-ignore - we know key is valid key of q.options
        optionsList.push({
          id: optionMap[key] || 0,
          content: q.options[key as keyof typeof q.options]
        });
      }
      
      // Transform answer "A" or "A, C" to list of IDs [1] or [1, 3]
      const correctAnswers = [];
      const answers = q.answer.split(',').map(a => a.trim());
      for (const ans of answers) {
        if (optionMap[ans]) {
          correctAnswers.push(optionMap[ans]);
        }
      }
      
      return {
        id: idx + 1,
        question: q.question,
        options: optionsList,
        correct_answers: correctAnswers,
        explanation: q.explanation,
        domain: q.topic || 'General',
        tags: [q.topic || 'General']
      };
    });
  };

  const handleDownloadPDF = async () => {
    if (questions.length === 0) return;
    
    try {
      const allTopics = selectedTopics.join('; ');
      // Convert to exam format first
      const examQuestions = convertToExamFormat(questions);
      
      const response = await fetch('http://localhost:8000/export-pdf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          questions: examQuestions, // Send converted questions
          topic: allTopics,
          difficulty: complexity
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate PDF');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedTopics.join('_').replace(/\s+/g, '_') || 'questions'}_questions.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (error) {
      console.error('PDF download error:', error);
      setError('Failed to download PDF. Please try again.');
    }
  };

  const handleDownloadExamFormat = () => {
    if (questions.length === 0) return;
    
    const examQuestions = convertToExamFormat(questions);
    
    // Wrap in object with "questions" key as required by exam system
    const exportData = {
      questions: examQuestions
    };
      
    const allTopics = selectedTopics.join('_').replace(/\s+/g, '_') || 'exam';
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `${allTopics}_exam_format.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-[#1A1A1A] font-sans selection:bg-black selection:text-white">
      {/* Minimalist Header */}
      <header className="border-b border-[#E5E7EB] bg-white px-8 py-5 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-black flex items-center justify-center">
            <Cpu className="text-white w-5 h-5" />
          </div>
          <h1 className="text-lg font-medium tracking-tight">
            GenCertQuiz <span className="text-[#9CA3AF] font-normal ml-2 text-sm">SYSTEM V2.0</span>
          </h1>
        </div>
        <div className="flex items-center gap-6 text-[12px] uppercase tracking-widest text-[#6B7280]">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" /> Core: Multi-Agent RAG
          </span>
          <span className="flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5" /> Ready
          </span>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-8 py-4">
          <div className="max-w-[1400px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-1 h-8 bg-red-500"></div>
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-red-900 mb-1">SYSTEM ERROR</p>
                <p className="text-sm text-red-800">{error}</p>
              </div>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <main className="max-w-[1400px] mx-auto p-8">
        <div className="grid grid-cols-12 gap-8">
          
          {/* Left Sidebar: Data Source Management */}
          <aside className="col-span-12 md:col-span-4 lg:col-span-3 space-y-8">
            {/* Textbooks Section */}
            <section>
              <div className="flex justify-between items-end mb-4 border-b border-[#E5E7EB] pb-2">
                <h3 className="text-xs font-bold uppercase tracking-widest text-[#374151]">01 / Textbooks</h3>
                <label htmlFor="textbook-upload" className={`cursor-pointer transition-colors ${uploadingTextbook ? 'text-[#D1D5DB] cursor-wait' : 'text-[#9CA3AF] hover:text-black'}`}>
                  {uploadingTextbook ? (
                    <div className="w-4 h-4 border-2 border-[#D1D5DB] border-t-black rounded-full animate-spin"></div>
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                </label>
                <input
                  id="textbook-upload"
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={handleTextbookUpload}
                  disabled={uploadingTextbook}
                />
              </div>
              <div className="space-y-2">
                {loadingFiles ? (
                  <div className="flex items-center justify-center p-8">
                    <div className="w-4 h-4 border-2 border-[#D1D5DB] border-t-black rounded-full animate-spin"></div>
                  </div>
                ) : textbooks.length > 0 ? (
                  textbooks.map(file => (
                    <div key={file.id} className="group bg-white border border-[#E5E7EB] p-3 hover:border-black transition-all flex justify-between items-center">
                      <div className="flex items-center gap-3 truncate flex-1">
                        <Book className="w-4 h-4 text-[#9CA3AF] flex-shrink-0" />
                        <div className="truncate">
                          <span className="text-[13px] truncate font-normal block">{file.name}</span>
                          <span className="text-[10px] text-[#9CA3AF]">{file.size}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteFile(file.name)}
                        className="text-gray-400 hover:text-red-600 transition-colors p-1"
                        title="Delete file"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-[#9CA3AF] italic p-3">No textbooks uploaded</p>
                )}
              </div>
            </section>

            {/* Exam Papers Section */}
            <section>
              <div className="flex justify-between items-end mb-4 border-b border-[#E5E7EB] pb-2">
                <h3 className="text-xs font-bold uppercase tracking-widest text-[#374151]">02 / Exam Papers</h3>
                <label htmlFor="exam-upload" className={`cursor-pointer transition-colors ${uploadingExam ? 'text-[#D1D5DB] cursor-wait' : 'text-[#9CA3AF] hover:text-black'}`}>
                  {uploadingExam ? (
                    <div className="w-4 h-4 border-2 border-[#D1D5DB] border-t-black rounded-full animate-spin"></div>
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                </label>
                <input
                  id="exam-upload"
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={handleExamPaperUpload}
                  disabled={uploadingExam}
                />
              </div>
              <div className="space-y-2">
                {loadingFiles ? (
                  <div className="flex items-center justify-center p-8">
                    <div className="w-4 h-4 border-2 border-[#D1D5DB] border-t-black rounded-full animate-spin"></div>
                  </div>
                ) : examPapers.length > 0 ? (
                  examPapers.map(file => (
                    <div key={file.id} className="group bg-white border border-[#E5E7EB] p-3 hover:border-black transition-all flex justify-between items-center">
                      <div className="flex items-center gap-3 truncate flex-1">
                        <Binary className="w-4 h-4 text-[#9CA3AF] flex-shrink-0" />
                        <div className="truncate">
                          <span className="text-[13px] truncate font-normal block">{file.name}</span>
                          <span className="text-[10px] text-[#9CA3AF]">{file.size}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteFile(file.name)}
                        className="text-gray-400 hover:text-red-600 transition-colors p-1"
                        title="Delete file"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-[#9CA3AF] italic p-3">No exam papers uploaded</p>
                )}
              </div>
            </section>
          </aside>

          {/* Right Panel: Generation Configuration */}
          <section className="col-span-12 md:col-span-8 lg:col-span-9">
            <div className="bg-white border border-[#E5E7EB] p-8 h-full">
              <div className="flex items-center gap-2 mb-10">
                <Layers className="w-5 h-5" />
                <h2 className="text-sm font-bold uppercase tracking-[0.2em]">Inference Configuration</h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                {/* Topic Multi-Select Picker */}
                <div className="space-y-4 md:col-span-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Tags className="w-4 h-4 text-[#9CA3AF]" />
                      <label className="text-[11px] font-bold uppercase text-[#9CA3AF] tracking-wider block">
                        Target Topics
                      </label>
                      {(loadingTopics || regeneratingTopics) && (
                        <span className="text-[10px] text-[#9CA3AF] italic">
                          {regeneratingTopics ? 'Regenerating…' : 'Loading…'}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={handleRegenerateTopics}
                      disabled={regeneratingTopics || textbooks.length === 0}
                      title={textbooks.length === 0 ? 'Upload a textbook first' : 'Regenerate topics from uploaded textbooks'}
                      className="flex items-center gap-1.5 text-[11px] text-[#9CA3AF] hover:text-black disabled:opacity-30 transition-colors"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${regeneratingTopics ? 'animate-spin' : ''}`} />
                      Regenerate
                    </button>
                  </div>

                  {/* Available topics from DB */}
                  {availableTopics.length > 0 ? (
                    <div className="flex flex-wrap gap-2 pb-2 max-h-36 overflow-y-auto">
                      {availableTopics.map((t) => {
                        const isSelected = selectedTopics.includes(t.name);
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => toggleTopic(t.name)}
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                              isSelected
                                ? 'bg-black text-white border-black'
                                : 'bg-white text-[#374151] border-[#D1D5DB] hover:border-black'
                            }`}
                          >
                            {isSelected && <Check className="w-3 h-3" />}
                            {t.name}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    !loadingTopics && (
                      <p className="text-xs text-[#9CA3AF] italic">
                        No topics extracted yet — upload a textbook to auto-extract topics
                      </p>
                    )
                  )}

                  {/* Custom topic input */}
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        value={customTopic}
                        onChange={(e) => setCustomTopic(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addCustomTopic()}
                        placeholder="Add a custom topic…"
                        className="w-full bg-transparent border-b border-[#E5E7EB] py-2 focus:border-black outline-none transition-colors text-sm pr-8"
                      />
                      <Search className="absolute right-0 top-2 w-4 h-4 text-[#D1D5DB]" />
                    </div>
                    <button
                      type="button"
                      onClick={addCustomTopic}
                      disabled={!customTopic.trim()}
                      className="text-[#9CA3AF] hover:text-black disabled:opacity-30 transition-colors"
                      title="Add custom topic"
                    >
                      <PlusCircle className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Selected topics summary */}
                  {selectedTopics.length > 0 && (
                    <div className="pt-2 border-t border-[#F3F4F6]">
                      <p className="text-[10px] uppercase tracking-wider text-[#9CA3AF] font-bold mb-2">Selected</p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedTopics.map((t) => (
                          <span
                            key={t}
                            className="inline-flex items-center gap-1 bg-black text-white text-xs px-2.5 py-1 rounded-full"
                          >
                            {t}
                            <button
                              type="button"
                              onClick={() => removeSelectedTopic(t)}
                              className="text-white/60 hover:text-white ml-0.5"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Parameters */}
                <div className="grid grid-cols-2 gap-8">
                  <div className="space-y-4">
                    <label className="text-[11px] font-bold uppercase text-[#9CA3AF] tracking-wider block">Complexity</label>
                    <select 
                      value={complexity}
                      onChange={(e) => setComplexity(e.target.value)}
                      className="w-full bg-transparent border-b border-[#E5E7EB] py-2 focus:border-black outline-none transition-colors text-sm appearance-none cursor-pointer"
                    >
                      <option value="easy">Standard</option>
                      <option value="medium">Advanced</option>
                      <option value="hard">Academic</option>
                    </select>
                  </div>
                  <div className="space-y-4">
                    <label className="text-[11px] font-bold uppercase text-[#9CA3AF] tracking-wider block">Quantity</label>
                    <input 
                      type="number" 
                      value={quantity}
                      onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
                      className="w-full bg-transparent border-b border-[#E5E7EB] py-2 focus:border-black outline-none transition-colors text-sm"
                    />
                  </div>
                </div>
              </div>

              <div className="mt-16">
                <button 
                  onClick={triggerInference}
                  disabled={isProcessing || selectedTopics.length === 0}
                  className="w-full bg-black text-white py-4 flex items-center justify-center gap-4 hover:bg-[#2A2A2A] transition-all disabled:bg-[#D1D5DB] group"
                >
                  {isProcessing ? (
                    <span className="flex items-center gap-3">
                      <span className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
                      PROCESSOR_BUSY...
                    </span>
                  ) : (
                    <>
                      <span className="text-sm font-bold uppercase tracking-[0.3em]">Initialize Generation</span>
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              </div>

              {/* Progress Stream Log */}
              {(isProcessing || progressLogs.length > 0) && (
                <div className="mt-8 bg-black text-green-400 p-6 font-mono text-xs rounded-sm border border-gray-800 shadow-xl">
                  <div className="flex justify-between items-center mb-4 border-b border-gray-800 pb-2">
                    <span className="uppercase tracking-widest font-bold flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                      System Logs
                    </span>
                    <span className="text-gray-500">{currentStage.toUpperCase()}</span>
                  </div>
                  <div id="log-container" className="h-64 overflow-y-auto space-y-2 pr-2 scrollbar-thin scrollbar-thumb-gray-700">
                    {progressLogs.length === 0 ? (
                      <span className="text-gray-600 italic">Waiting for process initiation...</span>
                    ) : (
                      progressLogs.map((log, idx) => (
                        <div key={idx} className="flex gap-4 hover:bg-gray-900/50 p-1 rounded">
                          <span className="text-gray-600 flex-shrink-0">[{log.timestamp}]</span>
                          <span className="text-green-400/90 text-[10px] w-16 uppercase">{log.stage}</span>
                          <span className={`${
                            log.stage === 'error' ? 'text-red-400' : 
                            log.stage === 'success' ? 'text-blue-400 font-bold' : 
                            log.stage === 'approve' ? 'text-yellow-400' :
                            'text-gray-300'
                          }`}>
                            {log.message}
                            {isProcessing && idx === progressLogs.length - 1 && (
                              <span className="inline-block w-1.5 h-3 ml-1 bg-green-500 animate-pulse align-middle"></span>
                            )}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>

        {/* Results: Generated Questions */}
        {questions.length > 0 && (
          <div className="mt-12 space-y-12">
            <div className="flex items-center gap-4">
              <div className="h-[1px] flex-grow bg-[#E5E7EB]"></div>
              <span className="text-[11px] font-bold uppercase tracking-[0.5em] text-[#9CA3AF]">Output Stream</span>
              <div className="h-[1px] flex-grow bg-[#E5E7EB] mr-4"></div>
              
              <div className="flex gap-2">
                <button 
                  onClick={handleDownloadExamFormat}
                  className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded transition-colors"
                  title="Download in Exam System Format"
                >
                  <FileJson className="w-3.5 h-3.5" />
                  Exam Format
                </button>
                <button 
                  onClick={handleDownloadJSON}
                  className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium rounded transition-colors"
                  title="Download as JSON"
                >
                  <FileJson className="w-3.5 h-3.5" />
                  JSON
                </button>
                <button 
                  onClick={handleDownloadPDF}
                  className="flex items-center gap-2 px-3 py-1.5 bg-black hover:bg-gray-800 text-white text-xs font-medium rounded transition-colors"
                  title="Download as PDF"
                >
                  <Download className="w-3.5 h-3.5" />
                  PDF
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {questions.map((q) => (
                <QuestionBlock key={q.id} data={q} number={q.id} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// Minimalist Question Component with V2 Multi-Agent Metadata
function QuestionBlock({ data, number }: { data: Question; number: number }) {
  const [revealed, setRevealed] = useState(false);

  // Get quality score color
  const getQualityColor = (score: number) => {
    if (score >= 8) return 'text-green-600 bg-green-50';
    if (score >= 6) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  // Get cognitive level icon
  const getCognitiveIcon = (level: string) => {
    switch (level.toLowerCase()) {
      case 'recall': return 'R';
      case 'application': return 'A';
      case 'analysis': return 'An';
      case 'synthesis': return 'S';
      default: return level[0].toUpperCase();
    }
  };

  return (
    <div className="bg-white border border-[#E5E7EB] hover:border-[#1A1A1A] transition-colors p-8 flex flex-col h-full">
      <div className="flex justify-between items-start mb-6 flex-wrap gap-2">
        <span className="text-[10px] font-black text-white bg-black px-2 py-0.5 tracking-tighter">
          Q_{number.toString().padStart(2, '0')}
        </span>
        <div className="flex items-center gap-2">
          {/* Quality Score Badge */}
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded ${getQualityColor(data.quality_score)}`}>
            QLTY:{data.quality_score}/10
          </span>
          {/* Cognitive Level Badge */}
          <span className="text-[9px] font-bold text-[#6B7280] border border-[#E5E7EB] px-2 py-0.5">
            {getCognitiveIcon(data.cognitive_level)}/{data.cognitive_level.toUpperCase().slice(0, 3)}
          </span>
        </div>
      </div>

      <h4 className="text-[15px] font-medium leading-relaxed mb-8 flex-grow">
        {data.question}
      </h4>

      <div className="space-y-3 mb-10">
        {Object.entries(data.options).map(([key, value]) => {
          const isCorrect = key === data.answer;
          
          return (
            <div 
              key={key} 
              className="flex items-start gap-4 text-sm group cursor-pointer"
            >
              <span className={`w-5 h-5 flex items-center justify-center border text-[10px] font-bold transition-all flex-shrink-0 ${
                isCorrect 
                  ? 'border-green-500 bg-green-50 text-green-700' 
                  : 'border-[#E5E7EB] group-hover:bg-black group-hover:text-white'
              }`}>
                {key}
              </span>
              <span className={`${isCorrect ? 'text-green-700' : 'text-[#6B7280] group-hover:text-black'} transition-colors`}>
                {value}
              </span>
            </div>
          );
        })}
      </div>

      <div className="pt-6 border-t border-[#F3F4F6]">
        <button 
          onClick={() => setRevealed(!revealed)}
          className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[#9CA3AF] hover:text-black transition-colors"
        >
          <Zap className={`w-3 h-3 ${revealed ? 'fill-black text-black' : ''}`} />
          {revealed ? 'Close Analysis' : 'Show Logic & Solution'}
        </button>
        
        {revealed && (
          <div className="mt-4 space-y-4">
            {/* Solution Header */}
            <div className="p-4 bg-[#F9FAFB] border-l-2 border-black">
              <p className="text-[12px] text-[#374151] leading-relaxed italic">
                <span className="font-bold not-italic mr-2 text-black underline">
                  SOLUTION_{data.answer}
                </span>
                {data.explanation}
              </p>
            </div>

            {/* Multi-Agent Metadata Section */}
            <div className="space-y-3">
              {/* Distractor Reasoning */}
              {data.distractor_reasoning.length > 0 && (
                <div className="bg-white border border-[#E5E7EB] rounded p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertCircle className="w-3 h-3 text-[#9CA3AF]" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">
                      Distractor Analysis
                    </span>
                  </div>
                  <div className="space-y-2">
                    {data.distractor_reasoning.filter(r => r.option !== data.answer).map((r) => (
                      <div key={r.option} className="flex gap-2 text-[11px]">
                        <span className="font-bold text-[#9CA3AF] w-4">{r.option}:</span>
                        <span className="text-[#6B7280]">{r.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Source References */}
              {data.source_references.length > 0 && (
                <div className="bg-white border border-[#E5E7EB] rounded p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="w-3 h-3 text-[#9CA3AF]" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">
                      Source References
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {data.source_references.slice(0, 3).map((ref, idx) => (
                      <span key={idx} className="text-[10px] text-[#9CA3AF] bg-[#F9FAFB] px-2 py-0.5 rounded">
                        {ref}
                      </span>
                    ))}
                    {data.source_references.length > 3 && (
                      <span className="text-[10px] text-[#9CA3AF] px-1">
                        +{data.source_references.length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Topic Tag */}
              <div className="flex items-center gap-2">
                <Target className="w-3 h-3 text-[#9CA3AF]" />
                <span className="text-[10px] text-[#9CA3AF]">Topic: <span className="text-[#374151]">{data.topic}</span></span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}