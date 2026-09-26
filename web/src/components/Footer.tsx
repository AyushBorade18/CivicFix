import { Link } from 'react-router-dom';
import { MapPin, CheckCircle2 } from 'lucide-react';

const ADMIN_URL = import.meta.env.VITE_ADMIN_URL ?? 'http://localhost:5174';

const LINKS: [string, string][] = [
  ['Report a problem', '/citizen/report'],
  ['My reports', '/citizen/my-reports'],
  ['Reported problems', '/citizen/issues'],
  ['How it works', '/#watch'],
];

const PROMISES = [
  'Report in English, Hindi or Marathi — type or speak.',
  'Neighbours reporting the same problem are counted together.',
  'Nothing is marked fixed without a photo from the spot.',
];

export function Footer() {
  return (
    <footer className="bg-muted/80 border-t border-border mt-20 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
          <div className="space-y-4">
            <Link to="/" className="flex items-center space-x-3">
              <div className="relative w-8 h-8">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg transform rotate-12" />
                <div className="absolute inset-0 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg transform -rotate-12" />
                <div className="absolute inset-0 bg-black rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">W</span>
                </div>
              </div>
              <span className="text-xl font-bold text-foreground tracking-tight">WardSentry</span>
            </Link>
            <p className="text-secondary text-sm leading-relaxed">
              Report problems on your street, follow them, and see them fixed. For every ward of Pune.
            </p>
            <div className="flex items-center gap-2 text-xs text-secondary">
              <MapPin className="w-3.5 h-3.5 text-primary" />
              Pune, Maharashtra
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-foreground text-sm uppercase tracking-wider">For residents</h4>
            <ul className="space-y-2 text-sm">
              {LINKS.map(([label, to]) => (
                <li key={to}>
                  {to.includes('#')
                    ? <a href={to} className="text-secondary hover:text-foreground transition-colors">{label}</a>
                    : <Link to={to} className="text-secondary hover:text-foreground transition-colors">{label}</Link>}
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-foreground text-sm uppercase tracking-wider">Our promise</h4>
            <ul className="space-y-2 text-xs text-secondary">
              {PROMISES.map((p) => (
                <li key={p} className="flex items-start gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-border mt-10 pt-6 flex flex-col sm:flex-row justify-between items-center text-xs text-secondary gap-3">
          <p>© {new Date().getFullYear()} WardSentry · Made in Pune, for Pune.</p>
          <a href={ADMIN_URL} className="hover:text-foreground transition-colors">PMC staff sign-in</a>
        </div>
      </div>
    </footer>
  );
}
export default Footer;
