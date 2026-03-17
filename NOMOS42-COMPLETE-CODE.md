# NOMOS42 - PNL 3D - CODE COMPLET

Ce document contient tout le code nécessaire pour créer le projet NOMOS42 PNL 3D.

## 📁 Structure des fichiers

```
nomos42-pnl-3d/
├── public/
│   ├── ademo-character.jpg
│   ├── nos-character.jpg      (Deux Frères - Sicile)
│   ├── monk-character.jpg     (Singe Dragon Ball Z)
│   ├── environment-bg.jpg     (Sicile)
│   └── live-data.json
├── src/
│   ├── hooks/
│   │   └── useLiveData.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── App.css
│   ├── main.tsx
│   └── index.css
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── eslint.config.js
├── index.html
├── .gitignore
└── README.md
```

---

## 📦 package.json

```json
{
  "name": "nomos42-pnl-3d",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "description": "PNL NOMOS42 - AI Agents 3D Conversation with GTA VI style graphics",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "@react-three/drei": "^9.120.0",
    "@react-three/fiber": "^9.0.0",
    "@react-three/postprocessing": "^2.16.3",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "three": "^0.170.0"
  },
  "devDependencies": {
    "@types/node": "^24.10.1",
    "@types/react": "^19.2.5",
    "@types/react-dom": "^19.2.3",
    "@types/three": "^0.170.0",
    "@vitejs/plugin-react": "^5.1.1",
    "autoprefixer": "^10.4.23",
    "eslint": "^9.39.1",
    "eslint-plugin-react-hooks": "^7.0.1",
    "eslint-plugin-react-refresh": "^0.4.24",
    "globals": "^16.5.0",
    "postcss": "^8.5.6",
    "tailwindcss": "^3.4.19",
    "typescript": "~5.9.3",
    "typescript-eslint": "^8.46.4",
    "vite": "^7.2.4"
  },
  "keywords": ["pnl", "nomos42", "ai-agents", "threejs", "react", "gta-vi", "3d", "webgl"],
  "author": "TON_NOM",
  "license": "MIT"
}
```

---

## ⚙️ vite.config.ts

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          r3f: ['@react-three/fiber', '@react-three/drei'],
        },
      },
    },
  },
  server: {
    port: 3000,
    host: true,
  },
})
```

---

## 📋 tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

---

## 📋 tsconfig.node.json

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

---

## 🔧 eslint.config.js

```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
)
```

---

## 🌐 index.html

```html
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="NOMOS42 - PNL AI Agents 3D Conversation Experience" />
    <meta name="theme-color" content="#0a0a1a" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Rajdhani:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <title>NOMOS42 | PNL AI Agents 3D</title>
    <style>
      body {
        margin: 0;
        padding: 0;
        background: #0a0a1a;
        overflow: hidden;
      }
      #loading {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #0a0a1a;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        transition: opacity 0.5s ease;
      }
      #loading.hidden {
        opacity: 0;
        pointer-events: none;
      }
      #loading h1 {
        font-family: 'Orbitron', sans-serif;
        font-size: 3rem;
        background: linear-gradient(90deg, #00d4ff, #ff00ff, #ff6b35);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: pulse 2s ease-in-out infinite;
      }
      #loading p {
        font-family: 'Rajdhani', sans-serif;
        color: rgba(255,255,255,0.6);
        margin-top: 1rem;
        letter-spacing: 4px;
      }
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }
    </style>
  </head>
  <body>
    <div id="loading">
      <h1>NOMOS42</h1>
      <p>CHARGEMENT...</p>
    </div>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
    <script>
      window.addEventListener('load', () => {
        setTimeout(() => {
          document.getElementById('loading').classList.add('hidden');
        }, 1000);
      });
    </script>
  </body>
</html>
```

---

## 🎨 src/index.css

```css
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --pnl-cyan: #00d4ff;
  --pnl-orange: #ff6b35;
  --pnl-green: #00ff88;
  --pnl-pink: #ff00ff;
  --pnl-gold: #c9a227;
  --pnl-dark: #0a0a1a;
  --pnl-darker: #050510;
  --pnl-panel: rgba(10, 10, 26, 0.95);
  --glow-cyan: 0 0 20px rgba(0, 212, 255, 0.5);
  --glow-orange: 0 0 20px rgba(255, 107, 53, 0.5);
  --glow-green: 0 0 20px rgba(0, 255, 136, 0.5);
  --font-display: 'Orbitron', sans-serif;
  --font-body: 'Rajdhani', sans-serif;
}

html, body, #root {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

body {
  font-family: var(--font-body);
  background: var(--pnl-darker);
  color: white;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: var(--pnl-dark);
}

::-webkit-scrollbar-thumb {
  background: var(--pnl-cyan);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--pnl-pink);
}

::selection {
  background: var(--pnl-cyan);
  color: var(--pnl-darker);
}

