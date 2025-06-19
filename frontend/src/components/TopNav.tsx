import { Link } from "react-router-dom";

export default function TopNav() {
  return (
    <header className="sticky top-0 z-50 w-full flex items-center justify-between px-1 sm:px-4 lg:px-6 py-3 sm:py-4 lg:py-4 border-b border-border bg-background/80 backdrop-blur-md">
      <Link to="/" className="flex items-center space-x-3">
        <img
          src="/logo/Reelix_logo_dark.svg"
          alt="Reelix"
          className="h-10 w-auto"
        />
      </Link>
    </header>
  );
}
