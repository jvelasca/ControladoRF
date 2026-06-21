# Help — RF Supervision

Guide for the **Monitor → Supervision** operator.

---

## 1. What supervision does

Checks **all inventory channels** while the spectrum is running:

- Measures signal quality (SNR) at each channel’s frequency.
- Shows **warning** or **critical alarm** when signal drops below thresholds.
- Lets you **acknowledge** incidents and review **history**.
- Produces **reports** for your records (CSV or text).

**Requires:** open project, channels in inventory, and **Play** active.

---

## 2. Supervision window (F3)

Open from the **Alarms** panel → **View events**, or press **F3**.

### Top toolbar

| Button | Purpose |
|--------|---------|
| Floating window | Tree in a separate window |
| Thresholds | Warning/critical rules (**F5**) |
| Group | Tree order (zone, type, model…) |
| Locate | Center spectrum on channel (**F8**) |
| REC | Start/stop log session |
| Clock | REC session start time and duration |
| Settings | Log folders and trigger modes |
| Open last log | View CSV and folder of last session |
| (i) | Context help for this panel |

### Channel tree

- **Click** a channel → highlights on spectrum (does not move span).
- **Locate (F8)** → centers spectrum on channel or branch.
- **Right-click** → supervise, acknowledge, thresholds, export/view log.
- **Unsupervised** channels appear dimmed.

---

## 3. Alarms panel (side)

Compact toolbar: floating window · thresholds · group · locate · **REC** · clock · settings · open last log · (i) help.

- **Floating window (F3):** supervision tree detached from the side panel.
- **Thresholds (F5):** warning/critical rules by project, zone, type, or channel.
- **Group:** tree grouping (zone, manufacturer, model…).
- **Locate (F8):** centers spectrum on selection (tree click alone only highlights).
- **REC:** starts or stops a log session (dedicated folder with CSV, TXT, metadata).
- **Clock:** start time and elapsed duration; after stop, last session summary.
- **Settings (gear):** log/export folders, CSV trigger, and REC start (manual or on Play).
- **Open last log:** CSV viewer and folder in file explorer.

Tree context menu: supervise, acknowledge, scope thresholds, export/view filtered log.

---

## 4. Application status bar

Permanent bottom zone (with project path and workspace):

| Element | Purpose |
|---------|---------|
| **Green (n)** | OK channels — click opens alarms |
| **Orange (n)** | Warnings and minor — click opens alarms |
| **Red (n)** | Critical — click opens alarms |
| **REC** | Same control as in the Alarms panel |
| **Clock** | Active REC session or last closed session |
| **Open** | Last supervision log session |
| **Gear** | Log settings |

Counts appear in parentheses next to each color dot.

---

## 5. REC logging and CSV

Each REC session creates a subfolder with:

- `alarms.csv` — live events (transitions, ack…).
- `report.txt` — readable report when the session stops.
- `session.json` — metadata (start, end, duration, event count).

**REC start:** manual (REC button) or automatic on **Play** (configurable).

**CSV trigger:** REC only, on Play, or automatic while the engine runs (configurable).

REC can run **without Play**; the folder is created empty until capture starts.

Default paths: custom folder → `{project}/logs/supervision/` → Documents.

---

## 6. Thresholds — when alarms trigger

Thresholds compare signal **to local noise**, not absolute dBm.

| Level | Typical meaning (defaults) |
|-------|----------------------------|
| **Warning** | Signal barely above noise (≈ 6 dB) |
| **Critical** | Very weak signal (≈ 3 dB above noise) |

You can set different values for:

- The whole **project** (default).
- A **zone** (stage, FOH…).
- A **device type** (microphone, IEM…).
- A **manufacturer** or **model**.
- A single **channel**.

Practical rule: the most specific setting wins (a single channel overrides general defaults).

In the threshold dialog, **Reset to inherited** restores values from the level above.

---

## 7. Alarm states

| State | Meaning | What to do |
|-------|---------|------------|
| **Active warning** | Signal low now | Check TX, antenna, distance, interference |
| **Active critical** | Very weak or missing signal | Urgent action on that channel |
| **Latched** | Signal recovered but incident logged | **Acknowledge** after reviewing cause |
| **Acknowledged** | Operator confirmed the incident | No pending action |

**Acknowledge** does not fix RF by itself — it confirms you have seen and handled the incident.

---

## 8. History and export (F6 / F7)

**History:** filter by severity, phase, or text. See time, channel, event type, and detail.

**Export:**

- **CSV** — detailed list (one row per event).
- **TXT (report)** — summary by **incidents** with start, end, duration, and cause. Useful for show logs.

---

## 9. Keyboard shortcuts (Monitor active)

| Key | Function |
|-----|----------|
| **F1** | This help |
| **F2** | Play / Stop |
| **F3** | Supervision window |
| **F4** | Acknowledge all |
| **F5** | Thresholds |
| **F6** | History |
| **F7** | Export TXT report |
| **F8** | Locate channel |
| **F9** | Acknowledge selected channel |
| **F10** | Manual sweep trigger |

---

## 10. Troubleshooting

| Issue | Check |
|-------|--------|
| No alarms | Play active? Channel supervised? Correct frequency in inventory? |
| Thresholds unchanged | Saved in dialog? Edited correct scope (channel vs project)? |
| Empty history | Any incidents occurred? Project saved? |
| F8 / F9 no action | Open window (**F3**) and select a channel in the tree |
| Empty export | Clear filters in history or widen date range |
| REC with no events | Was Play active during the session? Supervised channels with incidents? |
| Cannot open last log | At least one REC session must exist (active or closed) |

---

*ControladoRF — RF Supervision*
