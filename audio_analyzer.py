"""
Audio Analyzer - Speech/Silence Gap Detection Tool
Opens an MP3 file and visualizes the waveform with dynamic threshold-based
detection of speech segments vs. silence/gaps. The threshold slider reacts
in real-time, highlighting spoken parts and gaps on the waveform.
Includes audio playback with a moving playhead on the waveform.
"""

import tkinter as tk
from tkinter import filedialog, ttk
import numpy as np
import os
import sys
import threading
import time as _time

# ---------------------------------------------------------------------------
# Lazy-imported heavy libs (imported once, on first use)
# ---------------------------------------------------------------------------
AudioSegment = None
Figure = None
FigureCanvasTkAgg = None
NavigationToolbar2Tk = None
pygame = None

def _ensure_imports():
    global AudioSegment, Figure, FigureCanvasTkAgg, NavigationToolbar2Tk, pygame
    if AudioSegment is None:
        from pydub import AudioSegment as _AS
        AudioSegment = _AS
    if Figure is None:
        from matplotlib.figure import Figure as _Fig
        Figure = _Fig
    if FigureCanvasTkAgg is None:
        from matplotlib.backends.backend_tkagg import (
            FigureCanvasTkAgg as _Canvas,
            NavigationToolbar2Tk as _Toolbar,
        )
        FigureCanvasTkAgg = _Canvas
        NavigationToolbar2Tk = _Toolbar
    if pygame is None:
        import pygame as _pg
        _pg.mixer.init()
        pygame = _pg


