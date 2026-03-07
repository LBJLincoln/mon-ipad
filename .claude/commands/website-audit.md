Audit a website for UX, GEO, SEO, and conversion optimization.

Arguments: $ARGUMENTS (repo name: rag-website, rag-pme-connectors, or rag-dashboard)

Steps:
1. Read the design brief from `directives/website-design-briefs.md`
2. Read the repo directive from `directives/repos/{repo-name}.md`
3. Check the live site status (curl the Vercel URL)
4. Analyze against the design brief:
   - Color palette compliance (target vs actual)
   - CTA placement and color
   - GEO checklist (TLDR-first, structured data, meta tags)
   - Mobile responsiveness indicators
   - Persona alignment
5. Compare with competitor sites (web search for similar B2B SaaS in France)
6. Output: Structured audit report with:
   - Score /100 per category (UX, GEO, SEO, Brand, Conversion)
   - Top 5 priority fixes with expected impact
   - Code snippets for quick wins (Tailwind color changes, meta tags)
