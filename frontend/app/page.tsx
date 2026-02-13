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
  FileText
} from 'lucide-react';

type FileItem = {
  id: string;
  name: string;
  size: string;
};

type DistractorReasoning = {
  option: string;
  reason: string;
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
  
  // Form state
  const [topic, setTopic] = useState('');
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

  // Load files from database on mount
  useEffect(() => {
    fetchFiles();
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

      // Refresh file list from database
      await fetchFiles();
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

  // Generate questions using V2 endpoint with multi-agent metadata
  const triggerInference = async () => {
    // Client-side validation
    if (!topic || topic.trim().length < 3) {
      setError('Please enter a topic with at least 3 characters');
      return;
    }

    if (quantity < 1 || quantity > 50) {
      setError('Quantity must be between 1 and 50');
      return;
    }

    setIsProcessing(true);
    setError(null);
    
    try {
      // Use V2 endpoint for full multi-agent metadata
      const response = await fetch('http://localhost:8000/generate/v2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic.trim(), difficulty: complexity, count: quantity }),
      });

      if (!response.ok) {
        const errorData: ErrorResponse = await response.json().catch(() => ({ detail: 'Generation failed' }));
        throw new Error(errorData.detail || 'Failed to generate questions');
      }

      const data: QuestionResponseData[] = await response.json();
      
      if (!data || data.length === 0) {
        throw new Error('No questions generated. Try uploading more textbooks or changing the topic.');
      }
      
      // Map V2 response to frontend format
      const mappedQuestions: Question[] = data.map((q, idx: number) => ({
        id: idx + 1,
        context: "SOURCE: Multi-Agent RAG",
        question: q.question,
        options: q.options,
        answer: q.answer,
        explanation: q.explanation,
        difficulty: q.difficulty,
        // V2 multi-agent metadata
        topic: q.topic || topic.trim(),
        cognitive_level: q.cognitive_level || 'application',
        quality_score: q.quality_score || 7,
        distractor_reasoning: q.distractor_reasoning || [],
        source_references: q.source_references || [],
        quality_checks: q.quality_checks || {}
      }));
      
      setQuestions(mappedQuestions);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Backend connection failed. Make sure the server is running on port 8000.';
      setError(message);
    } finally {
      setIsProcessing(false);
    }
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
                      <div className="flex items-center gap-3 truncate">
                        <Book className="w-4 h-4 text-[#9CA3AF] flex-shrink-0" />
                        <div className="truncate">
                          <span className="text-[13px] truncate font-normal block">{file.name}</span>
                          <span className="text-[10px] text-[#9CA3AF]">{file.size}</span>
                        </div>
                      </div>
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
                      <div className="flex items-center gap-3 truncate">
                        <Binary className="w-4 h-4 text-[#9CA3AF] flex-shrink-0" />
                        <div className="truncate">
                          <span className="text-[13px] truncate font-normal block">{file.name}</span>
                          <span className="text-[10px] text-[#9CA3AF]">{file.size}</span>
                        </div>
                      </div>
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
                {/* Topic Input */}
                <div className="space-y-4">
                  <label className="text-[11px] font-bold uppercase text-[#9CA3AF] tracking-wider block">Target Topic</label>
                  <div className="relative">
                    <input 
                      type="text" 
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="e.g. Distributed Systems Architecture"
                      className="w-full bg-transparent border-b border-[#E5E7EB] py-2 focus:border-black outline-none transition-colors text-sm"
                    />
                    <Search className="absolute right-0 top-2 w-4 h-4 text-[#D1D5DB]" />
                  </div>
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
                  disabled={isProcessing || !topic}
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
            </div>
          </section>
        </div>

        {/* Results: Generated Questions */}
        {questions.length > 0 && (
          <div className="mt-12 space-y-12">
            <div className="flex items-center gap-4">
              <div className="h-[1px] flex-grow bg-[#E5E7EB]"></div>
              <span className="text-[11px] font-bold uppercase tracking-[0.5em] text-[#9CA3AF]">Output Stream</span>
              <div className="h-[1px] flex-grow bg-[#E5E7EB]"></div>
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