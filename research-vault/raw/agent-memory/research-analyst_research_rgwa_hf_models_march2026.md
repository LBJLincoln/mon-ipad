---
name: RGWA HuggingFace Models Survey March 2026
description: Best-available HF Spaces models per modality (music, voice, video, image, audio tools) as of March 2026, with ZeroGPU status and gradio_client patterns
type: reference
---

# RGWA HuggingFace Models — March 2026 Survey

## Music Generation

### Current: DiffRhythm (ASLP-lab/DiffRhythm) + Foundation-1 (instrumental fallback)

### ACE-Step v1.5 — CLEAR UPGRADE (PRIMARY recommendation)
- Space: `ACE-Step/Ace-Step-v1.5` — Running on ZeroGPU (free)
- Speed: 4-minute song in ~2 seconds on A100 (15–100x faster than DiffRhythm)
- Quality: SongEval 8.09 vs DiffRhythm's 7.61 (6% better overall)
- Features: lyrics sync (50+ languages), vocals + instrumentals, style repainting, LoRA personalization, BPM/key/time-sig control
- Modes: Simple (text), Custom (full params), Remix, Repaint, Cover, Lego, Complete
- API: `client.predict(audio_duration, prompt, lyrics, infer_step, guidance_scale, scheduler_type, cfg_type, seed, use_erg_tag, use_erg_lyric, use_erg_diffusion, api_name="/generate_music")`
- Verdict: Replaces DiffRhythm as primary. Better quality, 10-100x faster, ZeroGPU free.

### LeVo / SongGeneration v2 — HIGH QUALITY ALTERNATIVE
- Space: `tencent/SongGeneration` — ZeroGPU
- Released: 2026-03-01. 4B parameter model (SongGeneration-v2-large)
- Quality: PER 8.55% (beats Suno v5 at 12.4%), professionally evaluated as best open-source vocal quality
- Fast variant: SongGeneration-v2-Fast generates complete song in <1 minute
- Weakness: slower than ACE-Step, heavier model
- Verdict: Use as secondary/fallback for maximum vocal quality when speed not critical

### YuE — KEEP AS TERTIARY
- Space: `fffiloni/YuE` (community) or `innova-ai/YuE-music-generator-demo`
- Apache 2.0 licensed. Full-song up to 5 minutes with lyric alignment
- Speed: Very slow (RTF 0.083x — ~120x slower than ACE-Step)
- Verdict: Retain only for unique use cases (long-form, specific lyric control)

### Stable Audio Open — SOUND EFFECTS/AMBIENT ONLY
- Space: `artificialguybr/Stable-Audio-Open-Zero` — ZeroGPU
- Good for: ambient soundscapes, sound design (not songs/vocals)

## Voice / TTS

### Current: Dia-1.6B (primary) + F5-TTS (fallback)

### Qwen3-TTS — POTENTIAL UPGRADE (best multilingual)
- Space: `Qwen/Qwen3-TTS` — free demo (0.6B and 1.7B variants)
- Faster space: `HuggingFaceM4/faster-qwen3-tts-demo`
- Features: voice cloning (3-second samples), voice design by description, 10 languages, built-in speakers
- Trained on 5M+ hours of speech
- Weakness: slight "anime" quality on some English voices; Chinese is strongest
- Models: Qwen3-TTS-12Hz-0.6B-Base, Qwen3-TTS-12Hz-1.7B-CustomVoice, Qwen3-TTS-12Hz-1.7B-VoiceDesign

### IndexTTS-2 — BEST ZERO-SHOT VOICE CLONING
- Space: `IndexTeam/IndexTTS-2-Demo` — ZeroGPU confirmed (`shawange/MoTTS` for ZeroGPU variant)
- Features: disentangled timbre + emotion control (independent speaker ID from emotion), precise duration control
- Benchmarks: beats CosyVoice2, Fish Speech on WER + speaker similarity + emotional fidelity
- API: upload voice reference + emotion reference separately
- Verdict: Best for voice cloning use cases in RGWA (e.g., consistent character voices)

