'use client'

import Image from 'next/image'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

export default function PrivacyPage() {
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
          Privacy Policy
        </h1>
        <p className="text-gray-500 mb-12">Last updated: January 30, 2026</p>

        <div className="prose prose-gray max-w-none">
          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">1. Introduction</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              Welcome to Hunt ("we," "our," or "us"). We are committed to protecting your personal information and your right to privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our website and services.
            </p>
            <p className="text-gray-600 leading-relaxed">
              Please read this privacy policy carefully. If you do not agree with the terms of this privacy policy, please do not access the site or use our services.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">2. Information We Collect</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              We collect information that you provide directly to us, including:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
              <li><strong>Account Information:</strong> When you create an account, we collect your name, email address, and password.</li>
              <li><strong>Profile Information:</strong> Information you provide in your profile, including your resume, work history, skills, education, and career preferences.</li>
              <li><strong>Resume Data:</strong> When you upload your resume, we process and store the information contained within it to provide job matching services.</li>
              <li><strong>Communications:</strong> When you contact us, we collect information you provide in your messages.</li>
            </ul>
            <p className="text-gray-600 leading-relaxed mb-4">
              We also automatically collect certain information when you use our services:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li><strong>Usage Data:</strong> Information about how you interact with our services, including pages viewed, features used, and search queries.</li>
              <li><strong>Device Information:</strong> Information about the device you use to access our services, including device type, operating system, and browser type.</li>
              <li><strong>Log Data:</strong> Server logs that may include your IP address, access times, and referring URLs.</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">3. How We Use Your Information</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              We use the information we collect to:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>Provide, maintain, and improve our job matching services</li>
              <li>Match your profile with relevant job opportunities</li>
              <li>Send you notifications about job matches and account updates</li>
              <li>Respond to your comments, questions, and support requests</li>
              <li>Analyze usage patterns to improve our services</li>
              <li>Detect, prevent, and address technical issues and security threats</li>
              <li>Comply with legal obligations</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">4. Information Sharing</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              We do not sell your personal information. We may share your information in the following circumstances:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li><strong>With Your Consent:</strong> We may share information when you direct us to do so.</li>
              <li><strong>Service Providers:</strong> We may share information with third-party vendors who perform services on our behalf, such as hosting, analytics, and customer support.</li>
              <li><strong>Legal Requirements:</strong> We may disclose information if required by law or in response to valid legal requests.</li>
              <li><strong>Business Transfers:</strong> If we are involved in a merger, acquisition, or sale of assets, your information may be transferred as part of that transaction.</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">5. Data Security</h2>
            <p className="text-gray-600 leading-relaxed">
              We implement appropriate technical and organizational security measures to protect your personal information against unauthorized access, alteration, disclosure, or destruction. However, no method of transmission over the Internet or electronic storage is 100% secure, and we cannot guarantee absolute security.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">6. Data Retention</h2>
            <p className="text-gray-600 leading-relaxed">
              We retain your personal information for as long as your account is active or as needed to provide you services. You may request deletion of your account and associated data at any time by contacting us through our website.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">7. Your Rights</h2>
            <p className="text-gray-600 leading-relaxed mb-4">
              Depending on your location, you may have certain rights regarding your personal information, including:
            </p>
            <ul className="list-disc pl-6 text-gray-600 space-y-2">
              <li>The right to access your personal information</li>
              <li>The right to correct inaccurate information</li>
              <li>The right to delete your personal information</li>
              <li>The right to data portability</li>
              <li>The right to opt out of certain data processing</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">8. Cookies and Tracking</h2>
            <p className="text-gray-600 leading-relaxed">
              We use cookies and similar tracking technologies to collect information about your browsing activities. You can control cookies through your browser settings, though disabling cookies may affect your ability to use certain features of our services.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">9. Children's Privacy</h2>
            <p className="text-gray-600 leading-relaxed">
              Our services are not intended for individuals under the age of 16. We do not knowingly collect personal information from children. If you believe we have collected information from a child, please contact us immediately.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">10. Changes to This Policy</h2>
            <p className="text-gray-600 leading-relaxed">
              We may update this privacy policy from time to time. We will notify you of any changes by posting the new privacy policy on this page and updating the "Last updated" date. We encourage you to review this policy periodically.
            </p>
          </section>

          <section>
            <h2 className="font-hunt text-2xl font-bold text-black mb-4">11. Contact Us</h2>
            <p className="text-gray-600 leading-relaxed">
              If you have any questions about this Privacy Policy or our privacy practices, please contact us through our website.
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
            <Link href="/privacy" className="text-sm text-primary font-medium">
              Privacy Policy
            </Link>
            <Link href="/terms" className="text-sm text-gray-600 hover:text-primary transition-colors">
              Terms of Service
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
