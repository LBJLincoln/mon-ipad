# Live Pipeline Monitoring Dashboard

This directory contains the source for the live monitoring dashboard deployed to Vercel.

## Deployment
- **Repository**: https://github.com/LBJLincoln/rag-dashboard
- **Live URL**: https://nomos-dashboard-alexis-morets-projects.vercel.app
- **Platform**: Vercel (static site, auto-deploy)

## Local File
- `index.html` - Single-file dashboard (24.7 KB, no dependencies)

## Features
- Real-time pipeline status (Standard, Graph, Quantitative, Orchestrator)
- Auto-refresh every 30 seconds
- Live webhook health checks
- Infrastructure monitoring
- Accuracy tracking with visual progress bars
- Dark theme, responsive design

## Data Sources
1. GitHub raw: `docs/status.json` and `docs/data.json`
2. HF Space: Live webhook pings with 8s timeout

## To Update Dashboard
1. Edit `dashboard/index.html` in this repo
2. Push to rag-dashboard repo:
   ```bash
   git worktree add /tmp/rag-dashboard-worktree rag-dashboard/main
   cp dashboard/index.html /tmp/rag-dashboard-worktree/index.html
   cd /tmp/rag-dashboard-worktree
   git add index.html
   git commit -m "Update dashboard"
   git push origin main
   git worktree remove /tmp/rag-dashboard-worktree --force
   ```
3. Vercel auto-deploys within 1-2 minutes

## Technical
- Pure HTML/CSS/JS (no build step)
- ES6+ (async/await, fetch API, AbortController)
- Responsive grid layout
- 30s data refresh, 8s webhook timeout