### Fish Speech 1.5 — KEEP, high quality multilingual
- Model: `fishaudio/fish-speech-1.5` — ELO 1339, WER 3.5% English
- Space: community hosted, check `fishaudio` org spaces

### Dia-1.6B — KEEP as primary (unique multi-speaker dialogue)
- Dia's unique strength is [S1]/[S2] dialogue format — not replicated by others
- Keep as primary for dialogue/narrator content

### MegaTTS 3 (ByteDance) — PAUSED SPACE, SKIP FOR NOW
- Space `mrfakename/MegaTTS3-Voice-Cloning` is currently PAUSED
- WavVAE encoder community-released, but integration complex
- Revisit when Space is active again

## Video Generation

### Current: Wan2.1

### Wan2.2 — DIRECT UPGRADE (use instead of Wan2.1)
- Space: `zerogpu-aoti/wan2-2-fp8da-aoti-faster` (ZeroGPU, FP8 optimized)
- Also: `zerogpu-aoti/wan2-2-fp8da-aoti` and `alexnasa/Wan2.2-Animate-ZEROGPU`
- Model: `Wan-AI/Wan2.2-I2V-A14B` (image-to-video, 14B MoE), `Wan-AI/Wan2.2-TI2V-5B` (text+image, 5B)
- Improvements: MoE architecture, +65.6% images / +83.2% videos in training, cinematic style control
- TI2V-5B: 5-second 720P in <9 min on consumer GPU — fastest 720P@24fps option
- Verdict: Upgrade Wan2.1 → Wan2.2 in SPACE_REGISTRY

### LTX-2.3 — BEST FOR SPEED + NATIVE AUDIO
- Space: `Lightricks/LTX-2-3` — Running on Zero (ZeroGPU confirmed)
- Released: 2026-03-05 (most recent major video model)
- Features: native synchronized audio generation (ambient, SFX, footsteps), 4K capability, 50fps, joint audio-video in single pass
- Paper: arXiv:2601.03233 (LTX-2: Efficient Joint Audio-Visual Foundation Model)
- Speed: faster than Wan2.1, HunyuanVideo, SkyReels
- Quality: slightly below Wan2.2 for pure visual quality; leads on audio integration
- Verdict: Add as secondary for content requiring sound-synced video

### SkyReels V2 — UNLIMITED LENGTH VIDEOS
- Space: `fffiloni/SkyReels-V2` or `svjack/SkyReels-V2`
- Feature: infinite-length video via Diffusion Forcing
- V3 released 2026-01-29: `Skywork/SkyReels-V3` Space with A2V (audio-to-video lipsync), R2V, V2V modes
- SkyReels-V3-A2V-19B: image + audio → lip-sync video at 720p/24fps, multilingual
- Verdict: Add SkyReels V3 for lipsync/character animation use cases

### HunyuanVideo — HIGH QUALITY, HIGH VRAM
- `tencent/HunyuanVideo` — 13B params, 45-80GB VRAM, best for multi-person scenes
- Not practical on ZeroGPU without quantization; skip for now

## Image Generation

### Current: FLUX.1-dev (HF Inference API)

