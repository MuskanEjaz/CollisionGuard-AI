# Demo Video Plan — CollisionGuard AI

> This document is Suryansh's production plan for the required demo video.
> Maximum duration: 3 minutes (180 seconds).
> Recommended filename: CollisionGuard_AI_Demo.mp4
> Do not record until all branches are merged to main.

---

## Pre-recording checklist

Complete every item before pressing record.

### Environment

- [ ] All branches merged to `main`; working directory is up to date
- [ ] Real 1,000-trial Monte Carlo has been executed and `n_trials=1000` confirmed
- [ ] Pushkar has confirmed Granite status: live OR fallback — decide which path to record
- [ ] `backend/.env` configured (or absent for fallback path — see section below)
- [ ] Backend server is running: `cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- [ ] Frontend server is running: `cd frontend && npm run dev`
- [ ] Dashboard loads at `http://localhost:5173` with no console errors
- [ ] CONJ-001 analysis completes and shows a red "Conjunction Alert" badge
- [ ] SAFE-001 analysis completes and shows a green "Safe separation" badge
- [ ] Approval gate works: selecting a safe candidate, confirming, and seeing "Simulated Execution Complete"
- [ ] Incident report appears after execution

### Screen setup

- [ ] Browser is at 1920x1080 or 2560x1440 (see resolution guidance)
- [ ] Browser zoom level: 100% or 90% (enough to see all cards)
- [ ] Browser window is maximised
- [ ] Developer Tools panel is closed
- [ ] Browser tabs: only `http://localhost:5173` visible
- [ ] Terminal windows are in a separate virtual desktop or hidden
- [ ] No notifications, calendar popups, or system alerts visible
- [ ] Desktop wallpaper is clean and neutral (not distracting)

### Audio

- [ ] Microphone tested — speech is clear and not muffled
- [ ] No background noise (fan, HVAC, street noise minimised)
- [ ] Test recording of 10 seconds reviewed before starting the full take

---

## Start commands (copy-paste)

