'use client'

import { useState, useRef } from 'react'
import { Upload, FileText, Linkedin, Shield, ArrowRight, X } from 'lucide-react'

interface ResumeUploadProps {
  onContinue: (data: { resumeFile?: File; linkedInConnected?: boolean }) => void
}

export function ResumeUpload({ onContinue }: ResumeUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile && (droppedFile.type === 'application/pdf' || droppedFile.name.endsWith('.doc') || droppedFile.name.endsWith('.docx'))) {
      setFile(droppedFile)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
    }
  }

  const handleLinkedInConnect = () => {
    // In a real app, this would trigger OAuth flow
    onContinue({ linkedInConnected: true })
  }

  const handleContinue = () => {
    if (file) {
      onContinue({ resumeFile: file })
    }
  }

  const removeFile = () => {
    setFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Title */}
      <div className="text-center mb-8">
        <h1 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
          Let's start with your background
        </h1>
        <p className="text-gray-600 text-lg leading-relaxed">
          Upload your resume and we'll do the heavy lifting.
          <br />
          We'll read it the way a great recruiter would — then ask a few quick follow‑ups.
        </p>
      </div>

      {/* Upload Area */}
      <div
        className={`relative border-2 border-dashed rounded-2xl p-8 md:p-10 text-center transition-all duration-200 ${
          isDragging
            ? 'border-primary bg-orange-50'
            : file
            ? 'border-green-300 bg-green-50'
            : 'border-gray-200 hover:border-gray-300 bg-gray-50'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          onChange={handleFileSelect}
          className="hidden"
          id="resume-upload"
        />

        {file ? (
          <div className="flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-4">
              <FileText className="w-8 h-8 text-green-600" />
            </div>
            <p className="font-medium text-gray-900 mb-1">{file.name}</p>
            <p className="text-sm text-gray-500 mb-4">
              {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
            <button
              onClick={removeFile}
              className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-red-600 transition-colors"
            >
              <X className="w-4 h-4" />
              Remove file
            </button>
          </div>
        ) : (
          <>
            <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
              <Upload className="w-8 h-8 text-gray-400" />
            </div>
            <label
              htmlFor="resume-upload"
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors cursor-pointer shadow-lg shadow-orange-500/25 mb-3"
            >
              <Upload className="w-4 h-4" />
              Upload Resume
            </label>
            <p className="text-sm text-gray-500">
              PDF or DOC · Drop file here or click to browse
            </p>
          </>
        )}
      </div>

      {/* Divider */}
      <div className="flex items-center gap-4 my-6">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-sm text-gray-400">or</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      {/* LinkedIn Connect */}
      <button
        onClick={handleLinkedInConnect}
        className="w-full flex items-center justify-center gap-3 px-6 py-3.5 border border-gray-200 rounded-full font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all"
      >
        <Linkedin className="w-5 h-5 text-[#0A66C2]" />
        Connect LinkedIn
      </button>

      {/* Trust Micro-copy */}
      <div className="mt-8 flex items-start gap-3 p-4 bg-gray-50 rounded-xl">
        <Shield className="w-5 h-5 text-gray-400 shrink-0 mt-0.5" />
        <div className="text-sm text-gray-600">
          <p className="font-medium text-gray-700 mb-1">Your data is private</p>
          <p>We don't share your resume with employers. This is only used to improve matching.</p>
        </div>
      </div>

      {/* Continue Button (only show when file is uploaded) */}
      {file && (
        <button
          onClick={handleContinue}
          className="w-full mt-6 px-8 py-4 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 flex items-center justify-center gap-2"
        >
          Continue
          <ArrowRight className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
