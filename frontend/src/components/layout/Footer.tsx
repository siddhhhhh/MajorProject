import Link from "next/link";
import { ShieldCheck } from "lucide-react";

export default function Footer() {
  return (
    <footer className="bg-neutral-900 text-white pt-16 pb-8 border-t border-neutral-800">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
          <div className="md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 bg-primary-600 rounded-md flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-white" />
              </div>
              <span className="font-heading font-semibold text-lg tracking-tight">
                ESG Intelligence
              </span>
            </Link>
            <p className="text-sm text-neutral-400 leading-relaxed">
              Advanced AI platform for detecting greenwashing and analyzing corporate sustainability claims with regulatory intelligence.
            </p>
          </div>
          
          <div>
            <h4 className="font-heading font-semibold mb-4 text-neutral-100">Platform</h4>
            <ul className="space-y-3 hidden-scrollbar">
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">AI Agents</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Carbon Accounting</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Regulatory Scanner</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Explainability</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-heading font-semibold mb-4 text-neutral-100">Resources</h4>
            <ul className="space-y-3">
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Documentation</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">API Reference</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Case Studies</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Blog</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-heading font-semibold mb-4 text-neutral-100">Legal</h4>
            <ul className="space-y-3">
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Privacy Policy</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Terms of Service</Link></li>
              <li><Link href="#" className="text-sm text-neutral-400 hover:text-primary-400 transition-colors">Security</Link></li>
            </ul>
          </div>
        </div>
        
        <div className="border-t border-neutral-800 pt-8 flex flex-col md:flex-row items-center justify-between">
          <p className="text-sm text-neutral-500 mb-4 md:mb-0">
            © {new Date().getFullYear()} ESG Intelligence Platform. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center hover:bg-primary-900 transition-colors cursor-pointer">
              <span className="sr-only">Twitter</span>
              <svg className="w-4 h-4 text-neutral-400" fill="currentColor" viewBox="0 0 24 24"><path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"/></svg>
            </div>
            <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center hover:bg-primary-900 transition-colors cursor-pointer">
              <span className="sr-only">LinkedIn</span>
              <svg className="w-4 h-4 text-neutral-400" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
