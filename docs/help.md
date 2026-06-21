# User manual — CONTROLADORF

Guide for RF operators and production staff.

---

## 1. What it is for

CONTROLADORF helps you **manage wireless inventory** for your show and **monitor frequencies live**:

- Store mics, IEMs, intercoms, and frequencies in a **project**.
- Import lists from **Shure Wireless Workbench**.
- View the **real-time spectrum** and get **warnings** when a carrier degrades.

---

## 2. Getting started

1. **File → New** or **Open** — choose or create a project (`.crf`).
2. In **RF Inventory**, review or add channels (name, frequency, model, zone…).
3. **File → Save** — save often during setup.
4. Switch modules with the top tabs: **Inventory**, **Monitor**, etc.

**Workspace:** under **Tools → Workspaces** you can save panel layouts (sizes and visibility) for different workstations.

---

## 3. RF Inventory

| Task | How |
|------|-----|
| New channel | New button or **Ctrl+N** |
| Edit | Select row and **F2**, or Properties panel |
| Duplicate | **Ctrl+D** |
| Delete | **Del** |
| Apply changes | **Ctrl+S** in properties |
| Undo edit | **Esc** |

You can show/hide columns and export inventory from the actions panel.

---

## 4. Monitor — overview

In the **Monitor** module:

1. Set the **source** (SDR radio) in the side panel.
2. Press **Play** on the top bar to start capture.
3. Adjust **center frequency**, **span**, and gains as needed.
4. Use **Analyzer** for spectrum/waterfall or **SDR** to listen to demodulated audio.

Inventory **markers** can appear on the spectrum when supervision is enabled.

---

## 5. Supervision and alarms (summary)

**Supervision** checks that each inventory channel keeps an acceptable signal compared to local noise.

**Requirements:** open project, loaded inventory, and **Play** running.

| Action | Where |
|--------|--------|
| View channel status | **Alarms** panel → **View events** (or **F3**) |
| Thresholds (when to warn) | **Thresholds…** or **F5** |
| Acknowledge one alarm | Right-click channel → **Acknowledge**, or **F9** |
| Acknowledge all | Supervision toolbar or **F4** |
| History | **F6** |
| Report for records | **F7** (text with times and duration) |
| Locate on spectrum | Select channel and **F8** |

Full guide: **Help → Monitor supervision**.

---

## 6. Useful shortcuts (Monitor active)

| Key | Function |
|-----|----------|
| **F1** | Supervision help |
| **F2** | Start / stop capture |
| **F3** | Supervision window |
| **F4** | Acknowledge all alarms |
| **F5** | Thresholds |
| **F6** | History |
| **F7** | Export report |
| **F8** | Locate channel |
| **F9** | Acknowledge selected channel |
| **F10** | Manual sweep trigger |

---

## 7. Everyday tips

- **Save the project** before rehearsals and before closing the app.
- If you see no alarms, check that **Play** is running and the channel is not unsupervised (struck-through text in the tree).
- More **specific thresholds** (single channel) override general project defaults.
- To change language: **Tools → Settings → Language**.

---

## 8. More help

- **Help → User manual** — this document.
- **Help → Monitor supervision** — alarms, thresholds, and reports.
- **Help → About…** — application version.

*© CONTROLADORF — J. Alberto Velasco*
