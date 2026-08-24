import { Route, Routes } from "react-router-dom";

import Sidebar from "./components/Sidebar";
import Analytics from "./pages/Analytics";
import ApplicationDetail from "./pages/ApplicationDetail";
import Applications from "./pages/Applications";
import AssistantPage from "./pages/AssistantPage";
import Dashboard from "./pages/Dashboard";
import NewApplication from "./pages/NewApplication";
import ReviewerQueue from "./pages/ReviewerQueue";

export default function App() {
  return (
    <div className="min-h-screen bg-ink">
      <Sidebar />
      <main className="ml-60 min-h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/applications/new" element={<NewApplication />} />
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="/reviewer-queue" element={<ReviewerQueue />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/assistant" element={<AssistantPage />} />
        </Routes>
      </main>
    </div>
  );
}
