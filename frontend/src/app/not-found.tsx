import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white px-6">
      <div className="max-w-md text-center">
        <p className="text-7xl font-bold text-blue-500 mb-4">404</p>
        <h1 className="text-2xl font-bold mb-3">Page Not Found</h1>
        <p className="text-blue-200/60 mb-8 text-sm">The page you&apos;re looking for doesn&apos;t exist or has been moved.</p>
        <Link
          href="/"
          className="px-6 py-3 rounded-xl bg-blue-500 hover:bg-blue-400 text-white font-semibold transition-colors inline-block"
        >
          Go Home
        </Link>
      </div>
    </main>
  );
}
