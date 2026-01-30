import React, { useRef, useState, useEffect } from 'react';
import { Check, X, ChevronRight } from 'lucide-react';

const ComparisonTable = () => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollHint, setShowScrollHint] = useState(false);

  const checkScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
      // Show hint if there's content to scroll to and we haven't scrolled much yet
      const canScrollRight = scrollWidth > clientWidth;
      const isScrolledEnd = Math.ceil(scrollLeft + clientWidth) >= scrollWidth;
      const isScrolledStart = scrollLeft < 20; // Only show when near start
      
      setShowScrollHint(canScrollRight && !isScrolledEnd && isScrolledStart);
    }
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, []);

  const features = [
    {
      title: "The Goal",
      hunt: "Get You Hired",
      others: "Sell Ads & Engagement",
      isHuntBetter: true
    },
    {
      title: "Matching",
      hunt: "Context Analysis",
      others: "Keyword Search",
      isHuntBetter: true
    },
    {
      title: "Quality",
      hunt: "Verified & Active",
      others: "Often Stale / Fake",
      isHuntBetter: true
    },
    {
      title: "Experience",
      hunt: "Zero Distractions",
      others: "Influencers & Spam",
      isHuntBetter: true
    },
    {
      title: "Apply",
      hunt: "Direct to Company",
      others: "Resume Black Hole",
      isHuntBetter: true
    }
  ];

  return (
    <div className="w-full max-w-5xl mx-auto py-16 px-4 md:px-6">
      <div className="text-center mb-10 md:mb-16">
        <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-black mb-6 font-hunt">
          Why we built <span className="font-hunt">hunt<span className="text-primary">.</span></span>
        </h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          We built Hunt to get you hired. We prioritize the candidate experience by ensuring you see the best roles based on merit, not just who paid for visibility.
        </p>
      </div>
      
      <div className="border border-gray-200 rounded-xl shadow-sm bg-white overflow-hidden relative">
        <div 
          ref={scrollContainerRef}
          onScroll={checkScroll}
          className="overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']"
        >
          <div className="min-w-[600px] grid grid-cols-[140px_1fr_1fr] divide-y divide-gray-100">
            {/* Header */}
            <div className="contents">
              <div className="px-4 py-6 md:p-5 flex items-center font-semibold text-gray-500 text-sm md:text-base bg-gray-50/50">
                Feature
              </div>
              
              <div className="px-4 py-6 md:p-5 relative flex items-center bg-orange-50 border-x border-orange-100/50">
                <div className="flex items-center gap-2">
                    <span className="font-bold text-lg md:text-xl text-black font-hunt">hunt<span className="text-primary">.</span></span>
                </div>
              </div>
              
              <div className="px-4 py-6 md:p-5 flex items-center font-semibold text-gray-500 text-sm md:text-base bg-gray-50/50">
                LinkedIn / Indeed
              </div>
            </div>

            {/* Rows */}
            {features.map((feature, index) => (
              <div key={index} className="contents group">
                <div className="px-4 py-6 md:p-5 flex items-center font-medium text-gray-600 text-sm bg-white group-hover:bg-gray-50/30 transition-colors">
                  {feature.title}
                </div>
                
                <div className="px-4 py-6 md:p-5 flex items-center bg-orange-50/40 border-x border-orange-100/50 group-hover:bg-orange-50/60 transition-colors">
                  <div className="flex items-center gap-3 text-gray-900">
                    <div className="shrink-0 text-green-500">
                      <Check className="w-4 h-4 md:w-5 md:h-5" strokeWidth={4} />
                    </div>
                    <span className="font-bold text-sm md:text-base leading-tight">{feature.hunt}</span>
                  </div>
                </div>
                
                <div className="px-4 py-6 md:p-5 flex items-center text-gray-500 bg-white group-hover:bg-gray-50/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="shrink-0 text-red-500">
                      {feature.isHuntBetter ? <X className="w-4 h-4 md:w-5 md:h-5" strokeWidth={3} /> : <Check className="w-4 h-4 md:w-5 md:h-5" />}
                    </div>
                    <span className="text-sm md:text-base leading-tight">{feature.others}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Scroll Hint Overlay */}
        <div 
          className={`absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-white to-transparent pointer-events-none flex items-center justify-end pr-4 transition-opacity duration-300 md:hidden ${
            showScrollHint ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <div className="w-8 h-8 rounded-full bg-white shadow-md border border-gray-100 flex items-center justify-center animate-bounce-horizontal text-primary">
            <ChevronRight size={20} />
          </div>
        </div>
      </div>
    </div>
  );
};

export { ComparisonTable };