### FLUX.2-dev — MAJOR UPGRADE but heavy
- Space: `black-forest-labs/FLUX.2-dev` — HF official Space
- 32B params (vs FLUX.1's 12B), requires 80GB VRAM full / ~20GB with quantization
- Improvements: Mistral Small 3.1 text encoder, better spatial reasoning, multi-image reference (up to 10), image editing
- License: Non-commercial (same as FLUX.1-dev) — OK for RGWA artistic use
- ZeroGPU: H200 has ~70GB VRAM — borderline; check if Space is queued/free
- Klein variant: `black-forest-labs/FLUX.2-klein-4B` — Apache 2.0, runs on RTX 3090, fastest

### FLUX.2-Klein-4B — FAST FREE OPTION
- Space: `black-forest-labs/FLUX.2-klein-4B` — ZeroGPU
- 4B params, Apache 2.0 (fully open), multi-reference editing without finetuning
- Verdict: Switch HF Inference API calls to FLUX.2-Klein-4B for speed + zero cost; keep FLUX.1-dev as fallback

### FLUX.1-schnell — STILL USEFUL
- Apache 2.0, 1-4 step generation, free
- Space: `black-forest-labs/FLUX.1-schnell` — ZeroGPU

## Audio Editing / Enhancement / Stem Separation

### MMAudio — VIDEO-TO-AUDIO (sound effects sync)
- Space: `hkchengrex/MMAudio` — ZeroGPU
- Generates synchronized audio from video + text prompt
- Use case: add foley/SFX to Wan2.2 or LTX videos that don't have audio

### Spleeter / HT-Demucs — STEM SEPARATION
- Space: `ahk-d/Spleeter-HT-Demucs-Stem-Separation-2025` — drums/bass/vocals/piano
- Space: `r3gm/Audio_separator` — multi-stem

### ClearerVoice-Studio (Alibaba SLAB)
- Space: `alibabasglab/ClearVoice` — speech enhancement, separation, speaker extraction
- Good for: cleaning up voice references before cloning

### Video SoundFX + Sound AI SFX
- `fffiloni/Video-to-SoundFX` — AI describes video → generates matching SFX
- `fantaxy/Sound-AI-SFX` — text-to-SFX

## 3D Generation

### TripoSR — IMAGE TO 3D
- Space: `AleenDG/3DGenTripoSR` / `stabilityai/TripoSR`
- Image upload → 3D mesh (fast feedforward, stability AI)
- Shap-E: text or image → 3D (`hysts/Shap-E`)
- Note: 3D generation not currently in RGWA scope but available

## New Modalities Not Currently in RGWA

1. **Audio-driven lipsync**: SkyReels V3 A2V (19B, `Skywork/SkyReels-V3`) — image + audio → lip-sync video
2. **Video-to-audio Foley**: MMAudio (`hkchengrex/MMAudio`) — generate matching sound for silent video
3. **Music stems**: Spleeter/Demucs for stem separation → remixing capability
4. **Voice design (no reference)**: Qwen3-TTS VoiceDesign — create new voices from text description

## Priority Upgrade List for RGWA space_client.py

Priority 1 (immediate, drop-in replacements):
- Music PRIMARY: DiffRhythm → ACE-Step v1.5 (`ACE-Step/Ace-Step-v1.5`)
- Video PRIMARY: Wan2.1 → Wan2.2 TI2V-5B (`zerogpu-aoti/wan2-2-fp8da-aoti-faster`)
- Image: Add FLUX.2-Klein fallback (`black-forest-labs/FLUX.2-klein-4B`)

Priority 2 (add as new capabilities):
- Music SECONDARY: Add LeVo/SongGeneration v2 (`tencent/SongGeneration`) for vocal quality
- Voice CLONING: Add IndexTTS-2 (`IndexTeam/IndexTTS-2-Demo`) as voice cloning mode
- Video AUDIO: Add LTX-2.3 (`Lightricks/LTX-2-3`) for audio-synced video
- Video LIPSYNC: Add SkyReels V3 A2V (`Skywork/SkyReels-V3`) for lipsync
- Audio SFX: Add MMAudio (`hkchengrex/MMAudio`) for video-to-foley

Priority 3 (enhancement tools):
- Add Qwen3-TTS (`Qwen/Qwen3-TTS`) as multilingual TTS option
- Add ClearerVoice (`alibabasglab/ClearVoice`) for audio enhancement preprocessing
- Add Spleeter/Demucs for stem separation

**Why:** RGWA needs best-in-class models to compete. ACE-Step 1.5 is objectively better than DiffRhythm on both speed and quality. Wan2.2 is a free upgrade with more training data and MoE architecture. LTX-2.3 is the only model offering native joint audio-video generation.
**How to apply:** When updating RGWA space_client.py SPACE_REGISTRY, use these exact space IDs and document API parameter changes in comments.
