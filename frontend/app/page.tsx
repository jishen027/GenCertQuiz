'use client';

import { useState, useEffect } from 'react';
import { 
  Book, 
  Binary, 
  Cpu, 
  Plus, 
  Trash2, 
  ArrowRight, 
  Layers, 
  Database,
  Search,
  ShieldCheck,
  Zap,
  Download
} from 'lucide-react';

type FileItem = {
  id: string;
  name: string;
  size: string;
};

type Question = {
  id: number;
  context: string;
  question: string;
  options: { A: string; B: string; C: string; D: string };
  answer: string;
  explanation: string;
  difficulty: string;
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
        const data = await response.json();
        
        // Map database response to frontend format
        const textbookList = data.textbooks.map((file: any, idx: number) => ({
          id: `tb-${idx}`,
          name: file.name,
          size: `${file.chunks} chunks`
        }));
        
        const examList = data.exam_papers.map((file: any, idx: number) => ({
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
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Failed to upload textbook');
      }

      // Refresh file list from database
      await fetchFiles();
    } catch (error: any) {
      setError(error.message || 'Backend connection failed. Make sure the server is running on port 8000.');
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
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Failed to upload exam paper');
      }

      // Refresh file list from database
      await fetchFiles();
    } catch (error: any) {
      setError(error.message || 'Backend connection failed. Make sure the server is running on port 8000.');
    } finally {
      setUploadingExam(false);
      e.target.value = '';
    }
  };

  // Generate questions
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
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic.trim(), difficulty: complexity, count: quantity }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Generation failed' }));
        throw new Error(errorData.detail || 'Failed to generate questions');
      }

      const data = await response.json();
      
      if (!data || data.length === 0) {
        throw new Error('No questions generated. Try uploading more textbooks or changing the topic.');
      }
      
      // Map backend response to frontend format
      const mappedQuestions: Question[] = data.map((q: any, idx: number) => ({
        id: idx + 1,
        context: "SOURCE: Knowledge Base / RAG",
        question: q.question,
        options: q.options,
        answer: q.answer,
        explanation: q.explanation,
        difficulty: q.difficulty
      }));
      
      setQuestions(mappedQuestions);
    } catch (error: any) {
      setError(error.message || 'Backend connection failed. Make sure the server is running on port 8000.');
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
            <ShieldCheck className="w-3.5 h-3.5" /> Core: GPT-4o-RAG
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

// Minimalist Question Component
function QuestionBlock({ data, number }: { data: Question; number: number }) {
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="bg-white border border-[#E5E7EB] hover:border-[#1A1A1A] transition-colors p-8 flex flex-col h-full">
      <div className="flex justify-between items-start mb-6">
        <span className="text-[10px] font-black text-white bg-black px-2 py-0.5 tracking-tighter">
          Q_{number.toString().padStart(2, '0')}
        </span>
        <span className="text-[10px] font-medium text-[#9CA3AF] tracking-widest uppercase">{data.context}</span>
      </div>

      <h4 className="text-[15px] font-medium leading-relaxed mb-8 flex-grow">
        {data.question}
      </h4>

      <div className="space-y-3 mb-10">
        {Object.entries(data.options).map(([key, value]) => (
          <div 
            key={key} 
            className="flex items-center gap-4 text-sm group cursor-pointer"
          >
            <span className="w-5 h-5 flex items-center justify-center border border-[#E5E7EB] text-[10px] font-bold group-hover:bg-black group-hover:text-white transition-all">
              {key}
            </span>
            <span className="text-[#6B7280] group-hover:text-black transition-colors">{value}</span>
          </div>
        ))}
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
          <div className="mt-4 p-4 bg-[#F9FAFB] border-l-2 border-black">
            <p className="text-[12px] text-[#374151] leading-relaxed italic">
              <span className="font-bold not-italic mr-2 text-black underline">
                SOLUTION_{data.answer}
              </span>
              {data.explanation}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
