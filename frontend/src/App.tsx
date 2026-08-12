import { Link, Route, Routes } from "react-router-dom";

import { AllListingsPage } from "./pages/AllListingsPage.tsx";
import { SingleListingPage } from "./pages/SingleListingPage.tsx";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          Tenant<span>Bestie</span>
        </Link>
        <p className="tagline">Search by how a flat actually lives</p>
      </header>

      <Routes>
        <Route path="/" element={<AllListingsPage />} />
        <Route path="/listing/:id" element={<SingleListingPage />} />
        <Route path="*" element={<p className="state">Page not found.</p>} />
      </Routes>
    </div>
  );
}