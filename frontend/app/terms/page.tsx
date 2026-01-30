'use client'

import Image from 'next/image'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="w-full py-5 px-6 md:px-12 lg:px-20 border-b border-gray-100">
        <nav className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/home" className="flex items-center gap-2">
            <Image
              src="/paper.png"
              alt="Hunt"
              width={32}
              height={32}
              priority
            />
            <span className="text-2xl font-bold text-black font-hunt">
              hunt<span className="text-primary">.</span>
            </span>
          </Link>
          <Link 
            href="/home" 
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-black transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
        </nav>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 md:px-12 py-16 md:py-24">
        <h1 className="font-hunt text-4xl md:text-5xl font-bold text-black mb-4">
          Terms of Service
        </h1>
        <p className="text-gray-500 mb-12">Last updated: January 30, 2026</p>

        <div className="prose prose-gray max-w-none">
          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">1. Acceptance of Terms</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              Welcome to Hunt. By accessing or using our website, mobile application, or any of our services (collectively, the "Services"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, please do not use our Services.
            </p>
            <p className="text-gray-600 leading-relaxed">
              We reserve the right to modify these Terms at any time. We will notify you of any changes by updating the "Last updated" date. Your continued use of the Services after any changes constitutes your acceptance of the new Terms.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">2. Description of Services</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              Hunt provides an AI-powered job matching platform that connects job seekers with employment opportunities. Our Services include:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Job discovery and matching based on your profile and preferences</li>
              <li>Resume analysis and profile building tools</li>
              <li>Job alerts and notifications</li>
              <li>Career-related content and resources</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">3. Account Registration</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              To access certain features of our Services, you may need to create an account. When you create an account, you agree to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Provide accurate, current, and complete information</li>
              <li>Maintain and promptly update your account information</li>
              <li>Keep your password secure and confidential</li>
              <li>Accept responsibility for all activities that occur under your account</li>
              <li>Notify us immediately of any unauthorized use of your account</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">4. User Conduct</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              You agree not to use our Services to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Violate any applicable laws or regulations</li>
              <li>Infringe on the rights of others</li>
              <li>Submit false, misleading, or fraudulent information</li>
              <li>Impersonate any person or entity</li>
              <li>Transmit any viruses, malware, or other harmful code</li>
              <li>Interfere with or disrupt the Services or servers</li>
              <li>Scrape, crawl, or use automated means to access the Services without our permission</li>
              <li>Use the Services for any unauthorized commercial purposes</li>
              <li>Harass, abuse, or harm other users</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">5. User Content</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              You retain ownership of any content you submit to the Services, including your resume, profile information, and other materials ("User Content"). By submitting User Content, you grant us a non-exclusive, worldwide, royalty-free license to use, store, display, and process your User Content solely for the purpose of providing and improving our Services.
            </p>
            <p className="text-gray-600 leading-relaxed">
              You represent and warrant that you have all necessary rights to submit your User Content and that it does not violate any third-party rights or applicable laws.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">6. Intellectual Property</h2>
            <p className="text-gray-600 leading-relaxed">
              The Services, including all content, features, and functionality, are owned by Hunt and are protected by copyright, trademark, and other intellectual property laws. You may not copy, modify, distribute, sell, or lease any part of our Services without our prior written consent.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">7. Third-Party Links and Services</h2>
            <p className="text-gray-600 leading-relaxed">
              Our Services may contain links to third-party websites or services that are not owned or controlled by Hunt. We are not responsible for the content, privacy policies, or practices of any third-party websites or services. You acknowledge and agree that we are not liable for any damage or loss caused by your use of any third-party content.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">8. Disclaimer of Warranties</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              THE SERVICES ARE PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED. WE DISCLAIM ALL WARRANTIES, INCLUDING BUT NOT LIMITED TO:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Merchantability and fitness for a particular purpose</li>
              <li>Accuracy, reliability, or completeness of job listings</li>
              <li>That the Services will be uninterrupted, secure, or error-free</li>
              <li>That any particular job application will result in employment</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">9. Limitation of Liability</h2>
            <p className="text-gray-600 leading-relaxed">
              TO THE MAXIMUM EXTENT PERMITTED BY LAW, HUNT SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS OR REVENUES, WHETHER INCURRED DIRECTLY OR INDIRECTLY, OR ANY LOSS OF DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES, RESULTING FROM YOUR USE OF THE SERVICES.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">10. Indemnification</h2>
            <p className="text-gray-600 leading-relaxed">
              You agree to indemnify, defend, and hold harmless Hunt and its officers, directors, employees, and agents from any claims, damages, losses, liabilities, and expenses (including reasonable attorneys' fees) arising out of or related to your use of the Services, your User Content, or your violation of these Terms.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">11. Termination</h2>
            <p className="text-gray-600 leading-relaxed">
              We may terminate or suspend your account and access to the Services at any time, without prior notice or liability, for any reason, including if you breach these Terms. Upon termination, your right to use the Services will immediately cease. You may also delete your account at any time by contacting us.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">12. Governing Law</h2>
            <p className="text-gray-600 leading-relaxed">
              These Terms shall be governed by and construed in accordance with the laws of the State of California, United States, without regard to its conflict of law provisions. Any disputes arising under these Terms shall be resolved in the courts located in San Francisco County, California.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">13. Severability</h2>
            <p className="text-gray-600 leading-relaxed">
              If any provision of these Terms is found to be unenforceable or invalid, that provision will be limited or eliminated to the minimum extent necessary so that these Terms will otherwise remain in full force and effect.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">14. Entire Agreement</h2>
            <p className="text-gray-600 leading-relaxed">
              These Terms, together with our Privacy Policy, constitute the entire agreement between you and Hunt regarding the use of our Services and supersede any prior agreements.
            </p>
          </section>

          <section>
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">15. Contact Us</h2>
            <p className="text-gray-600 leading-relaxed">
              If you have any questions about these Terms of Service, please contact us through our website.
            </p>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-20 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-gray-500">
            © {new Date().getFullYear()} Hunt. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/privacy" className="text-sm text-gray-600 hover:text-primary transition-colors">
              Privacy Policy
            </Link>
            <Link href="/terms" className="text-sm text-primary font-medium">
              Terms of Service
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
