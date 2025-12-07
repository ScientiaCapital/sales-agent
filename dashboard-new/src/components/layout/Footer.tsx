export function Footer() {
  return (
    <footer className="border-t bg-slate-50">
      <div className="container mx-auto px-4 py-6">
        <div className="flex flex-col items-center gap-4 text-center">
          {/* Ataturk Quote */}
          <blockquote className="max-w-2xl text-sm text-muted-foreground italic">
            &ldquo;The truest guide in life is science and wisdom.&rdquo;
            <footer className="mt-1 text-xs not-italic">
              &mdash; Mustafa Kemal Ataturk
            </footer>
          </blockquote>

          {/* Divider */}
          <div className="w-16 border-t border-[var(--turkish-blue)]/30" />

          {/* Bottom Row */}
          <div className="flex flex-col sm:flex-row items-center gap-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="text-lg">🧿</span>
              Sales Agent Dashboard
            </span>
            <span className="hidden sm:inline">&bull;</span>
            <span>Signal over noise. Quality over quantity.</span>
            <span className="hidden sm:inline">&bull;</span>
            <span>Powered by Cerebras &amp; Claude</span>
          </div>

          {/* Version */}
          <p className="text-xs text-muted-foreground/60">
            v1.0.0-mvp &bull; Built with Next.js 15 &amp; shadcn/ui
          </p>
        </div>
      </div>
    </footer>
  );
}
