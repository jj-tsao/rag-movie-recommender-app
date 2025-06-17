import { Routes, Route, useLocation } from "react-router-dom";
import TopNav from "./components/TopNav";
import Home from "./components/Home";

export default function App() {
  const location = useLocation();

  return (
    <>
      <TopNav />
      <Routes location={location} key={location.key}>
        <Route path="/" element={<Home />} />
      </Routes>
    </>
  );
}
