# 🎮 NOMOS42 - PNL AI Agents 3D GAME

[![PNL](https://img.shields.io/badge/PNL-Deux%20Fr%C3%A8res-orange)](https://qlf.fr)
[![Three.js](https://img.shields.io/badge/Three.js-r160-blue)](https://threejs.org)
[![GTA Style](https://img.shields.io/badge/Style-GTA%20VI-ff6b35)](https://rockstargames.com)

> **Une expérience JEU VIDÉO 3D immersive inspirée de GTA VI et de l'univers PNL**
> 
> Conversation animée entre agents IA N.O.S, ADEMO et MONK avec graphismes next-gen

![Game Preview](./docs/preview.png)

## 🌟 Features Jeu Vidéo

### 🎮 Gameplay
- 🏙️ **Environnement 3D ville** avec bâtiments, néons, lampadaires
- 🚶 **Personnages animés** avec respiration et effets visuels
- 📹 **Caméra dynamique** style GTA qui suit les personnages
- 🗺️ **Minimap** interactive avec position des agents
- 💬 **Dialogues style GTA V** avec bulles et animations

### ✨ Effets Next-Gen
- 🌟 **Bloom** avec glow néon
- 🌫️ **SSAO** (Screen Space Ambient Occlusion)
- 📷 **Depth of Field** (profondeur de champ)
- 🌈 **Chromatic Aberration**
- 🌁 **Fog atmosphérique**
- 💧 **Sol réfléchissant** style GTA VI

### 🎨 UI/HUD
- 📊 **Stats panel** (Brier, Accuracy, Features)
- 🗺️ **Minimap** avec dots animés
- 💬 **Dialogue box** style Rockstar Games
- 🎮 **Boutons interactifs** Play/Pause
- 📈 **Barre de progression**

## 🚀 Quick Start

```bash
# Cloner et installer
git clone https://github.com/ton-username/nomos42-pnl-3d.git
cd nomos42-pnl-3d
npm install

# Lancer le jeu
npm run dev

# Build pour production
npm run build
```

## 🎮 Contrôles

| Touche | Action |
|--------|--------|
| ▶ / ⏸ | Play/Pause la conversation |

## 📁 Structure

```
nomos42-pnl-3d/
├── src/
│   ├── App.tsx          # Scène 3D + gameplay
│   ├── App.css          # HUD style GTA
│   └── ...
├── public/
│   ├── nos-character.jpg      # N.O.S (PNL)
│   ├── ademo-character.jpg    # ADEMO (PNL)
│   ├── monk-character.jpg     # Singe DBZ
│   └── environment-bg.jpg     # Ville
└── ...
```

## 🔧 Tech Stack

- **Three.js** - Moteur 3D
- **React Three Fiber** - React renderer pour Three.js
- **Drei** - Helpers R3F
- **Post Processing** - Effets visuels next-gen
- **Vite** - Build tool

## 🎭 Personnages

| Agent | Rôle | Style |
|-------|------|-------|
| **N.O.S** | Strategic Commander | PNL Deux Frères |
| **ADEMO** | Research & Execution | PNL classique |
| **MONK** | Evolution Engine | Singe Dragon Ball Z |

## 🌐 Déploiement Hugging Face

```bash
npm run build
cd dist
git init
git add .
git commit -m "Deploy NOMOS42 Game"
git push https://huggingface.co/spaces/TON_USERNAME/nomos42-pnl main
```

## 📸 Screenshots

| Environnement 3D | HUD | Dialogue |
|------------------|-----|----------|
| ![city](./docs/city.png) | ![hud](./docs/hud.png) | ![dialogue](./docs/dialogue.png) |

## 📝 License

MIT - Libre d'utilisation

---

**QLF** 🌍✌🏽
