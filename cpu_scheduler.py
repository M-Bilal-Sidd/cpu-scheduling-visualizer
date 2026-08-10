"""
=============================================================================
  CPU SCHEDULING VISUALIZER  —  "Quantum Stealth" Edition
  A Modern Desktop Application built with CustomTkinter
=============================================================================

  Purpose : Visualize FCFS, SJF (Non-Preemptive), and Round Robin
            scheduling algorithms with animated Gantt charts and
            performance metrics.

  Architecture:
    - CPUScheduler  : Pure logic class — handles ALL algorithm math.
                      Zero GUI code lives here. Fully testable in isolation.
    - GanttCanvas   : A tk.Canvas subclass that draws / animates the Gantt
                      timeline block-by-block, left to right.
    - App           : The main CTk window — all panels, event handlers,
                      and animation orchestration.

  NEW in "Quantum Stealth" Edition:
    - Deeper space-grey palette with 1-px card borders
    - "Populate with Example Processes" one-click demo loader
    - Smooth 150 ms hover-color transitions on all buttons
    - Slow sine-wave heartbeat pulse on the main title
    - Run Simulation button pulses while Gantt animation is in progress
    - Table rows fade in from invisible to full color on every render

  How to run:
    pip install customtkinter
    python cpu_scheduler.py
=============================================================================
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import math
import time

# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 0-A: CUSTOMTKINTER APPEARANCE
# ─────────────────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 0-B: "QUANTUM STEALTH" PALETTE
#  All colors live here — change once, propagates everywhere.
# ─────────────────────────────────────────────────────────────────────────────

BG_DARK        = "#1A1D21"   # Main window — deeper space grey
BG_PANEL       = "#212529"   # Card / panel surface
BG_CARD        = "#2A2E35"   # Inner rows / nested containers
ACCENT         = "#A8E6FF"   # Light blue — all headers & titles
ACCENT_CYAN    = "#00C2FF"   # Cyan — "Add Process" button
ACCENT_GREEN   = "#2EB872"   # Forest green — "Run Simulation" button
ACCENT_AMBER   = "#D29922"   # Amber — moderate waiting-time flag
ACCENT_RED     = "#F85149"   # Red — reset / high WT / errors
TEXT_PRIMARY   = "#E8EDF2"   # Bright body text (slightly lighter than before)
TEXT_MUTED     = "#8B949E"   # Secondary / label text
BORDER_COLOR   = "#2D3238"   # Subtle 1-px card borders

# Hover targets (darker shades of the base button colors)
CYAN_HOVER     = "#009ACC"   # Hover for "Add Process"
GREEN_HOVER    = "#229558"   # Hover for "Run Simulation"
RED_HOVER_BG   = "#3A1C1A"   # Hover background for "Reset" (ghost button)
POPULATE_HOVER = "#1C2E3A"   # Hover background for "Populate" button

# Gantt process colors — 10 vivid, distinct hues tuned for dark backgrounds
GANTT_COLORS = [
    "#00C2FF",  # Cyan
    "#2EB872",  # Forest Green
    "#F0883E",  # Orange
    "#BC8CFF",  # Purple
    "#FF7B72",  # Coral
    "#FFD166",  # Yellow-Gold
    "#79C0FF",  # Sky Blue
    "#56D364",  # Mint
    "#D2A8FF",  # Lavender
    "#FF9E5E",  # Peach
]

# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 0-C: EXAMPLE PROCESS SET
#  10 hand-crafted processes that produce interesting Gantt charts across
#  all three algorithms. Loaded by "Populate with Example Processes".
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLE_PROCESSES = [
    # { pid, arrival, burst }
    # Spread arrivals 0–14 with varied burst lengths (2–12).
    # These values are chosen so that:
    #   • FCFS: straightforward, shows convoy effect clearly
    #   • SJF : picks short jobs P3/P5/P7 early, lowers avg WT
    #   • RR  : lots of context switches — great for explaining preemption
    {"pid": "P1",  "arrival":  0, "burst":  8},
    {"pid": "P2",  "arrival":  2, "burst":  4},
    {"pid": "P3",  "arrival":  3, "burst":  9},
    {"pid": "P4",  "arrival":  4, "burst":  5},
    {"pid": "P5",  "arrival":  6, "burst":  2},
    {"pid": "P6",  "arrival":  7, "burst": 12},
    {"pid": "P7",  "arrival":  8, "burst":  3},
    {"pid": "P8",  "arrival": 10, "burst":  7},
    {"pid": "P9",  "arrival": 12, "burst":  6},
    {"pid": "P10", "arrival": 14, "burst": 10},
]

# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 0-D: COLOR INTERPOLATION UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def lerp_color(c1: str, c2: str, t: float) -> str:
    """
    Linearly interpolate between two hex colors.

    Parameters
    ----------
    c1 : str   starting hex color  (e.g. '#1A1D21')
    c2 : str   ending hex color    (e.g. '#00C2FF')
    t  : float interpolation factor  0.0 → c1,  1.0 → c2

    Returns
    -------
    str  interpolated hex color

    Used for:
      • Smooth button hover transitions
      • Row fade-in animations (text invisible → visible)
      • Header heartbeat pulse (title color oscillates via sine wave)
    """
    # Clamp t to [0, 1] to prevent over/underflow
    t = max(0.0, min(1.0, t))

    # Unpack each RGB channel from the 6-char hex strings
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)

    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)

    return f"#{r:02x}{g:02x}{b:02x}"


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 1: CPU SCHEDULER  (Pure Logic — Zero GUI code)
#  This class is completely independent of the GUI layer.
#  You can import it and test it from any plain Python script.
# ─────────────────────────────────────────────────────────────────────────────

class CPUScheduler:
    """
    Computes CPU scheduling algorithms and returns two data structures:

    gantt_blocks : list[dict]
        Ordered execution segments:  { 'pid': str, 'start': int, 'end': int }
        Suitable for direct Gantt chart rendering.

    results : list[dict]
        Per-process output metrics:
        { 'pid', 'arrival', 'burst', 'completion', 'turnaround', 'waiting' }

    Key OS concepts expressed in the code:
      • Completion Time (CT)  = wall-clock time when a process finishes
      • Turnaround Time (TAT) = CT  − Arrival   (total time in system)
      • Waiting Time (WT)     = TAT − Burst      (time spent in ready queue)
    """

    # ── FCFS ─────────────────────────────────────────────────────────────────
    @staticmethod
    def fcfs(processes):
        """
        First-Come, First-Served (Non-Preemptive).

        Rule: Sort by arrival time. The running process is never interrupted.
        If the CPU is idle (gap between jobs), advance the virtual clock to
        the next arriving process.
        """
        # Sort a copy — never mutate the caller's list
        procs    = sorted(processes, key=lambda p: (p["arrival"], p["pid"]))
        gantt    = []
        results  = []
        time_now = 0    # Virtual CPU clock

        for p in procs:
            # CPU idle gap: jump clock forward to this process's arrival
            if time_now < p["arrival"]:
                time_now = p["arrival"]

            start    = time_now
            end      = time_now + p["burst"]
            time_now = end

            gantt.append({"pid": p["pid"], "start": start, "end": end})

            ct  = end
            tat = ct  - p["arrival"]   # Total time in system
            wt  = tat - p["burst"]     # Time waiting in ready queue

            results.append({
                "pid"        : p["pid"],
                "arrival"    : p["arrival"],
                "burst"      : p["burst"],
                "completion" : ct,
                "turnaround" : tat,
                "waiting"    : wt,
            })

        return gantt, results

    # ── SJF (Non-Preemptive) ─────────────────────────────────────────────────
    @staticmethod
    def sjf(processes):
        """
        Shortest Job First — Non-Preemptive.

        Rule: At each dispatch decision, look at all processes that have
        arrived (arrival ≤ time_now) and select the one with the smallest
        burst time. Ties broken by arrival time, then lexicographic PID.
        The selected process runs to completion before the next dispatch.
        """
        remaining = list(processes)   # Processes still waiting to be scheduled
        gantt     = []
        results   = []
        time_now  = 0

        while remaining:
            # All processes whose arrival time ≤ current clock
            ready = [p for p in remaining if p["arrival"] <= time_now]

            if not ready:
                # CPU is idle — jump to the next process arrival
                time_now = min(p["arrival"] for p in remaining)
                continue

            # Pick the shortest job; tie-break by arrival, then PID
            chosen = min(ready, key=lambda p: (p["burst"], p["arrival"], p["pid"]))
            remaining.remove(chosen)

            start    = time_now
            end      = time_now + chosen["burst"]
            time_now = end

            gantt.append({"pid": chosen["pid"], "start": start, "end": end})

            ct  = end
            tat = ct  - chosen["arrival"]
            wt  = tat - chosen["burst"]

            results.append({
                "pid"        : chosen["pid"],
                "arrival"    : chosen["arrival"],
                "burst"      : chosen["burst"],
                "completion" : ct,
                "turnaround" : tat,
                "waiting"    : wt,
            })

        return gantt, results

    # ── Round Robin ──────────────────────────────────────────────────────────
    @staticmethod
    def round_robin(processes, quantum):
        """
        Round Robin (Preemptive with a fixed time quantum).

        Rule: Maintain a ready queue (FIFO). Each process runs for at most
        `quantum` time units.  If it does not finish in that slice, it goes
        to the tail of the ready queue.  New arrivals are enqueued as the
        virtual clock advances — arrival order within a slice is preserved.

        CPU idle fast-forward: if the queue empties but unvisited processes
        remain, jump the clock to the earliest pending arrival.
        """
        procs           = sorted(processes, key=lambda p: (p["arrival"], p["pid"]))
        remaining_burst = {p["pid"]: p["burst"] for p in procs}
        completion_time = {}   # pid → wall-clock time when finished

        gantt    = []
        time_now = 0
        queue    = []       # Ready queue: ordered list of pid strings
        visited  = set()   # PIDs that have entered the queue at least once

        # ── Inner helper: scan for newly arrived processes and enqueue them ──
        def enqueue_arrivals(current_time, exclude_pid=None):
            """
            Add all processes with arrival ≤ current_time that haven't been
            seen yet.  exclude_pid prevents the currently-running process from
            re-joining mid-slice (it is added explicitly at the slice end if
            it still has burst remaining).
            """
            for p in procs:
                if (p["arrival"] <= current_time
                        and p["pid"] not in visited
                        and p["pid"] != exclude_pid):
                    queue.append(p["pid"])
                    visited.add(p["pid"])

        # Seed queue with any processes already arrived at t=0
        enqueue_arrivals(time_now)

        # If nothing has arrived yet, fast-forward to the first arrival
        if not queue:
            time_now = procs[0]["arrival"]
            enqueue_arrivals(time_now)

        while queue:
            pid = queue.pop(0)                      # Dequeue front process

            run_for = min(quantum, remaining_burst[pid])
            start   = time_now
            end     = time_now + run_for

            gantt.append({"pid": pid, "start": start, "end": end})
            time_now             = end
            remaining_burst[pid] -= run_for

            # Enqueue any processes that arrived during this CPU slice
            enqueue_arrivals(time_now, exclude_pid=pid)

            if remaining_burst[pid] > 0:
                # Process not finished — it goes back to the tail
                queue.append(pid)
            else:
                # Process finished — record completion wall-clock
                completion_time[pid] = time_now

            # CPU idle gap: queue empty but unvisited processes still exist
            if not queue:
                unvisited = [p for p in procs if p["pid"] not in visited]
                if unvisited:
                    time_now = min(p["arrival"] for p in unvisited)
                    enqueue_arrivals(time_now)

        # Build results in the ORIGINAL INPUT order (not scheduling order)
        results = []
        for p in processes:
            ct  = completion_time[p["pid"]]
            tat = ct  - p["arrival"]
            wt  = tat - p["burst"]
            results.append({
                "pid"        : p["pid"],
                "arrival"    : p["arrival"],
                "burst"      : p["burst"],
                "completion" : ct,
                "turnaround" : tat,
                "waiting"    : wt,
            })

        return gantt, results

    # ── Dispatcher ────────────────────────────────────────────────────────────
    @classmethod
    def run(cls, algorithm, processes, quantum=2):
        """
        Main entry point.  Select the correct algorithm and return four values:

        Parameters
        ----------
        algorithm : 'FCFS' | 'SJF' | 'RR'
        processes : list[dict]  { pid, arrival, burst }
        quantum   : int  (used only when algorithm == 'RR')

        Returns
        -------
        gantt_blocks : list[dict]
        results      : list[dict]
        avg_wt       : float   average waiting time across all processes
        avg_tat      : float   average turnaround time across all processes
        """
        if not processes:
            raise ValueError("No processes to schedule.")

        if algorithm == "FCFS":
            gantt, results = cls.fcfs(processes)
        elif algorithm == "SJF":
            gantt, results = cls.sjf(processes)
        elif algorithm == "RR":
            if quantum < 1:
                raise ValueError("Time quantum must be ≥ 1.")
            gantt, results = cls.round_robin(processes, quantum)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        avg_wt  = sum(r["waiting"]    for r in results) / len(results)
        avg_tat = sum(r["turnaround"] for r in results) / len(results)

        return gantt, results, avg_wt, avg_tat


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 2: GANTT CANVAS WIDGET
#  A tk.Canvas subclass.  Call animate() to start a left-to-right sequential
#  block drawing over a target total duration of ~1.5 seconds.
# ─────────────────────────────────────────────────────────────────────────────

class GanttCanvas(tk.Canvas):
    """
    Renders the CPU execution Gantt chart.

    Animation model
    ───────────────
    animate() schedules _draw_block_at(0) which draws one block then
    schedules _draw_block_at(1) via after(), and so on.  The total target
    animation duration is TARGET_ANIM_MS milliseconds, spread evenly across
    all blocks.  When the last block is drawn, _draw_time_labels() is called
    to add the time axis, and the optional on_complete callback is invoked
    so the caller (App) can stop its button-pulse animation.
    """

    TARGET_ANIM_MS = 1500   # Total Gantt animation time in milliseconds
    MIN_BLOCK_MS   = 50     # Minimum delay per block (prevents too-fast flicker)

    TRACK_H   = 56    # Height of the process execution bar (px)
    LABEL_H   = 22    # Height of the time-label row below the bar (px)
    TOP_PAD   = 32    # Vertical padding above the track (px)
    LEFT_PAD  = 12    # Left margin
    RIGHT_PAD = 20    # Right margin

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            bg=BG_PANEL,
            highlightthickness=0,
            **kwargs,
        )
        self._animation_id = None   # Handle to cancel in-flight after() calls
        self._gantt        = []
        self._color_map    = {}
        self._on_complete  = None   # Optional callback: fired when animation ends

    # ── Public API ───────────────────────────────────────────────────────────

    def animate(self, gantt_blocks, color_map, on_complete=None):
        """
        Start a fresh animated render.

        Parameters
        ----------
        gantt_blocks : list[dict]   { pid, start, end }
        color_map    : dict         { pid: hex_color }
        on_complete  : callable     invoked with no arguments when done
                       (used by App to stop the button-pulse animation)
        """
        self._stop_animation()
        self.delete("all")

        if not gantt_blocks:
            if on_complete:
                on_complete()
            return

        self._gantt       = gantt_blocks
        self._color_map   = color_map
        self._on_complete = on_complete
        self._total_end   = gantt_blocks[-1]["end"]

        # Compute the px-per-time-unit scale so the whole chart fits the canvas
        canvas_w  = self.winfo_width() or 900
        available = canvas_w - self.LEFT_PAD - self.RIGHT_PAD
        self._px_per_unit = max(1.0, available / self._total_end)

        # Resize canvas height to fit track + label row
        chart_h = self.TOP_PAD + self.TRACK_H + self.LABEL_H + 18
        self.config(height=chart_h)

        # Background track rectangle (shown before any blocks are drawn)
        y_top = self.TOP_PAD
        y_bot = self.TOP_PAD + self.TRACK_H

        self.create_rectangle(
            self.LEFT_PAD,
            y_top,
            self.LEFT_PAD + int(self._total_end * self._px_per_unit),
            y_bot,
            fill=BG_CARD,
            outline=BORDER_COLOR,
            width=1,
        )

        # Compute per-block delay based on target total duration
        n_blocks  = len(gantt_blocks)
        self._block_delay = max(
            self.MIN_BLOCK_MS,
            self.TARGET_ANIM_MS // n_blocks
        )

        # Kick off the sequential block drawing
        self._draw_block_at(0)

    def clear(self):
        """Remove all drawn content and cancel any in-progress animation."""
        self._stop_animation()
        self.delete("all")

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _stop_animation(self):
        """Cancel the current after() chain (if any)."""
        if self._animation_id is not None:
            self.after_cancel(self._animation_id)
            self._animation_id = None

    def _draw_block_at(self, index):
        """
        Draw the block at `index`, then schedule the next one.
        When all blocks have been drawn, render the time labels and
        fire the on_complete callback.
        """
        if index >= len(self._gantt):
            # All blocks drawn — add the time axis and signal completion
            self._draw_time_labels()
            if self._on_complete:
                # Small delay so the last block is visible before callback fires
                self.after(80, self._on_complete)
            return

        self._draw_single_block(self._gantt[index])

        # Schedule the next block after the computed per-block delay
        self._animation_id = self.after(
            self._block_delay,
            self._draw_block_at,
            index + 1,
        )

    def _draw_single_block(self, block):
        """
        Draw one colored rectangle + centered PID label for a single
        execution segment.

        Visual structure:
          ┌──────────────────────────────┐
          │           P3                 │  ← TRACK_H pixels tall
          └──────────────────────────────┘
        """
        color = self._color_map.get(block["pid"], ACCENT)
        y_top = self.TOP_PAD
        y_bot = self.TOP_PAD + self.TRACK_H

        x1 = self.LEFT_PAD + int(block["start"] * self._px_per_unit)
        x2 = self.LEFT_PAD + int(block["end"]   * self._px_per_unit)

        # Main rectangle (1 px inset on each side for a gap between blocks)
        self.create_rectangle(
            x1 + 1, y_top + 1,
            x2 - 1, y_bot - 1,
            fill=color,
            outline=BG_PANEL,
            width=2,
        )

        # Subtle inner highlight line (top edge — gives a 3-D feel)
        highlight = lerp_color(color, "#FFFFFF", 0.35)
        self.create_line(
            x1 + 2, y_top + 2,
            x2 - 2, y_top + 2,
            fill=highlight,
            width=1,
        )

        # PID label centered in the block (only if the block is wide enough)
        if (x2 - x1) > 20:
            self.create_text(
                (x1 + x2) // 2,
                (y_top + y_bot) // 2,
                text=block["pid"],
                fill="white",
                font=("Segoe UI", 9, "bold"),
            )

    def _draw_time_labels(self):
        """
        Draw tick marks and numeric time labels along the bottom axis after
        all process blocks have been rendered.

        Overlap prevention: if two consecutive labels would be closer than
        MIN_LABEL_GAP pixels, the second one is skipped.
        """
        MIN_LABEL_GAP = 24   # Minimum pixel gap between time labels

        y_track_bot = self.TOP_PAD + self.TRACK_H
        y_label_top = y_track_bot + 4

        # Collect every unique time boundary across all blocks
        time_points = set()
        for b in self._gantt:
            time_points.add(b["start"])
            time_points.add(b["end"])

        prev_x = None

        for t in sorted(time_points):
            x = self.LEFT_PAD + int(t * self._px_per_unit)

            # Skip if too close to the previous label (avoids overlap)
            if prev_x is not None and (x - prev_x) < MIN_LABEL_GAP:
                continue

            prev_x = x

            # Tick mark line
            self.create_line(
                x, y_track_bot,
                x, y_track_bot + 5,
                fill=TEXT_MUTED,
                width=1,
            )

            # Numeric time label
            self.create_text(
                x,
                y_label_top + 6,
                text=str(t),
                fill=TEXT_MUTED,
                font=("Segoe UI", 8),
            )


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 3: MAIN APPLICATION  (All GUI construction and event handling)
# ─────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    """
    Main application window.

    Layout
    ──────
    ┌────────────────────── HEADER ──────────────────────────┐
    │  ⚙ CPU Scheduling Visualizer  (slow heartbeat pulse)   │
    │  subtitle                                              │
    ├─────── LEFT PANEL ──────┬──────── RIGHT PANEL ─────────┤
    │  • Add Process form     │  • Process Queue table        │
    │  • Populate button      │  • Gantt Chart (animated)     │
    │  • Algorithm settings   │  • Performance Metrics table  │
    │  • Run / Reset buttons  │  • Summary cards              │
    └─────────────────────────┴───────────────────────────────┘

    Animation orchestration:
      1. _run_simulation() calls CPUScheduler.run() (synchronous, fast).
      2. _show_gantt() passes an on_complete callback to GanttCanvas.animate().
      3. GanttCanvas draws blocks one-by-one via after() over ~1.5 s.
      4. Simultaneously, _start_sim_pulse() makes the Run button glow.
      5. When the last block is drawn, on_complete → _on_gantt_complete()
         which stops the pulse and re-enables the button.
      6. Metrics table rows and process queue rows fade in via
         _fadein_row() which interpolates text color over ~400 ms.
    """

    def __init__(self):
        super().__init__()

        # ── Window setup ─────────────────────────────────────────────────
        self.title("CPU Scheduling Visualizer")
        self.geometry("1300x840")
        self.minsize(980, 720)
        self.configure(fg_color=BG_DARK)

        # ── Application state ────────────────────────────────────────────
        self.processes   = []   # List[dict]  { pid, arrival, burst }
        self.color_map   = {}   # { pid: hex_color }  stable across resets
        self.color_index = 0    # Cycles through GANTT_COLORS

        # ── Animation state flags ────────────────────────────────────────
        self._sim_pulsing   = False   # True while Run button is pulsing
        self._sim_pulse_id  = None    # after() handle for sim pulse loop
        self._header_pulse_id = None  # after() handle for heartbeat loop

        # ── Build UI ─────────────────────────────────────────────────────
        self._build_header()
        self._build_body()

        # Start the always-on heartbeat animation for the title
        self._start_header_pulse()

    # =========================================================================
    #  ANIMATION 1 — HEADER HEARTBEAT PULSE
    #  A slow sine-wave oscillation on the title label's text color.
    #  Frequency ≈ 0.5 Hz (one full cycle every ~2 s).  Very subtle.
    # =========================================================================

    def _start_header_pulse(self):
        """
        Drive a slow sinusoidal color oscillation on the main title label.

        Math:
          • time.time() gives wall-clock seconds (float).
          • math.sin(t * SPEED) oscillates −1 … +1 at SPEED radians/second.
          • We normalize to [0, 1] then blend TEXT_PRIMARY → ACCENT at 40 %
            strength, so the color never drifts far from white.

        Frame rate: ~30 fps (33 ms between frames) — smooth and low-CPU.
        """
        PULSE_SPEED  = 1.0    # radians/second — controls oscillation frequency
        BLEND_AMOUNT = 0.40   # max fraction blended toward ACCENT (40 % peak)

        def _pulse_frame():
            # Compute current blend factor from sine wave
            raw       = math.sin(time.time() * PULSE_SPEED)   # -1 … +1
            normalized = (raw + 1.0) / 2.0                    # 0 … 1
            t_blend   = normalized * BLEND_AMOUNT              # 0 … 0.4

            color = lerp_color(TEXT_PRIMARY, ACCENT, t_blend)

            try:
                self.header_title_label.configure(text_color=color)
            except Exception:
                return   # Widget was destroyed; silently stop

            # Schedule next frame at ~30 fps
            self._header_pulse_id = self.after(33, _pulse_frame)

        _pulse_frame()

    # =========================================================================
    #  ANIMATION 2 — SIMULATION BUTTON PULSE
    #  Pulses the "Run Simulation" button between ACCENT_GREEN and a
    #  brighter lime while the Gantt chart is being drawn.
    # =========================================================================

    def _start_sim_pulse(self):
        """
        Begin pulsing the Run Simulation button to signal "working…"

        Uses a faster sine wave (≈2 Hz) to create a noticeable but not
        frantic glow between forest-green and bright-lime.
        """
        PULSE_SPEED = 4.0             # radians/second — faster than header
        BRIGHT_GREEN = "#5AE695"      # Bright lime target for pulse peak

        self._sim_pulsing = True

        def _pulse_frame():
            if not self._sim_pulsing:
                # Animation cancelled — restore button to default state
                try:
                    self.run_btn.configure(
                        fg_color=ACCENT_GREEN,
                        text="▶  Run Simulation",
                        state="normal",
                    )
                except Exception:
                    pass
                return

            raw        = math.sin(time.time() * PULSE_SPEED)
            normalized = (raw + 1.0) / 2.0
            color      = lerp_color(ACCENT_GREEN, BRIGHT_GREEN, normalized)

            try:
                self.run_btn.configure(fg_color=color)
            except Exception:
                return

            # Schedule next frame at ~20 fps (50 ms) — plenty smooth
            self._sim_pulse_id = self.after(50, _pulse_frame)

        _pulse_frame()

    def _stop_sim_pulse(self):
        """
        Stop the simulation button pulse and restore the button to its
        normal resting state.  Called by _on_gantt_complete().
        """
        self._sim_pulsing = False
        if self._sim_pulse_id is not None:
            self.after_cancel(self._sim_pulse_id)
            self._sim_pulse_id = None

    def _on_gantt_complete(self):
        """
        Callback fired by GanttCanvas when its animation finishes.
        Stops the Run Simulation pulse and re-enables the button.
        """
        self._stop_sim_pulse()

    # =========================================================================
    #  ANIMATION 3 — ROW FADE-IN
    #  New table rows start with text the same color as the background (invisible)
    #  then interpolate to their target text colors over FADE_MS milliseconds.
    # =========================================================================

    def _fadein_row(self, label_target_pairs, bg_color,
                    fade_ms=380, steps=20):
        """
        Animate a list of (CTkLabel, target_text_color) pairs from invisible
        (text color == bg_color) to their respective target text colors.

        Parameters
        ----------
        label_target_pairs : list[tuple[ctk.CTkLabel, str]]
            Each tuple is (label_widget, final_text_color).
        bg_color           : str   the row's background color (starting text color)
        fade_ms            : int   total animation duration in ms
        steps              : int   number of interpolation frames
        """
        delay = max(1, fade_ms // steps)   # ms between frames

        # Ease-in-out: quadratic — feels more organic than linear
        def ease(t):
            return t * t * (3.0 - 2.0 * t)   # smoothstep

        def _frame(step):
            if step > steps:
                # Ensure final colors are exactly correct (no float rounding)
                for label, target in label_target_pairs:
                    try:
                        label.configure(text_color=target)
                    except Exception:
                        pass
                return

            t_raw   = step / steps
            t_eased = ease(t_raw)

            for label, target_color in label_target_pairs:
                try:
                    color = lerp_color(bg_color, target_color, t_eased)
                    label.configure(text_color=color)
                except Exception:
                    pass   # Widget may have been destroyed (e.g., during reset)

            self.after(delay, _frame, step + 1)

        _frame(0)

    # =========================================================================
    #  ANIMATION 4 — SMOOTH BUTTON HOVER
    #  Binds Enter/Leave events to animate button color transitions.
    #  CTk's built-in hover is neutralized (hover_color == fg_color)
    #  so our animation has full control.
    # =========================================================================

    def _bind_smooth_hover(self, widget, base_color, hover_color,
                            steps=14, duration_ms=140):
        """
        Attach smooth color-transition hover animation to a CTkButton.

        Strategy:
          • CTk's internal hover_color is set equal to fg_color so that
            CTk's own <Enter> handler causes no visible change.
          • We bind <Enter> and <Leave> ourselves to run a lerp animation.
          • A shared mutable state [current_step, direction, after_id] is
            captured in the closure so interruptions (quick hover in/out)
            are handled gracefully by reversing mid-animation.

        Parameters
        ----------
        widget      : ctk.CTkButton
        base_color  : str  normal (un-hovered) button color
        hover_color : str  fully-hovered button color
        steps       : int  number of animation frames
        duration_ms : int  total transition duration in ms
        """
        delay = max(1, duration_ms // steps)

        # Mutable state shared by both event handlers
        state = {
            "step"     : 0,         # Current animation frame (0 = base, steps = hover)
            "direction": 0,         # +1 = entering, -1 = leaving
            "after_id" : None,      # Handle to cancel in-progress animation
        }

        def _cancel():
            if state["after_id"] is not None:
                widget.after_cancel(state["after_id"])
                state["after_id"] = None

        def _animate():
            # Advance one step in the current direction
            state["step"] = max(0, min(steps, state["step"] + state["direction"]))
            t     = state["step"] / steps
            color = lerp_color(base_color, hover_color, t)

            try:
                widget.configure(fg_color=color)
            except Exception:
                return   # Widget destroyed

            # Continue if not yet at the target end
            if 0 < state["step"] < steps:
                state["after_id"] = widget.after(delay, _animate)

        def on_enter(event):
            _cancel()
            state["direction"] = 1    # Animate toward hover_color
            _animate()

        def on_leave(event):
            _cancel()
            state["direction"] = -1   # Animate back toward base_color
            _animate()

        widget.bind("<Enter>", on_enter, add="+")
        widget.bind("<Leave>", on_leave, add="+")

    # =========================================================================
    #  UI CONSTRUCTION
    # =========================================================================

    # ── HEADER ────────────────────────────────────────────────────────────────

    def _build_header(self):
        """
        Top banner:
          • 3-px cyan accent bar across the very top
          • Title label (stores self.header_title_label for pulse animation)
          • Subtitle
          • Right-aligned status badge showing algorithm name
        """
        header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=84)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Decorative top accent line — uses the new ACCENT_CYAN color
        tk.Frame(header, bg=ACCENT_CYAN, height=3).pack(fill="x", side="top")

        content = ctk.CTkFrame(header, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=0)

        # Left side: title + subtitle
        left_side = ctk.CTkFrame(content, fg_color="transparent")
        left_side.pack(side="left", fill="y", pady=10)

        # ── Store reference — the pulse animation updates this label's color
        self.header_title_label = ctk.CTkLabel(
            left_side,
            text="⚙  CPU Scheduling Visualizer",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT_PRIMARY,   # Will be animated
        )
        self.header_title_label.pack(anchor="w")

        ctk.CTkLabel(
            left_side,
            text="Visualize FCFS  ·  SJF  ·  Round Robin  —  Gantt Chart & Performance Metrics",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))

        # Right side: algorithm badge (updated on simulation run)
        right_side = ctk.CTkFrame(content, fg_color="transparent")
        right_side.pack(side="right", fill="y", pady=14)

        badge_frame = ctk.CTkFrame(
            right_side,
            fg_color=BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        badge_frame.pack(anchor="e")

        ctk.CTkLabel(
            badge_frame,
            text="ALGORITHM",
            font=ctk.CTkFont(size=8, weight="bold"),
            text_color=TEXT_MUTED,
        ).pack(padx=12, pady=(8, 0))

        self.algo_badge_label = ctk.CTkLabel(
            badge_frame,
            text="—",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=ACCENT,
        )
        self.algo_badge_label.pack(padx=14, pady=(0, 8))

    # ── BODY ──────────────────────────────────────────────────────────────────

    def _build_body(self):
        """
        Two-column grid:
          Column 0 (fixed 316 px) — left control panel
          Column 1 (flexible)     — right output panels
        """
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(12, 16))

        body.columnconfigure(0, weight=0, minsize=316)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_right_panel(body)

    # ── LEFT PANEL ────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        """
        Left control panel:
          • Process input form  (PID, Arrival, Burst)
          • "Add Process" button  (cyan, smooth hover)
          • "Populate with Example Processes" button  (secondary cyan)
          • Algorithm selector dropdown
          • Time Quantum entry  (enabled only for RR)
          • "Run Simulation" button (green, pulses while running)
          • "Reset All" button (ghost red)
          • Process count status at bottom
        """
        left = ctk.CTkFrame(
            parent,
            fg_color=BG_PANEL,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
            width=316,
        )
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left.grid_propagate(False)

        # ── Section: Add Process ──────────────────────────────────────────
        self._section_label(left, "➕  Add Process")

        form = ctk.CTkFrame(left, fg_color="transparent")
        form.pack(fill="x", padx=14)

        # Process ID field
        self._field_label(form, "Process ID")
        self.pid_var   = ctk.StringVar(value="P1")
        self.pid_entry = ctk.CTkEntry(
            form,
            textvariable=self.pid_var,
            placeholder_text="e.g.  P1",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        self.pid_entry.pack(fill="x", pady=(0, 8))
        self._bind_entry_focus(self.pid_entry)

        # Arrival Time field
        self._field_label(form, "Arrival Time")
        self.arrival_var   = ctk.StringVar(value="0")
        self.arrival_entry = ctk.CTkEntry(
            form,
            textvariable=self.arrival_var,
            placeholder_text="e.g.  0",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        self.arrival_entry.pack(fill="x", pady=(0, 8))
        self._bind_entry_focus(self.arrival_entry)

        # Burst Time field
        self._field_label(form, "Burst Time")
        self.burst_var   = ctk.StringVar(value="5")
        self.burst_entry = ctk.CTkEntry(
            form,
            textvariable=self.burst_var,
            placeholder_text="e.g.  5",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        self.burst_entry.pack(fill="x", pady=(0, 10))
        self._bind_entry_focus(self.burst_entry)

        # ── "Add Process" button — ACCENT_CYAN with smooth hover ─────────
        add_btn = ctk.CTkButton(
            form,
            text="＋  Add Process",
            command=self._add_process,
            fg_color=ACCENT_CYAN,
            hover_color=ACCENT_CYAN,   # Neutralize CTk's built-in hover
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            corner_radius=8,
        )
        add_btn.pack(fill="x", pady=(0, 6))
        # Attach smooth 140 ms hover transition
        self._bind_smooth_hover(add_btn, ACCENT_CYAN, CYAN_HOVER)

        # ── "Populate with Example Processes" button ──────────────────────
        # A secondary action button below "Add Process".
        # Loads EXAMPLE_PROCESSES with a single click.
        populate_btn = ctk.CTkButton(
            form,
            text="⚡  Populate with Example Processes",
            command=self._populate_example_processes,
            fg_color=BG_CARD,
            hover_color=POPULATE_HOVER,  # CTk hover target (also used as our hover target)
            text_color=ACCENT_CYAN,
            border_width=1,
            border_color=ACCENT_CYAN,
            font=ctk.CTkFont(size=11),
            height=34,
            corner_radius=8,
        )
        populate_btn.pack(fill="x", pady=(0, 14))
        # Subtle hover: darken the background slightly toward POPULATE_HOVER
        self._bind_smooth_hover(populate_btn, BG_CARD, POPULATE_HOVER)

        # ── Divider ───────────────────────────────────────────────────────
        self._divider(left)

        # ── Section: Algorithm Settings ───────────────────────────────────
        self._section_label(left, "🔧  Algorithm Settings")

        algo_form = ctk.CTkFrame(left, fg_color="transparent")
        algo_form.pack(fill="x", padx=14)

        self._field_label(algo_form, "Scheduling Algorithm")
        self.algo_var  = ctk.StringVar(value="FCFS")
        self.algo_menu = ctk.CTkOptionMenu(
            algo_form,
            variable=self.algo_var,
            values=["FCFS", "SJF", "RR"],
            command=self._on_algo_change,
            fg_color=BG_CARD,
            button_color=ACCENT_CYAN,
            button_hover_color=CYAN_HOVER,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        self.algo_menu.pack(fill="x", pady=(0, 8))

        # Time Quantum — only active when RR is selected
        self._field_label(algo_form, "Time Quantum  (RR only)")
        self.quantum_var   = ctk.StringVar(value="2")
        self.quantum_entry = ctk.CTkEntry(
            algo_form,
            textvariable=self.quantum_var,
            placeholder_text="e.g.  2",
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_MUTED,
            height=36,
            state="disabled",
        )
        self.quantum_entry.pack(fill="x", pady=(0, 14))

        # ── Divider ───────────────────────────────────────────────────────
        self._divider(left)

        # ── Action Buttons ────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=14, pady=(4, 0))

        # "Run Simulation" — forest green, pulses while Gantt animates
        self.run_btn = ctk.CTkButton(
            btn_frame,
            text="▶  Run Simulation",
            command=self._run_simulation,
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_GREEN,   # Neutralize CTk hover; we animate it
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            corner_radius=8,
        )
        self.run_btn.pack(fill="x", pady=(0, 8))
        self._bind_smooth_hover(self.run_btn, ACCENT_GREEN, GREEN_HOVER)

        # "Reset All" — ghost button with red text / border
        # NOTE: CTkButton does not allow hover_color="transparent".
        # We set fg_color=BG_DARK (matches left panel bg) and hover_color=RED_HOVER_BG
        # to simulate a ghost button that warms up on hover.
        reset_btn = ctk.CTkButton(
            btn_frame,
            text="↺  Reset All",
            command=self._reset_all,
            fg_color=BG_DARK,           # Same as window bg → looks transparent
            hover_color=RED_HOVER_BG,   # CTk will use this color on Enter
            text_color=ACCENT_RED,
            border_color=ACCENT_RED,
            border_width=1,
            font=ctk.CTkFont(size=13),
            height=38,
            corner_radius=8,
        )
        reset_btn.pack(fill="x")
        # Our smooth hover animates from BG_DARK to RED_HOVER_BG
        self._bind_smooth_hover(reset_btn, BG_DARK, RED_HOVER_BG)

        # ── Process count status badge at panel bottom ────────────────────
        self.proc_count_label = ctk.CTkLabel(
            left,
            text="No processes added",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        )
        self.proc_count_label.pack(side="bottom", pady=10)

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        """
        Scrollable right panel containing (top to bottom):
          1. Process Queue table
          2. Gantt Chart canvas
          3. Performance Metrics table
          4. Summary cards (Avg WT & Avg TAT)
        """
        right = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=ACCENT,
        )
        right.grid(row=0, column=1, sticky="nsew")

        self._build_process_table(right)
        self._build_gantt_section(right)
        self._build_metrics_section(right)
        self._build_summary_section(right)

    # ── PROCESS QUEUE TABLE ───────────────────────────────────────────────────

    def _build_process_table(self, parent):
        """Scrollable table listing all queued processes."""
        card = self._card(parent, "📋  Process Queue")

        # Column header row
        hdr = ctk.CTkFrame(card, fg_color=BG_DARK, corner_radius=6)
        hdr.pack(fill="x", padx=10, pady=(0, 4))

        for col, (text, w) in enumerate([
            ("PID", 80), ("Arrival Time", 140), ("Burst Time", 120), ("", 60)
        ]):
            ctk.CTkLabel(
                hdr, text=text, width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=ACCENT,
                anchor="w",
            ).grid(row=0, column=col, padx=8, pady=6, sticky="w")

        # Scrollable data rows
        self.proc_table_frame = ctk.CTkScrollableFrame(
            card,
            fg_color="transparent",
            height=165,
            scrollbar_button_color=BORDER_COLOR,
        )
        self.proc_table_frame.pack(fill="x", padx=10, pady=(0, 8))

        # Empty-state placeholder
        ctk.CTkLabel(
            self.proc_table_frame,
            text="Add processes using the form on the left  ↖",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(pady=22)

    def _refresh_process_table(self):
        """
        Rebuild the process table from scratch.

        For each new row, the row's text labels are initially set to the row
        background color (making them invisible) and then faded in via
        _fadein_row() to create a smooth appearance animation.
        """
        # Destroy all existing rows
        for w in self.proc_table_frame.winfo_children():
            w.destroy()

        if not self.processes:
            self.proc_count_label.configure(text="No processes added")
            ctk.CTkLabel(
                self.proc_table_frame,
                text="Add processes using the form on the left  ↖",
                font=ctk.CTkFont(size=12),
                text_color=TEXT_MUTED,
            ).pack(pady=22)
            return

        count = len(self.processes)
        self.proc_count_label.configure(
            text=f"{count} process{'es' if count != 1 else ''} queued"
        )

        for i, p in enumerate(self.processes):
            row_bg = BG_CARD if i % 2 == 0 else BG_PANEL
            row    = ctk.CTkFrame(self.proc_table_frame, fg_color=row_bg, corner_radius=4)
            row.pack(fill="x", pady=1)

            # Color swatch (4-px wide strip on the left edge)
            proc_color = self.color_map.get(p["pid"], ACCENT_CYAN)
            tk.Frame(row, bg=proc_color, width=4).pack(side="left", fill="y")

            # ── Data labels — start invisible (text = bg color), then fade in ─
            labels_to_fadein = []   # (CTkLabel, target_color) pairs

            for text, w in [
                (p["pid"],          80),
                (str(p["arrival"]), 140),
                (str(p["burst"]),   120),
            ]:
                lbl = ctk.CTkLabel(
                    row, text=text, width=w,
                    font=ctk.CTkFont(size=12),
                    text_color=row_bg,   # Start invisible
                    anchor="w",
                )
                lbl.pack(side="left", padx=8, pady=6)
                labels_to_fadein.append((lbl, TEXT_PRIMARY))   # Fade to white

            # Animate this row's labels from invisible to their target colors
            # Stagger rows slightly so they cascade in (i * 30ms offset)
            self.after(i * 30, lambda pairs=labels_to_fadein, bg=row_bg:
                       self._fadein_row(pairs, bg))

            # Delete button (always visible — no fade needed)
            pid_to_del = p["pid"]
            ctk.CTkButton(
                row,
                text="✕",
                width=30, height=24,
                fg_color="transparent",
                hover_color=BG_DARK,
                text_color=ACCENT_RED,
                font=ctk.CTkFont(size=11),
                command=lambda pid=pid_to_del: self._delete_process(pid),
            ).pack(side="right", padx=6, pady=4)

    # ── GANTT CHART ───────────────────────────────────────────────────────────

    def _build_gantt_section(self, parent):
        """Gantt chart card with legend and the custom GanttCanvas widget."""
        card = self._card(parent, "⏱  Gantt Chart  —  CPU Execution Timeline")

        # Legend (filled after simulation)
        self.gantt_legend_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.gantt_legend_frame.pack(fill="x", padx=12, pady=(0, 4))

        # Placeholder shown before the first simulation
        self.gantt_placeholder = ctk.CTkLabel(
            card,
            text="Run the simulation to see the animated Gantt chart here.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        self.gantt_placeholder.pack(pady=24)

        # The canvas — hidden until simulation runs
        self.gantt_canvas = GanttCanvas(card, height=118)

    def _show_gantt(self, gantt_blocks, on_complete=None):
        """
        Swap the placeholder for the canvas and start the block animation.

        Parameters
        ----------
        gantt_blocks : list[dict]
        on_complete  : callable  passed through to GanttCanvas.animate()
        """
        self.gantt_placeholder.pack_forget()
        self.gantt_canvas.pack(fill="x", padx=10, pady=(0, 12))
        self.gantt_canvas.update_idletasks()   # Force width calculation

        self.gantt_canvas.animate(
            gantt_blocks,
            self.color_map,
            on_complete=on_complete,
        )

        # Rebuild the process-color legend below the chart
        for w in self.gantt_legend_frame.winfo_children():
            w.destroy()

        unique_pids = list(dict.fromkeys(b["pid"] for b in gantt_blocks))
        for pid in unique_pids:
            color = self.color_map.get(pid, ACCENT_CYAN)
            tk.Frame(self.gantt_legend_frame, bg=color, width=12, height=12).pack(
                side="left", padx=(0, 4), pady=2
            )
            ctk.CTkLabel(
                self.gantt_legend_frame,
                text=pid,
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED,
            ).pack(side="left", padx=(0, 10))

    # ── PERFORMANCE METRICS TABLE ─────────────────────────────────────────────

    def _build_metrics_section(self, parent):
        """Table card: per-process CT, TAT, WT."""
        card = self._card(parent, "📊  Performance Metrics")

        # Column header row
        hdr = ctk.CTkFrame(card, fg_color=BG_DARK, corner_radius=6)
        hdr.pack(fill="x", padx=10, pady=(0, 4))

        col_defs = [
            ("PID",              80),
            ("Arrival",         100),
            ("Burst",            90),
            ("Completion (CT)", 150),
            ("Turnaround (TAT)",165),
            ("Waiting (WT)",    135),
        ]
        for col, (text, w) in enumerate(col_defs):
            ctk.CTkLabel(
                hdr, text=text, width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=ACCENT,
                anchor="w",
            ).grid(row=0, column=col, padx=8, pady=6, sticky="w")

        # Scrollable data rows
        self.metrics_frame = ctk.CTkScrollableFrame(
            card,
            fg_color="transparent",
            height=185,
            scrollbar_button_color=BORDER_COLOR,
        )
        self.metrics_frame.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(
            self.metrics_frame,
            text="Metrics will appear here after running the simulation.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(pady=22)

    def _show_metrics(self, results):
        """
        Populate the metrics table with simulation results.

        Each row fades in from its background color to the correct text color.
        WT is color-coded: 0 → green, ≤5 → amber, >5 → red.
        Rows are staggered by 25 ms to create a cascade effect.
        """
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        col_keys = [
            ("pid",         80),
            ("arrival",    100),
            ("burst",       90),
            ("completion", 150),
            ("turnaround", 165),
            ("waiting",    135),
        ]

        for i, r in enumerate(results):
            row_bg = BG_CARD if i % 2 == 0 else BG_PANEL
            row    = ctk.CTkFrame(self.metrics_frame, fg_color=row_bg, corner_radius=4)
            row.pack(fill="x", pady=1)

            # Color swatch
            proc_color = self.color_map.get(r["pid"], ACCENT_CYAN)
            tk.Frame(row, bg=proc_color, width=4).pack(side="left", fill="y")

            labels_to_fadein = []

            for key, w in col_keys:
                value = r[key]

                # Choose final text color based on column & value
                if key == "waiting":
                    if value == 0:
                        target_color = ACCENT_GREEN
                    elif value <= 5:
                        target_color = ACCENT_AMBER
                    else:
                        target_color = ACCENT_RED
                else:
                    target_color = TEXT_PRIMARY

                lbl = ctk.CTkLabel(
                    row,
                    text=str(value),
                    width=w,
                    font=ctk.CTkFont(size=12),
                    text_color=row_bg,    # Start invisible for fade-in
                    anchor="w",
                )
                lbl.pack(side="left", padx=8, pady=7)
                labels_to_fadein.append((lbl, target_color))

            # Staggered fade-in: each row starts 25 ms after the previous
            self.after(i * 25, lambda pairs=labels_to_fadein, bg=row_bg:
                       self._fadein_row(pairs, bg, fade_ms=350))

    # ── SUMMARY CARDS ─────────────────────────────────────────────────────────

    def _build_summary_section(self, parent):
        """Two large metric badge cards at the bottom of the right panel."""
        card = self._card(parent, "🏆  Summary")

        frame = ctk.CTkFrame(card, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=(0, 12))

        self.avg_wt_card = self._make_summary_card(
            frame,
            "⏳  Avg Waiting Time",
            "—",
            ACCENT_CYAN,
            "time units",
        )
        self.avg_wt_card.pack(side="left", expand=True, fill="both", padx=(0, 6))

        self.avg_tat_card = self._make_summary_card(
            frame,
            "🔄  Avg Turnaround Time",
            "—",
            ACCENT_GREEN,
            "time units",
        )
        self.avg_tat_card.pack(side="left", expand=True, fill="both")

    def _make_summary_card(self, parent, title, value, accent_color, unit):
        """
        Build one summary badge card.

        Stores .value_label on the card frame so _update_summary_cards()
        can update it without rebuilding the whole card.
        """
        card = ctk.CTkFrame(
            parent,
            fg_color=BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_COLOR,
        )

        # Top accent stripe
        tk.Frame(card, bg=accent_color, height=3).pack(fill="x")

        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(pady=(10, 0))

        # Large numeric value
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(family="Segoe UI", size=38, weight="bold"),
            text_color=accent_color,
        )
        value_label.pack()
        card.value_label = value_label   # Expose for external updates

        ctk.CTkLabel(
            card,
            text=unit,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        ).pack(pady=(0, 14))

        return card

    def _update_summary_cards(self, avg_wt, avg_tat):
        """Update the displayed averages in the summary badge cards."""
        self.avg_wt_card.value_label.configure(text=f"{avg_wt:.2f}")
        self.avg_tat_card.value_label.configure(text=f"{avg_tat:.2f}")

    # =========================================================================
    #  EVENT HANDLERS
    # =========================================================================

    def _populate_example_processes(self):
        """
        Clear the current process queue and load the 10 hand-crafted
        example processes from EXAMPLE_PROCESSES (defined at module level).

        This is a pure convenience function to let the user see a meaningful
        Gantt chart immediately without entering data manually.

        Steps:
          1. Reset all application state (without touching the UI beyond
             what _reset_all() does, to avoid redundant redraws).
          2. Assign a color to each new PID from the GANTT_COLORS list.
          3. Copy EXAMPLE_PROCESSES into self.processes.
          4. Call _refresh_process_table() to render the new rows with fade-in.
          5. Auto-suggest the next PID ("P11") in the manual form.
        """
        # ── Step 1: Clear existing state ─────────────────────────────────
        self._reset_all()

        # ── Step 2 & 3: Load the predefined process set ───────────────────
        for p in EXAMPLE_PROCESSES:
            pid = p["pid"]

            # Assign a stable color from the palette
            if pid not in self.color_map:
                self.color_map[pid] = GANTT_COLORS[self.color_index % len(GANTT_COLORS)]
                self.color_index += 1

            # Append a copy so the constant is never mutated
            self.processes.append({
                "pid"    : pid,
                "arrival": p["arrival"],
                "burst"  : p["burst"],
            })

        # ── Step 4: Refresh the process table (rows fade in) ─────────────
        self._refresh_process_table()

        # ── Step 5: Suggest the next PID for manual additions ────────────
        self.pid_var.set("P11")
        self.arrival_var.set("0")
        self.burst_var.set("5")

    def _add_process(self):
        """
        Validate the manual input form and append one new process.

        Validation rules:
          • PID must not be empty.
          • PID must be unique in the current queue.
          • Arrival must be a non-negative integer.
          • Burst must be a positive integer (≥ 1).
        """
        pid     = self.pid_var.get().strip()
        arrival = self.arrival_var.get().strip()
        burst   = self.burst_var.get().strip()

        # ── Validation ───────────────────────────────────────────────────
        if not pid:
            self._show_error("Process ID cannot be empty.")
            return

        if any(p["pid"] == pid for p in self.processes):
            self._show_error(f'Process "{pid}" already exists.  Use a unique ID.')
            return

        try:
            arrival_int = int(arrival)
            if arrival_int < 0:
                raise ValueError
        except ValueError:
            self._show_error("Arrival Time must be a non-negative integer.")
            return

        try:
            burst_int = int(burst)
            if burst_int < 1:
                raise ValueError
        except ValueError:
            self._show_error("Burst Time must be a positive integer (≥ 1).")
            return

        # ── Assign stable color ───────────────────────────────────────────
        if pid not in self.color_map:
            self.color_map[pid] = GANTT_COLORS[self.color_index % len(GANTT_COLORS)]
            self.color_index   += 1

        # ── Append process & refresh table ────────────────────────────────
        self.processes.append({"pid": pid, "arrival": arrival_int, "burst": burst_int})
        self._refresh_process_table()

        # Auto-suggest next sequential PID
        next_num = len(self.processes) + 1
        self.pid_var.set(f"P{next_num}")
        self.arrival_var.set("0")
        self.burst_var.set("5")

    def _delete_process(self, pid):
        """Remove a single process by PID and refresh the table."""
        self.processes = [p for p in self.processes if p["pid"] != pid]
        self.color_map.pop(pid, None)
        self._refresh_process_table()

    def _on_algo_change(self, value):
        """Enable or disable the Time Quantum entry based on algorithm choice."""
        if value == "RR":
            self.quantum_entry.configure(state="normal", text_color=TEXT_PRIMARY)
        else:
            self.quantum_entry.configure(state="disabled", text_color=TEXT_MUTED)

    def _run_simulation(self):
        """
        Orchestrate a full simulation run:

          1. Validate inputs.
          2. Compute schedule via CPUScheduler.run().
          3. Disable the Run button + start its pulse animation.
          4. Show animated Gantt chart (pass _on_gantt_complete as callback).
          5. Show metrics table (rows fade in).
          6. Update summary cards.
          7. Update the algorithm badge in the header.
          (The button is re-enabled automatically by _on_gantt_complete.)
        """
        if not self.processes:
            self._show_error("Please add at least one process before running.")
            return

        algorithm = self.algo_var.get()
        quantum   = 2   # sensible default

        if algorithm == "RR":
            try:
                quantum = int(self.quantum_var.get().strip())
                if quantum < 1:
                    raise ValueError
            except ValueError:
                self._show_error("Time Quantum must be a positive integer (≥ 1).")
                return

        # ── Run the algorithm ─────────────────────────────────────────────
        try:
            gantt, results, avg_wt, avg_tat = CPUScheduler.run(
                algorithm=algorithm,
                processes=self.processes,
                quantum=quantum,
            )
        except Exception as e:
            self._show_error(str(e))
            return

        # ── Disable Run button and start pulse ────────────────────────────
        self.run_btn.configure(state="disabled", text="⏳  Simulating…")
        self._start_sim_pulse()

        # ── Update header badge ───────────────────────────────────────────
        self.algo_badge_label.configure(text=algorithm)

        # ── Show animated Gantt — button re-enabled via callback ──────────
        self._show_gantt(gantt, on_complete=self._on_gantt_complete)

        # ── Metrics and summary update immediately ────────────────────────
        self._show_metrics(results)
        self._update_summary_cards(avg_wt, avg_tat)

    def _reset_all(self):
        """
        Clear the entire application state and reset all output panels
        back to their empty/placeholder state.
        """
        # Stop any in-progress pulse so we don't leave the button broken
        self._stop_sim_pulse()

        self.processes   = []
        self.color_map   = {}
        self.color_index = 0

        # ── Reset process table ───────────────────────────────────────────
        self._refresh_process_table()

        # ── Reset Gantt chart ─────────────────────────────────────────────
        self.gantt_canvas.clear()
        self.gantt_canvas.pack_forget()
        self.gantt_placeholder.pack(pady=24)

        for w in self.gantt_legend_frame.winfo_children():
            w.destroy()

        # ── Reset metrics table ───────────────────────────────────────────
        for w in self.metrics_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.metrics_frame,
            text="Metrics will appear here after running the simulation.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(pady=22)

        # ── Reset summary cards ───────────────────────────────────────────
        self.avg_wt_card.value_label.configure(text="—")
        self.avg_tat_card.value_label.configure(text="—")

        # ── Reset header badge ────────────────────────────────────────────
        self.algo_badge_label.configure(text="—")

        # ── Reset Run button to normal state ──────────────────────────────
        self.run_btn.configure(
            fg_color=ACCENT_GREEN,
            text="▶  Run Simulation",
            state="normal",
        )

        # ── Reset form suggestions ────────────────────────────────────────
        self.pid_var.set("P1")
        self.arrival_var.set("0")
        self.burst_var.set("5")

    # =========================================================================
    #  SHARED UI HELPER METHODS
    # =========================================================================

    def _card(self, parent, title):
        """
        Create a titled card panel with 1-px border and corner radius.

        Returns the outer CTkFrame; callers pack their content widgets
        directly into this frame.
        """
        outer = ctk.CTkFrame(
            parent,
            fg_color=BG_PANEL,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        outer.pack(fill="x", pady=(0, 12))

        # Title bar
        title_bar = ctk.CTkFrame(outer, fg_color="transparent")
        title_bar.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            title_bar,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ACCENT,   # Light blue for all card headers
        ).pack(side="left")

        return outer

    def _section_label(self, parent, text):
        """Bold section heading inside the left control panel."""
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ACCENT,   # Light blue to match card headers
            anchor="w",
        ).pack(fill="x", padx=14, pady=(14, 6))

    def _field_label(self, parent, text):
        """Small muted label above a form input field."""
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(0, 3))

    def _divider(self, parent):
        """1-px horizontal separator line."""
        tk.Frame(parent, bg=BORDER_COLOR, height=1).pack(fill="x", padx=14, pady=8)

    def _show_error(self, message):
        """Standard error dialog."""
        messagebox.showerror("Input Error", message, parent=self)

    def _bind_entry_focus(self, entry):
        """
        Change an entry widget's border color to ACCENT_CYAN on focus and
        back to BORDER_COLOR on blur — subtle but professional focus ring.
        """
        entry.bind(
            "<FocusIn>",
            lambda e: entry.configure(border_color=ACCENT_CYAN),
            add="+",
        )
        entry.bind(
            "<FocusOut>",
            lambda e: entry.configure(border_color=BORDER_COLOR),
            add="+",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