:focus-visible {
  outline: 2px solid var(--pnl-cyan);
  outline-offset: 2px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { 
    opacity: 0;
    transform: translateY(20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes glow {
  0%, 100% { box-shadow: var(--glow-cyan); }
  50% { box-shadow: 0 0 40px rgba(0, 212, 255, 0.8); }
}

canvas {
  display: block;
}

.glass {
  background: rgba(10, 10, 26, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.text-gradient {
  background: linear-gradient(90deg, var(--pnl-cyan), var(--pnl-pink), var(--pnl-orange));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

---

## 📄 src/main.tsx

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

---

## 📝 src/types/index.ts

```typescript
export interface Message {
  id: string
  agent: 'N.O.S' | 'ADEMO' | 'MONK'
  content: string
  timestamp: Date | string
  type: 'status' | 'analysis' | 'action' | 'discovery' | 'error'
}

export interface Agent {
  id: string
  name: 'N.O.S' | 'ADEMO' | 'MONK'
  role: string
  image: string
  color: string
  position: [number, number, number]
}

export interface Metrics {
  brier: string
  accuracy: string
  roi: string
  features: string
  generation: string
  population: string
  cycles?: string
  discovered?: string
}

export interface LiveDataPayload {
  agent: string
  message: string
  type: Message['type']
  timestamp: string
  metrics?: Partial<Metrics>
}
```

---

## 🔄 src/hooks/useLiveData.ts

```typescript
import { useState, useEffect, useCallback } from 'react'
import type { Message, LiveDataPayload } from '../types'

interface UseLiveDataOptions {
  url?: string
  mode: 'websocket' | 'polling' | 'json' | 'eventsource'
  pollingInterval?: number
  onMessage?: (message: Message) => void
}

export function useLiveData(options: UseLiveDataOptions) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connectWebSocket = useCallback(() => {
    if (!options.url) {
      setError('URL WebSocket requise')
      return
    }
    const ws = new WebSocket(options.url)
    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
    }
    ws.onmessage = (event) => {
      try {
        const data: LiveDataPayload = JSON.parse(event.data)
        const message: Message = {
          id: Date.now().toString(),
          agent: data.agent as Message['agent'],
          content: data.message,
          timestamp: data.timestamp,
          type: data.type
        }
        setMessages(prev => [...prev, message])
        options.onMessage?.(message)
      } catch (err) {
        console.error('Erreur parsing:', err)
      }
    }
    ws.onerror = () => {
      setError('Erreur WebSocket')
      setIsConnected(false)
    }
    ws.onclose = () => setIsConnected(false)
    return () => ws.close()
  }, [options.url, options.onMessage])

  const startPolling = useCallback(() => {
    if (!options.url) {
      setError('URL API requise')
      return
    }
    const interval = setInterval(async () => {
      try {
        const response = await fetch(options.url!)
        if (!response.ok) throw new Error('API Error')
        const data: LiveDataPayload[] = await response.json()
        const newMessages: Message[] = data.map((item, index) => ({
          id: `${Date.now()}-${index}`,
          agent: item.agent as Message['agent'],
          content: item.message,
          timestamp: item.timestamp,
          type: item.type
        }))
        setMessages(newMessages)
        setIsConnected(true)
        setError(null)
      } catch (err) {
        setError('Erreur API')
        setIsConnected(false)
      }
    }, options.pollingInterval || 2000)
    return () => clearInterval(interval)
  }, [options.url, options.pollingInterval])

  const loadJsonFile = useCallback(async () => {
    try {
      const response = await fetch('/live-data.json')
      if (!response.ok) throw new Error('File not found')
      const data: LiveDataPayload[] = await response.json()
      const loadedMessages: Message[] = data.map((item, index) => ({
        id: `json-${index}`,
        agent: item.agent as Message['agent'],
        content: item.message,
        timestamp: item.timestamp,
        type: item.type
      }))
      setMessages(loadedMessages)
      setIsConnected(true)
    } catch (err) {
      setError('Fichier live-data.json non trouvé')
    }
  }, [])

  useEffect(() => {
    let cleanup: (() => void) | undefined
    switch (options.mode) {
      case 'websocket':
        cleanup = connectWebSocket()
        break
      case 'polling':
        cleanup = startPolling()
        break
      case 'json':
        loadJsonFile()
        break
    }
    return () => cleanup?.()
  }, [options.mode, connectWebSocket, startPolling, loadJsonFile])

  return {
    messages,
    isConnected,
    error,
    addMessage: (message: Omit<Message, 'id'>) => {
      const newMessage = { ...message, id: Date.now().toString() }
      setMessages(prev => [...prev, newMessage])
    },
    clearMessages: () => setMessages([])
  }
}
```

---

## 🎮 src/App.tsx

Voir le fichier complet dans l'archive TAR (trop long pour ce document).

---

## 🎨 src/App.css

Voir le fichier complet dans l'archive TAR (trop long pour ce document).

---

## 📊 public/live-data.json

```json
{
  "messages": [
    {
      "agent": "N.O.S",
      "message": "Status: Gen 0 | Brier 1.0000 | ROI 0.0%",
      "type": "status",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "agent": "ADEMO",
      "message": "Research cycle: deep-diving rest_schedule features",
      "type": "discovery",
      "timestamp": "2024-01-15T10:30:05Z"
    },
    {
      "agent": "MONK",
      "message": "AUTO-FIX applied: population reset",
      "type": "action",
      "timestamp": "2024-01-15T10:30:10Z"
    }
  ],
  "metrics": {
    "brier": "1.0000",
    "accuracy": "0.0%",
    "roi": "—",
    "features": "9",
    "generation": "0",
    "population": "0"
  }
}
```

---

## 🚀 Instructions de déploiement

### 1. Créer le projet
```bash
mkdir nomos42-pnl-3d
cd nomos42-pnl-3d
npm init -y
```

### 2. Copier tous les fichiers
Copier le contenu de ce document dans les fichiers correspondants.

### 3. Installer les dépendances
```bash
npm install
```

### 4. Lancer en développement
```bash
npm run dev
```

### 5. Build pour production
```bash
npm run build
```

### 6. Déployer sur Hugging Face
```bash
cd dist
git init
git add .
git commit -m "Deploy NOMOS42"
git push https://huggingface.co/spaces/TON_USERNAME/nomos42-pnl main
```

---

## 🔌 Connecter les données live

Modifier dans `src/App.tsx`:

```typescript
const DATA_MODE = 'websocket' // ou 'polling', 'json'
const LIVE_DATA_URL = 'wss://ton-worker.hf.space/ws'
```

---

**QLF** 🚀
