import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sidebar } from "@/components/layout/Sidebar";
import Dashboard from "./pages/Dashboard";
import NewAnalysis from "./pages/NewAnalysis";
import LivePipeline from "./pages/LivePipeline";
import Report from "./pages/Report";
import Chatbot from "./pages/Chatbot";
import ReportsLibrary from "./pages/ReportsLibrary";
import History from "./pages/History";
import ExecutiveKiosk from "./pages/ExecutiveKiosk";
import NotFound from "./pages/NotFound";
import { TickerBar } from "@/components/layout/TickerBar";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

const queryClient = new QueryClient();

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analyse" element={<NewAnalysis />} />
        <Route path="/pipeline" element={<LivePipeline />} />
        <Route path="/report" element={<Report />} />
        <Route path="/history" element={<History />} />
        <Route path="/chat" element={<Chatbot />} />
        <Route path="/reports" element={<ReportsLibrary />} />
        <Route path="/executive/:reportId" element={<ExecutiveKiosk />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AnimatePresence>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <div className="min-h-screen bg-bg-deep text-text-primary">
            <TickerBar />
            <Sidebar />
            <AnimatedRoutes />
          </div>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