```powershell
# Terminal 1 — backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Wait for both to be ready before opening the browser.

---

## Script (maximum 3 minutes)

---

### 0:00–0:20 — The problem and the solution

**Action**: Show the CollisionGuard AI dashboard title card (empty state).

**Narration**:
> "More than 27,000 objects orbit Earth today. Every satellite faces hundreds
> of potential conjunction alerts per year. Operators have minutes to evaluate
> geometry, assess risk, and decide whether to command a burn.
>
> CollisionGuard AI is a human-supervised decision-support prototype that
> compresses that decision loop into one dashboard — backed by IBM Granite and
> a deterministic safety gate that Granite cannot override."

---

### 0:20–0:40 — Safe scenario (SAFE-001)

**Action**:
1. Click SAFE-001 scenario button (left or right — whichever is SAFE-001)
2. Click "Run Deterministic Analysis"
3. Wait for the green "Safe separation" badge to appear

**Narration**:
> "Let's start with a normal pass. Scenario SAFE-001 shows our satellite and
> a tracked debris fragment. After SGP4 propagation over a 24-hour window,
> the predicted miss distance is approximately [READ VALUE FROM SCREEN] km —
> well above the 1 km conjunction threshold. Green. No action required.
> The system confirms the all-clear."

**Note**: Read the actual `nominal_miss_distance_km` value from the screen.
Do not pre-script a specific number.

---

### 0:40–1:05 — Critical conjunction (CONJ-001)

**Action**:
1. Click CONJ-001 scenario button
2. Click "Run Deterministic Analysis"
3. Wait for the red "Conjunction Alert" badge

**Narration**:
> "Now a conjunction scenario. CONJ-001: a derelict rocket body approaching
> our satellite. The SGP4 propagator runs a 24-hour search using a coarse
> 30-second grid, then refines to 0.01-second accuracy using Brent's method —
> implemented without any external optimisation library.
>
> The result: miss distance of approximately [READ VALUE] km at time of closest
> approach [READ TCA]. Red alert — below our 1 km threshold. Operator review is required."

---

### 1:05–1:30 — Miss distance, TCA, risk basis, uncertainty

**Action**: Point to the Conjunction Analysis card — the metrics grid and risk basis text.

**Narration**:
> "The dashboard shows miss distance, time to closest approach in UTC, and risk
> classification. Crucially, it also shows the basis for this estimate.
>
> [Read the risk_basis_label text, or paraphrase]: 'Screening-level estimate based on
> two-body propagation. Demonstration Pc based on synthetic covariance.' This
> prototype does not claim to compute a real probability of collision — that would
> require a Conjunction Data Message covariance. We're honest about what the numbers mean.
>
> Below, data quality notes flag that these are synthetic TLEs and that
> J2, drag, and solar-pressure effects are not modelled."

---

### 1:30–1:55 — Maneuver candidates, delta-v, fuel, robustness

**Action**: Scroll to the Maneuver Candidates card.

**Narration**:
> "The deterministic backend has evaluated 5 candidate delta-v maneuvers —
> prograde, retrograde, and out-of-plane burns. Each candidate passes a safety gate:
> delta-v budget check, Tsiolkovsky fuel cost, and post-maneuver miss distance.
>
> [Point to the table] Candidates marked SAFE exceed the 5 km post-maneuver
> threshold and improve on the nominal miss by at least 1 km. Rejected candidates
> show their specific reason.
>
> The baseline score combines miss distance improvement and fuel economy. This
> is a simplified linear weighting — the prototype is transparent about that."

---

### 1:55–2:15 — IBM Granite advisory

**Action**: Scroll to the AI Advisory card.

**Choose one of two narration paths:**

#### Path A — Live Granite is active (source = "granite")

**Narration**:
> "IBM Granite — running on watsonx.ai — has ranked the safe candidates with
> explanations. The live badge shows the model ID: [READ MODEL ID].
>
> Granite received only the backend-validated safe candidates. Its numeric
> values — miss distance, fuel cost — were validated against the backend at 1%
> tolerance before this response was returned. Granite cannot modify those
> numbers and cannot approve execution. It advises. The human decides."

#### Path B — Deterministic fallback (source = "deterministic_fallback")

**Narration**:
> "In this recording, IBM Granite credentials are not configured, so the system
> falls back to deterministic score-based ranking. The fallback badge tells the
> operator exactly what's happening — there's no silent failure.
>
> The architecture ensures that even without Granite, the full decision loop
> runs correctly. When Granite is available, it ranks the same safe candidates
> with AI-generated explanations — but it still cannot override the backend
> physics values or approve execution."

---

### 2:15–2:35 — Human approval and simulated execution

**Action**:
1. Click on a safe candidate in the table (it should highlight)
2. Click "Request Simulated Execution"
3. Read the confirmation dialog aloud
4. Click "Confirm — Simulate Execution"
5. Wait for the "Simulated Execution Complete" panel

**Narration**:
> "I'll select [CANDIDATE LABEL] — [READ DELTA-V, FUEL, POST-MISS FROM SCREEN].
>
> 'Request Simulated Execution.' The system shows a confirmation dialog with the
> delta-v, estimated fuel cost, and post-maneuver miss distance — all from the
> deterministic backend. The dialog also states in yellow: 'This is SIMULATION ONLY —
> not flight software.'
>
> 'Confirm.' The backend validates the candidate safety one more time server-side
> — the UI state is not trusted. Simulated execution complete."

---

### 2:35–2:50 — Post-maneuver verification

**Action**: Point to the execution result panel (delta-v applied, fuel consumed, post-miss).

**Narration**:
> "Post-maneuver verification: delta-v applied [READ VALUE], fuel consumed
> [READ VALUE] kg, post-maneuver miss [READ VALUE] km — all values from the
> deterministic evaluator. The system then generates a simulated incident report
> summarising the scenario, selected maneuver, and advisory source."

**Action**: Point briefly to the incident report text block.

---

### 2:50–3:00 — Closing pitch

**Action**: Scroll back to the top header.

**Narration**:
> "CollisionGuard AI shows how AI advisory intelligence can be integrated into
> a safety-critical workflow — grounded, validated, and always under human control.
>
> As LEO becomes more congested, tools like this could help operators respond to
> conjunction alerts faster, with more information, and with clear accountability.
> This is a simulation prototype — but the architecture and principles are real."

---

## Numbers to highlight during recording

Read these from the actual screen — do not pre-script specific values:

| Item | Location in UI |
|---|---|
| SAFE-001 miss distance (km) | Conjunction Analysis card, Miss Distance metric |
| CONJ-001 miss distance (km) | Same |
| TCA (UTC) | TCA (UTC) metric cell |
| Number of safe candidates | Scenario Selection card: "X/5 safe" |
| Selected candidate delta-v | Confirmation dialog |
| Selected candidate post-miss | Confirmation dialog |
| Post-maneuver miss (verification) | Execution result panel |
| Granite model ID (if live) | Granite badge |

---

## Statements Suryansh must NOT make

These statements are prohibited in the video narration:

- "CollisionGuard AI is an autonomous system"
- "The system will automatically maneuver the satellite"
- "This is flight-ready software"
- "This system can prevent collisions"
- "The probability of collision is [X]%"
- "This analysis is suitable for operational use"
- "Granite approved this maneuver"
- "The system guarantees safe separation"
- "This is a real spacecraft-control system"

---

## Granite live recording path

If Pushkar has confirmed live Granite:

1. Ensure `backend/.env` contains real credentials before starting the backend
2. Confirm the Granite badge shows "IBM Granite — Live" (not "Deterministic fallback")
3. Read the model ID from the badge
4. Use Path A narration for the advisory section
5. If the analysis takes more than 30 seconds, narrate: "The analysis is running —
   IBM Granite is querying watsonx.ai in real time."

Do NOT show the `.env` file or terminal window with credentials during recording.

---

## Fallback recording path

If live Granite is not available (Pushkar confirms unavailability):

1. Remove or leave blank the `WATSONX_*` variables in `.env`
2. Confirm the badge shows "Deterministic fallback — Granite unavailable"
3. Use Path B narration for the advisory section
4. Add a caption/title card: "IBM Granite advisory (live) — confirmed
   separately by Pushkar's smoke test evidence"

The fallback path demonstrates the full workflow and honest system behaviour.

---

## Network/API failure contingency

If the backend stops responding during recording:

1. Do not edit it out — restart if possible and re-record from that segment
2. If the demo shows a "Failed to load scenarios" error, narrate: "The backend
   has stopped — we'll restart and resume." Then restart and continue.
3. If the analysis stalls (> 90 seconds on cache miss), refresh the page and
   try again — the cache will be warm on the second attempt (< 1 second)

---

## Screen resolution recommendation

- Preferred: 1920x1080 full-screen browser
- Alternative: 2560x1440 (scale browser to 90% zoom)
- Avoid: 1366x768 (some cards will wrap awkwardly)
- Test the layout before recording

---

## Cursor and zoom guidance

- Move the cursor deliberately — do not let it wander
- Use the cursor to point at the element being narrated
- Do not use zoom-in tools unless narrating a specific small detail
- If using screen recording software zoom, zoom slowly (not snap)

---

## Audio checklist

- [ ] Microphone gain set so voice peaks at -12 to -6 dB (not clipping)
- [ ] Background noise floor below -50 dB (test in recording software)
- [ ] Use a pop filter or hold the microphone at an angle to avoid plosives
- [ ] No music playing in the background during recording
- [ ] Test recording reviewed before the full take

---

## Editing checklist

- [ ] Trim silence at beginning and end
- [ ] Cut any obvious mistakes (restart segments)
- [ ] Add captions/subtitles (see accessibility section)
- [ ] Add title card at 0:00: "CollisionGuard AI — IBM AI Builders Challenge"
- [ ] Add the disclaimer text overlay at 0:00–0:05:
      "Simulation only — not flight software"
- [ ] If using Path B (fallback): add title card overlay during advisory section:
      "IBM Granite live advisory confirmed separately (Pushkar's evidence)"
- [ ] Review final cut end-to-end before upload

---

## Copyright-safe music guidance

**Recommendation: use no background music.**

The narration is the content. Music competes with it and may trigger
copyright claims on YouTube or Vimeo. If music is desired:
- Use only CC0 / Public Domain tracks from sources such as:
  - Freesound.org (filter by CC0)
  - Free Music Archive (filter by CC0)
  - YouTube Audio Library (check "No attribution required")
- Keep music volume at least 20 dB below narration
- Confirm no platform-specific Content ID claim applies before upload

If in doubt, no music is always the safest choice.

---

## Caption/accessibility checklist

- [ ] Auto-captions enabled on YouTube (if using YouTube) — review for accuracy
- [ ] Manual caption corrections for technical terms:
  - "TCA" — not "TEC" or "TSA"
  - "delta-v" — not "delta V" or "Delti V"
  - "SGP4" — not "SGPF" or "SGP for"
  - "Brent's method" — not "brand's method"
  - "Tsiolkovsky" — not "Shulkowski" (correct as needed)
  - "TEME" — not "team" or "Tammy"
  - "watsonx" — not "Watson X" or "what's on X"
- [ ] Captions are readable on the dark dashboard background
- [ ] No private information in captions

---

## Export settings

| Setting | Value |
|---|---|
| Format | MP4 |
| Codec | H.264 |
| Resolution | 1920x1080 or source resolution |
| Frame rate | 30 fps |
| Bitrate | 6–12 Mbps (sufficient for screen content) |
| Audio codec | AAC 48 kHz stereo |
| Max file size | < 2 GB (well within typical platform limits) |
| Filename | `CollisionGuard_AI_Demo.mp4` |

---

## Maximum duration check

Before upload, confirm:
- `ffprobe CollisionGuard_AI_Demo.mp4 -show_format 2>&1 | Select-String "duration"`
- Value must be <= 180.0 seconds (3:00)
- If over: trim closing silence or tighten one of the slower sections

---

## Public-link permission check

Before including the link in submission materials:
- [ ] Video is publicly accessible without login (not "unlisted" with sharing disabled)
- [ ] Test the link in an incognito browser window
- [ ] Confirm the link does not expire before the challenge judging deadline
- [ ] Do not use a private link or a link requiring a Google/YouTube account

---

## Final video acceptance checklist

- [ ] Duration <= 3:00
- [ ] Title card visible at start
- [ ] Disclaimer "Simulation only — not flight software" shown
- [ ] Both scenarios demonstrated (SAFE-001 and CONJ-001)
- [ ] Approval gate shown end-to-end (idle -> confirming -> done)
- [ ] Execution result and incident report shown
- [ ] Granite source badge visible (live OR fallback clearly labelled)
- [ ] No credential values visible on screen
- [ ] No prohibited statements made
- [ ] Captions present and reviewed
- [ ] Public link verified in incognito window
- [ ] Link provided to Muskan for README and submission copy

---

## Recommended filename

```
CollisionGuard_AI_Demo.mp4
```

This exact filename must be used. It identifies the project and challenge
entry clearly.
