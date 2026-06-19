// =============================================================================
// AMTradeCockpit V2_6  —  L1 Pure Detection Indicator
// =============================================================================
// V2_6 is the L1 layer of the architect-spec'd L1/L2/L3 stack:
//   - L1 (this file): pure detection. Surfaces every candidate inside [low,high].
//                      No gating. No silent drops. No order/staging logic.
//   - L2 (Strategy):   scoring/ranking/decision. Hosts L1, subscribes to OnCandidate.
//   - L3 (Strategy):   safety gates. Owns lockouts, cooldowns, RTH cutoff, kill-switch.
//
// The first invariant: a bug that lets a trade through (recoverable, visible) is
// infinitely preferable to a bug that blocks one (silent, invisible).
//
// Major changes vs V2_4:
//   * Pattern A (level retest) and Pattern B (look-below/above-and-fail) both
//     surface as candidates.  No first-touch latching, no retrace-side gate, no
//     "best-only" pick.  Every level inside [low,high] emits its own candidate.
//   * LevelWatchState lifecycle (Untouched → Breached → Armed → Consumed/Invalidated)
//     drives Pattern B.  Each transition emits pattern_b_state_change.
//   * News-candle wick detection (volume > max(yesterday 9:30, yesterday 3:30)).
//   * 1:30 PM candle captured (Close130).  Multi-day master-candle revisits
//     (Pday1/2/3 Close330) exposed as candidate-eligible levels.
//   * Daily Woody's-style pivots PP/R1-R3/S1-S3 added to the candidate pool.
//   * VWAP/AnchVWAP surfaced as permission-level candidates (is_permission_level=true).
//   * box_capture JSONL events (every master-candle capture).
//   * Day-type vocab fixed: heartbeat emits day_type_v2 with Sideways/LongTrend/etc.
//     instead of the legacy congestion/trending labels.
//   * abstain JSONL events on the only remaining "skips" L1 makes (outside RTH window
//     or pre-warmup).
//   * Errors no longer swallowed silently — every catch emits an error JSONL event
//     in BOTH Historical and Realtime.
//   * Removed: SetSignal, MonitorSignal, RecordAndDrawTrade, OnStageClicked,
//     OnSkipClicked, Staging Card, demo signal, ATM-template params.  Those
//     concerns belong to L2/L3.
//   * State snapshots to state.json (writes on candidate emission and box capture).
//     Restore is currently informational only; do not rely on Pattern B continuity
//     across a NT restart until full deserialization is implemented and replay-tested.
//
// Coexists with V2_5 in the same Indicators folder.  Class name AMTradeCockpitV2_6.
// =============================================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    // CockpitDetailLevel / CockpitLabelPosition / CockpitCornerPosition are
    // declared in AMTradeCockpit.cs and shared across this namespace.

    public class AMTradeCockpitV2_6 : Indicator
    {
        // =================================================================
        // INTERNAL TYPES
        // =================================================================

        private class CandleBox
        {
            public string Name;
            public double High;
            public double Low;
            public double Open;
            public double Close;
            public double Volume;
            public DateTime StartTime;
            public DateTime EndTime;
            public bool IsComplete;
            public Brush BoxColor;
            public double Range => High - Low;

            public double BodyTop    => Math.Max(Open, Close);
            public double BodyBottom => Math.Min(Open, Close);
            public double BodySize   => Math.Abs(Close - Open);
            public double UpperWick  => High - BodyTop;
            public double LowerWick  => BodyBottom - Low;
            public bool   HasLargeWick
            {
                get
                {
                    if (BodySize <= 0) return true;
                    return UpperWick > BodySize || LowerWick > BodySize;
                }
            }

            public bool Contains(CandleBox other)
            {
                if (other == null) return false;
                return other.High <= this.High && other.Low >= this.Low;
            }

            public bool PartiallyOverlaps(CandleBox other)
            {
                if (other == null) return false;
                if (Contains(other) || other.Contains(this)) return false;
                bool highInside = other.High <= this.High && other.High >= this.Low;
                bool lowInside  = other.Low  >= this.Low  && other.Low  <= this.High;
                return highInside || lowInside;
            }

            public bool BodyStrictlyAbove(CandleBox other)
            {
                if (other == null) return false;
                return this.BodyBottom > other.BodyTop;
            }

            public bool BodyStrictlyBelow(CandleBox other)
            {
                if (other == null) return false;
                return this.BodyTop < other.BodyBottom;
            }
        }

        private class DayBoxes
        {
            public DateTime Date;
            public CandleBox Close330;       // A — prior 3:30 (or 10:00 for CL)
            public CandleBox GlobEx6PM;      // B
            public CandleBox Midnight;
            public CandleBox Europe4AM;      // C
            public CandleBox RTH930;         // D
            public CandleBox RTH1Min;
            public CandleBox Close130;       // 1:30 PM candle (V2_6 addition)
            public string InstitutionalName;
            public double SessionHigh;
            public double SessionLow;
            public double SessionClose;
            public double RTH930OpenPx = double.NaN;
            public MOCValidation MocState = MOCValidation.Pending;
            public double MocRatio = double.NaN;
            public double Sma200At930 = double.NaN;
            public double Sma200SlopeDelta = double.NaN;
            public double V930Volume = double.NaN;     // 9:30 30-min bar volume (for news-wick threshold)
            public double V330Volume = double.NaN;     // 3:30 30-min bar volume
            public bool   Sma200SlopeUp   { get { return !double.IsNaN(Sma200SlopeDelta) && Sma200SlopeDelta > 0; } }
            public bool   Sma200SlopeDown { get { return !double.IsNaN(Sma200SlopeDelta) && Sma200SlopeDelta < 0; } }
        }

        private enum LevelWatchStatus { Untouched, Breached, Armed, Consumed, Invalidated }

        // V2_6 Pattern B per-level state machine.  One instance per (level_name, direction)
        // per session.  Resets on session rollover.  Persists in state.json so a NT restart
        // does not lose an in-progress breach.
        private class LevelWatchState
        {
            public string    LevelName;
            public double    LevelPrice;
            public string    Direction;        // "LONG" or "SHORT"
            public LevelWatchStatus Status;
            public CandleBox AnchorCandle;     // the breach candle (Pattern B)
            public DateTime  BreachTime;
            public double    BreachBarHigh;
            public double    BreachBarLow;
            public double    BreachBarVolume;
            public DateTime  ArmedAtTime;
        }

        // V2_6 news-wick (volume-outlier) registration.
        private class NewsWick
        {
            public string Kind;                // "lower" or "upper"
            public double LevelPrice;
            public DateTime CandleTime;
            public double CandleVolume;
            public double RatioToMax;
            public bool   Active;
        }

        // V2_6 §3.3 / §7 — public so the L2 strategy can reference the enum
        // returned from MocState / CurrentDayType3Node / CurrentDayType4Node.
        public enum MOCValidation { Pending, Green, Orange, Gray }
        private enum Bias { Wait, Long, Short, Neutral }

        private enum TradingPhase
        {
            PreGlobEx, GlobExOpen, Midnight, EuropeOpen,
            RTHOpen, RTHActive, RTHClose
        }

        // V2_6: AM's apr-24 day-type classification (body-stack on prior 3:30 →
        // 6 PM Globex → 4 AM Europe → 9:30 RTH).  Both 3-node (B<C<D) and 4-node
        // (A<B<C<D) interpretations are emitted as features per architect spec
        // §11.1 — the L2 scorer decides which interpretation matters.
        // Public so L2 strategies can consume the enum from CurrentDayType*Node.
        public enum AMDayType
        {
            Unknown, LongTrend, ShortTrend, CautiousLong, CautiousShort, Sideways
        }

        // Public so L2 strategies can consume the current AM directional filter.
        public enum AMDirectionFilter { Unknown, Long, Short, Sideways }

        private enum DayType { Unknown, Congestion, Trending, Extended }

        private class PriceLabel
        {
            public double Price;
            public string Text;
            public Brush Color;
            public DashStyleHelper Dash;
            public int LineWidth;
            public bool DrawLine = true;                  // false = label-only (line drawn elsewhere)
            public CockpitLabelPosition? SideOverride;    // null = use global LabelPosition
        }

        // =================================================================
        // CANDIDATE / BOX_CAPTURE EVENT ARGS (in-process subscribers)
        // =================================================================

        // Hosting Strategy subscribes to OnCandidate to receive every level
        // interaction L1 detects.  No gating happens here — L2 ranks/decides.
        public class CandidateEventArgs
        {
            public string CandidateId;
            public DateTime BarTime;
            public string SessionDate;
            public string LevelName;
            public double LevelPrice;
            public bool   IsPermissionLevel;
            public string Direction;            // "LONG" / "SHORT"
            public string PatternType;          // "A" or "B"
            public string LwsState;             // null for Pattern A
            public double BarOpen, BarHigh, BarLow, BarClose;
            public double BarVolume;
            // anchor candle: this 1-min bar (A), or breach candle (B)
            public double AnchorHigh, AnchorLow, AnchorBodyTop, AnchorBodyBottom, AnchorVolume;
            public DateTime AnchorTime;
            // Feature vector — flat dictionary so the JSONL builder can stamp it
            // verbatim and the strategy can scope-cast at need.
            public Dictionary<string, object> Features;
        }

        public class BoxCaptureEventArgs
        {
            public string Name;
            public string Subtype;             // "primary" | "institutional_reassignment"
            public int InstanceDayOffset;
            public DateTime StartTime;
            public double High, Low, Open, Close, Volume;
            public bool IsInstitutionalNow;
            public double MocRatio;
            public string MocState;
        }

        public class AbstainEventArgs
        {
            public DateTime BarTime;
            public string Reason;
            public string Layer;               // "L1"
            public string CandidateId;         // V2_6 spec §3.5: every abstain references the candidate
            public string GateName;
        }

        // -------------------------------------------------------------------
        // DEPRECATED LEGACY EVENT ARGS (V2_4 compatibility shim)
        //
        // Pre-refactor V2_4 emitted OnTouch/OnSignal with these payloads. V2_6
        // replaces them with OnCandidate (full feature vector). These classes
        // remain ONLY so that downstream strategies that still reference the
        // legacy events compile; V2_6 itself does NOT fire them. A subscriber
        // SHOULD migrate to OnCandidate. See architect spec §3.3, §7.1.
        // -------------------------------------------------------------------
        [Obsolete("V2_6 emits OnCandidate with full feature vector. TouchEventArgs is retained only for backwards-compat with V2_4-era subscribers and is never fired by V2_6.")]
        public class TouchEventArgs
        {
            public DateTime EventTs;
            public string SessionDate;
            public string Level;
            public double LevelPrice;
            public string Direction;
            public double BarOpen, BarHigh, BarLow, BarClose;
            public bool   RetraceSide;
            public bool   AlreadyLatched;
        }

        [Obsolete("V2_6 does not emit signals (L2 owns signaling). SignalEventArgs is retained for compile compat only.")]
        public class SignalEventArgs
        {
            public DateTime EventTs;
            public string Level;
            public string Direction;
            public double Entry;
            public double Stop;
            public string Phase;
            public string DayType;
        }

        public event Action<CandidateEventArgs>  OnCandidate;
        public event Action<BoxCaptureEventArgs> OnBoxCapture;
        public event Action<AbstainEventArgs>    OnAbstain;

        // Deprecated legacy events. V2_6 NEVER fires these. They exist only so
        // that subscribers built against V2_4 (which expected OnTouch/OnSignal)
        // compile against V2_6 without code changes. New code MUST use
        // OnCandidate per architect spec §3.3.
        #pragma warning disable 67    // event never used by indicator (intentional — legacy compat only)
        [Obsolete("V2_6 emits OnCandidate, not OnTouch. Use OnCandidate.")]
        public event Action<TouchEventArgs>      OnTouch;
        [Obsolete("V2_6 does not emit signals (L2 owns signaling). Subscribe to OnCandidate.")]
        public event Action<SignalEventArgs>     OnSignal;
        #pragma warning restore 67

        // =================================================================
        // STATE FIELDS
        // =================================================================

        // Day boxes
        private List<DayBoxes> dayHistory;
        private DayBoxes currentDay;
        private DayBoxes priorDay;

        // Institutional
        private CandleBox institutionalBox;
        private string institutionalName;
        private string priorDayInstitutionalName;

        // SMAs
        private double sma50_30min  = double.NaN;
        private double sma200_30min = double.NaN;
        private double sma50_1min   = double.NaN;
        private double sma200_1min  = double.NaN;
        private string smaDirection30;
        private string smaDirection1;
        private double priorSma200At930 = double.NaN;

        // VWAP
        private double currentVWAP = double.NaN;
        private string vwapSlope;
        private double cumulativeTPV, cumulativeVol, prevVWAP;

        // Anchored VWAP
        private DateTime v2AVWAPAnchorTime = DateTime.MinValue;
        private double   v2AVWAPCumTPV;
        private double   v2AVWAPCumVol;
        private double   v2AVWAP = double.NaN;

        // Pivots (Woody's-style daily)
        private double pivotPP, pivotR1, pivotR2, pivotR3, pivotR4;
        private double pivotS1, pivotS2, pivotS3, pivotS4;
        private bool pivotsCalculated;

        // RTH session tracking (for next-day pivots)
        private double rthSessionHigh, rthSessionLow;
        private bool rthSessionTracking;

        // 1-minute opening candle
        private double rth1MinHigh, rth1MinLow;
        private int rth1MinVolume;
        private bool rth1MinComplete;

        // Day-type / bias / phase
        private DayType currentDayType;
        private Bias currentBias;
        private TradingPhase currentPhase;
        private AMDayType lastDayTypeEmitted = AMDayType.Unknown;
        private AMDayType lastDayTypeEmitted4Node = AMDayType.Unknown;
        private AMDirectionFilter lastDirectionFilterEmitted = AMDirectionFilter.Unknown;

        // Rolling Pr30
        private double v2PriorRolling30High;
        private double v2PriorRolling30Low;
        private DateTime v2PriorRolling30BarTime;

        // Opening range
        private double v2OpenRangeHigh;
        private double v2OpenRangeLow;
        private bool v2OpenRangeLocked;

        // ADR_20
        private Queue<double> v2DailyRanges = new Queue<double>();
        private double v2TodayHigh = double.NaN;
        private double v2TodayLow  = double.NaN;
        private DateTime v2TodayDate = DateTime.MinValue;
        private double v2Adr20 = double.NaN;

        // Pattern B state machines (per (level_name, direction))
        private Dictionary<string, LevelWatchState> levelWatchStates = new Dictionary<string, LevelWatchState>();

        // News wicks
        private List<NewsWick> newsWicks = new List<NewsWick>();

        // L1 informational counters (computed for diagnostic display only — never gate candidate emission)
        private bool lockoutActive;
        private string lockoutReason;
        private int losingTradesToday;
        private double realizedPnlDollarsToday;
        private DateTime lastStopTime;

        // Per-session stats
        private int candidatesEmittedToday;
        private int patternBArmedToday;
        private HashSet<string> uniqueLevelsTouchedToday = new HashSet<string>();
        // High-value subset (master candles + Pday1 + news wicks) — same prefixes
        // DrawCandidateMarker uses.  Tracks the levels that actually get a chart
        // marker, useful for at-a-glance "what's been hit that I care about."
        private HashSet<string> highValueLevelsTouchedToday = new HashSet<string>();

        // Pre-touch watch labels: the levels a trader should be watching before
        // price gets there. These are chart-only and do not emit candidates.
        private const int MaxPreTouchWatchLevelsPerSide = 6;
        private HashSet<string> preTouchCandidateTags = new HashSet<string>();

        // Deterministic candidate_id sequence counters keyed by
        // "{HHmm}_{level}_{direction}". Per integration spec Gap 3 / architect
        // §3.3, the seq segment is 001..NNN within a (bar, level, direction)
        // tuple — typically 001 except on re-emission. Cleared on session
        // rollover by ResetForNewDay.
        private Dictionary<string, int> candidateSeqByKey = new Dictionary<string, int>();

        // Data series indices
        private int idx30Min = -1;
        private int idx1Min  = -1;

        // SMA caches
        private SMA sma50Ind30, sma200Ind30;
        private SMA sma50Ind1, sma200Ind1;

        // Instrument-specific times
        private bool isCL;
        private int closeHour, closeMinute;
        private int rthOpenHour, rthOpenMinute;
        private int instCloseHour, instCloseMinute;

        // SharpDX cached resources
        private SharpDX.Direct2D1.RenderTarget cachedTarget;
        private SharpDX.Direct2D1.SolidColorBrush dxBgBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxTextBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxBorderBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxTitleTextBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxTealBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxAmberBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxDimGoldBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxRedBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxGreenBrush;
        private SharpDX.Direct2D1.SolidColorBrush dxSlateBrush;
        private SharpDX.DirectWrite.TextFormat dxTextFormat;
        private SharpDX.DirectWrite.TextFormat dxTitleFormat;

        // Drawing tag / label tracking
        private List<string> sessionDrawTags;
        private string prevInstitutionalTag;
        private Dictionary<string, PriceLabel> priceLabels;

        // JSONL log
        private string jsonlPathToday;
        private DateTime jsonlDateActive;
        private DateTime lastHeartbeatAt;
        private string lastPhaseLogged;
        private string lastBiasLogged;

        // Logging
        private List<string> logEntries;

        // Daily diagnostics
        private int diagBarsChecked;

        // Coach panel
        private string currentCoachMessage;

        // State.json path (set in DataLoaded)
        private string stateJsonPath;
        private DateTime lastStatePersistedAt = DateTime.MinValue;

        // Snapshot of latest 1-min bar time for OnRender
        private DateTime lastBarTime = DateTime.MinValue;

        // =================================================================
        // USER PARAMETERS
        // =================================================================

        [NinjaScriptProperty]
        [Display(Name = "Detail Level", Order = 0, GroupName = "1. Display")]
        public CockpitDetailLevel DetailLevel { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Only Current Session", Order = 1, GroupName = "1. Display")]
        public bool ShowOnlyCurrentSession { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Label Position", Order = 2, GroupName = "1. Display")]
        public CockpitLabelPosition LabelPosition { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Key Candle Label Side (1-min only)", Order = 3, GroupName = "1. Display")]
        public CockpitLabelPosition KeyCandleLabelSide { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Institutional Candle Corner", Order = 4, GroupName = "1. Display")]
        public CockpitCornerPosition InstitutionalCorner { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Candidate Markers", Order = 4, GroupName = "1. Display")]
        public bool ShowCandidateMarkers { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Pre-Touch Candidate Levels", Order = 5, GroupName = "1. Display")]
        public bool ShowPreTouchCandidateLevels { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Days of History", Order = 0, GroupName = "2. Data")]
        [Range(3, 10)]
        public int DaysOfHistory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Lookback Days For Levels", Order = 1, GroupName = "2. Data")]
        [Range(1, 5)]
        public int MaxLookbackDaysForLevels { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Pattern A (level retest)", Order = 0, GroupName = "3. Detection")]
        public bool EnablePatternA { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Pattern B (look-below/above-and-fail)", Order = 1, GroupName = "3. Detection")]
        public bool EnablePatternB { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Emit VWAP As Permission Level", Order = 2, GroupName = "3. Detection")]
        public bool EmitVwapAsPermissionLevel { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "News Volume Multiplier Threshold", Order = 3, GroupName = "3. Detection")]
        [Range(0.5, 5.0)]
        public double NewsVolumeMultiplierThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show 50 SMA", Order = 0, GroupName = "4. Moving Averages")]
        public bool Show50SMA { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show 200 SMA", Order = 1, GroupName = "4. Moving Averages")]
        public bool Show200SMA { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Legend X Offset (px from left)", Order = 0, GroupName = "5. Layout")]
        [Range(0, 2000)]
        public int LegendXOffset { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Legend Y Offset (px from top)", Order = 1, GroupName = "5. Layout")]
        [Range(0, 800)]
        public int LegendYOffset { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pre-Place Panel X Offset", Order = 2, GroupName = "5. Layout")]
        [Range(0, 2000)]
        public int PrePlacePanelX { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Pre-Place Panel Y Offset", Order = 3, GroupName = "5. Layout")]
        [Range(0, 1200)]
        public int PrePlacePanelY { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable JSONL Event Log", Order = 0, GroupName = "6. Cockpit Logger")]
        public bool EnableJsonlLog { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "JSONL Log Root Folder", Order = 1, GroupName = "6. Cockpit Logger")]
        public string JsonlLogFolder { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Heartbeat Seconds (0 = disabled)", Order = 2, GroupName = "6. Cockpit Logger")]
        public int HeartbeatSeconds { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable State Persistence (state.json)", Order = 3, GroupName = "6. Cockpit Logger")]
        public bool EnableStatePersistence { get; set; }

        // Brush colors (preserved from V2_4)
        [XmlIgnore]
        [Display(Name = "Institutional Candle Color", Order = 0, GroupName = "7. Colors")]
        public Brush InstitutionalColor { get; set; }
        [Browsable(false)]
        public string InstitutionalColorSerializable
        { get { return Serialize.BrushToString(InstitutionalColor); } set { InstitutionalColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "GlobEx Box Color", Order = 1, GroupName = "7. Colors")]
        public Brush GlobExColor { get; set; }
        [Browsable(false)]
        public string GlobExColorSerializable
        { get { return Serialize.BrushToString(GlobExColor); } set { GlobExColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "Europe Box Color", Order = 2, GroupName = "7. Colors")]
        public Brush EuropeColor { get; set; }
        [Browsable(false)]
        public string EuropeColorSerializable
        { get { return Serialize.BrushToString(EuropeColor); } set { EuropeColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "RTH Box Color", Order = 3, GroupName = "7. Colors")]
        public Brush RTHColor { get; set; }
        [Browsable(false)]
        public string RTHColorSerializable
        { get { return Serialize.BrushToString(RTHColor); } set { RTHColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "Close Box Color", Order = 4, GroupName = "7. Colors")]
        public Brush CloseColor { get; set; }
        [Browsable(false)]
        public string CloseColorSerializable
        { get { return Serialize.BrushToString(CloseColor); } set { CloseColor = Serialize.StringToBrush(value); } }

        [XmlIgnore]
        [Display(Name = "Midnight Line Color", Order = 5, GroupName = "7. Colors")]
        public Brush MidnightColor { get; set; }
        [Browsable(false)]
        public string MidnightColorSerializable
        { get { return Serialize.BrushToString(MidnightColor); } set { MidnightColor = Serialize.StringToBrush(value); } }

        // =================================================================
        // PUBLIC READ-ONLY PROPERTIES (for L2 cross-layer access)
        // -----------------------------------------------------------------
        // Per integration spec Gap 2: the L2 strategy needs live access to
        // L1 state (day-type, MOC, slope, master-candle anchors, ADR, VWAP).
        // These getters never throw and never mutate state. They are recomputed
        // on demand where cheap; otherwise they read cached fields populated by
        // the bar-processing pipeline.
        // =================================================================

        public bool LockoutActive            => lockoutActive;
        public int  CandidatesEmittedToday   => candidatesEmittedToday;
        public int  PatternBArmedToday       => patternBArmedToday;

        // Day-type classifications — both 3-node and 4-node interpretations
        // (architect §11.1). Computed on demand from currentDay's body stack.
        public AMDayType CurrentDayType3Node => ClassifyAMDayType3Node();
        public AMDayType CurrentDayType4Node => ClassifyAMDayType4Node();
        public AMDirectionFilter CurrentDirectionFilter => ComputeDirectionFilter();

        // MOC validation. "Pending" before today's 3:30 bar closes.
        public MOCValidation MocState
            => currentDay != null ? currentDay.MocState : MOCValidation.Pending;
        public double MocRatio
            => currentDay != null ? currentDay.MocRatio : double.NaN;

        // 200 SMA slope (delta points across last 30-min RTH bars).
        public double Sma200SlopeDeltaPts
            => currentDay != null ? currentDay.Sma200SlopeDelta : double.NaN;
        public bool Sma200SlopeUp
            => currentDay != null && currentDay.Sma200SlopeUp;
        public bool Sma200SlopeDown
            => currentDay != null && currentDay.Sma200SlopeDown;

        // Institutional master-candle anchor. Null/NaN until determined.
        public double InstitutionalHigh
            => institutionalBox != null ? institutionalBox.High : double.NaN;
        public double InstitutionalLow
            => institutionalBox != null ? institutionalBox.Low  : double.NaN;
        public string InstitutionalName  => institutionalName;

        // ADR_20 (20-day average daily range, points).
        public double Adr20 => v2Adr20;

        // 4 AM Europe-session range width.
        public double EuropeWidth
            => (currentDay != null && currentDay.Europe4AM != null)
               ? (currentDay.Europe4AM.High - currentDay.Europe4AM.Low) : double.NaN;

        // VWAP / AnchVWAP live values.
        public double VWAPValue     => currentVWAP;
        public double AnchVWAPValue => v2AVWAP;

        // =================================================================
        // LIFECYCLE
        // =================================================================

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "AMTradeCockpit V2_6 — L1 pure detection. Surfaces every candidate inside [low,high] with rich feature vector. Hosted by an L2 strategy for scoring + L3 safety.";
                Name = "AMTradeCockpitV2_6";
                IsOverlay = true;
                IsSuspendedWhileInactive = false;
                Calculate = Calculate.OnBarClose;

                DetailLevel = CockpitDetailLevel.Full;
                ShowOnlyCurrentSession = true;
                LabelPosition = CockpitLabelPosition.Right;
                KeyCandleLabelSide = CockpitLabelPosition.Right;
                InstitutionalCorner = CockpitCornerPosition.TopRight;
                ShowCandidateMarkers = true;
                ShowPreTouchCandidateLevels = true;

                DaysOfHistory = 5;
                MaxLookbackDaysForLevels = 3;

                EnablePatternA = true;
                EnablePatternB = true;
                EmitVwapAsPermissionLevel = true;
                NewsVolumeMultiplierThreshold = 1.0;

                Show50SMA = true;
                Show200SMA = true;

                LegendXOffset = 8;
                LegendYOffset = 25;
                PrePlacePanelX = 10;
                PrePlacePanelY = 65;

                EnableJsonlLog = true;
                JsonlLogFolder = @"C:\seasonals\cockpit\sessions";
                HeartbeatSeconds = 30;
                EnableStatePersistence = true;

                AddPlot(new Stroke(Brushes.DeepPink, 2), PlotStyle.Line, "SMA50");
                AddPlot(new Stroke(Brushes.LightGray, 2), PlotStyle.Line, "SMA200");

                InstitutionalColor = Brushes.Gold;
                GlobExColor = Brushes.Cyan;
                EuropeColor = Brushes.Orange;
                RTHColor = Brushes.Magenta;
                CloseColor = Brushes.HotPink;
                MidnightColor = Brushes.Gray;
            }
            else if (State == State.Configure)
            {
                if (BarsPeriod.BarsPeriodType == BarsPeriodType.Minute && BarsPeriod.Value == 30)
                {
                    AddDataSeries(Instrument.FullName, new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1 });
                    idx30Min = 0;
                    idx1Min = 1;
                }
                else if (BarsPeriod.BarsPeriodType == BarsPeriodType.Minute && BarsPeriod.Value == 1)
                {
                    AddDataSeries(Instrument.FullName, new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 30 });
                    idx1Min = 0;
                    idx30Min = 1;
                }
                else
                {
                    AddDataSeries(Instrument.FullName, new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 30 });
                    AddDataSeries(Instrument.FullName, new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1 });
                    idx30Min = 1;
                    idx1Min = 2;
                }
            }
            else if (State == State.DataLoaded)
            {
                // Wipe historical drawings from prior runs
                try
                {
                    string[] legacyBoxNames = { "GlobEx 6PM", "Europe 4AM", "RTH 9:30", "Close 3:30", "Close 10:00", "Midnight", "RTH 1-Min", "Close 1:30" };
                    foreach (var nm in legacyBoxNames)
                    {
                        RemoveDrawObject($"Box_{nm}_Rect");
                        RemoveDrawObject($"Box_{nm}_Top");
                        RemoveDrawObject($"Box_{nm}_Bot");
                        RemoveDrawObject($"Box_{nm}_DashTop");
                        RemoveDrawObject($"Box_{nm}_DashBot");
                    }
                    for (int k = 1; k <= 500; k++)
                    {
                        RemoveDrawObject($"V26Cand_{k}");
                    }
                }
                catch { /* expected on first load */ }

                if (idx30Min >= 0)
                {
                    sma50Ind30 = SMA(BarsArray[idx30Min], 50);
                    sma200Ind30 = SMA(BarsArray[idx30Min], 200);
                }
                if (idx1Min >= 0)
                {
                    sma50Ind1 = SMA(BarsArray[idx1Min], 50);
                    sma200Ind1 = SMA(BarsArray[idx1Min], 200);
                }

                isCL = Instrument != null
                    && Instrument.MasterInstrument != null
                    && string.Equals(Instrument.MasterInstrument.Name, "CL", StringComparison.OrdinalIgnoreCase);
                closeHour       = isCL ? 14 : 15;
                closeMinute     = isCL ? 30 :  0;
                rthOpenHour     = isCL ?  9 :  9;
                rthOpenMinute   = isCL ?  0 : 30;     // V2_6 keeps the CL 9:00 ET RTH open rule.
                instCloseHour   = isCL ? 10 : 15;
                instCloseMinute = isCL ?  0 : 30;

                dayHistory = new List<DayBoxes>();
                logEntries = new List<string>();
                sessionDrawTags = new List<string>();
                priceLabels = new Dictionary<string, PriceLabel>();

                currentDayType = DayType.Unknown;
                currentBias = Bias.Wait;
                currentPhase = TradingPhase.PreGlobEx;
                currentCoachMessage = "AMTradeCockpit V2_6 initializing...";
                institutionalName = "Determining...";
                priorDayInstitutionalName = "";
                pivotsCalculated = false;

                // Try to restore state.json
                TryRestoreStateJson();

                Log("AMTradeCockpit V2_6 initialized (L1 detection-only).");
            }
            else if (State == State.Terminated)
            {
                if (EnableStatePersistence)
                    PersistStateJson("terminated");
                DisposeSharpDX();
            }
        }

        // =================================================================
        // OnBarUpdate — top-level dispatch
        // =================================================================

        protected override void OnBarUpdate()
        {
            if (CurrentBars[BarsInProgress] < 2) return;

            if (BarsInProgress == 0)
            {
                bool have30_50  = Show50SMA  && idx30Min >= 0 && sma50Ind30  != null
                                  && CurrentBars[idx30Min] >= 50  && sma50Ind30.Count  > 0;
                bool have30_200 = Show200SMA && idx30Min >= 0 && sma200Ind30 != null
                                  && CurrentBars[idx30Min] >= 200 && sma200Ind30.Count > 0;
                Values[0][0] = have30_50  ? sma50Ind30[0]  : double.NaN;
                Values[1][0] = have30_200 ? sma200Ind30[0] : double.NaN;

                // Extend the SMA lines one bar forward into the forming bar.
                // Calculate.OnBarClose normally stops the plot at the last
                // CLOSED bar; this Draw.Line overlay (start=0=current bar,
                // end=-1=one bar in the future) carries the same value forward
                // so the line visually reaches the right edge.  Tag is reused
                // each bar so only ONE extension exists at a time.
                if (have30_50)
                    Draw.Line(this, "SMA50_extend", false, 0, sma50Ind30[0],
                              -1, sma50Ind30[0], Brushes.DeepPink,
                              DashStyleHelper.Solid, 2);
                if (have30_200)
                    Draw.Line(this, "SMA200_extend", false, 0, sma200Ind30[0],
                              -1, sma200Ind30[0], Brushes.LightGray,
                              DashStyleHelper.Solid, 2);

                // NO early return here.  When the chart's primary timeframe is
                // 30-min, BarsInProgress==0 IS the 30-min bar, and we MUST fall
                // through to the BarsInProgress==idx30Min branch below to fire
                // Process30MinBar.  An early return here breaks all box capture
                // and drawing on 30-min-primary charts (V2_4 didn't have this
                // return; the L1 refactor agent added it as an "optimization"
                // and silently killed every visual feature).
            }

            // Per architect spec §5.7: every exception emits an error event in BOTH
            // Historical and Realtime.  No swallowing.
            try
            {
                if (BarsInProgress == idx30Min)
                {
                    Process30MinBar();
                    LogEvent("bar_close",
                        "tf", "30m",
                        "o", Opens[idx30Min][0],
                        "h", Highs[idx30Min][0],
                        "l", Lows[idx30Min][0],
                        "c", Closes[idx30Min][0],
                        "v", (double)Volumes[idx30Min][0]);
                }
                else if (BarsInProgress == idx1Min)
                {
                    Process1MinBar();
                    LogEvent("bar_close",
                        "tf", "1m",
                        "o", Opens[idx1Min][0],
                        "h", Highs[idx1Min][0],
                        "l", Lows[idx1Min][0],
                        "c", Closes[idx1Min][0],
                        "v", (double)Volumes[idx1Min][0]);

                    string phaseNow = currentPhase.ToString().ToLowerInvariant();
                    if (lastPhaseLogged != null && lastPhaseLogged != phaseNow)
                        LogEvent("phase_change", "from", lastPhaseLogged, "to", phaseNow);
                    lastPhaseLogged = phaseNow;

                    string biasNow = currentBias.ToString().ToLowerInvariant();
                    if (lastBiasLogged != null && lastBiasLogged != biasNow)
                        LogEvent("bias_change", "from", lastBiasLogged, "to", biasNow);
                    lastBiasLogged = biasNow;

                    MaybeHeartbeat(Closes[idx1Min][0]);
                }
            }
            catch (Exception ex)
            {
                EmitError(ex);
            }
        }

        // =================================================================
        // 30-MINUTE BAR PROCESSING
        // =================================================================

        private void Process30MinBar()
        {
            DateTime barTime = Times[idx30Min][0];
            DateTime barOpen = barTime.AddMinutes(-30);
            int h = barOpen.Hour;
            int m = barOpen.Minute;

            double high  = Highs[idx30Min][0];
            double low   = Lows[idx30Min][0];
            double close = Closes[idx30Min][0];
            double open  = Opens[idx30Min][0];
            double vol   = Volumes[idx30Min][0];

            // VWAP slope snapshot
            double slopeThresh = 4 * TickSize;
            if (h == rthOpenHour && m == rthOpenMinute)
                vwapSlope = "Flat";
            else
            {
                double vwapDelta = currentVWAP - prevVWAP;
                vwapSlope = vwapDelta > slopeThresh ? "Up" : vwapDelta < -slopeThresh ? "Down" : "Flat";
            }
            prevVWAP = currentVWAP;

            // RTH session tracking for pivots
            bool isRTH = (h == rthOpenHour && m >= rthOpenMinute) || (h > rthOpenHour && h < closeHour) || (h == closeHour && m <= closeMinute);
            if (isRTH)
            {
                if (h == rthOpenHour && m == rthOpenMinute)
                {
                    rthSessionHigh = high;
                    rthSessionLow = low;
                    rthSessionTracking = true;
                }
                else if (rthSessionTracking)
                {
                    if (high > rthSessionHigh) rthSessionHigh = high;
                    if (low  < rthSessionLow)  rthSessionLow  = low;
                }
            }

            // ---- BOX CAPTURE ----

            // Session close (3:30 PM for ES/NQ/GC, 2:30 PM for CL)
            if (h == closeHour && m == closeMinute)
            {
                double sessClose = close;
                if (rthSessionTracking)
                {
                    if (high > rthSessionHigh) rthSessionHigh = high;
                    if (low  < rthSessionLow)  rthSessionLow  = low;
                }

                if (currentDay != null && currentDay.Close330 != null)
                {
                    currentDay.SessionHigh = rthSessionHigh;
                    currentDay.SessionLow = rthSessionLow;
                    currentDay.SessionClose = sessClose;
                    currentDay.InstitutionalName = institutionalName;
                    priorDay = currentDay;
                    priorDayInstitutionalName = institutionalName;
                    dayHistory.Add(currentDay);
                    while (dayHistory.Count > DaysOfHistory)
                        dayHistory.RemoveAt(0);
                }

                ResetForNewDay();

                if (rthSessionTracking && rthSessionHigh > 0)
                    CalculatePivots(rthSessionHigh, rthSessionLow, sessClose);
                rthSessionTracking = false;

                currentDay = new DayBoxes { Date = barTime.Date.AddDays(1) };
                Log($"SESSION CLOSED: archiving day, awaiting institutional capture.");

                if (pivotsCalculated && DetailLevel == CockpitDetailLevel.Full)
                    DrawPivotLines();
            }
            else if (h == 18 && m == 0)
            {
                EnsureCurrentDay(barTime);
                currentDay.GlobEx6PM = MakeBox("GlobEx 6PM", high, low, open, close, vol, barOpen, barTime, GlobExColor);
                EmitBoxCapture(currentDay.GlobEx6PM, "primary", 0, false);
                Log($"GLOBEX captured: {low:F2} - {high:F2}");
                DrawBoxLines(currentDay.GlobEx6PM);
                RunContainmentCheck();
            }
            else if (h == 0 && m == 0)
            {
                EnsureCurrentDay(barTime);
                currentDay.Midnight = MakeBox("Midnight", high, low, open, close, vol, barOpen, barTime, MidnightColor);
                EmitBoxCapture(currentDay.Midnight, "primary", 0, false);
                Log($"MIDNIGHT captured: {low:F2} - {high:F2}");
                if (DetailLevel == CockpitDetailLevel.Full)
                    DrawMidnightLines(currentDay.Midnight);
            }
            else if (h == 4 && m == 0)
            {
                EnsureCurrentDay(barTime);
                currentDay.Europe4AM = MakeBox("Europe 4AM", high, low, open, close, vol, barOpen, barTime, EuropeColor);
                EmitBoxCapture(currentDay.Europe4AM, "primary", 0, false);
                Log($"EUROPE captured: {low:F2} - {high:F2}");
                DrawBoxLines(currentDay.Europe4AM);
                RunContainmentCheck();
            }
            else if (h == rthOpenHour && m == rthOpenMinute)
            {
                EnsureCurrentDay(barTime);
                currentDay.RTH930 = MakeBox("RTH 9:30", high, low, open, close, vol, barOpen, barTime, RTHColor);
                currentDay.V930Volume = vol;
                EmitBoxCapture(currentDay.RTH930, "primary", 0, false);
                Log($"RTH 9:30 captured: {low:F2} - {high:F2}");
                DrawBoxLines(currentDay.RTH930);
                RunContainmentCheck();

                if (sma200Ind30 != null && sma200Ind30.Count > 0
                    && CurrentBars[idx30Min] >= 200)
                    sma200_30min = sma200Ind30[0];
                if (!double.IsNaN(sma200_30min) && sma200_30min > 0)
                {
                    currentDay.Sma200At930 = sma200_30min;
                    if (!double.IsNaN(priorSma200At930))
                    {
                        currentDay.Sma200SlopeDelta = sma200_30min - priorSma200At930;
                        string dir = currentDay.Sma200SlopeUp ? "UP" : (currentDay.Sma200SlopeDown ? "DOWN" : "FLAT");
                        Log($"200 SMA slope: {currentDay.Sma200SlopeDelta:+0.00;-0.00;0.00} → {dir}");
                    }
                    priorSma200At930 = sma200_30min;
                }

                if (institutionalBox != null && DetailLevel == CockpitDetailLevel.Full)
                    DrawMeasuredMoves(institutionalBox);
            }

            // V2_6: 1:30 PM candle (per AM mar-6 / apr-16) — daily turn-around level.
            if (h == 13 && m == 30)
            {
                EnsureCurrentDay(barTime);
                currentDay.Close130 = MakeBox("Close 1:30", high, low, open, close, vol, barOpen, barTime, Brushes.Pink);
                EmitBoxCapture(currentDay.Close130, "primary", 0, false);
                Log($"CLOSE 1:30 captured: {low:F2} - {high:F2}");
                DrawBoxLines(currentDay.Close130);
            }

            // Institutional candle capture
            if (h == instCloseHour && m == instCloseMinute)
            {
                EnsureCurrentDay(barTime);
                string instLabel = isCL ? "Close 10:00" : "Close 3:30";
                currentDay.Close330 = MakeBox(instLabel, high, low, open, close, vol, barOpen, barTime, CloseColor);
                currentDay.V330Volume = vol;
                Log($"INSTITUTIONAL captured ({instLabel}): {low:F2} - {high:F2}");
                DrawBoxLines(currentDay.Close330);
                institutionalBox = currentDay.Close330;
                institutionalName = instLabel;
                DrawInstitutionalBox(institutionalBox);

                // MOC validation
                if (idx30Min >= 0 && Volumes[idx30Min].Count > 1)
                {
                    double thisVol = Volumes[idx30Min][0];
                    double priorVol = Volumes[idx30Min][1];
                    if (priorVol > 0)
                    {
                        double ratio = thisVol / priorVol;
                        currentDay.MocRatio = ratio;
                        if (ratio > 1.20)      currentDay.MocState = MOCValidation.Green;
                        else if (ratio > 1.00) currentDay.MocState = MOCValidation.Orange;
                        else                   currentDay.MocState = MOCValidation.Gray;
                        Log($"MOC: ratio={ratio:F2} → {currentDay.MocState.ToString().ToUpperInvariant()}");
                    }
                }

                EmitBoxCapture(currentDay.Close330, "primary", 0, true);
            }

            // 30-min SMA direction
            if (sma50Ind30 != null && sma200Ind30 != null
                && CurrentBars[idx30Min] >= 210
                && sma50Ind30.Count > 5 && sma200Ind30.Count > 5)
            {
                sma50_30min = sma50Ind30[0];
                sma200_30min = sma200Ind30[0];

                if (CurrentBars[idx30Min] >= 215
                    && sma50Ind30.Count > 10 && sma200Ind30.Count > 10)
                {
                    double slope50 = sma50_30min - sma50Ind30[5];
                    double slope200 = sma200_30min - sma200Ind30[5];
                    if (slope50 > slopeThresh && slope200 > slopeThresh)
                        smaDirection30 = "Up";
                    else if (slope50 < -slopeThresh && slope200 < -slopeThresh)
                        smaDirection30 = "Down";
                    else
                        smaDirection30 = "Flat";
                }
            }

            // Rolling Pr30 — RTH only
            {
                int p30BarTotal = barTime.Hour * 60 + barTime.Minute;
                int p30RthOpen  = rthOpenHour * 60 + rthOpenMinute;
                int p30Close    = closeHour * 60 + closeMinute;
                if (p30BarTotal > p30RthOpen && p30BarTotal <= p30Close)
                {
                    v2PriorRolling30High = high;
                    v2PriorRolling30Low  = low;
                    v2PriorRolling30BarTime = barTime;
                }
            }

            UpdatePhase(barOpen);
            DetermineDayType();
            DetermineBias(close);

            if (currentVWAP > 0)
                DrawLabeledLine("VWAP_Line", currentVWAP, "VWAP", Brushes.DodgerBlue, DashStyleHelper.Solid, 1);

            RedrawActiveBoxes();
            UpdateCoachMessage();
        }

        private void RedrawActiveBoxes()
        {
            if (currentDay != null)
            {
                if (currentDay.Close330  != null) DrawBoxLines(currentDay.Close330);
                if (currentDay.GlobEx6PM != null) DrawBoxLines(currentDay.GlobEx6PM);
                if (currentDay.Europe4AM != null) DrawBoxLines(currentDay.Europe4AM);
                if (currentDay.RTH930    != null) DrawBoxLines(currentDay.RTH930);
                if (currentDay.Close130  != null) DrawBoxLines(currentDay.Close130);
            }
            if (dayHistory != null)
            {
                foreach (var d in dayHistory)
                {
                    if (d == null || d == currentDay) continue;
                    if (d.Close330  != null) DrawBoxLines(d.Close330);
                    if (d.GlobEx6PM != null) DrawBoxLines(d.GlobEx6PM);
                    if (d.Europe4AM != null) DrawBoxLines(d.Europe4AM);
                    if (d.RTH930    != null) DrawBoxLines(d.RTH930);
                    if (d.Close130  != null) DrawBoxLines(d.Close130);
                }
            }
            if (institutionalBox != null) DrawInstitutionalBox(institutionalBox);
        }

        // =================================================================
        // 1-MINUTE BAR PROCESSING
        // =================================================================

        private void Process1MinBar()
        {
            DateTime barTime = Times[idx1Min][0];
            DateTime barOpen = barTime.AddMinutes(-1);
            int h = barOpen.Hour;
            int m = barOpen.Minute;

            double high = Highs[idx1Min][0];
            double low  = Lows[idx1Min][0];
            double close = Closes[idx1Min][0];
            double open = Opens[idx1Min][0];
            long vol  = (long)Volumes[idx1Min][0];

            lastBarTime = barTime;

            // VWAP (1-min, RTH-only)
            int vwapHhmm = h * 60 + m;
            int vwapRthStart = rthOpenHour * 60 + rthOpenMinute;
            int vwapRthEnd   = closeHour   * 60 + closeMinute;
            if (vwapHhmm == vwapRthStart)
            {
                cumulativeTPV = 0;
                cumulativeVol = 0;
            }
            if (vwapHhmm >= vwapRthStart && vwapHhmm < vwapRthEnd)
            {
                double vwapTp = (high + low + close) / 3.0;
                cumulativeTPV += vwapTp * (double)vol;
                cumulativeVol += (double)vol;
                currentVWAP = cumulativeVol > 0 ? cumulativeTPV / cumulativeVol : close;
            }

            // Day boundary + ADR
            DateTime sessionDate = barOpen.Date;
            if (v2TodayDate == DateTime.MinValue) v2TodayDate = sessionDate;
            if (sessionDate != v2TodayDate)
            {
                if (!double.IsNaN(v2TodayHigh) && !double.IsNaN(v2TodayLow) && v2TodayHigh > v2TodayLow)
                {
                    v2DailyRanges.Enqueue(v2TodayHigh - v2TodayLow);
                    while (v2DailyRanges.Count > 20) v2DailyRanges.Dequeue();
                    if (v2DailyRanges.Count > 0)
                    {
                        double sum = 0; foreach (double r in v2DailyRanges) sum += r;
                        v2Adr20 = sum / v2DailyRanges.Count;
                    }
                }
                v2TodayDate = sessionDate;
                v2TodayHigh = high;
                v2TodayLow  = low;
                v2OpenRangeLocked = false;
                v2OpenRangeHigh = 0; v2OpenRangeLow = 0;
                // Daily reset of session-scoped state
                levelWatchStates.Clear();
                candidatesEmittedToday = 0;
                patternBArmedToday = 0;
                uniqueLevelsTouchedToday.Clear();
                highValueLevelsTouchedToday.Clear();
                candidateSeqByKey.Clear();   // architect §3.3 — seq counters reset per session
            }
            else
            {
                if (double.IsNaN(v2TodayHigh) || high > v2TodayHigh) v2TodayHigh = high;
                if (double.IsNaN(v2TodayLow)  || low  < v2TodayLow)  v2TodayLow  = low;
            }

            // Opening range
            if (h == rthOpenHour && m >= rthOpenMinute)
            {
                if (!v2OpenRangeLocked)
                {
                    if (v2OpenRangeHigh == 0 || high > v2OpenRangeHigh) v2OpenRangeHigh = high;
                    if (v2OpenRangeLow  == 0 || low  < v2OpenRangeLow)  v2OpenRangeLow  = low;
                }
            }
            {
                int btTotal = barTime.Hour * 60 + barTime.Minute;
                int lockTotal = rthOpenHour * 60 + rthOpenMinute + 30;
                if (!v2OpenRangeLocked && btTotal >= lockTotal)
                    v2OpenRangeLocked = true;
            }

            UpdatePhase(barOpen);

            // 9:30 1-min opening candle capture
            if (h == rthOpenHour && m == rthOpenMinute && !rth1MinComplete)
            {
                rth1MinHigh = high;
                rth1MinLow = low;
                rth1MinVolume = (int)vol;
                rth1MinComplete = true;
                if (currentDay != null)
                {
                    currentDay.RTH1Min = MakeBox("RTH 1-Min", high, low, open, close, (double)vol, barOpen, barTime, Brushes.Plum);
                    currentDay.RTH930OpenPx = open;
                }
                DrawLabeledLine("RTH1Min_H", rth1MinHigh, "1m H", Brushes.Plum, DashStyleHelper.Dash, 1);
                DrawLabeledLine("RTH1Min_L", rth1MinLow, "1m L", Brushes.Plum, DashStyleHelper.Dash, 1);
            }

            // 1-min SMAs
            double slopeThresh = 4 * TickSize;
            if (sma50Ind1 != null && sma200Ind1 != null
                && CurrentBars[idx1Min] >= 210
                && sma50Ind1.Count > 10 && sma200Ind1.Count > 10)
            {
                sma50_1min = sma50Ind1[0];
                sma200_1min = sma200Ind1[0];
                if (CurrentBars[idx1Min] >= 220
                    && sma50Ind1.Count > 15 && sma200Ind1.Count > 15)
                {
                    double slope50 = sma50_1min - sma50Ind1[10];
                    bool priceBelowBoth = close < sma50_1min && close < sma200_1min;
                    bool priceAboveBoth = close > sma50_1min && close > sma200_1min;
                    if (slope50 < -slopeThresh && priceBelowBoth)      smaDirection1 = "Down";
                    else if (slope50 > slopeThresh && priceAboveBoth)  smaDirection1 = "Up";
                    else                                                smaDirection1 = "Flat";
                }
            }

            // Anchored VWAP
            V2UpdateAnchoredVWAP(high, low, close, (double)vol, barOpen);
            if (!double.IsNaN(v2AVWAP) && v2AVWAP > 0 && DetailLevel == CockpitDetailLevel.Full)
                DrawLabeledLine("AnchVWAP_Line", v2AVWAP, "AnchVWAP", Brushes.MediumOrchid, DashStyleHelper.Solid, 1);

            // News-wick detection (RTH only)
            DetectNewsWick(barTime, barOpen, open, high, low, close, (double)vol);

            // Day-type classification — emit both 3-node and 4-node interpretations.
            AMDayType v2DayType3 = ClassifyAMDayType3Node();
            AMDayType v2DayType4 = ClassifyAMDayType4Node();
            if (v2DayType3 != lastDayTypeEmitted)
            {
                LogEvent("day_type_change",
                    "from", lastDayTypeEmitted.ToString(),
                    "to", v2DayType3.ToString(),
                    "interpretation", "v2_3node");
                lastDayTypeEmitted = v2DayType3;
            }
            if (v2DayType4 != lastDayTypeEmitted4Node)
            {
                LogEvent("day_type_change",
                    "from", lastDayTypeEmitted4Node.ToString(),
                    "to", v2DayType4.ToString(),
                    "interpretation", "v2_4node");
                lastDayTypeEmitted4Node = v2DayType4;
            }
            AMDirectionFilter directionFilter = ComputeDirectionFilter();
            if (directionFilter != lastDirectionFilterEmitted)
            {
                LogEvent("direction_filter_change",
                    "from", lastDirectionFilterEmitted.ToString(),
                    "to", directionFilter.ToString());
                lastDirectionFilterEmitted = directionFilter;
            }

            // Pre-touch watch display: show likely next AM levels before price gets there.
            UpdatePreTouchCandidateDisplay(close);

            // RTH window check — ONLY remaining "skip" L1 makes (per architect spec §1.3).
            // If outside RTH, emit abstain event with reason; do NOT run candidate detection.
            int nowTotal = barTime.Hour * 60 + barTime.Minute;
            int lastEntryTotal = closeHour * 60 + closeMinute - 30;
            bool inRthWindow = ((h == rthOpenHour && m >= rthOpenMinute) || h > rthOpenHour)
                && nowTotal < lastEntryTotal;

            if (!inRthWindow)
            {
                EmitAbstain(barTime, "outside_rth_window");
            }
            else
            {
                // CHECK ENTRY runs always inside RTH (no day-type, lockout, cooldown, signalsToday gates).
                CheckEntry(close, high, low, open, barTime, (double)vol);
            }

            // Periodic state.json persistence
            if (EnableStatePersistence)
            {
                if (lastStatePersistedAt == DateTime.MinValue
                    || (barTime - lastStatePersistedAt).TotalMinutes >= 5)
                {
                    PersistStateJson("periodic");
                }
            }

            UpdateCoachMessage();
        }

        // =================================================================
        // CHECK ENTRY — Pattern A and Pattern B candidate emission.
        // =================================================================

        // Per architect spec §1.1: every level inside [low, high] emits a candidate
        // event for EVERY direction supported (LONG and SHORT separately).  No filters,
        // no latching, no retrace-side gate, no "best-only" pick.  Pattern A and
        // Pattern B both surface their candidates with the appropriate pattern_type.
        private void CheckEntry(double close, double high, double low, double barOpen,
                                 DateTime barTime, double barVolume)
        {
            diagBarsChecked++;
            var levels = BuildAllLevels();
            if (levels.Count == 0) return;

            foreach (var kv in levels)
            {
                string name = kv.Key;
                double px = kv.Value.Price;
                bool isPermissionLevel = kv.Value.IsPermission;

                // Skip if level not in bar range (no interaction)
                if (px < low || px > high) continue;

                uniqueLevelsTouchedToday.Add(name);
                // High-value subset — same whitelist as DrawCandidateMarker.
                if (name.StartsWith("GlobEx") || name.StartsWith("Europe")
                    || name.StartsWith("OR30") || name.StartsWith("RTH1Min")
                    || name.StartsWith("PrInst")
                    || name.StartsWith("Pr130") || name.StartsWith("Pday1")
                    || name.StartsWith("News"))
                {
                    highValueLevelsTouchedToday.Add(name);
                }

                // Pattern A — for both directions, regardless of retrace_side or latch.
                if (EnablePatternA)
                {
                    // LONG: level held as support (close >= L)
                    if (close >= px)
                        EmitCandidate(name, px, isPermissionLevel, "LONG", "A", null,
                                      barTime, barOpen, high, low, close, barVolume,
                                      anchorH: high, anchorL: low,
                                      anchorBT: Math.Max(barOpen, close), anchorBB: Math.Min(barOpen, close),
                                      anchorVol: barVolume, anchorTime: barTime);

                    // SHORT: level held as resistance (close <= L)
                    if (close <= px)
                        EmitCandidate(name, px, isPermissionLevel, "SHORT", "A", null,
                                      barTime, barOpen, high, low, close, barVolume,
                                      anchorH: high, anchorL: low,
                                      anchorBT: Math.Max(barOpen, close), anchorBB: Math.Min(barOpen, close),
                                      anchorVol: barVolume, anchorTime: barTime);
                }

                // Pattern B (LevelWatchState lifecycle)
                if (EnablePatternB)
                {
                    UpdateLevelWatchStates(name, px, isPermissionLevel,
                                           barTime, barOpen, high, low, close, barVolume);
                }
            }
        }

        // ---- Pattern B state machine ----

        private struct LevelInfo
        {
            public double Price;
            public bool IsPermission;
            public LevelInfo(double px, bool perm) { Price = px; IsPermission = perm; }
        }

        private class PreTouchWatchLevel
        {
            public string Name;
            public double Price;
            public double DistancePts;
            public bool IsPermission;
        }

        // V2_6 Pattern B per architect spec §6.3:
        //   Untouched → Breached:  bar.Low < L && bar.Close >= L (long); flip for short.
        //   Breached  → Armed:     next bar.Low > AnchorCandle.Low (long).  Emit candidate.
        //   Breached  → Invalidated: next bar.Low <= AnchorCandle.Low.
        //   Armed     → Consumed:  subsequent bar.High > AnchorCandle.High (entry trigger).
        //   Reset to Untouched only at session rollover.
        private void UpdateLevelWatchStates(string name, double levelPrice, bool isPermissionLevel,
                                              DateTime barTime, double barOpen,
                                              double high, double low, double close, double barVolume)
        {
            // We maintain TWO LevelWatchStates per level (one for LONG, one for SHORT).
            UpdatePatternBSide(name, levelPrice, isPermissionLevel, "LONG",
                               barTime, barOpen, high, low, close, barVolume);
            UpdatePatternBSide(name, levelPrice, isPermissionLevel, "SHORT",
                               barTime, barOpen, high, low, close, barVolume);
        }

        private void UpdatePatternBSide(string name, double levelPrice, bool isPermissionLevel,
                                          string direction,
                                          DateTime barTime, double barOpen,
                                          double high, double low, double close, double barVolume)
        {
            string key = name + "|" + direction;
            LevelWatchState lws;
            if (!levelWatchStates.TryGetValue(key, out lws))
            {
                lws = new LevelWatchState
                {
                    LevelName  = name,
                    LevelPrice = levelPrice,
                    Direction  = direction,
                    Status     = LevelWatchStatus.Untouched
                };
                levelWatchStates[key] = lws;
            }
            // Refresh price if it's a moving level (e.g., VWAP, Pr30 with stamp)
            lws.LevelPrice = levelPrice;

            bool isLong = direction == "LONG";

            switch (lws.Status)
            {
                case LevelWatchStatus.Untouched:
                {
                    bool breach = isLong
                        ? (low < levelPrice && close >= levelPrice)
                        : (high > levelPrice && close <= levelPrice);
                    if (breach)
                    {
                        lws.Status = LevelWatchStatus.Breached;
                        lws.AnchorCandle = new CandleBox
                        {
                            Name = "BreachAt_" + name,
                            High = high, Low = low,
                            Open = barOpen, Close = close,
                            Volume = barVolume,
                            StartTime = barTime.AddMinutes(-1),
                            EndTime = barTime
                        };
                        lws.BreachTime = barTime;
                        lws.BreachBarHigh = high;
                        lws.BreachBarLow = low;
                        lws.BreachBarVolume = barVolume;
                        EmitPatternBStateChange(name, direction, "Untouched", "Breached", lws);

                        // Per architect spec §6.3: the breach itself can immediately confirm via
                        // a 1-bar pattern.  Emit Armed candidate on next bar's evaluation.
                    }
                    break;
                }

                case LevelWatchStatus.Breached:
                {
                    if (lws.AnchorCandle == null) { lws.Status = LevelWatchStatus.Untouched; break; }
                    // Confirmation: subsequent bar must hold higher low (long) / lower high (short)
                    bool armed     = isLong ? low > lws.AnchorCandle.Low  : high < lws.AnchorCandle.High;
                    bool invalid   = isLong ? low <= lws.AnchorCandle.Low : high >= lws.AnchorCandle.High;
                    if (armed)
                    {
                        lws.Status = LevelWatchStatus.Armed;
                        lws.ArmedAtTime = barTime;
                        EmitPatternBStateChange(name, direction, "Breached", "Armed", lws);
                        patternBArmedToday++;

                        // Emit the Armed candidate — this is the firing event for Pattern B.
                        EmitCandidate(name, levelPrice, isPermissionLevel, direction, "B", "Armed",
                                      barTime, barOpen, high, low, close, barVolume,
                                      anchorH: lws.AnchorCandle.High,
                                      anchorL: lws.AnchorCandle.Low,
                                      anchorBT: lws.AnchorCandle.BodyTop,
                                      anchorBB: lws.AnchorCandle.BodyBottom,
                                      anchorVol: lws.AnchorCandle.Volume,
                                      anchorTime: lws.AnchorCandle.StartTime);
                    }
                    else if (invalid)
                    {
                        lws.Status = LevelWatchStatus.Invalidated;
                        EmitPatternBStateChange(name, direction, "Breached", "Invalidated", lws);
                    }
                    break;
                }

                case LevelWatchStatus.Armed:
                {
                    if (lws.AnchorCandle == null) break;
                    // Entry trigger crossed: bar high crosses anchor high (long) / bar low crosses anchor low (short)
                    bool consumed = isLong ? high >= lws.AnchorCandle.High : low <= lws.AnchorCandle.Low;
                    if (consumed)
                    {
                        lws.Status = LevelWatchStatus.Consumed;
                        EmitPatternBStateChange(name, direction, "Armed", "Consumed", lws);

                        // Emit a Consumed candidate (informational — L2 may already have submitted).
                        EmitCandidate(name, levelPrice, isPermissionLevel, direction, "B", "Consumed",
                                      barTime, barOpen, high, low, close, barVolume,
                                      anchorH: lws.AnchorCandle.High,
                                      anchorL: lws.AnchorCandle.Low,
                                      anchorBT: lws.AnchorCandle.BodyTop,
                                      anchorBB: lws.AnchorCandle.BodyBottom,
                                      anchorVol: lws.AnchorCandle.Volume,
                                      anchorTime: lws.AnchorCandle.StartTime);
                    }
                    break;
                }

                case LevelWatchStatus.Consumed:
                case LevelWatchStatus.Invalidated:
                    // Latched for the rest of the session; reset only at daily rollover.
                    break;
            }
        }

        // ---- Build all candidate-eligible levels ----

        // Per architect §6: a single dictionary of every named level, with a
        // boolean flag is_permission_level (true for VWAP/AnchVWAP).  We do NOT
        // gate by trade direction — both LONG and SHORT candidates flow through.
        // L2 ranks; L3 blocks.  L1 surfaces.
        private Dictionary<string, LevelInfo> BuildAllLevels()
        {
            var d = new Dictionary<string, LevelInfo>(64);

            void Add(string nm, double px, bool perm = false)
            {
                if (px > 0 && !double.IsNaN(px) && !double.IsInfinity(px))
                    d[nm] = new LevelInfo(px, perm);
            }

            if (currentDay != null)
            {
                if (currentDay.GlobEx6PM != null)
                {
                    Add("GlobExH",   currentDay.GlobEx6PM.High);
                    Add("GlobExL",   currentDay.GlobEx6PM.Low);
                    Add("GlobExMid", (currentDay.GlobEx6PM.High + currentDay.GlobEx6PM.Low) / 2.0);
                }
                if (currentDay.Midnight != null)
                {
                    Add("MidH",   currentDay.Midnight.High);
                    Add("MidL",   currentDay.Midnight.Low);
                    Add("MidMid", (currentDay.Midnight.High + currentDay.Midnight.Low) / 2.0);
                }
                if (currentDay.Europe4AM != null)
                {
                    Add("EuropeH",   currentDay.Europe4AM.High);
                    Add("EuropeL",   currentDay.Europe4AM.Low);
                    Add("EuropeMid", (currentDay.Europe4AM.High + currentDay.Europe4AM.Low) / 2.0);
                }
                if (currentDay.RTH930 != null)
                {
                    Add("OR30H",     currentDay.RTH930.High);
                    Add("OR30L",     currentDay.RTH930.Low);
                    Add("OR30Mid",   (currentDay.RTH930.High + currentDay.RTH930.Low) / 2.0);
                }
                if (currentDay.RTH1Min != null)
                {
                    Add("RTH1MinH",   currentDay.RTH1Min.High);
                    Add("RTH1MinL",   currentDay.RTH1Min.Low);
                    Add("RTH1MinMid", (currentDay.RTH1Min.High + currentDay.RTH1Min.Low) / 2.0);
                }
                if (currentDay.Close330 != null)
                {
                    Add("PrInstH",   currentDay.Close330.High);
                    Add("PrInstL",   currentDay.Close330.Low);
                    Add("PrInstMid", (currentDay.Close330.High + currentDay.Close330.Low) / 2.0);
                }
                if (currentDay.Close130 != null)
                {
                    Add("Pr130H",    currentDay.Close130.High);
                    Add("Pr130L",    currentDay.Close130.Low);
                    Add("Pr130Mid",  (currentDay.Close130.High + currentDay.Close130.Low) / 2.0);
                }
            }

            // Multi-day master-candle revisits (t-1, t-2, t-3) per AM mar-6.
            if (dayHistory != null)
            {
                for (int i = 0; i < Math.Min(MaxLookbackDaysForLevels, dayHistory.Count); i++)
                {
                    int idx = dayHistory.Count - 1 - i;
                    if (idx < 0) break;
                    var d_back = dayHistory[idx];
                    int offset = i + 1;
                    if (d_back.Close330 != null)
                    {
                        Add($"Pday{offset}Close330H", d_back.Close330.High);
                        Add($"Pday{offset}Close330L", d_back.Close330.Low);
                    }
                    if (d_back.Europe4AM != null)
                    {
                        Add($"Pday{offset}Europe4AMH", d_back.Europe4AM.High);
                        Add($"Pday{offset}Europe4AML", d_back.Europe4AM.Low);
                    }
                    if (d_back.GlobEx6PM != null)
                    {
                        Add($"Pday{offset}GlobEx6PMH", d_back.GlobEx6PM.High);
                        Add($"Pday{offset}GlobEx6PML", d_back.GlobEx6PM.Low);
                    }
                    if (d_back.RTH930 != null)
                    {
                        Add($"Pday{offset}RTH930H", d_back.RTH930.High);
                        Add($"Pday{offset}RTH930L", d_back.RTH930.Low);
                    }
                }
            }

            // Opening range (locked levels)
            if (v2OpenRangeLocked && v2OpenRangeHigh > 0)
            {
                Add("ORH", v2OpenRangeHigh);
                Add("ORL", v2OpenRangeLow);
            }

            // Rolling Pr30 — stamped key per AM's "fresh roll = fresh candidate".
            if (v2PriorRolling30High > 0)
            {
                string stamp = v2PriorRolling30BarTime != DateTime.MinValue
                    ? v2PriorRolling30BarTime.ToString("HHmm") : "00";
                Add("Pr30H@" + stamp, v2PriorRolling30High);
                Add("Pr30L@" + stamp, v2PriorRolling30Low);
            }

            // SMAs
            if (!double.IsNaN(sma50_30min)  && sma50_30min  > 0) Add("SMA50_30",  sma50_30min);
            if (!double.IsNaN(sma200_30min) && sma200_30min > 0) Add("SMA200_30", sma200_30min);
            if (!double.IsNaN(sma50_1min)   && sma50_1min   > 0) Add("SMA50_1",   sma50_1min);
            if (!double.IsNaN(sma200_1min)  && sma200_1min  > 0) Add("SMA200_1",  sma200_1min);

            // VWAP / AnchVWAP — surface as permission levels per architect §6.7.
            if (EmitVwapAsPermissionLevel)
            {
                if (!double.IsNaN(currentVWAP) && currentVWAP > 0)
                    Add("VWAP", currentVWAP, true);
                if (!double.IsNaN(v2AVWAP) && v2AVWAP > 0)
                    Add("AnchVWAP", v2AVWAP, true);
            }

            // Daily pivots (Woody's-style)
            if (pivotsCalculated)
            {
                Add("PP", pivotPP);
                Add("R1", pivotR1); Add("R2", pivotR2); Add("R3", pivotR3); Add("R4", pivotR4);
                Add("S1", pivotS1); Add("S2", pivotS2); Add("S3", pivotS3); Add("S4", pivotS4);
            }

            // News wicks (volume-outlier candles)
            foreach (var nw in newsWicks)
            {
                if (!nw.Active) continue;
                string nm = "NewsWick" + (nw.Kind == "lower" ? "L" : "H") + "_" + nw.CandleTime.ToString("HHmm");
                Add(nm, nw.LevelPrice);
            }

            return d;
        }

        // =================================================================
        // CANDIDATE EMISSION
        // =================================================================

        // The central new event of V2_6.  Per architect §3.3.  Every level
        // interaction in [low, high] for both directions emits a candidate.
        private void EmitCandidate(string levelName, double levelPrice, bool isPermissionLevel,
                                    string direction, string patternType, string lwsState,
                                    DateTime barTime, double barOpen,
                                    double barHigh, double barLow, double barClose, double barVolume,
                                    double anchorH, double anchorL,
                                    double anchorBT, double anchorBB,
                                    double anchorVol, DateTime anchorTime)
        {
            candidatesEmittedToday++;
            string sessionDate = barTime.Date.ToString("yyyy-MM-dd");
            string strippedLevel = StripStamp(levelName);

            // Deterministic candidate_id per integration spec Gap 3 /
            // architect §3.3:
            //     {instrument_short}_{yyyymmdd}_{HHmm}_{level_kind}_{direction}_{seq}
            // where seq is a per-(bar, level, direction) counter (typically 001
            // unless re-emitted). Pattern type is encoded into level_kind so the
            // tuple disambiguates pattern A vs pattern B re-emissions on the
            // same bar. Direction stays UPPERCASE (LONG/SHORT) per integration
            // brief example "ES_20260427_0930_GlobExL_LONG_001".
            string instrShort = Instrument != null && Instrument.MasterInstrument != null
                                ? Instrument.MasterInstrument.Name : "UNK";
            string yyyymmdd  = barTime.ToString("yyyyMMdd");
            string hhmm      = barTime.ToString("HHmm");
            string levelKind = strippedLevel + (string.IsNullOrEmpty(patternType) ? "" : "_" + patternType);
            string seqKey    = $"{hhmm}|{levelKind}|{direction}";
            int seq;
            if (!candidateSeqByKey.TryGetValue(seqKey, out seq)) seq = 0;
            seq++;
            candidateSeqByKey[seqKey] = seq;
            string candidateId = $"{instrShort}_{yyyymmdd}_{hhmm}_{levelKind}_{direction}_{seq:000}";

            // Build feature vector (architect §3.3)
            var features = BuildFeatureVector(barTime, barOpen, barHigh, barLow, barClose, barVolume,
                                               levelPrice, direction, isPermissionLevel);

            var args = new CandidateEventArgs
            {
                CandidateId        = candidateId,
                BarTime            = barTime,
                SessionDate        = sessionDate,
                LevelName          = strippedLevel,
                LevelPrice         = levelPrice,
                IsPermissionLevel  = isPermissionLevel,
                Direction          = direction,
                PatternType        = patternType,
                LwsState           = lwsState,
                BarOpen            = barOpen,
                BarHigh            = barHigh,
                BarLow             = barLow,
                BarClose           = barClose,
                BarVolume          = barVolume,
                AnchorHigh         = anchorH,
                AnchorLow          = anchorL,
                AnchorBodyTop      = anchorBT,
                AnchorBodyBottom   = anchorBB,
                AnchorVolume       = anchorVol,
                AnchorTime         = anchorTime,
                Features           = features
            };

            // JSONL emission — flatten to key/value pairs for the cockpit logger.
            // Top-level fields (then features inline).
            var flat = new List<object>();
            flat.Add("candidate_id"); flat.Add(candidateId);
            flat.Add("session_date"); flat.Add(sessionDate);
            flat.Add("level_name"); flat.Add(strippedLevel);
            flat.Add("level_price"); flat.Add(levelPrice);
            flat.Add("is_permission_level"); flat.Add(isPermissionLevel);
            flat.Add("direction"); flat.Add(direction);
            flat.Add("pattern_type"); flat.Add(patternType);
            flat.Add("lws_state"); flat.Add(lwsState ?? "");
            flat.Add("bar_time"); flat.Add(barTime);
            flat.Add("bar_open"); flat.Add(barOpen);
            flat.Add("bar_high"); flat.Add(barHigh);
            flat.Add("bar_low"); flat.Add(barLow);
            flat.Add("bar_close"); flat.Add(barClose);
            flat.Add("bar_volume"); flat.Add(barVolume);
            flat.Add("anchor_high"); flat.Add(anchorH);
            flat.Add("anchor_low"); flat.Add(anchorL);
            flat.Add("anchor_body_top"); flat.Add(anchorBT);
            flat.Add("anchor_body_bottom"); flat.Add(anchorBB);
            flat.Add("anchor_volume"); flat.Add(anchorVol);
            // Inline feature vector
            foreach (var kv in features)
            {
                flat.Add("f_" + kv.Key);
                flat.Add(kv.Value);
            }
            LogEvent("candidate", flat.ToArray());

            // Fire in-process event for L2 strategy
            try
            {
                var sub = OnCandidate;
                if (sub != null) sub(args);
            }
            catch (Exception ex)
            {
                EmitError(ex);
            }

            // Visual marker on chart (tiny dot/circle/triangle/x at level + bar)
            if (ShowCandidateMarkers)
                DrawCandidateMarker(args);
        }

        // ---- Feature vector builder (architect §3.3) ----

        private Dictionary<string, object> BuildFeatureVector(
            DateTime barTime, double barOpen, double barHigh, double barLow, double barClose, double barVolume,
            double levelPrice, string direction, bool isPermissionLevel)
        {
            var f = new Dictionary<string, object>(96);

            // Day type — emit BOTH 3-node and 4-node interpretations.
            AMDayType dt3 = ClassifyAMDayType3Node();
            AMDayType dt4 = ClassifyAMDayType4Node();
            f["day_type_v2_3node"] = dt3.ToString();
            f["day_type_v2_4node"] = dt4.ToString();

            // Body-stack overlap flags
            CandleBox a = currentDay?.Close330;
            CandleBox b = currentDay?.GlobEx6PM;
            CandleBox c = currentDay?.Europe4AM;
            CandleBox d = currentDay?.RTH930;
            f["body_overlap_AB"] = a != null && b != null && !b.BodyStrictlyAbove(a) && !b.BodyStrictlyBelow(a);
            f["body_overlap_BC"] = b != null && c != null && !c.BodyStrictlyAbove(b) && !c.BodyStrictlyBelow(b);
            f["body_overlap_CD"] = c != null && d != null && !d.BodyStrictlyAbove(c) && !d.BodyStrictlyBelow(c);
            f["large_wick_flag_A"] = a != null && a.HasLargeWick;
            f["large_wick_flag_B"] = b != null && b.HasLargeWick;
            f["large_wick_flag_C"] = c != null && c.HasLargeWick;
            f["large_wick_flag_D"] = d != null && d.HasLargeWick;

            // SMA200 slope
            if (currentDay != null && !double.IsNaN(currentDay.Sma200SlopeDelta))
            {
                f["sma200_slope_delta_pts"] = currentDay.Sma200SlopeDelta;
                f["sma200_slope_available"] = true;
                f["sma200_slope_sign"] = currentDay.Sma200SlopeUp ? "Up"
                                          : currentDay.Sma200SlopeDown ? "Down" : "Flat";
            }
            else
            {
                f["sma200_slope_delta_pts"] = null;
                f["sma200_slope_available"] = false;
                f["sma200_slope_sign"] = "Unknown";
            }
            // SMA50 slope (from sma direction)
            if (!double.IsNaN(sma50_30min) && sma50_30min > 0)
            {
                f["sma50_30_value"] = sma50_30min;
                f["sma50_30_slope_available"] = true;
                f["sma50_30_slope_sign"] = smaDirection30 ?? "Unknown";
            }
            else
            {
                f["sma50_30_value"] = null;
                f["sma50_30_slope_available"] = false;
                f["sma50_30_slope_sign"] = "Unknown";
            }

            // MOC
            if (currentDay != null && currentDay.MocState != MOCValidation.Pending && !double.IsNaN(currentDay.MocRatio))
            {
                f["moc_ratio"] = currentDay.MocRatio;
                f["moc_state"] = currentDay.MocState.ToString();
                f["moc_observed_today"] = true;
            }
            else
            {
                f["moc_ratio"] = null;
                f["moc_state"] = "Pending";
                f["moc_observed_today"] = false;
            }

            // VWAP/AnchVWAP context
            f["vwap_price"] = double.IsNaN(currentVWAP) ? (object)null : currentVWAP;
            f["vwap_slope"] = vwapSlope ?? "Unknown";
            f["anchored_vwap_price"] = double.IsNaN(v2AVWAP) ? (object)null : v2AVWAP;
            f["dist_to_vwap_pts"] = !double.IsNaN(currentVWAP) && currentVWAP > 0 ? (object)(barClose - currentVWAP) : null;
            f["dist_to_anchvwap_pts"] = !double.IsNaN(v2AVWAP) && v2AVWAP > 0 ? (object)(barClose - v2AVWAP) : null;

            // Distances to other named levels (in points; null if level missing)
            f["dist_to_close330_high"] = a != null ? (object)(barClose - a.High) : null;
            f["dist_to_close330_low"]  = a != null ? (object)(barClose - a.Low) : null;
            f["dist_to_globex_high"]   = b != null ? (object)(barClose - b.High) : null;
            f["dist_to_globex_low"]    = b != null ? (object)(barClose - b.Low) : null;
            f["dist_to_midnight_high"] = currentDay?.Midnight != null ? (object)(barClose - currentDay.Midnight.High) : null;
            f["dist_to_midnight_low"]  = currentDay?.Midnight != null ? (object)(barClose - currentDay.Midnight.Low) : null;
            f["dist_to_europe_high"]   = c != null ? (object)(barClose - c.High) : null;
            f["dist_to_europe_low"]    = c != null ? (object)(barClose - c.Low) : null;
            f["dist_to_rth930_high"]   = d != null ? (object)(barClose - d.High) : null;
            f["dist_to_rth930_low"]    = d != null ? (object)(barClose - d.Low) : null;
            f["dist_to_close130_high"] = currentDay?.Close130 != null ? (object)(barClose - currentDay.Close130.High) : null;
            f["dist_to_close130_low"]  = currentDay?.Close130 != null ? (object)(barClose - currentDay.Close130.Low) : null;
            f["dist_to_or_high"] = v2OpenRangeLocked && v2OpenRangeHigh > 0 ? (object)(barClose - v2OpenRangeHigh) : null;
            f["dist_to_or_low"]  = v2OpenRangeLocked && v2OpenRangeLow  > 0 ? (object)(barClose - v2OpenRangeLow)  : null;
            f["dist_to_pp"] = pivotsCalculated ? (object)(barClose - pivotPP) : null;
            f["dist_to_r1"] = pivotsCalculated ? (object)(barClose - pivotR1) : null;
            f["dist_to_r2"] = pivotsCalculated ? (object)(barClose - pivotR2) : null;
            f["dist_to_r3"] = pivotsCalculated ? (object)(barClose - pivotR3) : null;
            f["dist_to_r4"] = pivotsCalculated ? (object)(barClose - pivotR4) : null;
            f["dist_to_s1"] = pivotsCalculated ? (object)(barClose - pivotS1) : null;
            f["dist_to_s2"] = pivotsCalculated ? (object)(barClose - pivotS2) : null;
            f["dist_to_s3"] = pivotsCalculated ? (object)(barClose - pivotS3) : null;
            f["dist_to_s4"] = pivotsCalculated ? (object)(barClose - pivotS4) : null;
            f["is_above_r3"] = pivotsCalculated && barClose > pivotR3;

            // Multi-day prior master candles
            for (int i = 1; i <= MaxLookbackDaysForLevels && dayHistory != null; i++)
            {
                int idx = dayHistory.Count - i;
                if (idx < 0) break;
                var dh = dayHistory[idx];
                f[$"dist_to_pday{i}_close330_high"] = dh.Close330 != null ? (object)(barClose - dh.Close330.High) : null;
                f[$"dist_to_pday{i}_close330_low"]  = dh.Close330 != null ? (object)(barClose - dh.Close330.Low) : null;
            }

            // Bar shape
            double range = barHigh - barLow;
            f["body_pct"] = range > 0 ? (object)(Math.Abs(barClose - barOpen) / range) : null;
            f["candle_range_pct"] = range > 0 ? (object)1.0 : null;
            f["upper_wick_pct"] = range > 0 ? (object)((barHigh - Math.Max(barOpen, barClose)) / range) : null;
            f["lower_wick_pct"] = range > 0 ? (object)((Math.Min(barOpen, barClose) - barLow) / range) : null;
            f["candle_direction"] = barClose > barOpen ? "Up" : (barClose < barOpen ? "Down" : "Doji");

            // Latch / retrace state (informational only — never gates emission)
            // retrace_side: long needs px < barOpen; short needs px > barOpen.
            bool retraceLong  = levelPrice < barOpen;
            bool retraceShort = levelPrice > barOpen;
            bool atOpen = Math.Abs(levelPrice - barOpen) < TickSize / 2.0;
            f["retrace_side"] = atOpen ? (object)null : (object)(direction == "LONG" ? retraceLong : retraceShort);
            f["retrace_side_at_open"] = atOpen;
            // Per-level "already touched" — informational only.  L1 never gates on this;
            // L2's scorer may use it as a soft penalty.
            f["already_touched_today"] = false;

            // Time-of-day
            int totalMin = barTime.Hour * 60 + barTime.Minute;
            int rthOpenTotal = rthOpenHour * 60 + rthOpenMinute;
            int rthCloseTotal = closeHour * 60 + closeMinute;
            f["minutes_since_rth_open"] = Math.Max(0, totalMin - rthOpenTotal);
            f["minutes_until_rth_close"] = Math.Max(0, rthCloseTotal - totalMin);
            f["hour_et"] = barTime.Hour;
            f["day_of_week"] = barTime.DayOfWeek.ToString();
            f["month"] = barTime.Month;
            f["time_of_day_hhmm"] = barTime.ToString("HHmm");

            // Volume context
            f["bar_volume"] = barVolume;

            // ADR / volatility
            f["adr_20d_pts"] = double.IsNaN(v2Adr20) ? (object)null : v2Adr20;
            double euWidth = c != null ? c.High - c.Low : 0;
            f["europe_width_pts"] = c != null ? (object)euWidth : null;
            f["candle_width_pct_of_adr"] = !double.IsNaN(v2Adr20) && v2Adr20 > 0 ? (object)(range / v2Adr20) : null;

            // Phase / bias
            f["phase"] = currentPhase.ToString();
            f["bias"] = currentBias.ToString();
            AMDirectionFilter directionFilter = ComputeDirectionFilter();
            f["direction_filter"] = directionFilter.ToString();
            f["direction_filter_allows_candidate"] = DirectionFilterAllowsCandidate(directionFilter, direction);

            // Stop distance proposal: per-trigger candle width clipped to [0.30, 0.80] * ADR.
            // Per architect §13.2 — V2_4's anchor dead-parameter bug fixed by computing here.
            double anchorWidth = barHigh - barLow;
            CandleBox effectiveAnchor = null;
            if (currentDay != null)
            {
                if (currentDay.Close330 != null
                    && anchorWidth > 0
                    && barLow >= currentDay.Close330.Low && barHigh <= currentDay.Close330.High)
                    effectiveAnchor = currentDay.Close330;
                else if (currentDay.RTH930 != null
                    && anchorWidth > 0
                    && barLow >= currentDay.RTH930.Low && barHigh <= currentDay.RTH930.High)
                    effectiveAnchor = currentDay.RTH930;
            }
            double stopBase = effectiveAnchor != null ? (effectiveAnchor.High - effectiveAnchor.Low) : anchorWidth;
            object stopProposal = null;
            if (stopBase > 0)
            {
                if (!double.IsNaN(v2Adr20) && v2Adr20 > 0)
                {
                    double lo = 0.30 * v2Adr20;
                    double hi = 0.80 * v2Adr20;
                    if (stopBase < lo) stopBase = lo;
                    if (stopBase > hi) stopBase = hi;
                }
                stopProposal = stopBase;
            }
            f["stop_dist_proposal_pts"] = stopProposal;

            // Target proposals
            // FADE-style (PrInst H/L)
            if (currentDay != null && currentDay.Close330 != null)
            {
                f["target_fade_prinst_h"] = currentDay.Close330.High;
                f["target_fade_prinst_l"] = currentDay.Close330.Low;
            }
            else
            {
                f["target_fade_prinst_h"] = null;
                f["target_fade_prinst_l"] = null;
            }
            // Fib-style (100/150/200/250% extensions of the trigger candle width)
            if (anchorWidth > 0)
            {
                f["target_fib_100_pts"] = anchorWidth * 1.0;
                f["target_fib_150_pts"] = anchorWidth * 1.5;
                f["target_fib_200_pts"] = anchorWidth * 2.0;
                f["target_fib_250_pts"] = anchorWidth * 2.5;
            }
            else
            {
                f["target_fib_100_pts"] = null;
                f["target_fib_150_pts"] = null;
                f["target_fib_200_pts"] = null;
                f["target_fib_250_pts"] = null;
            }

            // Institutional box
            f["inst_box_name"] = institutionalName ?? "";
            f["inst_box_high"] = institutionalBox != null ? (object)institutionalBox.High : null;
            f["inst_box_low"] = institutionalBox != null ? (object)institutionalBox.Low : null;

            // News-wick
            bool nwActive = false;
            double? nwDist = null;
            foreach (var nw in newsWicks)
            {
                if (!nw.Active) continue;
                nwActive = true;
                double dist = barClose - nw.LevelPrice;
                if (nwDist == null || Math.Abs(dist) < Math.Abs(nwDist.Value)) nwDist = dist;
            }
            f["news_wick_active_today"] = nwActive;
            f["news_wick_distance_pts"] = nwDist.HasValue ? (object)nwDist.Value : null;

            // Permission-level flag
            f["is_permission_level"] = isPermissionLevel;

            // Diagnostic counters
            f["candidates_emitted_today"] = candidatesEmittedToday;
            f["pattern_b_armed_today"] = patternBArmedToday;

            return f;
        }

        // =================================================================
        // PATTERN B STATE CHANGE EVENT
        // =================================================================

        private void EmitPatternBStateChange(string levelName, string direction, string fromState, string toState, LevelWatchState lws)
        {
            LogEvent("pattern_b_state_change",
                "level_name", StripStamp(levelName),
                "direction", direction,
                "from_state", fromState,
                "to_state", toState,
                "breach_candle_high", lws.AnchorCandle != null ? lws.AnchorCandle.High : 0.0,
                "breach_candle_low",  lws.AnchorCandle != null ? lws.AnchorCandle.Low  : 0.0,
                "breach_bar_time", lws.BreachTime);
        }

        // =================================================================
        // BOX CAPTURE EVENT
        // =================================================================

        private void EmitBoxCapture(CandleBox box, string subtype, int dayOffset, bool institutionalNowFlag)
        {
            if (box == null) return;
            // JSONL emission
            object mocRatio = (currentDay != null && !double.IsNaN(currentDay.MocRatio)) ? (object)currentDay.MocRatio : null;
            double mocRatioVal = (currentDay != null && !double.IsNaN(currentDay.MocRatio)) ? currentDay.MocRatio : double.NaN;
            string mocState = (currentDay != null) ? currentDay.MocState.ToString() : "Pending";

            LogEvent("box_capture",
                "name", box.Name,
                "subtype", subtype,
                "instance_day_offset", dayOffset,
                "start_time", box.StartTime,
                "high", box.High,
                "low", box.Low,
                "open", box.Open,
                "close", box.Close,
                "body_top", box.BodyTop,
                "body_bottom", box.BodyBottom,
                "wick_top_pts", box.UpperWick,
                "wick_bottom_pts", box.LowerWick,
                "volume", box.Volume,
                "is_institutional_now", institutionalNowFlag,
                "moc_ratio", mocRatio,
                "moc_state", mocState);

            // In-process event
            try
            {
                var sub = OnBoxCapture;
                if (sub != null)
                    sub(new BoxCaptureEventArgs
                    {
                        Name = box.Name,
                        Subtype = subtype,
                        InstanceDayOffset = dayOffset,
                        StartTime = box.StartTime,
                        High = box.High, Low = box.Low,
                        Open = box.Open, Close = box.Close,
                        Volume = box.Volume,
                        IsInstitutionalNow = institutionalNowFlag,
                        MocRatio = mocRatioVal,
                        MocState = mocState
                    });
            }
            catch (Exception ex) { EmitError(ex); }
        }

        // =================================================================
        // ABSTAIN / ERROR
        // =================================================================

        private void EmitAbstain(DateTime barTime, string reason)
        {
            LogEvent("abstain",
                "layer", "L1",
                "reason", reason,
                "bar_time", barTime);
            try
            {
                var sub = OnAbstain;
                if (sub != null) sub(new AbstainEventArgs { BarTime = barTime, Reason = reason, Layer = "L1" });
            }
            catch { /* abstain emit best-effort; never throw */ }
        }

        private void EmitError(Exception ex)
        {
            string barCtx = "n/a";
            try { if (Times != null && Times.Length > 0 && CurrentBars[0] >= 0) barCtx = Times[0][0].ToString("o"); } catch { }
            string barInProgress = "?";
            try { barInProgress = BarsInProgress.ToString(); } catch { }

            LogEvent("error",
                "msg", ex != null ? ex.Message : "(null)",
                "type", ex != null ? ex.GetType().Name : "(null)",
                "stack_trace", ex != null ? ex.StackTrace ?? "" : "",
                "bar_time", barCtx,
                "bar_in_progress", barInProgress,
                "current_state", State.ToString());

            // Also Print so the developer sees it in NT Output (both Historical and Realtime).
            Print($"AMTradeCockpitV2_6 error (BIP={barInProgress}, bar={barCtx}): {ex?.Message}");
        }

        // =================================================================
        // NEWS-WICK DETECTION
        // =================================================================

        // Per architect §6.4 / GAP14.  In RTH only, if a candle's volume exceeds
        // NewsVolumeMultiplierThreshold * max(yesterday 9:30 vol, yesterday 3:30 vol),
        // register its wick as a level.
        private void DetectNewsWick(DateTime barTime, DateTime barOpen,
                                      double open, double high, double low, double close, double vol)
        {
            int totalMin = barTime.Hour * 60 + barTime.Minute;
            int rthOpenTotal = rthOpenHour * 60 + rthOpenMinute;
            int rthCloseTotal = closeHour * 60 + closeMinute;
            if (totalMin < rthOpenTotal || totalMin > rthCloseTotal) return;

            // Threshold: max of yesterday's 9:30 + 3:30 30-min vols (priorDay or last in dayHistory)
            double thresh = 0;
            if (priorDay != null)
            {
                if (!double.IsNaN(priorDay.V930Volume)) thresh = Math.Max(thresh, priorDay.V930Volume);
                if (!double.IsNaN(priorDay.V330Volume)) thresh = Math.Max(thresh, priorDay.V330Volume);
            }
            if (thresh <= 0) return;
            if (vol < NewsVolumeMultiplierThreshold * thresh) return;

            // Slope-gated registration
            string slopeSign = currentDay != null && currentDay.Sma200SlopeUp ? "Up"
                              : currentDay != null && currentDay.Sma200SlopeDown ? "Down" : "Flat";
            string kind;
            double levelPrice;
            if (slopeSign == "Up")    { kind = "lower"; levelPrice = low; }
            else if (slopeSign == "Down") { kind = "upper"; levelPrice = high; }
            else
            {
                LogEvent("warning",
                    "msg", "News-wick detected but slope flat; skipping registration.",
                    "candle_time", barTime, "candle_volume", vol);
                return;
            }

            var nw = new NewsWick
            {
                Kind = kind,
                LevelPrice = levelPrice,
                CandleTime = barTime,
                CandleVolume = vol,
                RatioToMax = thresh > 0 ? vol / thresh : 0,
                Active = true
            };
            newsWicks.Add(nw);
            // Cap list at last 10 wicks
            while (newsWicks.Count > 10) newsWicks.RemoveAt(0);

            LogEvent("news_wick_registered",
                "wick_kind", kind,
                "level_price", levelPrice,
                "candle_time", barTime,
                "candle_volume", vol,
                "threshold", thresh,
                "ratio_to_max", nw.RatioToMax);
        }

        // =================================================================
        // CANDIDATE MARKERS ON CHART
        // =================================================================

        private int candidateMarkerCounter;

        // Marker filter: counts UNIQUE 30-MIN BARS that touched each level.
        // Allows up to 2 distinct 30-min bars per (level, direction, pattern) per
        // session — the FIRST 30-min bar (initial test) and the SECOND (AM "shake
        // the trees" rule from mar-6: first wick is often a stop-run, second probe
        // is where the trade sets up).  Multiple 1-min touches within the SAME
        // 30-min window count as one.  Cleared each session in ResetForNewDay.
        private const int MaxMarkersPerLevelPerSession = 1;  // first-touch-only for V1; bump to 2 for "shake the trees" later
        // composite key = level|dir|pattern|30minSlot ; value = barsAgo at first draw (unused, just dedup)
        private HashSet<string> markerDrawnInSlot = new HashSet<string>();
        // base key = level|dir|pattern ; value = count of UNIQUE 30-min slots already marked
        private Dictionary<string, int> markerDrawCounts = new Dictionary<string, int>();

        private void DrawCandidateMarker(CandidateEventArgs args)
        {
            try
            {
                // Visual filter 1: retrace-side only.  V2_6 emits BOTH directions
                // for every level (LONG and SHORT) so L2 ML can score both, but
                // visually we only show the side that's an actual retracement
                // (level price < bar_open for LONG, > bar_open for SHORT).  The
                // continuation-side candidate still emits to JSONL for ML.  This
                // halves the markers without information loss in the data layer.
                bool isRetrace = args.Direction == "LONG"
                    ? args.LevelPrice < args.BarOpen
                    : args.LevelPrice > args.BarOpen;
                if (!isRetrace) return;

                // Visual filter 1b: high-value level types only — applies to BOTH
                // Pattern A (dots) AND Pattern B (cyan triangles).  Markers are
                // restricted to master-candle edges, multi-day master candles, and
                // news-candle wicks.  Pivots / SMAs / opening range / rolling Pr30 /
                // RTH 1-min H/L still emit to JSONL for ML but produce no marker —
                // they're reference info, not setup levels.  This dramatically
                // reduces clutter on volatile bars (RTH open especially) where
                // many secondary levels would otherwise produce triangles.
                {
                    string lvl = args.LevelName ?? "";
                    // Whitelist of level-name prefixes that get a marker.  These
                    // are the AM master-candle edges + multi-day (Pday) + news
                    // wicks.  Skipped: ORH/ORL (opening range), Pr30* (rolling),
                    // SMA*, PP, R1-R4, S1-S4, VWAP/AnchVWAP, MidH/L (midnight).
                    // V1 whitelist: TODAY's 5 master candles + news wicks ONLY.
                    // Multi-day Pday1/Pday2/Pday3 dropped — too many lines (24+
                    // levels × 2 directions × 2 patterns = clutter).  News wicks
                    // are rare so kept.  Add Pday* back to the whitelist later if
                    // needed.  H/L/Mid suffixes covered by prefix match.
                    bool isHighValue = lvl.StartsWith("GlobEx")   // today's GlobEx 6PM box
                                    || lvl.StartsWith("Europe")   // today's Europe 4AM box
                                    || lvl.StartsWith("OR30")     // today's RTH 9:30 box
                                    || lvl.StartsWith("RTH1Min")  // 9:30 1-min opening H/L
                                    || lvl.StartsWith("PrInst")   // today's prior 3:30 institutional
                                    || lvl.StartsWith("Pr130")    // today's prior 1:30 candle
                                    || lvl.StartsWith("Pday1")    // YESTERDAY's master candles (t-1) only
                                    || lvl.StartsWith("News");    // news-candle wicks
                    if (!isHighValue) return;
                }

                // Visual filter 2: count UNIQUE 30-min bars that touched this
                // (level, direction, pattern). Multiple 1-min touches in the same
                // 30-min window count as ONE.  Allow up to N (default 2) unique
                // 30-min slots — first probe + second probe per AM's "shake the
                // trees" rule.  3rd+ unique 30-min bars: JSONL only, no marker.
                DateTime barOpenTime = args.BarTime.AddMinutes(-1);
                int slotMin = (barOpenTime.Minute / 30) * 30;
                DateTime slot30 = new DateTime(barOpenTime.Year, barOpenTime.Month, barOpenTime.Day,
                                               barOpenTime.Hour, slotMin, 0);
                string baseKey = (args.LevelName ?? "") + "|" + (args.Direction ?? "") + "|" + (args.PatternType ?? "");
                string compositeKey = baseKey + "|" + slot30.ToString("yyyyMMddHHmm");
                if (markerDrawnInSlot.Contains(compositeKey)) return;  // same 30-min slot already marked
                int curCount;
                markerDrawCounts.TryGetValue(baseKey, out curCount);
                if (curCount >= MaxMarkersPerLevelPerSession) return;  // 3rd unique 30-min bar
                markerDrawnInSlot.Add(compositeKey);
                markerDrawCounts[baseKey] = curCount + 1;

                candidateMarkerCounter++;
                string tag = "V26Cand_" + candidateMarkerCounter;

                // BarsAgo bug fix: a 1-min bar at e.g. 10:15 fires from
                // BarsInProgress=1.  At that moment, Times[0][0] (last closed
                // primary 30-min bar) = 10:00.  Drawing at barsAgo=0 places
                // the marker at the 10:00 X-tick (= NT8 "10:00 bar" = window
                // 9:30→10:00), which is ONE BAR TO THE LEFT of where the 1-min
                // touch actually happened (which is in the 10:00→10:30 window
                // = NT8 "10:30 bar").  Fix: when the 1-min bar's time is past
                // the last closed primary, draw at barsAgo=-1 (forming bar).
                int markerBarsAgo = 0;
                try
                {
                    if (CurrentBars[0] >= 0 && Times[0].Count > 0
                        && args.BarTime > Times[0][0])
                        markerBarsAgo = -1;
                }
                catch { markerBarsAgo = 0; }

                Brush color;
                if (args.PatternType == "B")
                {
                    color = Brushes.Cyan;
                    if (args.Direction == "LONG")
                        Draw.TriangleUp(this, tag, false, markerBarsAgo, args.LevelPrice, color);
                    else
                        Draw.TriangleDown(this, tag, false, markerBarsAgo, args.LevelPrice, color);
                }
                else if (args.IsPermissionLevel)
                {
                    color = Brushes.Gray;
                    Draw.Text(this, tag, false, "x", markerBarsAgo, args.LevelPrice, 0, color,
                        new Gui.Tools.SimpleFont("Arial", 9), TextAlignment.Center,
                        Brushes.Transparent, Brushes.Transparent, 0);
                }
                else
                {
                    color = args.Direction == "LONG" ? Brushes.LimeGreen : Brushes.OrangeRed;
                    Draw.Dot(this, tag, false, markerBarsAgo, args.LevelPrice, color);
                }
                if (sessionDrawTags != null) sessionDrawTags.Add(tag);
            }
            catch { /* marker drawing is best-effort */ }
        }

        // =================================================================
        // PRE-TOUCH WATCH LEVELS
        // =================================================================

        private void UpdatePreTouchCandidateDisplay(double lastPrice)
        {
            if (priceLabels == null) return;

            ClearPreTouchCandidateLabels();

            if (!ShowPreTouchCandidateLevels) return;
            if (lastPrice <= 0 || double.IsNaN(lastPrice) || double.IsInfinity(lastPrice)) return;

            var levels = BuildAllLevels();
            if (levels == null || levels.Count == 0) return;

            var buyWatch = new List<PreTouchWatchLevel>();
            var sellWatch = new List<PreTouchWatchLevel>();
            AMDirectionFilter directionFilter = ComputeDirectionFilter();

            foreach (var kv in levels)
            {
                string name = StripStamp(kv.Key);
                double px = kv.Value.Price;
                if (!IsPreTouchWatchLevel(name, kv.Value.IsPermission)) continue;
                if (px <= 0 || double.IsNaN(px) || double.IsInfinity(px)) continue;

                double dist = px - lastPrice;
                var watch = new PreTouchWatchLevel
                {
                    Name = name,
                    Price = px,
                    DistancePts = dist,
                    IsPermission = kv.Value.IsPermission
                };

                // If price is above a level, the next touch is a support retest
                // candidate. If price is below it, the next touch is a resistance
                // retest candidate. L2 can still flip the thesis later.
                if (dist <= 0) buyWatch.Add(watch);
                else sellWatch.Add(watch);
            }

            if (directionFilter != AMDirectionFilter.Short)
            {
                foreach (var w in buyWatch.OrderBy(w => Math.Abs(w.DistancePts)).Take(MaxPreTouchWatchLevelsPerSide))
                    AddPreTouchCandidateLabel(w, true);
            }
            if (directionFilter != AMDirectionFilter.Long)
            {
                foreach (var w in sellWatch.OrderBy(w => Math.Abs(w.DistancePts)).Take(MaxPreTouchWatchLevelsPerSide))
                    AddPreTouchCandidateLabel(w, false);
            }
        }

        private void ClearPreTouchCandidateLabels()
        {
            if (priceLabels == null || preTouchCandidateTags == null || preTouchCandidateTags.Count == 0) return;
            foreach (string tag in preTouchCandidateTags)
                priceLabels.Remove(tag);
            preTouchCandidateTags.Clear();
        }

        private bool IsPreTouchWatchLevel(string name, bool isPermission)
        {
            if (string.IsNullOrEmpty(name)) return false;
            if (isPermission) return name == "VWAP" || name == "AnchVWAP";
            return name.StartsWith("GlobEx")
                || name.StartsWith("Europe")
                || name.StartsWith("OR30")
                || name.StartsWith("RTH1Min")
                || name.StartsWith("PrInst")
                || name.StartsWith("Pr130")
                || name.StartsWith("Pday1")
                || name.StartsWith("News");
        }

        private void AddPreTouchCandidateLabel(PreTouchWatchLevel w, bool buySide)
        {
            if (w == null || priceLabels == null) return;

            string side = buySide ? "BUY" : "SELL";
            string tag = "PreTouch_" + side + "_" + SafeTag(w.Name);
            string dist = w.DistancePts.ToString("+0.00;-0.00;0.00", CultureInfo.InvariantCulture);
            Brush color = w.IsPermission ? Brushes.Gray : (buySide ? Brushes.LimeGreen : Brushes.OrangeRed);

            preTouchCandidateTags.Add(tag);
            priceLabels[tag] = new PriceLabel
            {
                Price = w.Price,
                Text = $"{side} WATCH {w.Name}  {w.Price:F2}  {dist}",
                Color = color,
                Dash = DashStyleHelper.Dash,
                LineWidth = w.IsPermission ? 1 : 2,
                DrawLine = true,
                SideOverride = CockpitLabelPosition.Right
            };
        }

        // =================================================================
        // CONTAINMENT CHECK
        // =================================================================

        private void RunContainmentCheck()
        {
            var boxes = new List<CandleBox>();
            if (currentDay?.Close330  != null) boxes.Add(currentDay.Close330);
            if (currentDay?.GlobEx6PM != null) boxes.Add(currentDay.GlobEx6PM);
            if (currentDay?.Europe4AM != null) boxes.Add(currentDay.Europe4AM);
            if (currentDay?.RTH930    != null) boxes.Add(currentDay.RTH930);

            if (boxes.Count < 2)
            {
                if (boxes.Count == 1)
                {
                    institutionalBox = boxes[0];
                    institutionalName = boxes[0].Name;
                }
                return;
            }

            CandleBox bestInstitutional = null;
            int bestCount = -1;
            int partialOverlaps = 0;
            for (int i = 0; i < boxes.Count; i++)
            {
                int containCount = 0;
                for (int j = 0; j < boxes.Count; j++)
                {
                    if (i == j) continue;
                    if (boxes[i].Contains(boxes[j])) containCount++;
                    if (i < j && boxes[i].PartiallyOverlaps(boxes[j])) partialOverlaps++;
                }
                if (containCount > bestCount
                    || (containCount == bestCount && bestInstitutional != null && boxes[i].Range > bestInstitutional.Range))
                {
                    bestCount = containCount;
                    bestInstitutional = boxes[i];
                }
            }

            // Detect institutional reassignment for box_capture re-emission.
            bool reassigned = institutionalBox != null && bestInstitutional != institutionalBox;
            institutionalBox = bestInstitutional;
            institutionalName = bestInstitutional.Name;
            if (partialOverlaps >= 2)
                currentDayType = DayType.Congestion;

            Log($"INSTITUTIONAL: {institutionalName} ({institutionalBox.Low:F2} - {institutionalBox.High:F2})");
            DrawInstitutionalBox(institutionalBox);

            if (reassigned)
                EmitBoxCapture(institutionalBox, "institutional_reassignment", 0, true);
        }

        // =================================================================
        // PIVOTS (Woody's-style, daily)
        // =================================================================

        private void CalculatePivots(double high, double low, double close)
        {
            // Woody's pivots: weight close 2x.
            pivotPP = (high + low + 2.0 * close) / 4.0;
            pivotR1 = 2 * pivotPP - low;
            pivotS1 = 2 * pivotPP - high;
            pivotR2 = pivotPP + (high - low);
            pivotS2 = pivotPP - (high - low);
            pivotR3 = high + 2 * (pivotPP - low);
            pivotS3 = low  - 2 * (high - pivotPP);
            pivotR4 = pivotR3 + (high - low);
            pivotS4 = pivotS3 - (high - low);
            pivotsCalculated = true;
            Log($"PIVOTS (Woody's): PP={pivotPP:F2} R1-4={pivotR1:F2}/{pivotR2:F2}/{pivotR3:F2}/{pivotR4:F2} S1-4={pivotS1:F2}/{pivotS2:F2}/{pivotS3:F2}/{pivotS4:F2}");
        }

        // =================================================================
        // DAY TYPE / BIAS / PHASE (informational only)
        // =================================================================

        private void DetermineDayType()
        {
            if (institutionalBox == null) return;
            if (pivotsCalculated && idx30Min >= 0 && CurrentBars[idx30Min] >= 1)
            {
                double price = Closes[idx30Min][0];
                if (price > pivotR2 || price < pivotS2)
                {
                    currentDayType = DayType.Extended;
                    return;
                }
            }
            if (smaDirection30 == "Flat" && vwapSlope == "Flat")
                currentDayType = DayType.Congestion;
            else if ((smaDirection30 == "Up" || smaDirection30 == "Down")
                && (vwapSlope == "Up" || vwapSlope == "Down"))
                currentDayType = DayType.Trending;
            else
                currentDayType = DayType.Unknown;
        }

        private void DetermineBias(double price)
        {
            if (institutionalBox == null) { currentBias = Bias.Wait; return; }
            if (price > institutionalBox.High) currentBias = Bias.Long;
            else if (price < institutionalBox.Low) currentBias = Bias.Short;
            else currentBias = Bias.Neutral;
        }

        private void UpdatePhase(DateTime time)
        {
            int h = time.Hour;
            int m = time.Minute;
            if ((h == closeHour && m >= closeMinute) || (h > closeHour && h <= 16))
                currentPhase = TradingPhase.RTHClose;
            else if (h == 17)
                currentPhase = TradingPhase.PreGlobEx;
            else if (h >= 18)
                currentPhase = TradingPhase.GlobExOpen;
            else if (h < 4)
                currentPhase = TradingPhase.Midnight;
            else if (h >= 4 && (h < rthOpenHour || (h == rthOpenHour && m < rthOpenMinute)))
                currentPhase = TradingPhase.EuropeOpen;
            else if (h == rthOpenHour && m == rthOpenMinute)
                currentPhase = TradingPhase.RTHOpen;
            else if ((h == rthOpenHour && m > rthOpenMinute) || (h > rthOpenHour && h < closeHour) || (h == closeHour && m < closeMinute))
                currentPhase = TradingPhase.RTHActive;
        }

        // =================================================================
        // DAY-TYPE CLASSIFIERS
        // =================================================================

        // 3-node interpretation (B<C<D) per AM apr-23 verbatim.
        private AMDayType ClassifyAMDayType3Node()
        {
            if (currentDay == null) return AMDayType.Unknown;
            CandleBox b = currentDay.GlobEx6PM;
            CandleBox c = currentDay.Europe4AM;
            CandleBox d = currentDay.RTH930;
            if (b == null || c == null) return AMDayType.Unknown;

            bool bc_up   = c.BodyStrictlyAbove(b);
            bool bc_down = c.BodyStrictlyBelow(b);
            if (d != null)
            {
                bool cd_up = d.BodyStrictlyAbove(c);
                bool cd_down = d.BodyStrictlyBelow(c);
                if (bc_up && cd_up)            return AMDayType.LongTrend;
                if (bc_down && cd_down)        return AMDayType.ShortTrend;
                if (bc_up && !cd_up)           return AMDayType.CautiousLong;
                if (bc_down && !cd_down)       return AMDayType.CautiousShort;
                return AMDayType.Sideways;
            }
            if (double.IsNaN(currentDay.RTH930OpenPx)) return AMDayType.Unknown;
            double openD = currentDay.RTH930OpenPx;
            bool cd_up_p   = openD > c.BodyTop;
            bool cd_down_p = openD < c.BodyBottom;
            if (bc_up && cd_up_p)         return AMDayType.LongTrend;
            if (bc_down && cd_down_p)     return AMDayType.ShortTrend;
            if (bc_up && !cd_up_p)        return AMDayType.CautiousLong;
            if (bc_down && !cd_down_p)    return AMDayType.CautiousShort;
            return AMDayType.Sideways;
        }

        // 4-node interpretation (A<B<C<D) — V2_4 legacy / AM_rules_v2_spec.md §1.
        private AMDayType ClassifyAMDayType4Node()
        {
            if (currentDay == null) return AMDayType.Unknown;
            CandleBox a = currentDay.Close330;
            CandleBox b = currentDay.GlobEx6PM;
            CandleBox c = currentDay.Europe4AM;
            CandleBox d = currentDay.RTH930;
            if (a == null || b == null || c == null) return AMDayType.Unknown;

            bool ab_up = b.BodyStrictlyAbove(a); bool bc_up = c.BodyStrictlyAbove(b);
            bool ab_down = b.BodyStrictlyBelow(a); bool bc_down = c.BodyStrictlyBelow(b);
            if (d != null)
            {
                bool cd_up = d.BodyStrictlyAbove(c);
                bool cd_down = d.BodyStrictlyBelow(c);
                if (ab_up && bc_up && cd_up)             return AMDayType.LongTrend;
                if (ab_down && bc_down && cd_down)       return AMDayType.ShortTrend;
                if (ab_up && bc_up && !cd_up)            return AMDayType.CautiousLong;
                if (ab_down && bc_down && !cd_down)      return AMDayType.CautiousShort;
                return AMDayType.Sideways;
            }
            if (double.IsNaN(currentDay.RTH930OpenPx)) return AMDayType.Unknown;
            double openD = currentDay.RTH930OpenPx;
            bool cd_up_p = openD > c.BodyTop;
            bool cd_down_p = openD < c.BodyBottom;
            if (ab_up && bc_up && cd_up_p)         return AMDayType.LongTrend;
            if (ab_down && bc_down && cd_down_p)   return AMDayType.ShortTrend;
            if (ab_up && bc_up && !cd_up_p)        return AMDayType.CautiousLong;
            if (ab_down && bc_down && !cd_down_p)  return AMDayType.CautiousShort;
            return AMDayType.Sideways;
        }

        private AMDirectionFilter ComputeDirectionFilter()
        {
            AMDirectionFilter from3Node = MapDayTypeToDirection(ClassifyAMDayType3Node());
            if (from3Node != AMDirectionFilter.Unknown) return from3Node;

            AMDirectionFilter from4Node = MapDayTypeToDirection(ClassifyAMDayType4Node());
            if (from4Node != AMDirectionFilter.Unknown) return from4Node;

            if (currentBias == Bias.Long) return AMDirectionFilter.Long;
            if (currentBias == Bias.Short) return AMDirectionFilter.Short;
            if (currentBias == Bias.Neutral) return AMDirectionFilter.Sideways;
            return AMDirectionFilter.Unknown;
        }

        private AMDirectionFilter MapDayTypeToDirection(AMDayType dayType)
        {
            switch (dayType)
            {
                case AMDayType.LongTrend:
                case AMDayType.CautiousLong:
                    return AMDirectionFilter.Long;
                case AMDayType.ShortTrend:
                case AMDayType.CautiousShort:
                    return AMDirectionFilter.Short;
                case AMDayType.Sideways:
                    return AMDirectionFilter.Sideways;
                default:
                    return AMDirectionFilter.Unknown;
            }
        }

        private bool DirectionFilterAllowsCandidate(AMDirectionFilter filter, string candidateDirection)
        {
            if (filter == AMDirectionFilter.Long) return candidateDirection == "LONG";
            if (filter == AMDirectionFilter.Short) return candidateDirection == "SHORT";
            return true;
        }

        // =================================================================
        // ANCHORED VWAP
        // =================================================================

        private void V2UpdateAnchoredVWAP(double high, double low, double close, double vol, DateTime barOpen)
        {
            if (institutionalBox == null)
            {
                v2AVWAP = double.NaN;
                v2AVWAPAnchorTime = DateTime.MinValue;
                v2AVWAPCumTPV = 0; v2AVWAPCumVol = 0;
                return;
            }
            DateTime anchor = institutionalBox.StartTime;
            if (barOpen < anchor) { v2AVWAP = double.NaN; return; }
            if (anchor != v2AVWAPAnchorTime)
            {
                v2AVWAPAnchorTime = anchor;
                v2AVWAPCumTPV = 0; v2AVWAPCumVol = 0;
                int maxBack = CurrentBars[idx1Min];
                int firstBarAgo = -1;
                for (int ba = 1; ba <= maxBack; ba++)
                {
                    DateTime bOpen = Times[idx1Min][ba].AddMinutes(-1);
                    if (bOpen < anchor) break;
                    firstBarAgo = ba;
                }
                if (firstBarAgo >= 1)
                {
                    for (int ba = firstBarAgo; ba >= 1; ba--)
                    {
                        double h = Highs[idx1Min][ba];
                        double l = Lows[idx1Min][ba];
                        double c = Closes[idx1Min][ba];
                        double v = Volumes[idx1Min][ba];
                        double tp = (h + l + c) / 3.0;
                        v2AVWAPCumTPV += tp * v;
                        v2AVWAPCumVol += v;
                    }
                }
            }
            double typical = (high + low + close) / 3.0;
            v2AVWAPCumTPV += typical * vol;
            v2AVWAPCumVol += vol;
            v2AVWAP = v2AVWAPCumVol > 0 ? v2AVWAPCumTPV / v2AVWAPCumVol : double.NaN;
        }

        // =================================================================
        // JSONL EVENT LOG
        // =================================================================

        private static string JsonEscape(string s)
        {
            if (s == null) return "";
            StringBuilder sb = new StringBuilder(s.Length + 4);
            foreach (char c in s)
            {
                if (c == '"') sb.Append("\\\"");
                else if (c == '\\') sb.Append("\\\\");
                else if (c == '\n') sb.Append("\\n");
                else if (c == '\r') sb.Append("\\r");
                else if (c == '\t') sb.Append("\\t");
                else if (c < 0x20) sb.AppendFormat("\\u{0:x4}", (int)c);
                else sb.Append(c);
            }
            return sb.ToString();
        }

        private static string FormatField(object v)
        {
            if (v == null) return "null";
            if (v is string s) return "\"" + JsonEscape(s) + "\"";
            if (v is bool b) return b ? "true" : "false";
            if (v is double d) {
                if (double.IsNaN(d) || double.IsInfinity(d)) return "null";
                return d.ToString("R", CultureInfo.InvariantCulture);
            }
            if (v is float f) {
                if (double.IsNaN(f) || double.IsInfinity(f)) return "null";
                return f.ToString("R", CultureInfo.InvariantCulture);
            }
            if (v is int i) return i.ToString(CultureInfo.InvariantCulture);
            if (v is long l) return l.ToString(CultureInfo.InvariantCulture);
            if (v is DateTime dt) return "\"" + dt.ToString("o", CultureInfo.InvariantCulture) + "\"";
            return "\"" + JsonEscape(v.ToString()) + "\"";
        }

        private void EnsureJsonlPath(DateTime forEventTime)
        {
            if (!EnableJsonlLog || string.IsNullOrWhiteSpace(JsonlLogFolder)) return;
            DateTime day = forEventTime.Date;
            if (jsonlPathToday != null && jsonlDateActive == day) return;
            try
            {
                string dayFolder = Path.Combine(JsonlLogFolder, day.ToString("yyyy-MM-dd"));
                if (!Directory.Exists(dayFolder)) Directory.CreateDirectory(dayFolder);
                jsonlPathToday = Path.Combine(dayFolder, "events.jsonl");
                jsonlDateActive = day;
                stateJsonPath = Path.Combine(dayFolder, "state.json");
            }
            catch (Exception ex)
            {
                Print("[V2_6 cockpit-log] folder init failed: " + ex.Message);
                jsonlPathToday = null;
            }
        }

        private void LogEvent(string type, params object[] payloadPairs)
        {
            if (!EnableJsonlLog) return;
            DateTime t = (CurrentBars != null && CurrentBars.Length > 0 && CurrentBars[0] >= 0)
                ? Times[0][0] : DateTime.Now;
            EnsureJsonlPath(t);
            if (jsonlPathToday == null) return;

            StringBuilder sb = new StringBuilder(512);
            sb.Append('{');
            sb.Append("\"t\":").Append(FormatField(t));
            sb.Append(",\"type\":").Append(FormatField(type));
            sb.Append(",\"schema_version\":\"v26.0\"");
            sb.Append(",\"instrument\":").Append(FormatField(Instrument != null ? Instrument.FullName : ""));
            sb.Append(",\"session_date\":").Append(FormatField(t.Date.ToString("yyyy-MM-dd")));
            sb.Append(",\"payload\":{");
            if (payloadPairs != null)
            {
                bool first = true;
                for (int i = 0; i + 1 < payloadPairs.Length; i += 2)
                {
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append(FormatField(payloadPairs[i] == null ? "" : payloadPairs[i].ToString()));
                    sb.Append(':');
                    sb.Append(FormatField(payloadPairs[i + 1]));
                }
            }
            sb.Append("}}");
            sb.Append('\n');

            try
            {
                File.AppendAllText(jsonlPathToday, sb.ToString());
            }
            catch (Exception ex)
            {
                Print("[V2_6 cockpit-log] write failed: " + ex.Message);
            }
        }

        private void MaybeHeartbeat(double lastPrice)
        {
            if (!EnableJsonlLog || HeartbeatSeconds <= 0) return;
            DateTime now = (CurrentBars != null && CurrentBars.Length > 0 && CurrentBars[0] >= 0)
                ? Times[0][0] : DateTime.Now;
            if (lastHeartbeatAt != default(DateTime)
                && (now - lastHeartbeatAt).TotalSeconds < HeartbeatSeconds) return;
            lastHeartbeatAt = now;

            // V2_6 vocab fix: emit BOTH legacy day_type and v2DayType (3-node).
            AMDayType dt3 = ClassifyAMDayType3Node();
            AMDayType dt4 = ClassifyAMDayType4Node();
            string v2DayTypeStr = dt3.ToString().ToLowerInvariant();
            string directionFilter = ComputeDirectionFilter().ToString().ToLowerInvariant();
            object mocRatio = (currentDay != null && !double.IsNaN(currentDay.MocRatio)) ? (object)currentDay.MocRatio : null;
            string mocState = currentDay != null ? currentDay.MocState.ToString() : "Pending";
            object slopeDelta = currentDay != null && !double.IsNaN(currentDay.Sma200SlopeDelta) ? (object)currentDay.Sma200SlopeDelta : null;

            LogEvent("heartbeat",
                "phase", currentPhase.ToString().ToLowerInvariant(),
                "bias",  currentBias.ToString().ToLowerInvariant(),
                "direction_filter", directionFilter,
                "day_type_v2_3node", v2DayTypeStr,
                "day_type_v2_4node", dt4.ToString().ToLowerInvariant(),
                "regime", currentDayType.ToString().ToLowerInvariant(),
                "price", lastPrice,
                "vwap", currentVWAP,
                "moc_state", mocState,
                "moc_ratio", mocRatio,
                "sma200_slope_delta", slopeDelta,
                "in_lockout", lockoutActive,
                "candidates_today", candidatesEmittedToday,
                "pattern_b_armed_today", patternBArmedToday,
                "unique_levels_touched", uniqueLevelsTouchedToday.Count);
        }

        // =================================================================
        // STATE PERSISTENCE (state.json)
        // =================================================================

        // Per architect §5.6: V2_6 writes its in-memory state to state.json
        // periodically + on Terminated. Current restore is informational only.
        private void PersistStateJson(string trigger)
        {
            if (!EnableStatePersistence) return;
            if (string.IsNullOrEmpty(stateJsonPath))
            {
                // EnsureJsonlPath sets stateJsonPath; trigger by reading current bar time.
                DateTime t = (CurrentBars != null && CurrentBars.Length > 0 && CurrentBars[0] >= 0)
                    ? Times[0][0] : DateTime.Now;
                EnsureJsonlPath(t);
                if (string.IsNullOrEmpty(stateJsonPath)) return;
            }
            try
            {
                StringBuilder sb = new StringBuilder(2048);
                sb.Append("{\n");
                sb.Append("  \"session_date\":").Append(FormatField(jsonlDateActive.ToString("yyyy-MM-dd"))).Append(",\n");
                sb.Append("  \"instrument\":").Append(FormatField(Instrument != null ? Instrument.FullName : "")).Append(",\n");
                sb.Append("  \"v2_6_version\":\"v26.0\",\n");
                sb.Append("  \"schema_version\":\"v26.0\",\n");
                sb.Append("  \"last_updated\":").Append(FormatField(DateTime.Now)).Append(",\n");
                sb.Append("  \"trigger\":").Append(FormatField(trigger)).Append(",\n");
                sb.Append("  \"counters\":{\n");
                sb.Append("    \"candidates_emitted_today\":").Append(candidatesEmittedToday).Append(",\n");
                sb.Append("    \"pattern_b_armed_today\":").Append(patternBArmedToday).Append(",\n");
                sb.Append("    \"unique_levels_touched\":").Append(uniqueLevelsTouchedToday.Count).Append("\n");
                sb.Append("  },\n");
                sb.Append("  \"level_watch_states\":[\n");
                bool first = true;
                foreach (var kv in levelWatchStates)
                {
                    if (kv.Value.Status == LevelWatchStatus.Untouched) continue;
                    if (!first) sb.Append(",\n");
                    first = false;
                    sb.Append("    {\"key\":").Append(FormatField(kv.Key));
                    sb.Append(",\"level_name\":").Append(FormatField(kv.Value.LevelName));
                    sb.Append(",\"level_price\":").Append(FormatField(kv.Value.LevelPrice));
                    sb.Append(",\"direction\":").Append(FormatField(kv.Value.Direction));
                    sb.Append(",\"status\":").Append(FormatField(kv.Value.Status.ToString()));
                    if (kv.Value.AnchorCandle != null)
                    {
                        sb.Append(",\"anchor_high\":").Append(FormatField(kv.Value.AnchorCandle.High));
                        sb.Append(",\"anchor_low\":").Append(FormatField(kv.Value.AnchorCandle.Low));
                        sb.Append(",\"anchor_volume\":").Append(FormatField(kv.Value.AnchorCandle.Volume));
                        sb.Append(",\"breach_time\":").Append(FormatField(kv.Value.BreachTime));
                    }
                    sb.Append("}");
                }
                sb.Append("\n  ],\n");
                sb.Append("  \"news_wicks_active\":[\n");
                first = true;
                foreach (var nw in newsWicks)
                {
                    if (!nw.Active) continue;
                    if (!first) sb.Append(",\n");
                    first = false;
                    sb.Append("    {");
                    sb.Append("\"wick_kind\":").Append(FormatField(nw.Kind));
                    sb.Append(",\"level_price\":").Append(FormatField(nw.LevelPrice));
                    sb.Append(",\"candle_time\":").Append(FormatField(nw.CandleTime));
                    sb.Append(",\"candle_volume\":").Append(FormatField(nw.CandleVolume));
                    sb.Append("}");
                }
                sb.Append("\n  ]\n");
                sb.Append("}\n");

                // Atomic write: tmp + replace.
                string tmpPath = stateJsonPath + ".tmp";
                File.WriteAllText(tmpPath, sb.ToString());
                if (File.Exists(stateJsonPath)) File.Delete(stateJsonPath);
                File.Move(tmpPath, stateJsonPath);
                lastStatePersistedAt = DateTime.Now;

                LogEvent("state_persisted",
                    "path", stateJsonPath,
                    "trigger", trigger);
            }
            catch (Exception ex)
            {
                EmitError(ex);
            }
        }

        private void TryRestoreStateJson()
        {
            if (!EnableStatePersistence) return;
            // We need stateJsonPath but EnsureJsonlPath only runs on first event;
            // bootstrap it here from today's date.
            try
            {
                DateTime today = DateTime.Today;
                string dayFolder = Path.Combine(JsonlLogFolder, today.ToString("yyyy-MM-dd"));
                string p = Path.Combine(dayFolder, "state.json");
                if (!File.Exists(p))
                {
                    Log("State.json not found; will warm up from bar history.");
                    return;
                }
                // Best-effort parse — for V1 we just log that we found it.  Full
                // deserialization is the strategy agent's concern for L3 counters.
                Log($"State.json found at {p} (size {new FileInfo(p).Length} bytes); warm restore deferred to L2/L3.");
            }
            catch (Exception ex)
            {
                EmitError(ex);
            }
        }

        // =================================================================
        // CHART RENDERING
        // =================================================================

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            base.OnRender(chartControl, chartScale);

            SharpDX.Direct2D1.RenderTarget rt = RenderTarget;
            if (rt == null) return;
            if (rt != cachedTarget)
            {
                DisposeSharpDX();
                cachedTarget = rt;
                EnsureBrushes(rt);
            }

            RenderChartLegend(rt, chartControl);

            if (lockoutActive) RenderLockoutBanner(rt, chartControl);

            // Price labels (preserved from V2_4) — render as horizontal lines + text.
            KeyValuePair<string, PriceLabel>[] labelSnapshot = null;
            if (priceLabels != null && priceLabels.Count > 0)
            {
                try { labelSnapshot = priceLabels.ToArray(); } catch { }
            }
            if (labelSnapshot != null && labelSnapshot.Length > 0 && chartScale != null)
            {
                float chartWidth = chartControl.Properties.BarMarginRight > 0
                    ? (float)ChartPanel.W - (float)chartControl.Properties.BarMarginRight
                    : (float)ChartPanel.W;
                foreach (var kvp in labelSnapshot)
                {
                    var lbl = kvp.Value;
                    float yLine = chartScale.GetYByValue(lbl.Price);
                    using (var lineBrush = new SharpDX.Direct2D1.SolidColorBrush(rt,
                        SharpDX.Color.FromBgra(((SolidColorBrush)lbl.Color).Color.B
                            | ((uint)((SolidColorBrush)lbl.Color).Color.G << 8)
                            | ((uint)((SolidColorBrush)lbl.Color).Color.R << 16)
                            | ((uint)255 << 24))))
                    {
                        SharpDX.Direct2D1.StrokeStyle ss = null;
                        if (lbl.Dash == DashStyleHelper.Dash || lbl.Dash == DashStyleHelper.Dot
                            || lbl.Dash == DashStyleHelper.DashDot || lbl.Dash == DashStyleHelper.DashDotDot)
                        {
                            var dashProps = new SharpDX.Direct2D1.StrokeStyleProperties
                            {
                                DashStyle = lbl.Dash == DashStyleHelper.Dash ? SharpDX.Direct2D1.DashStyle.Dash
                                          : lbl.Dash == DashStyleHelper.Dot ? SharpDX.Direct2D1.DashStyle.Dot
                                          : lbl.Dash == DashStyleHelper.DashDot ? SharpDX.Direct2D1.DashStyle.DashDot
                                          : SharpDX.Direct2D1.DashStyle.DashDotDot
                            };
                            try { ss = new SharpDX.Direct2D1.StrokeStyle(rt.Factory, dashProps); } catch { ss = null; }
                        }
                        float lineW = lbl.LineWidth > 0 ? lbl.LineWidth : 1;
                        if (lbl.DrawLine)
                        {
                            if (ss != null)
                            {
                                rt.DrawLine(new SharpDX.Vector2(0, yLine), new SharpDX.Vector2((float)ChartPanel.W, yLine), lineBrush, lineW, ss);
                                ss.Dispose();
                            }
                            else
                            {
                                rt.DrawLine(new SharpDX.Vector2(0, yLine), new SharpDX.Vector2((float)ChartPanel.W, yLine), lineBrush, lineW);
                            }
                        }
                        else if (ss != null) { ss.Dispose(); }
                    }
                    CockpitLabelPosition pos = lbl.SideOverride ?? LabelPosition;
                    float x;
                    switch (pos)
                    {
                        case CockpitLabelPosition.Left:   x = 5; break;
                        case CockpitLabelPosition.Center: x = chartWidth / 2; break;
                        default:                          x = chartWidth - 10; break;
                    }
                    using (var labelBrush = new SharpDX.Direct2D1.SolidColorBrush(rt,
                        SharpDX.Color.FromBgra(((SolidColorBrush)lbl.Color).Color.B
                            | ((uint)((SolidColorBrush)lbl.Color).Color.G << 8)
                            | ((uint)((SolidColorBrush)lbl.Color).Color.R << 16)
                            | ((uint)255 << 24))))
                    using (var bgBrush = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(0, 0, 0, 180)))
                    using (var fmt = new SharpDX.DirectWrite.TextFormat(
                        NinjaTrader.Core.Globals.DirectWriteFactory, "Consolas", 10))
                    using (var txtLayout = new SharpDX.DirectWrite.TextLayout(
                        NinjaTrader.Core.Globals.DirectWriteFactory, lbl.Text, fmt, 300, 20))
                    {
                        float y = yLine - 15;
                        float txtW = txtLayout.Metrics.Width;
                        float txtH = txtLayout.Metrics.Height;
                        if (pos == CockpitLabelPosition.Right) x = x - txtW;
                        else if (pos == CockpitLabelPosition.Center) x = x - txtW / 2;
                        var bgRect = new SharpDX.RectangleF(x - 2, y - 1, txtW + 4, txtH + 2);
                        rt.FillRectangle(bgRect, bgBrush);
                        rt.DrawTextLayout(new SharpDX.Vector2(x, y), txtLayout, labelBrush);
                    }
                }
            }

            // Diagnostic info panel (preserves V2_4 visual surface but updated verdict text)
            RenderDiagnosticPanel(rt, chartControl);
        }

        private void RenderDiagnosticPanel(SharpDX.Direct2D1.RenderTarget rt, ChartControl chartControl)
        {
            if (dxBgBrush == null || dxTealBrush == null) return;
            float panelW = 340f;
            float rowH = 15f;
            float titleH = 22f;
            float pad = 8f;
            // Header + 8 rows (incl. direction filter and high-value-levels counter)
            float bodyH = titleH + 8 * rowH + pad;
            float panelX = PrePlacePanelX;
            float panelY = PrePlacePanelY;
            if (lockoutActive) panelY += 30f;

            var panelRect = new SharpDX.RectangleF(panelX, panelY, panelW, bodyH);
            rt.FillRectangle(panelRect, dxBgBrush);
            rt.DrawRectangle(panelRect, dxTealBrush, 1.5f);

            using (var titleFmt = new SharpDX.DirectWrite.TextFormat(
                NinjaTrader.Core.Globals.DirectWriteFactory, "Arial",
                SharpDX.DirectWrite.FontWeight.Bold,
                SharpDX.DirectWrite.FontStyle.Normal, 12f))
            using (var rowFmt = new SharpDX.DirectWrite.TextFormat(
                NinjaTrader.Core.Globals.DirectWriteFactory, "Consolas", 11f))
            {
                float y = panelY + 4;
                float xText = panelX + pad;
                float wText = panelW - pad * 2;
                var headerRect = new SharpDX.RectangleF(panelX, panelY, panelW, 20f);
                rt.FillRectangle(headerRect, dxTealBrush);
                string inst = Instrument != null && Instrument.MasterInstrument != null
                    ? Instrument.MasterInstrument.Name : "?";
                rt.DrawText($"V2_6 L1 — {inst}  {lastBarTime:HH:mm} ET",
                    titleFmt, new SharpDX.RectangleF(xText, y, wText, 16f), dxTitleTextBrush);
                y += titleH;

                AMDayType dt3 = ClassifyAMDayType3Node();
                AMDayType dt4 = ClassifyAMDayType4Node();
                rt.DrawText($"DayType (3-node): {dt3}",
                    rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxTextBrush);
                y += rowH;
                rt.DrawText($"DayType (4-node): {dt4}",
                    rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxTextBrush);
                y += rowH;

                AMDirectionFilter dir = ComputeDirectionFilter();
                SharpDX.Direct2D1.Brush directionBrush = dxTextBrush;
                if (dir == AMDirectionFilter.Long) directionBrush = dxGreenBrush;
                else if (dir == AMDirectionFilter.Short) directionBrush = dxRedBrush;
                else if (dir == AMDirectionFilter.Sideways) directionBrush = dxAmberBrush;
                rt.DrawText($"Direction filter: {dir}",
                    rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), directionBrush);
                y += rowH;

                string mocText;
                if (currentDay != null && currentDay.MocState != MOCValidation.Pending && !double.IsNaN(currentDay.MocRatio))
                    mocText = $"MOC: {currentDay.MocState} ratio {currentDay.MocRatio:F2}";
                else
                    mocText = "MOC: pending";
                rt.DrawText(mocText, rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxTextBrush);
                y += rowH;

                string slopeText;
                if (currentDay != null && !double.IsNaN(currentDay.Sma200SlopeDelta))
                    slopeText = $"200 SMA slope: {currentDay.Sma200SlopeDelta:+0.00;-0.00;0.00}";
                else
                    slopeText = "200 SMA slope: pending";
                rt.DrawText(slopeText, rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxTextBrush);
                y += rowH;

                rt.DrawText($"Candidates today: {candidatesEmittedToday}",
                    rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxGreenBrush);
                y += rowH;
                rt.DrawText($"Levels touched: {uniqueLevelsTouchedToday.Count}  | Pattern B armed: {patternBArmedToday}",
                    rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxAmberBrush);
                y += rowH;
                rt.DrawText($"High-value levels touched: {highValueLevelsTouchedToday.Count}",
                    rowFmt, new SharpDX.RectangleF(xText, y, wText, rowH), dxGreenBrush);
                y += rowH;
            }
        }

        private void RenderLockoutBanner(SharpDX.Direct2D1.RenderTarget rt, ChartControl chartControl)
        {
            string text = lockoutReason ?? "Daily loss lockout active (informational)";
            float bannerY = 22;
            float bannerH = 28;
            float panelW = chartControl != null ? (float)ChartPanel.W : 1200;
            var bannerRect = new SharpDX.RectangleF(0, bannerY, panelW, bannerH);
            rt.FillRectangle(bannerRect, dxRedBrush);
            rt.DrawText("L1 INFO LOCKOUT - " + text, dxTitleFormat, bannerRect, dxTextBrush);
        }

        private void RenderChartLegend(SharpDX.Direct2D1.RenderTarget rt, ChartControl chartControl)
        {
            float yTop = Math.Max(0, LegendYOffset);
            if (lockoutActive) yTop += 30f;
            float chipH = 26f;
            float padX = 12f;
            float gap = 3f;
            float x = Math.Max(0, LegendXOffset);
            var items = new[]
            {
                new { Label = "INSTITUTIONAL", Color = InstitutionalColor },
                new { Label = "3:30 CLOSE",    Color = CloseColor    },
                new { Label = "GLOBEX 6PM",    Color = GlobExColor   },
                new { Label = "MIDNIGHT",      Color = MidnightColor },
                new { Label = "EUROPE 4AM",    Color = EuropeColor   },
                new { Label = "RTH 9:30",      Color = RTHColor      },
            };
            using (var fmt = new SharpDX.DirectWrite.TextFormat(
                NinjaTrader.Core.Globals.DirectWriteFactory, "Arial",
                SharpDX.DirectWrite.FontWeight.Bold,
                SharpDX.DirectWrite.FontStyle.Normal, 12f))
            using (var textBrush = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(15, 15, 15, 255)))
            using (var borderBrush = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(0, 0, 0, 200)))
            {
                fmt.TextAlignment = SharpDX.DirectWrite.TextAlignment.Center;
                fmt.ParagraphAlignment = SharpDX.DirectWrite.ParagraphAlignment.Center;
                foreach (var it in items)
                {
                    float textW;
                    using (var layout = new SharpDX.DirectWrite.TextLayout(
                        NinjaTrader.Core.Globals.DirectWriteFactory, it.Label, fmt, 400, chipH))
                    { textW = layout.Metrics.Width; }
                    float chipW = textW + padX * 2;
                    var chipRect = new SharpDX.RectangleF(x, yTop, chipW, chipH);
                    using (var fillBrush = new SharpDX.Direct2D1.SolidColorBrush(rt, WpfToDx(it.Color, 235)))
                    {
                        rt.FillRectangle(chipRect, fillBrush);
                    }
                    rt.DrawRectangle(chipRect, borderBrush, 1f);
                    rt.DrawText(it.Label, fmt, chipRect, textBrush);
                    x += chipW + gap;
                }
            }
        }

        private static SharpDX.Color WpfToDx(Brush b, byte alpha)
        {
            var scb = b as SolidColorBrush;
            if (scb == null) return new SharpDX.Color((byte)200, (byte)200, (byte)200, alpha);
            var c = scb.Color;
            return new SharpDX.Color(c.R, c.G, c.B, alpha);
        }

        private void DisposeSharpDX()
        {
            if (dxBgBrush != null) { dxBgBrush.Dispose(); dxBgBrush = null; }
            if (dxTextBrush != null) { dxTextBrush.Dispose(); dxTextBrush = null; }
            if (dxBorderBrush != null) { dxBorderBrush.Dispose(); dxBorderBrush = null; }
            if (dxTitleTextBrush != null) { dxTitleTextBrush.Dispose(); dxTitleTextBrush = null; }
            if (dxTealBrush != null) { dxTealBrush.Dispose(); dxTealBrush = null; }
            if (dxAmberBrush != null) { dxAmberBrush.Dispose(); dxAmberBrush = null; }
            if (dxDimGoldBrush != null) { dxDimGoldBrush.Dispose(); dxDimGoldBrush = null; }
            if (dxRedBrush != null) { dxRedBrush.Dispose(); dxRedBrush = null; }
            if (dxGreenBrush != null) { dxGreenBrush.Dispose(); dxGreenBrush = null; }
            if (dxSlateBrush != null) { dxSlateBrush.Dispose(); dxSlateBrush = null; }
            if (dxTextFormat != null) { dxTextFormat.Dispose(); dxTextFormat = null; }
            if (dxTitleFormat != null) { dxTitleFormat.Dispose(); dxTitleFormat = null; }
            cachedTarget = null;
        }

        private void EnsureBrushes(SharpDX.Direct2D1.RenderTarget rt)
        {
            dxBgBrush         = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(0, 0, 0, 255));
            dxTextBrush       = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(241, 236, 216, 255));
            dxBorderBrush     = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(26, 163, 154, 255));
            dxTitleTextBrush  = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(0, 0, 0, 255));
            dxTealBrush       = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(26, 163, 154, 255));
            dxAmberBrush      = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(232, 154, 31, 255));
            dxDimGoldBrush    = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(138, 115, 40, 255));
            dxRedBrush        = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(200, 40, 40, 255));
            dxGreenBrush      = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(0, 160, 80, 255));
            dxSlateBrush      = new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(107, 114, 128, 255));
            dxTextFormat      = new SharpDX.DirectWrite.TextFormat(
                NinjaTrader.Core.Globals.DirectWriteFactory, "Consolas", 12);
            dxTitleFormat     = new SharpDX.DirectWrite.TextFormat(
                NinjaTrader.Core.Globals.DirectWriteFactory, "Arial",
                SharpDX.DirectWrite.FontWeight.Bold, SharpDX.DirectWrite.FontStyle.Normal, 11);
            dxTitleFormat.TextAlignment       = SharpDX.DirectWrite.TextAlignment.Center;
            dxTitleFormat.ParagraphAlignment  = SharpDX.DirectWrite.ParagraphAlignment.Center;
        }

        // =================================================================
        // BOX DRAWING
        // =================================================================

        private DateTime ComputeBoxFadeMidnight(CandleBox box)
        {
            DateTime boxDate = box.StartTime.Date;
            DateTime tradingDay = (box.StartTime.Hour >= 18) ? boxDate.AddDays(1) : boxDate;
            int extraDays = (box.Name != null && box.Name.StartsWith("Close ")) ? 2 : 1;
            return AddTradingDays(tradingDay, extraDays);
        }

        private static DateTime AddTradingDays(DateTime start, int days)
        {
            DateTime d = start;
            int added = 0;
            while (added < days)
            {
                d = d.AddDays(1);
                if (d.DayOfWeek != DayOfWeek.Saturday && d.DayOfWeek != DayOfWeek.Sunday) added++;
            }
            return d;
        }

        private DateTime ComputeBoxRemoveMidnight(CandleBox box) => ComputeBoxFadeMidnight(box).AddDays(1);

        // True if `box` is the latest of its name across currentDay AND every
        // entry in dayHistory. Used by DrawBoxLines so the most recent
        // GlobEx / Europe / RTH 9:30 / Close 3:30 stays shaded until the next
        // day's equivalent forms (e.g. yesterday's 3:30 close — the
        // institutional reference — remains shaded into today until today's
        // 3:30 captures). Close 1:30 is exempted in DrawBoxLines: it only
        // shades on its own trading day.
        private bool IsNewestOfKind(CandleBox box)
        {
            if (box == null || string.IsNullOrEmpty(box.Name)) return false;
            DateTime myStart = box.StartTime;
            string  name    = box.Name;
            if (currentDay != null)
            {
                var cdArr = new CandleBox[] {
                    currentDay.Close330, currentDay.GlobEx6PM, currentDay.Midnight,
                    currentDay.Europe4AM, currentDay.RTH930, currentDay.Close130
                };
                foreach (var b in cdArr)
                    if (b != null && b != box && b.Name == name && b.StartTime > myStart)
                        return false;
            }
            if (dayHistory != null)
            {
                foreach (var d in dayHistory)
                {
                    if (d == null) continue;
                    var dArr = new CandleBox[] {
                        d.Close330, d.GlobEx6PM, d.Midnight,
                        d.Europe4AM, d.RTH930, d.Close130
                    };
                    foreach (var b in dArr)
                        if (b != null && b != box && b.Name == name && b.StartTime > myStart)
                            return false;
                }
            }
            return true;
        }

        private DateTime GetBoxAgingNow()
        {
            if (idx1Min >= 0 && BarsArray != null && idx1Min < BarsArray.Length
                && BarsArray[idx1Min] != null && CurrentBars[idx1Min] >= 0)
                return Times[idx1Min][0];
            return Time[0];
        }

        private void DrawBoxLines(CandleBox box)
        {
            if (box == null) return;
            if (DetailLevel == CockpitDetailLevel.Signal && box != institutionalBox) return;

            DateTime tradingDay = (box.StartTime.Hour >= 18) ? box.StartTime.Date.AddDays(1) : box.StartTime.Date;
            string dateKey = tradingDay.ToString("yyyyMMdd");
            string tagRect = $"Box_{box.Name}_{dateKey}_Rect";
            string tagTop  = $"Box_{box.Name}_{dateKey}_Top";
            string tagBot  = $"Box_{box.Name}_{dateKey}_Bot";
            string tagDTop = $"Box_{box.Name}_{dateKey}_DashTop";
            string tagDBot = $"Box_{box.Name}_{dateKey}_DashBot";

            DateTime now      = GetBoxAgingNow();
            DateTime fadeAt   = ComputeBoxFadeMidnight(box);
            DateTime removeAt = ComputeBoxRemoveMidnight(box);

            // V2_6 user-facing rule (apr-29):
            //  - Close 1:30 is the only master candle that shades for its own
            //    trading day only. Yesterday's 1:30 collapses to dashed
            //    reference lines at session rollover (6 PM ET), regardless of
            //    whether today's 1:30 has captured yet. Rationale: 1:30 is a
            //    purely intraday retracement marker; it has no carry-over
            //    role into the next session.
            //  - All other master candles (GlobEx, Midnight, Europe, RTH 9:30,
            //    Close 3:30) keep the "newest of kind" rule: yesterday's stays
            //    shaded until today's equivalent captures. This is correct for
            //    the 3:30 close especially — it's the institutional reference
            //    candle that anchors the next day's bias.
            bool isClose130 = box.Name == "Close 1:30";
            bool keepShaded;
            if (isClose130)
            {
                DateTime boxTradingDay = (box.StartTime.Hour >= 18) ? box.StartTime.Date.AddDays(1) : box.StartTime.Date;
                keepShaded = currentDay != null && boxTradingDay == currentDay.Date;
            }
            else
            {
                keepShaded = IsNewestOfKind(box);
            }
            if (!keepShaded)
            {
                fadeAt = box.StartTime;
            }

            if (now >= removeAt)
            {
                RemoveDrawObject(tagRect);
                RemoveDrawObject(tagTop);
                RemoveDrawObject(tagBot);
                RemoveDrawObject(tagDTop);
                RemoveDrawObject(tagDBot);
                return;
            }

            int primaryCur = CurrentBars[0];
            int barIdx = Bars.GetBar(box.StartTime.AddMinutes(1));
            int barsAgo;
            if (barIdx < 0)
            {
                // box.StartTime is older than loaded primary history (common on
                // 1-min charts viewing yesterday's 30-min candles). Extend the
                // line back to the chart's earliest loaded bar so it spans the
                // visible chart all the way to the current candle.
                barsAgo = primaryCur;
            }
            else
            {
                barsAgo = Math.Max(0, Math.Min(primaryCur, primaryCur - barIdx));
            }

            bool primaryIs1Min = (idx1Min == 0);

            if (now >= fadeAt)
            {
                RemoveDrawObject(tagRect);
                RemoveDrawObject(tagTop);
                RemoveDrawObject(tagBot);
                if (!sessionDrawTags.Contains(tagDTop)) sessionDrawTags.Add(tagDTop);
                if (!sessionDrawTags.Contains(tagDBot)) sessionDrawTags.Add(tagDBot);
                Draw.Line(this, tagDTop, false, barsAgo, box.High, -1, box.High, box.BoxColor, DashStyleHelper.Dash, 1);
                Draw.Line(this, tagDBot, false, barsAgo, box.Low,  -1, box.Low,  box.BoxColor, DashStyleHelper.Dash, 1);
                if (primaryIs1Min) AddBoxLineLabels(box, dateKey, isFade: true, lineStartBarsAgo: barsAgo);
                return;
            }

            if (!sessionDrawTags.Contains(tagTop)) sessionDrawTags.Add(tagTop);
            if (!sessionDrawTags.Contains(tagBot)) sessionDrawTags.Add(tagBot);
            RemoveDrawObject(tagDTop);
            RemoveDrawObject(tagDBot);

            if (primaryIs1Min)
                RemoveDrawObject(tagRect);
            else
            {
                if (!sessionDrawTags.Contains(tagRect)) sessionDrawTags.Add(tagRect);
                Draw.Rectangle(this, tagRect, false, barsAgo, box.High, -1, box.Low, Brushes.Transparent, box.BoxColor, 25);
            }
            Draw.Line(this, tagTop, false, barsAgo, box.High, -1, box.High, box.BoxColor, DashStyleHelper.Solid, 2);
            Draw.Line(this, tagBot, false, barsAgo, box.Low,  -1, box.Low,  box.BoxColor, DashStyleHelper.Solid, 2);

            if (primaryIs1Min) AddBoxLineLabels(box, dateKey, isFade: false, lineStartBarsAgo: barsAgo);
        }

        // 1-min primary only: draw the master-candle name above each H/L line
        // in CHART COORDINATES so the label moves with the line as the user
        // pans / zooms / new bars print.  KeyCandleLabelSide picks where on
        // the line the label anchors:
        //   Left   = start of line (box's first bar)
        //   Center = midpoint between line start and current bar
        //   Right  = current bar (rightmost visible position)
        private void AddBoxLineLabels(CandleBox box, string dateKey, bool isFade, int lineStartBarsAgo)
        {
            if (box == null || sessionDrawTags == null) return;
            string baseName = box.Name;
            string highTag = $"BoxLbl_{baseName}_{dateKey}_H";
            string lowTag  = $"BoxLbl_{baseName}_{dateKey}_L";
            sessionDrawTags.Add(highTag);
            sessionDrawTags.Add(lowTag);

            int labelBarsAgo;
            switch (KeyCandleLabelSide)
            {
                case CockpitLabelPosition.Left:
                    labelBarsAgo = Math.Max(0, lineStartBarsAgo);
                    break;
                case CockpitLabelPosition.Center:
                    labelBarsAgo = Math.Max(0, lineStartBarsAgo / 2);
                    break;
                default: // Right
                    labelBarsAgo = 0;
                    break;
            }

            var font = new Gui.Tools.SimpleFont("Consolas", 10);
            // High label sits ABOVE the high line (negative pixel offset = up).
            Draw.Text(this, highTag, false, $"{baseName} H  {box.High:F2}",
                labelBarsAgo, box.High, -10,
                box.BoxColor, font, TextAlignment.Center,
                Brushes.Transparent, Brushes.Black, 70);
            // Low label sits ABOVE the low line as well (per user spec
            // "above the line" applies to both H and L).
            Draw.Text(this, lowTag, false, $"{baseName} L  {box.Low:F2}",
                labelBarsAgo, box.Low, -10,
                box.BoxColor, font, TextAlignment.Center,
                Brushes.Transparent, Brushes.Black, 70);
        }

        private void DrawInstitutionalBox(CandleBox box)
        {
            if (box == null) return;
            if (!string.IsNullOrEmpty(prevInstitutionalTag))
            {
                RemoveDrawObject(prevInstitutionalTag);
                RemoveDrawObject(prevInstitutionalTag + "_lbl");
                RemoveDrawObject(prevInstitutionalTag + "_top");
                RemoveDrawObject(prevInstitutionalTag + "_bot");
            }
            string tag = "InstitutionalBox";
            int primaryCur = CurrentBars[0];
            int barIdx = Bars.GetBar(box.StartTime.AddMinutes(1));
            int startBarsAgo = Math.Max(0, Math.Min(primaryCur, primaryCur - barIdx));
            if (barIdx < 0) startBarsAgo = 0;
            Draw.Rectangle(this, tag, false, startBarsAgo, box.High, -1, box.Low,
                Brushes.Transparent, InstitutionalColor, 25);
            Draw.Line(this, tag + "_top", false, startBarsAgo, box.High, -1, box.High,
                InstitutionalColor, DashStyleHelper.Solid, 2);
            Draw.Line(this, tag + "_bot", false, startBarsAgo, box.Low, -1, box.Low,
                InstitutionalColor, DashStyleHelper.Solid, 2);

            int lblBarsAgo;
            double lblY;
            int lblYOffset;
            TextAlignment lblAlign;
            switch (InstitutionalCorner)
            {
                case CockpitCornerPosition.TopLeft:
                    lblBarsAgo = startBarsAgo; lblY = box.High; lblYOffset = -8; lblAlign = TextAlignment.Left; break;
                case CockpitCornerPosition.BottomLeft:
                    lblBarsAgo = startBarsAgo; lblY = box.Low;  lblYOffset =  8; lblAlign = TextAlignment.Left; break;
                case CockpitCornerPosition.BottomRight:
                    lblBarsAgo = primaryCur >= 1 ? 1 : 0; lblY = box.Low; lblYOffset = 8; lblAlign = TextAlignment.Right; break;
                default:
                    lblBarsAgo = primaryCur >= 1 ? 1 : 0; lblY = box.High; lblYOffset = -8; lblAlign = TextAlignment.Right; break;
            }
            Draw.Text(this, tag + "_lbl", false, $"INSTITUTIONAL: {box.Name}",
                lblBarsAgo, lblY, lblYOffset,
                InstitutionalColor, new Gui.Tools.SimpleFont("Arial", 10),
                lblAlign, Brushes.Transparent, Brushes.Transparent, 0);
            prevInstitutionalTag = tag;
        }

        private void DrawMidnightLines(CandleBox mid)
        {
            if (mid == null) return;
            string tag = $"Mid_{mid.StartTime:yyyyMMdd}";
            DrawLabeledLine(tag + "_H", mid.High, "MID H", MidnightColor, DashStyleHelper.Dash, 1);
            DrawLabeledLine(tag + "_L", mid.Low,  "MID L", MidnightColor, DashStyleHelper.Dash, 1);
        }

        private void DrawMeasuredMoves(CandleBox inst)
        {
            if (inst == null) return;
            double r = inst.Range;
            DrawLabeledLine("MM_P1", inst.High + r, "MM+1", InstitutionalColor, DashStyleHelper.Dash, 1);
            DrawLabeledLine("MM_P2", inst.High + 2 * r, "MM+2", InstitutionalColor, DashStyleHelper.Dash, 1);
            DrawLabeledLine("MM_M1", inst.Low - r, "MM-1", InstitutionalColor, DashStyleHelper.Dash, 1);
            DrawLabeledLine("MM_M2", inst.Low - 2 * r, "MM-2", InstitutionalColor, DashStyleHelper.Dash, 1);
        }

        private void DrawPivotLines()
        {
            if (!pivotsCalculated) return;
            DrawLabeledLine("Piv_PP", pivotPP, "PP", Brushes.White, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_R1", pivotR1, "R1", Brushes.IndianRed, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_R2", pivotR2, "R2", Brushes.IndianRed, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_R3", pivotR3, "R3", Brushes.Red, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_R4", pivotR4, "R4", Brushes.DarkRed, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_S1", pivotS1, "S1", Brushes.MediumSeaGreen, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_S2", pivotS2, "S2", Brushes.MediumSeaGreen, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_S3", pivotS3, "S3", Brushes.Green, DashStyleHelper.Dot, 1);
            DrawLabeledLine("Piv_S4", pivotS4, "S4", Brushes.DarkGreen, DashStyleHelper.Dot, 1);
        }

        private void DrawLabeledLine(string tag, double price, string label, Brush color, DashStyleHelper dash, int width)
        {
            if (sessionDrawTags == null || priceLabels == null) return;
            if (!sessionDrawTags.Contains(tag)) sessionDrawTags.Add(tag);
            priceLabels[tag] = new PriceLabel
            {
                Price = price, Text = $"{label}  {price:F2}", Color = color,
                Dash = dash, LineWidth = width
            };
        }

        // =================================================================
        // UTILITIES
        // =================================================================

        private CandleBox MakeBox(string name, double high, double low, double open, double close, double vol,
                                    DateTime start, DateTime end, Brush color)
        {
            return new CandleBox
            {
                Name = name, High = high, Low = low, Open = open, Close = close, Volume = vol,
                StartTime = start, EndTime = end, IsComplete = true, BoxColor = color
            };
        }

        private void EnsureCurrentDay(DateTime barTime)
        {
            if (currentDay == null) currentDay = new DayBoxes { Date = barTime.Date };
        }

        private static string StripStamp(string name)
        {
            if (string.IsNullOrEmpty(name)) return name;
            int at = name.IndexOf('@');
            return at > 0 ? name.Substring(0, at) : name;
        }

        private static string SafeTag(string text)
        {
            if (string.IsNullOrEmpty(text)) return "blank";
            var sb = new StringBuilder(text.Length);
            foreach (char c in text)
                sb.Append(char.IsLetterOrDigit(c) ? c : '_');
            return sb.ToString();
        }

        private void Log(string message)
        {
            string entry = $"{DateTime.Now:HH:mm:ss} | {message}";
            if (logEntries != null)
            {
                logEntries.Add(entry);
                while (logEntries.Count > 5000) logEntries.RemoveAt(0);
            }
            if (State != State.Historical) Print(entry);
        }

        private void UpdateCoachMessage()
        {
            // Verdict line (architect spec): "X candidates today, Y unique levels, Z patterns_B armed"
            currentCoachMessage = $"V2_6 L1 {ComputeDirectionFilter()} watch: {candidatesEmittedToday} candidates today, {uniqueLevelsTouchedToday.Count} unique levels, {patternBArmedToday} Pattern B armed.";
        }

        // =================================================================
        // RESET
        // =================================================================

        private void ResetForNewDay()
        {
            // L1 daily reset.  L2/L3 own their own counters via state.json.
            v2OpenRangeLocked = false;
            v2OpenRangeHigh = 0;
            v2OpenRangeLow = 0;
            v2PriorRolling30High = 0;
            v2PriorRolling30Low = 0;
            v2PriorRolling30BarTime = DateTime.MinValue;
            rth1MinComplete = false;
            rth1MinHigh = rth1MinLow = 0;
            rth1MinVolume = 0;
            currentDayType = DayType.Unknown;
            currentBias = Bias.Wait;
            lastDirectionFilterEmitted = AMDirectionFilter.Unknown;
            institutionalBox = null;
            institutionalName = "Determining...";

            levelWatchStates.Clear();
            candidatesEmittedToday = 0;
            patternBArmedToday = 0;
            uniqueLevelsTouchedToday.Clear();
            highValueLevelsTouchedToday.Clear();
            preTouchCandidateTags.Clear();
            candidateSeqByKey.Clear();   // architect §3.3 — seq counters reset per session
            markerDrawCounts.Clear();  // first-N-30min-bars marker filter — reset each session
            markerDrawnInSlot.Clear();

            // Informational lockout state — purely diagnostic, never gates emission.
            lockoutActive = false;
            lockoutReason = "";
            losingTradesToday = 0;
            realizedPnlDollarsToday = 0;
            lastStopTime = DateTime.MinValue;

            if (priceLabels != null) priceLabels.Clear();
            if (ShowOnlyCurrentSession && sessionDrawTags != null)
            {
                foreach (string tag in sessionDrawTags) RemoveDrawObject(tag);
                sessionDrawTags.Clear();
            }
            RemoveDrawObject("RTH1Min_H");
            RemoveDrawObject("RTH1Min_L");
            RemoveDrawObject("VWAP_Line");
            RemoveDrawObject("InstitutionalBox");
            RemoveDrawObject("InstitutionalBox_lbl");

            Log("=== V2_6 NEW SESSION ===");
        }
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private AMTradeCockpitV2_6[] cacheAMTradeCockpitV2_6;
		public AMTradeCockpitV2_6 AMTradeCockpitV2_6(CockpitDetailLevel detailLevel, bool showOnlyCurrentSession, CockpitLabelPosition labelPosition, CockpitLabelPosition keyCandleLabelSide, CockpitCornerPosition institutionalCorner, bool showCandidateMarkers, bool showPreTouchCandidateLevels, int daysOfHistory, int maxLookbackDaysForLevels, bool enablePatternA, bool enablePatternB, bool emitVwapAsPermissionLevel, double newsVolumeMultiplierThreshold, bool show50SMA, bool show200SMA, int legendXOffset, int legendYOffset, int prePlacePanelX, int prePlacePanelY, bool enableJsonlLog, string jsonlLogFolder, int heartbeatSeconds, bool enableStatePersistence)
		{
			return AMTradeCockpitV2_6(Input, detailLevel, showOnlyCurrentSession, labelPosition, keyCandleLabelSide, institutionalCorner, showCandidateMarkers, showPreTouchCandidateLevels, daysOfHistory, maxLookbackDaysForLevels, enablePatternA, enablePatternB, emitVwapAsPermissionLevel, newsVolumeMultiplierThreshold, show50SMA, show200SMA, legendXOffset, legendYOffset, prePlacePanelX, prePlacePanelY, enableJsonlLog, jsonlLogFolder, heartbeatSeconds, enableStatePersistence);
		}

		public AMTradeCockpitV2_6 AMTradeCockpitV2_6(ISeries<double> input, CockpitDetailLevel detailLevel, bool showOnlyCurrentSession, CockpitLabelPosition labelPosition, CockpitLabelPosition keyCandleLabelSide, CockpitCornerPosition institutionalCorner, bool showCandidateMarkers, bool showPreTouchCandidateLevels, int daysOfHistory, int maxLookbackDaysForLevels, bool enablePatternA, bool enablePatternB, bool emitVwapAsPermissionLevel, double newsVolumeMultiplierThreshold, bool show50SMA, bool show200SMA, int legendXOffset, int legendYOffset, int prePlacePanelX, int prePlacePanelY, bool enableJsonlLog, string jsonlLogFolder, int heartbeatSeconds, bool enableStatePersistence)
		{
			if (cacheAMTradeCockpitV2_6 != null)
				for (int idx = 0; idx < cacheAMTradeCockpitV2_6.Length; idx++)
					if (cacheAMTradeCockpitV2_6[idx] != null && cacheAMTradeCockpitV2_6[idx].DetailLevel == detailLevel && cacheAMTradeCockpitV2_6[idx].ShowOnlyCurrentSession == showOnlyCurrentSession && cacheAMTradeCockpitV2_6[idx].LabelPosition == labelPosition && cacheAMTradeCockpitV2_6[idx].KeyCandleLabelSide == keyCandleLabelSide && cacheAMTradeCockpitV2_6[idx].InstitutionalCorner == institutionalCorner && cacheAMTradeCockpitV2_6[idx].ShowCandidateMarkers == showCandidateMarkers && cacheAMTradeCockpitV2_6[idx].ShowPreTouchCandidateLevels == showPreTouchCandidateLevels && cacheAMTradeCockpitV2_6[idx].DaysOfHistory == daysOfHistory && cacheAMTradeCockpitV2_6[idx].MaxLookbackDaysForLevels == maxLookbackDaysForLevels && cacheAMTradeCockpitV2_6[idx].EnablePatternA == enablePatternA && cacheAMTradeCockpitV2_6[idx].EnablePatternB == enablePatternB && cacheAMTradeCockpitV2_6[idx].EmitVwapAsPermissionLevel == emitVwapAsPermissionLevel && cacheAMTradeCockpitV2_6[idx].NewsVolumeMultiplierThreshold == newsVolumeMultiplierThreshold && cacheAMTradeCockpitV2_6[idx].Show50SMA == show50SMA && cacheAMTradeCockpitV2_6[idx].Show200SMA == show200SMA && cacheAMTradeCockpitV2_6[idx].LegendXOffset == legendXOffset && cacheAMTradeCockpitV2_6[idx].LegendYOffset == legendYOffset && cacheAMTradeCockpitV2_6[idx].PrePlacePanelX == prePlacePanelX && cacheAMTradeCockpitV2_6[idx].PrePlacePanelY == prePlacePanelY && cacheAMTradeCockpitV2_6[idx].EnableJsonlLog == enableJsonlLog && cacheAMTradeCockpitV2_6[idx].JsonlLogFolder == jsonlLogFolder && cacheAMTradeCockpitV2_6[idx].HeartbeatSeconds == heartbeatSeconds && cacheAMTradeCockpitV2_6[idx].EnableStatePersistence == enableStatePersistence && cacheAMTradeCockpitV2_6[idx].EqualsInput(input))
						return cacheAMTradeCockpitV2_6[idx];
			return CacheIndicator<AMTradeCockpitV2_6>(new AMTradeCockpitV2_6(){ DetailLevel = detailLevel, ShowOnlyCurrentSession = showOnlyCurrentSession, LabelPosition = labelPosition, KeyCandleLabelSide = keyCandleLabelSide, InstitutionalCorner = institutionalCorner, ShowCandidateMarkers = showCandidateMarkers, ShowPreTouchCandidateLevels = showPreTouchCandidateLevels, DaysOfHistory = daysOfHistory, MaxLookbackDaysForLevels = maxLookbackDaysForLevels, EnablePatternA = enablePatternA, EnablePatternB = enablePatternB, EmitVwapAsPermissionLevel = emitVwapAsPermissionLevel, NewsVolumeMultiplierThreshold = newsVolumeMultiplierThreshold, Show50SMA = show50SMA, Show200SMA = show200SMA, LegendXOffset = legendXOffset, LegendYOffset = legendYOffset, PrePlacePanelX = prePlacePanelX, PrePlacePanelY = prePlacePanelY, EnableJsonlLog = enableJsonlLog, JsonlLogFolder = jsonlLogFolder, HeartbeatSeconds = heartbeatSeconds, EnableStatePersistence = enableStatePersistence }, input, ref cacheAMTradeCockpitV2_6);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.AMTradeCockpitV2_6 AMTradeCockpitV2_6(CockpitDetailLevel detailLevel, bool showOnlyCurrentSession, CockpitLabelPosition labelPosition, CockpitLabelPosition keyCandleLabelSide, CockpitCornerPosition institutionalCorner, bool showCandidateMarkers, bool showPreTouchCandidateLevels, int daysOfHistory, int maxLookbackDaysForLevels, bool enablePatternA, bool enablePatternB, bool emitVwapAsPermissionLevel, double newsVolumeMultiplierThreshold, bool show50SMA, bool show200SMA, int legendXOffset, int legendYOffset, int prePlacePanelX, int prePlacePanelY, bool enableJsonlLog, string jsonlLogFolder, int heartbeatSeconds, bool enableStatePersistence)
		{
			return indicator.AMTradeCockpitV2_6(Input, detailLevel, showOnlyCurrentSession, labelPosition, keyCandleLabelSide, institutionalCorner, showCandidateMarkers, showPreTouchCandidateLevels, daysOfHistory, maxLookbackDaysForLevels, enablePatternA, enablePatternB, emitVwapAsPermissionLevel, newsVolumeMultiplierThreshold, show50SMA, show200SMA, legendXOffset, legendYOffset, prePlacePanelX, prePlacePanelY, enableJsonlLog, jsonlLogFolder, heartbeatSeconds, enableStatePersistence);
		}

		public Indicators.AMTradeCockpitV2_6 AMTradeCockpitV2_6(ISeries<double> input , CockpitDetailLevel detailLevel, bool showOnlyCurrentSession, CockpitLabelPosition labelPosition, CockpitLabelPosition keyCandleLabelSide, CockpitCornerPosition institutionalCorner, bool showCandidateMarkers, bool showPreTouchCandidateLevels, int daysOfHistory, int maxLookbackDaysForLevels, bool enablePatternA, bool enablePatternB, bool emitVwapAsPermissionLevel, double newsVolumeMultiplierThreshold, bool show50SMA, bool show200SMA, int legendXOffset, int legendYOffset, int prePlacePanelX, int prePlacePanelY, bool enableJsonlLog, string jsonlLogFolder, int heartbeatSeconds, bool enableStatePersistence)
		{
			return indicator.AMTradeCockpitV2_6(input, detailLevel, showOnlyCurrentSession, labelPosition, keyCandleLabelSide, institutionalCorner, showCandidateMarkers, showPreTouchCandidateLevels, daysOfHistory, maxLookbackDaysForLevels, enablePatternA, enablePatternB, emitVwapAsPermissionLevel, newsVolumeMultiplierThreshold, show50SMA, show200SMA, legendXOffset, legendYOffset, prePlacePanelX, prePlacePanelY, enableJsonlLog, jsonlLogFolder, heartbeatSeconds, enableStatePersistence);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.AMTradeCockpitV2_6 AMTradeCockpitV2_6(CockpitDetailLevel detailLevel, bool showOnlyCurrentSession, CockpitLabelPosition labelPosition, CockpitLabelPosition keyCandleLabelSide, CockpitCornerPosition institutionalCorner, bool showCandidateMarkers, bool showPreTouchCandidateLevels, int daysOfHistory, int maxLookbackDaysForLevels, bool enablePatternA, bool enablePatternB, bool emitVwapAsPermissionLevel, double newsVolumeMultiplierThreshold, bool show50SMA, bool show200SMA, int legendXOffset, int legendYOffset, int prePlacePanelX, int prePlacePanelY, bool enableJsonlLog, string jsonlLogFolder, int heartbeatSeconds, bool enableStatePersistence)
		{
			return indicator.AMTradeCockpitV2_6(Input, detailLevel, showOnlyCurrentSession, labelPosition, keyCandleLabelSide, institutionalCorner, showCandidateMarkers, showPreTouchCandidateLevels, daysOfHistory, maxLookbackDaysForLevels, enablePatternA, enablePatternB, emitVwapAsPermissionLevel, newsVolumeMultiplierThreshold, show50SMA, show200SMA, legendXOffset, legendYOffset, prePlacePanelX, prePlacePanelY, enableJsonlLog, jsonlLogFolder, heartbeatSeconds, enableStatePersistence);
		}

		public Indicators.AMTradeCockpitV2_6 AMTradeCockpitV2_6(ISeries<double> input , CockpitDetailLevel detailLevel, bool showOnlyCurrentSession, CockpitLabelPosition labelPosition, CockpitLabelPosition keyCandleLabelSide, CockpitCornerPosition institutionalCorner, bool showCandidateMarkers, bool showPreTouchCandidateLevels, int daysOfHistory, int maxLookbackDaysForLevels, bool enablePatternA, bool enablePatternB, bool emitVwapAsPermissionLevel, double newsVolumeMultiplierThreshold, bool show50SMA, bool show200SMA, int legendXOffset, int legendYOffset, int prePlacePanelX, int prePlacePanelY, bool enableJsonlLog, string jsonlLogFolder, int heartbeatSeconds, bool enableStatePersistence)
		{
			return indicator.AMTradeCockpitV2_6(input, detailLevel, showOnlyCurrentSession, labelPosition, keyCandleLabelSide, institutionalCorner, showCandidateMarkers, showPreTouchCandidateLevels, daysOfHistory, maxLookbackDaysForLevels, enablePatternA, enablePatternB, emitVwapAsPermissionLevel, newsVolumeMultiplierThreshold, show50SMA, show200SMA, legendXOffset, legendYOffset, prePlacePanelX, prePlacePanelY, enableJsonlLog, jsonlLogFolder, heartbeatSeconds, enableStatePersistence);
		}
	}
}

#endregion