# ═══════════════════════════════════════════════════════════════════════════
class AudioAnalyzerApp:
    """Main application class."""

    # ── colour palette ────────────────────────────────────────────────────
    COL_WAVEFORM   = "#3a86ff"      # blue waveform
    COL_SPEECH     = "#06d6a0"      # green overlay  – speech
    COL_GAP        = "#ef476f"      # red overlay    – gap / silence
    COL_THRESHOLD  = "#ffd166"      # yellow threshold line
    COL_ENVELOPE   = "#ff6b35"      # orange envelope line
    COL_BG         = "#1a1a2e"      # dark background
    COL_FG         = "#e0e0e0"      # light foreground text

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Audio Analyzer – Speech / Gap Detection")
        self.root.geometry("1200x750")
        self.root.configure(bg=self.COL_BG)
        self.root.minsize(900, 600)

        # ── state ─────────────────────────────────────────────────────────
        self.samples: np.ndarray | None = None   # mono float32 samples
        self.sample_rate: int = 44100
        self.duration_sec: float = 0.0
        self.time_axis: np.ndarray | None = None
        self.envelope: np.ndarray | None = None  # smoothed amplitude envelope
        self.loaded_file: str = ""

        # ── envelope parameters ──────────────────────────────────────────
        self.envelope_window_ms = 50        # RMS window in milliseconds

        # ── playback state ───────────────────────────────────────────────
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.play_start_time: float = 0.0   # time.time() when playback started
        self.play_offset: float = 0.0       # seconds into the track
        self.playhead_line = None           # matplotlib Line2D object
        self._playhead_after_id = None      # root.after() id for animation

        # ── build UI ─────────────────────────────────────────────────────
        self._build_toolbar()
        self._build_canvas()
        self._build_controls()

        # ── cleanup on close ─────────────────────────────────────────────
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── open file dialog immediately ─────────────────────────────────
        self.root.after(200, self._open_file)

    # =====================================================================
    #  UI construction
    # =====================================================================
    def _build_toolbar(self):
        """Top bar: file name label + Open button + transport controls."""
        bar = tk.Frame(self.root, bg="#16213e", pady=6)
        bar.pack(fill=tk.X)

        self.open_btn = tk.Button(
            bar, text="📂 Open MP3", command=self._open_file,
            bg="#0f3460", fg="white", font=("Arial", 10, "bold"),
            activebackground="#1a1a5e", cursor="hand2", padx=12
        )
        self.open_btn.pack(side=tk.LEFT, padx=10)

        # ── Transport buttons ────────────────────────────────────────────
        transport = tk.Frame(bar, bg="#16213e")
        transport.pack(side=tk.LEFT, padx=10)

        btn_style = dict(
            bg="#0f3460", fg="white", font=("Arial", 12, "bold"),
            activebackground="#1a1a5e", cursor="hand2",
            width=3, relief=tk.FLAT, bd=0
        )

        self.play_btn = tk.Button(
            transport, text="▶", command=self._play, **btn_style
        )
        self.play_btn.pack(side=tk.LEFT, padx=2)

        self.pause_btn = tk.Button(
            transport, text="⏸", command=self._pause, state=tk.DISABLED,
            **btn_style
        )
        self.pause_btn.pack(side=tk.LEFT, padx=2)

        self.stop_btn = tk.Button(
            transport, text="⏹", command=self._stop, state=tk.DISABLED,
            **btn_style
        )
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        # ── Playback time label ──────────────────────────────────────────
        self.time_label = tk.Label(
            bar, text="0:00 / 0:00", bg="#16213e", fg="#aaaaaa",
            font=("Consolas", 10)
        )
        self.time_label.pack(side=tk.LEFT, padx=10)

        self.file_label = tk.Label(
            bar, text="No file loaded", bg="#16213e", fg=self.COL_FG,
            font=("Arial", 10), anchor="w"
        )
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.status_label = tk.Label(
            bar, text="", bg="#16213e", fg=self.COL_THRESHOLD,
            font=("Arial", 9)
        )
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def _build_canvas(self):
        """Matplotlib canvas for waveform + overlays."""
        _ensure_imports()

        self.fig = Figure(figsize=(12, 4.5), dpi=100, facecolor=self.COL_BG)
        self.ax = self.fig.add_subplot(111)
        self._style_axes()

        self.canvas_frame = tk.Frame(self.root, bg=self.COL_BG)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # matplotlib nav toolbar (zoom/pan)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
        self.toolbar.update()

        # ── Click-to-seek on waveform ────────────────────────────────────
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)

    def _build_controls(self):
        """Bottom panel: threshold slider + info."""
        ctrl = tk.Frame(self.root, bg="#16213e", pady=8)
        ctrl.pack(fill=tk.X, side=tk.BOTTOM)

        # ── Threshold slider ─────────────────────────────────────────────
        lbl1 = tk.Label(ctrl, text="Silence threshold:", bg="#16213e",
                        fg=self.COL_FG, font=("Arial", 10))
        lbl1.pack(side=tk.LEFT, padx=(15, 5))

        self.threshold_var = tk.DoubleVar(value=0.05)
        self.threshold_slider = tk.Scale(
            ctrl, from_=0.001, to=0.50, resolution=0.001,
            orient=tk.HORIZONTAL, variable=self.threshold_var,
            command=self._on_threshold_change,
            length=500, showvalue=0,
            bg="#16213e", fg=self.COL_FG, troughcolor="#0f3460",
            highlightthickness=0, activebackground=self.COL_THRESHOLD
        )
        self.threshold_slider.pack(side=tk.LEFT, padx=5)

        self.threshold_value_label = tk.Label(
            ctrl, text="0.0500", bg="#16213e",
            fg=self.COL_THRESHOLD, font=("Arial", 11, "bold"), width=7
        )
        self.threshold_value_label.pack(side=tk.LEFT, padx=(0, 20))

        # ── Envelope window slider ───────────────────────────────────────
        lbl2 = tk.Label(ctrl, text="Smoothing (ms):", bg="#16213e",
                        fg=self.COL_FG, font=("Arial", 10))
        lbl2.pack(side=tk.LEFT, padx=(10, 5))

        self.smooth_var = tk.IntVar(value=50)
        self.smooth_slider = tk.Scale(
            ctrl, from_=10, to=300, resolution=5,
            orient=tk.HORIZONTAL, variable=self.smooth_var,
            command=self._on_smooth_change,
            length=180, showvalue=0,
            bg="#16213e", fg=self.COL_FG, troughcolor="#0f3460",
            highlightthickness=0, activebackground=self.COL_ENVELOPE
        )
        self.smooth_slider.pack(side=tk.LEFT, padx=5)

        self.smooth_value_label = tk.Label(
            ctrl, text="50 ms", bg="#16213e",
            fg=self.COL_ENVELOPE, font=("Arial", 10, "bold"), width=7
        )
        self.smooth_value_label.pack(side=tk.LEFT, padx=(0, 20))

        # ── Stats ────────────────────────────────────────────────────────
        self.stats_label = tk.Label(
            ctrl, text="", bg="#16213e", fg=self.COL_FG,
            font=("Arial", 9), anchor="e"
        )
        self.stats_label.pack(side=tk.RIGHT, padx=15)

        # ── Legend ───────────────────────────────────────────────────────
        legend_frame = tk.Frame(ctrl, bg="#16213e")
        legend_frame.pack(side=tk.RIGHT, padx=10)
        
        for color, label in [(self.COL_SPEECH, "Speech"), (self.COL_GAP, "Gap")]:
            tk.Canvas(legend_frame, width=12, height=12, bg=color,
                      highlightthickness=0).pack(side=tk.LEFT, padx=(8, 2))
            tk.Label(legend_frame, text=label, bg="#16213e", fg=self.COL_FG,
                     font=("Arial", 9)).pack(side=tk.LEFT)

    # =====================================================================
    #  Axes styling
    # =====================================================================
    def _style_axes(self):
        self.ax.set_facecolor(self.COL_BG)
        self.ax.tick_params(colors=self.COL_FG, labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color("#444")
        self.ax.set_xlabel("Time (s)", color=self.COL_FG, fontsize=9)
        self.ax.set_ylabel("Amplitude", color=self.COL_FG, fontsize=9)
        self.ax.set_title("Load an MP3 file to begin", color=self.COL_FG,
                          fontsize=11, pad=8)

    # =====================================================================
    #  File loading
    # =====================================================================
    def _open_file(self):
        # Stop any current playback before loading a new file
        self._stop()

        filepath = filedialog.askopenfilename(
            title="Select an audio file",
            filetypes=[
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("All audio", "*.mp3;*.wav;*.ogg;*.flac"),
            ]
        )
        if not filepath:
            return

        self.file_label.config(text=f"Loading: {os.path.basename(filepath)}…")
        self.status_label.config(text="⏳ Processing…")
        self.root.update_idletasks()

        # Load in background thread to keep UI responsive
        threading.Thread(target=self._load_audio, args=(filepath,),
                         daemon=True).start()

    def _load_audio(self, filepath: str):
        """Load, convert to mono float32 samples, compute envelope."""
        _ensure_imports()
        try:
            audio = AudioSegment.from_file(filepath)
            audio = audio.set_channels(1)           # force mono
            self.sample_rate = audio.frame_rate
            self.duration_sec = len(audio) / 1000.0

            # Convert to float32 normalised to [-1, 1]
            raw = np.array(audio.get_array_of_samples(), dtype=np.float32)
            max_val = float(np.iinfo(np.int16).max)  # pydub uses int16
            self.samples = raw / max_val

            self.time_axis = np.linspace(0, self.duration_sec,
                                         num=len(self.samples), endpoint=False)

            self.loaded_file = filepath

            # Compute initial envelope
            self._compute_envelope()

            # Schedule UI update on main thread
            self.root.after(0, self._after_load)

        except Exception as exc:
            self.root.after(0, lambda: self._show_error(str(exc)))

    def _after_load(self):
        fname = os.path.basename(self.loaded_file)
        dur = self.duration_sec
        self.file_label.config(
            text=f"📁 {fname}   |   {dur:.1f}s   |   {self.sample_rate} Hz"
        )
        self.status_label.config(text="✅ Loaded")
        
        # Set slider max to peak envelope amplitude for precision
        self._update_threshold_slider_range()

        # Enable transport controls
        self._update_transport_buttons()
        self._update_time_label(0.0)
        
        self._redraw()

    def _show_error(self, msg):
        self.file_label.config(text=f"❌ Error: {msg}")
        self.status_label.config(text="")

    def _update_threshold_slider_range(self):
        """Set the threshold slider maximum to the peak envelope amplitude
        so the full slider range maps to the actual dynamic range of the file."""
        if self.envelope is None:
            return
        peak = float(np.max(self.envelope))
        if peak < 0.01:
            peak = 0.01  # safety floor
        
        # Round up to a clean number for readability
        # e.g. 0.237 → 0.24,  0.089 → 0.09
        import math
        peak = math.ceil(peak * 100) / 100.0
        
        # Pick a resolution that gives ~500 distinct steps across the range
        resolution = max(0.0001, round(peak / 500, 4))
        
        # Keep current value if it's still in range, otherwise reset
        current = self.threshold_var.get()
        if current > peak:
            current = peak * 0.1
        
        self.threshold_slider.config(from_=0.0001, to=peak,
                                      resolution=resolution)
        self.threshold_var.set(current)
        self.threshold_value_label.config(text=f"{current:.4f}")

    # =====================================================================
    #  Envelope computation
    # =====================================================================
    def _compute_envelope(self):
        """RMS envelope with a sliding window."""
        win_samples = max(1, int(self.sample_rate * self.envelope_window_ms / 1000))
        # Use a fast convolution approach for RMS
        sq = self.samples ** 2
        kernel = np.ones(win_samples) / win_samples
        mean_sq = np.convolve(sq, kernel, mode="same")
        self.envelope = np.sqrt(np.maximum(mean_sq, 0))

    # =====================================================================
    #  Drawing
    # =====================================================================
    def _redraw(self):
        """Full redraw: waveform + envelope + threshold overlays."""
        if self.samples is None:
            return

        self.ax.clear()
        self._style_axes()

        # The playhead_line was removed by ax.clear(), reset reference
        self.playhead_line = None

        t = self.time_axis
        threshold = self.threshold_var.get()

        # ── Downsample for fast plotting when file is large ──────────────
        max_points = 80_000
        step = max(1, len(self.samples) // max_points)
        t_ds = t[::step]
        s_ds = self.samples[::step]
        env_ds = self.envelope[::step]

        # ── 1. Waveform ──────────────────────────────────────────────────
        self.ax.plot(t_ds, s_ds, color=self.COL_WAVEFORM, linewidth=0.3,
                     alpha=0.55, rasterized=True)

        # ── 2. Envelope ──────────────────────────────────────────────────
        self.ax.plot(t_ds, env_ds, color=self.COL_ENVELOPE, linewidth=0.8,
                     alpha=0.9, label="Envelope")

        # ── 3. Threshold line ────────────────────────────────────────────
        self.ax.axhline(y=threshold, color=self.COL_THRESHOLD,
                        linewidth=1, linestyle="--", alpha=0.85,
                        label=f"Threshold ({threshold:.3f})")

        # ── 4. Speech / gap overlays ─────────────────────────────────────
        is_speech = self.envelope >= threshold
        speech_regions, gap_regions = self._find_regions(is_speech)

        for start_s, end_s in speech_regions:
            self.ax.axvspan(start_s, end_s, alpha=0.18,
                            color=self.COL_SPEECH, zorder=0)
        for start_s, end_s in gap_regions:
            self.ax.axvspan(start_s, end_s, alpha=0.18,
                            color=self.COL_GAP, zorder=0)

        # ── axis limits ──────────────────────────────────────────────────
        self.ax.set_xlim(0, self.duration_sec)
        y_max = max(0.1, float(np.max(np.abs(s_ds))) * 1.1)
        self.ax.set_ylim(-y_max, y_max)
        self.ax.set_title(os.path.basename(self.loaded_file),
                          color=self.COL_FG, fontsize=11, pad=8)

        self.fig.tight_layout()
        self.canvas.draw_idle()

        # ── Update stats ─────────────────────────────────────────────────
        total_speech = sum(e - s for s, e in speech_regions)
        total_gap = sum(e - s for s, e in gap_regions)
        self.stats_label.config(
            text=f"Speech: {total_speech:.1f}s ({len(speech_regions)} segments)  |  "
                 f"Gaps: {total_gap:.1f}s ({len(gap_regions)} segments)"
        )

        # ── Restore playhead if playback is active or paused ─────────────
        if self.is_playing:
            pos = _time.time() - self.play_start_time
            self._draw_playhead(pos)
        elif self.is_paused:
            self._draw_playhead(self.play_offset)

    # =====================================================================
    #  Region detection
    # =====================================================================
    def _find_regions(self, is_speech: np.ndarray):
        """Convert a boolean mask into lists of (start_sec, end_sec) tuples
        for speech regions and gap regions."""
        speech_regions: list[tuple[float, float]] = []
        gap_regions: list[tuple[float, float]] = []

        if len(is_speech) == 0:
            return speech_regions, gap_regions

        # Find transitions
        diff = np.diff(is_speech.astype(np.int8))
        # Indices where speech starts (+1) or ends (-1)
        starts = np.where(diff == 1)[0] + 1
        ends = np.where(diff == -1)[0] + 1

        # Handle edge cases
        if is_speech[0]:
            starts = np.insert(starts, 0, 0)
        if is_speech[-1]:
            ends = np.append(ends, len(is_speech))

        # Convert sample indices to seconds
        sample_to_sec = self.duration_sec / len(is_speech)

        for s, e in zip(starts, ends):
            speech_regions.append((s * sample_to_sec, e * sample_to_sec))

        # Gaps are the complement
        prev_end = 0.0
        for s, e in speech_regions:
            if s > prev_end + 0.001:
                gap_regions.append((prev_end, s))
            prev_end = e
        if prev_end < self.duration_sec - 0.001:
            gap_regions.append((prev_end, self.duration_sec))

        return speech_regions, gap_regions

    # =====================================================================
    #  Playback controls
    # =====================================================================
    def _play(self):
        """Start or resume audio playback."""
        if self.samples is None or not self.loaded_file:
            return

        _ensure_imports()

        if self.is_paused:
            # Resume from where we paused
            pygame.mixer.music.unpause()
            self.play_start_time = _time.time() - self.play_offset
            self.is_paused = False
            self.is_playing = True
        else:
            # Fresh start (or restart after stop)
            try:
                pygame.mixer.music.load(self.loaded_file)
                pygame.mixer.music.play(start=self.play_offset)
                self.play_start_time = _time.time() - self.play_offset
                self.is_playing = True
                self.is_paused = False
            except Exception as exc:
                self.status_label.config(text=f"❌ Playback error: {exc}")
                return

        self._update_transport_buttons()
        self._animate_playhead()

    def _pause(self):
        """Pause playback, remember position."""
        if not self.is_playing:
            return
        _ensure_imports()
        pygame.mixer.music.pause()
        self.play_offset = _time.time() - self.play_start_time
        self.is_playing = False
        self.is_paused = True
        self._cancel_playhead_timer()
        self._update_transport_buttons()

    def _stop(self):
        """Stop playback, reset position to 0."""
        _ensure_imports()
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass
        self.is_playing = False
        self.is_paused = False
        self.play_offset = 0.0
        self._cancel_playhead_timer()
        self._remove_playhead()
        self._update_transport_buttons()
        self._update_time_label(0.0)

    def _update_transport_buttons(self):
        """Enable / disable transport buttons based on state."""
        has_file = self.samples is not None
        if self.is_playing:
            self.play_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
        elif self.is_paused:
            self.play_btn.config(state=tk.NORMAL)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        else:
            self.play_btn.config(state=tk.NORMAL if has_file else tk.DISABLED)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)

    def _update_time_label(self, pos: float):
        """Update the time display  current / total."""
        total = self.duration_sec
        def fmt(sec):
            m, s = divmod(max(0, sec), 60)
            return f"{int(m)}:{int(s):02d}"
        self.time_label.config(text=f"{fmt(pos)} / {fmt(total)}")

    # =====================================================================
    #  Playhead animation
    # =====================================================================
    def _animate_playhead(self):
        """Timer tick: update playhead line position every ~40ms."""
        if not self.is_playing:
            return

        pos = _time.time() - self.play_start_time

        # Check if playback reached the end
        if pos >= self.duration_sec:
            self._stop()
            return

        self._draw_playhead(pos)
        self._update_time_label(pos)

        # Schedule next tick
        self._playhead_after_id = self.root.after(40, self._animate_playhead)

    def _draw_playhead(self, pos_sec: float):
        """Draw or move the vertical playhead line on the axes."""
        if self.playhead_line is not None:
            try:
                self.playhead_line.set_xdata([pos_sec, pos_sec])
            except Exception:
                self.playhead_line = None

        if self.playhead_line is None:
            self.playhead_line = self.ax.axvline(
                x=pos_sec, color="#ffffff", linewidth=1.5,
                alpha=0.9, zorder=10
            )
        self.canvas.draw_idle()

    def _remove_playhead(self):
        """Remove the playhead line from the axes."""
        if self.playhead_line is not None:
            try:
                self.playhead_line.remove()
            except Exception:
                pass
            self.playhead_line = None
            if self.samples is not None:
                self.canvas.draw_idle()

    def _cancel_playhead_timer(self):
        """Cancel the pending after() callback."""
        if self._playhead_after_id is not None:
            self.root.after_cancel(self._playhead_after_id)
            self._playhead_after_id = None

    # =====================================================================
    #  Click-to-seek
    # =====================================================================
    def _on_canvas_click(self, event):
        """Click on the waveform to seek to that time position."""
        if event.inaxes != self.ax:
            return
        if self.samples is None:
            return
        # Only seek when the matplotlib toolbar is not in zoom/pan mode
        if self.toolbar.mode != '':
            return

        seek_time = max(0.0, min(event.xdata, self.duration_sec))
        self.play_offset = seek_time

        _ensure_imports()

        if self.is_playing:
            # Restart from the new position
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=seek_time)
            self.play_start_time = _time.time() - seek_time
        elif self.is_paused:
            # Update offset, will resume from here
            self._draw_playhead(seek_time)
            self._update_time_label(seek_time)
        else:
            # Not playing – just show playhead at click position
            self._draw_playhead(seek_time)
            self._update_time_label(seek_time)

    # =====================================================================
    #  Window close
    # =====================================================================
    def _on_close(self):
        """Clean shutdown: stop playback, quit pygame, destroy window."""
        self._cancel_playhead_timer()
        _ensure_imports()
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass
        self.root.destroy()

    # =====================================================================
    #  Slider callbacks
    # =====================================================================
    def _on_threshold_change(self, _value):
        val = self.threshold_var.get()
        self.threshold_value_label.config(text=f"{val:.4f}")
        if self.samples is not None:
            self._redraw()

    def _on_smooth_change(self, _value):
        val = self.smooth_var.get()
        self.smooth_value_label.config(text=f"{val} ms")
        if self.samples is not None:
            self.envelope_window_ms = val
            self._compute_envelope()
            self._update_threshold_slider_range()
            self._redraw()


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    app = AudioAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
