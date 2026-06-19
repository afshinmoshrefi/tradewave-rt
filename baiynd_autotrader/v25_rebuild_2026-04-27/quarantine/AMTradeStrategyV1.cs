// =============================================================================
// AMTradeStrategyV1  —  L2 Decision + L3 Safety host for AMTradeCockpitV2_5
// =============================================================================
// Implements the V2_5 architecture spec (architecture_spec_v25.md, Sections 1-3,
// 5, 7-8, 12). Strategy hosts AMTradeCockpitV2_5 as L1 detection-only indicator;
// subscribes to L1's OnCandidate / OnBoxCapture / OnAbstain events; runs the
// V1 heuristic scorer + 12 toggleable safety gates; submits limit-only entries
// via Account.CreateOrder + SubmitOrderUnmanaged.
//
// Architectural invariants (from architect spec Section 1):
//   - Fail-open: every block emits an explicit `abstain` JSONL event with
//     gate_name + reason + recoverable_until_time. NO silent drops.
//   - Determinism: bar-time timestamps everywhere; no DateTime.Now in path.
//   - Limits-only entries (AM apr-9 line 94: "I never use market orders").
//   - One position per instrument (V1 simplification per spec §7.6).
//   - Paired exit events: every signal terminates in stop_hit / target_hit /
//     time_close / cancel.
//
// V1 deferrals (per spec §11):
//   - Fibonacci runner ladder + manual runner exit -> V1.1
//   - 50% midpoint convergence add -> V2 (deferred per improvement_roadmap C-20)
//   - HTTP ML scorer client lives behind UseHttpScorer parameter (default off)
// =============================================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Input;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public partial class AMTradeStrategyV1 : Strategy
    {
        // =====================================================================
        // INTERNAL TYPES (replicate the L2/L3 contract structs from spec §7-8)
        // =====================================================================

        /// <summary>
        /// Mirror of the L1 candidate event payload. The L1 refactor in V2_5 will
        /// expose <c>OnCandidate(CandidateEventArgs)</c>; until then this type
        /// shadows the schema and is populated either from the real event (when
        /// L1 ships) or from the V2_4-style OnTouch/OnSignal compatibility shim
        /// at the bottom of this file. Field names match architect spec §3.3.
        /// </summary>
        public class CandidateEvent
        {
            public string CandidateId;
            public string LevelName;
            public double LevelPrice;
            public bool IsPermissionLevel;
            public string Direction;       // "LONG" | "SHORT"
            public string PatternType;     // "A" | "B"
            public string LwsState;        // null for A; "Armed"|... for B
            public DateTime BarTime;
            public double BarOpen, BarHigh, BarLow, BarClose;
            public long BarVolume;
            public double StopDistanceSuggestionPts;
            public double FirstTargetPts;
            public RunnerTargetOptions RunnerTargets;
            public FeatureVector Features = new FeatureVector();
            public string SessionDate;
        }

        public class RunnerTargetOptions
        {
            public double LevelToLevelNextPts;
            public double Fib150PctPts;
            public double Fib200PctPts;
            public double Fib250PctPts;
        }

        /// <summary>
        /// Feature vector consumed by the heuristic scorer. Values may be NaN
        /// or sentinel; each field has an *_available flag where the spec
        /// requires it. Unavailable features get zero weight in the scorer
        /// (per architect spec §2.2 fail-open table).
        /// </summary>
        public class FeatureVector
        {
            public string DayTypeV2_3node = "Unknown";
            public string DayTypeV2_4node = "Unknown";
            public bool BodyOverlapAB, BodyOverlapBC, BodyOverlapCD;
            public bool LargeWickA, LargeWickB, LargeWickC, LargeWickD;

            public double Sma200SlopeDeltaPts = double.NaN;
            public bool   Sma200SlopeAvailable = false;
            public string Sma200SlopeSign = "Flat";
            public double Sma50_30SlopePts = double.NaN;
            public bool   Sma50_30SlopeAvailable = false;

            public double MocRatio = double.NaN;
            public string MocState = "Pending";
            public bool   MocObservedToday = false;

            public double VwapPrice = double.NaN;
            public string VwapSlope = "Flat";
            public double DistToVwapPts = double.NaN;
            public double DistToAnchVwapPts = double.NaN;

            public double DistToR3 = double.NaN;
            public double DistToR4 = double.NaN;
            public double DistToS3 = double.NaN;
            public double DistToS4 = double.NaN;

            public int    NumLevelsInCluster = 1;
            public bool   IsHighestVolumeInCluster = false;
            public int    ConfluenceCount = 0;

            public double BodyPct = double.NaN;
            public string CandleDirection = "Up";

            public bool RetraceSide = true;
            public bool RetraceSideAtOpen = false;
            public bool AlreadyTouchedToday = false;

            public int MinutesSinceRthOpen = 0;
            public int MinutesUntilRthClose = 0;
            public int HourEt = 0;
            public string DayOfWeek = "Monday";

            public double VolZScoreVsSession = 0;
            public double FirstMinVolumePctOfNormal = 1.0;

            public double Adr20dPts = double.NaN;
            public double EuropeWidthPts = double.NaN;

            public bool   NewsWickActiveToday = false;
            public double NewsWickDistancePts = double.NaN;
        }

        /// <summary>L2 scorer output (architect §7.2).</summary>
        public struct ScorerDecision
        {
            public double PWin;            // probability candidate becomes winning trade
            public double ExpectedR;       // expected R-multiple
            public string SizeBucket;      // "FULL" | "HALF" | "MIN" | "SKIP"
            public string TargetChoice;    // "100" | "150" | "200" | "250" | "level_to_level"
            public double Confidence;      // [0,1] feature-availability score
            public string AbstainReason;   // null = take; otherwise reason string
            public string ScorerMode;      // "Heuristic" | "MlHttp"
        }

        /// <summary>L3 gate result (architect §8.1).</summary>
        public struct GateResult
        {
            public bool      Allowed;
            public string    GateName;
            public string    Reason;
            public DateTime? RecoverableUntil;   // null = next session / manual
            public string    StateSnapshotJson;  // already-serialized small payload
        }

        /// <summary>Live-trade book entry. Single-position model in V1.</summary>
        private class ActiveSignal
        {
            public string SignalId;
            public string CandidateId;
            public string Direction;
            public double EntryPrice;
            public double StopPrice;
            public double TargetPrice;
            public int    SizeQty;
            public DateTime SignalTime;
            public string LevelName;
            public string PatternType;

            // Broker-managed orders (Unmanaged path).
            public Order EntryOrder;
            public Order StopOrder;
            public Order TargetOrder;

            public bool   Filled;
            public double FilledPrice;
            public DateTime FilledAt;

            public ScorerDecision Decision;
        }

        private enum InternalSignalState { None, Pending, Active, Closing }

        // =====================================================================
        // STATE (transient + persisted)
        // =====================================================================

        // Hosted indicator (L1).
        private AMTradeCockpitV2_5 cockpit;

        // Series indices.
        private int idx30Min = 1;
        private int idx1Min  = 0; // primary

        // Live signal book.
        private InternalSignalState signalState = InternalSignalState.None;
        private ActiveSignal currentSignal;

        // Persisted counters (state.json).
        private int    signalsToday;
        private int    fillsToday;
        private int    losingTradesToday;
        private int    winningTradesToday;
        private int    consecutiveStops;
        private double realizedPnlDollarsToday;
        private bool   lockoutActive;
        private string lockoutTrigger;
        private DateTime lockoutExpiresAt;
        private bool   cooldownActive;
        private DateTime lastStopTime = DateTime.MinValue;
        private DateTime cooldownExpiresAt;
        private bool   manualKillSwitchActive;
        private bool   haltDueToDivergence;

        // Connection / heartbeat.
        private DateTime lastBarUpdateTime = DateTime.MinValue;
        private DateTime lastHeartbeatEmit = DateTime.MinValue;
        private bool     dataFeedConnected = true;
        private bool     orderFeedConnected = true;

        // Per-bar candidate batch (multi-candidate ranking).
        private readonly List<CandidateEvent> currentBarCandidates = new List<CandidateEvent>();
        private DateTime currentBarBucketTime = DateTime.MinValue;

        // Logging paths.
        private string sessionDate;
        private string strategyEventsPath;
        private string strategyStatePath;
        private string instrumentRoot;

        // Holiday list (V1: hard-coded; V3 reads parquet per spec §8.6).
        private static readonly HashSet<DateTime> FullCloseHolidays2026 = new HashSet<DateTime>
        {
            new DateTime(2026, 1, 1),    // New Year's
            new DateTime(2026, 1, 19),   // MLK
            new DateTime(2026, 2, 16),   // Presidents Day
            new DateTime(2026, 4, 3),    // Good Friday
            new DateTime(2026, 5, 25),   // Memorial Day
            new DateTime(2026, 6, 19),   // Juneteenth
            new DateTime(2026, 7, 3),    // July 4 (observed)
            new DateTime(2026, 9, 7),    // Labor Day
            new DateTime(2026, 11, 26),  // Thanksgiving
            new DateTime(2026, 12, 25),  // Christmas
        };
        private static readonly HashSet<DateTime> EarlyCloseHolidays2026 = new HashSet<DateTime>
        {
            new DateTime(2026, 7, 2),    // July 3 eve early
            new DateTime(2026, 11, 27),  // Black Friday
            new DateTime(2026, 12, 24),  // Christmas Eve
        };

        // Account margin estimate per MES contract (V1: hard-coded; V2: query broker).
        private const double MarginPerMesContractDollars = 50.0;
        private const double MesPointValue = 5.0;     // $5/pt MES
        private const double MesTickSize = 0.25;

        // =====================================================================
        // PROPERTIES (NinjaScriptProperty — user-tunable per spec §4.6)
        // =====================================================================

        #region Properties — Logging
        [NinjaScriptProperty]
        [Display(Name = "JSONL log folder", Order = 1, GroupName = "01 Logging")]
        public string JsonlLogFolder { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Heartbeat seconds", Order = 2, GroupName = "01 Logging")]
        public int HeartbeatSeconds { get; set; }
        #endregion

        #region Properties — Scorer (L2)
        [NinjaScriptProperty]
        [Display(Name = "Use HTTP scorer (V2 ML)", Order = 1, GroupName = "02 Scorer")]
        public bool UseHttpScorer { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "HTTP scorer endpoint", Order = 2, GroupName = "02 Scorer")]
        public string HttpScorerEndpoint { get; set; }

        [NinjaScriptProperty]
        [Range(100, 10000)]
        [Display(Name = "HTTP scorer timeout ms", Order = 3, GroupName = "02 Scorer")]
        public int HttpScorerTimeoutMs { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Min p_win", Order = 4, GroupName = "02 Scorer")]
        public double MinWinProbability { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 5.0)]
        [Display(Name = "Min expected R", Order = 5, GroupName = "02 Scorer")]
        public double MinExpectedR { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Min confidence", Order = 6, GroupName = "02 Scorer")]
        public double MinConfidence { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 5.0)]
        [Display(Name = "Min expected value (p*R)", Order = 7, GroupName = "02 Scorer")]
        public double MinExpectedValue { get; set; }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Max candidates per bar to take", Order = 8, GroupName = "02 Scorer")]
        public int MaxCandidatesPerBarToTake { get; set; }
        #endregion

        #region Properties — Order routing
        [NinjaScriptProperty]
        [Display(Name = "Account name", Order = 1, GroupName = "03 Orders")]
        public string AccountName { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "ATM template (Normal 2 MES)", Order = 2, GroupName = "03 Orders")]
        public string AtmTemplateNormal { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "ATM template (Wide 1 MES)", Order = 3, GroupName = "03 Orders")]
        public string AtmTemplateWide { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow live order submit", Order = 4, GroupName = "03 Orders")]
        public bool AllowLiveOrderSubmit { get; set; }
        #endregion

        #region Properties — L3 Safety Gates (each independently toggleable per spec §8)

        // Gate 1: RTH window
        [NinjaScriptProperty]
        [Display(Name = "Enable RTH window gate", Order = 1, GroupName = "04 L3 Safety Gates")]
        public bool EnableRTHWindowGate { get; set; }
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "RTH open hour ET", Order = 2, GroupName = "04 L3 Safety Gates")]
        public int RthOpenHourEt { get; set; }
        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "RTH open minute ET", Order = 3, GroupName = "04 L3 Safety Gates")]
        public int RthOpenMinuteEt { get; set; }
        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "RTH close hour ET", Order = 4, GroupName = "04 L3 Safety Gates")]
        public int RthCloseHourEt { get; set; }
        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "RTH close minute ET", Order = 5, GroupName = "04 L3 Safety Gates")]
        public int RthCloseMinuteEt { get; set; }
        [NinjaScriptProperty]
        [Range(0, 240)]
        [Display(Name = "Entry cutoff minutes before close", Order = 6, GroupName = "04 L3 Safety Gates")]
        public int EntryCutoffMinutesBeforeClose { get; set; }

        // Gate 2: daily $ loss kill
        [NinjaScriptProperty]
        [Display(Name = "Enable daily $ loss kill", Order = 7, GroupName = "04 L3 Safety Gates")]
        public bool EnableDailyLossKill { get; set; }
        [NinjaScriptProperty]
        [Range(50, 100000)]
        [Display(Name = "Max daily loss $", Order = 8, GroupName = "04 L3 Safety Gates")]
        public double MaxDailyLossDollars { get; set; }

        // Gate 3: daily losing trades count
        [NinjaScriptProperty]
        [Display(Name = "Enable daily losing trades kill", Order = 9, GroupName = "04 L3 Safety Gates")]
        public bool EnableDailyLosingTradesKill { get; set; }
        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Max daily losing trades", Order = 10, GroupName = "04 L3 Safety Gates")]
        public int MaxDailyLosingTrades { get; set; }

        // Gate 4: cooldown after stop
        [NinjaScriptProperty]
        [Display(Name = "Enable cooldown after stop", Order = 11, GroupName = "04 L3 Safety Gates")]
        public bool EnableCooldownAfterStop { get; set; }
        [NinjaScriptProperty]
        [Range(0, 240)]
        [Display(Name = "Cooldown minutes", Order = 12, GroupName = "04 L3 Safety Gates")]
        public int CooldownMinutes { get; set; }

        // Gate 5: max signals per day
        [NinjaScriptProperty]
        [Display(Name = "Enable max signals per day", Order = 13, GroupName = "04 L3 Safety Gates")]
        public bool EnableMaxSignalsPerDay { get; set; }
        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Max signals per day", Order = 14, GroupName = "04 L3 Safety Gates")]
        public int MaxSignalsPerDay { get; set; }

        // Gate 6: position state guard
        [NinjaScriptProperty]
        [Display(Name = "Enable position state guard", Order = 15, GroupName = "04 L3 Safety Gates")]
        public bool EnablePositionStateGuard { get; set; }

        // Gate 7: margin guard
        [NinjaScriptProperty]
        [Display(Name = "Enable margin guard", Order = 16, GroupName = "04 L3 Safety Gates")]
        public bool EnableMarginGuard { get; set; }

        // Gate 8: holiday gate
        [NinjaScriptProperty]
        [Display(Name = "Enable holiday gate", Order = 17, GroupName = "04 L3 Safety Gates")]
        public bool EnableHolidayGate { get; set; }

        // Gate 9: manual kill switch
        [NinjaScriptProperty]
        [Display(Name = "Enable manual kill switch UI", Order = 18, GroupName = "04 L3 Safety Gates")]
        public bool EnableManualKillSwitch { get; set; }

        // Gate 10: connection guard
        [NinjaScriptProperty]
        [Display(Name = "Enable connection guard", Order = 19, GroupName = "04 L3 Safety Gates")]
        public bool EnableConnectionGuard { get; set; }
        [NinjaScriptProperty]
        [Range(10, 600)]
        [Display(Name = "Connection stale seconds", Order = 20, GroupName = "04 L3 Safety Gates")]
        public int ConnectionStaleSeconds { get; set; }

        // Gate 11: heartbeat self-check
        [NinjaScriptProperty]
        [Display(Name = "Enable heartbeat self-check", Order = 21, GroupName = "04 L3 Safety Gates")]
        public bool EnableHeartbeatSelfCheck { get; set; }
        [NinjaScriptProperty]
        [Range(30, 600)]
        [Display(Name = "Heartbeat stale seconds", Order = 22, GroupName = "04 L3 Safety Gates")]
        public int HeartbeatStaleSeconds { get; set; }

        // Gate 12: daily loss percent (alternative to gate 2)
        [NinjaScriptProperty]
        [Display(Name = "Enable daily loss % kill", Order = 23, GroupName = "04 L3 Safety Gates")]
        public bool EnableDailyLossPercent { get; set; }
        [NinjaScriptProperty]
        [Range(0.1, 50.0)]
        [Display(Name = "Max daily loss percent", Order = 24, GroupName = "04 L3 Safety Gates")]
        public double MaxDailyLossPercent { get; set; }
        #endregion

        #region Properties — V2_5 indicator passthrough (kept for hosted instance)
        [NinjaScriptProperty]
        [Display(Name = "Days of history (cockpit)", Order = 1, GroupName = "05 Hosted Indicator")]
        public int CockpitDaysOfHistory { get; set; }

        // V2_5 dropped these knobs (volume thresholds & opening-range cap moved
        // to feature-vector context only; no UI gates). UI properties retained
        // to keep workspace serialization stable across users upgrading from
        // V2_4 → V2_5 strategy. Values are not passed to V2_5's factory.
        [NinjaScriptProperty]
        [Display(Name = "ES volume threshold (legacy)", Order = 2, GroupName = "05 Hosted Indicator")]
        public int CockpitESVolumeThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "NQ volume threshold (legacy)", Order = 3, GroupName = "05 Hosted Indicator")]
        public int CockpitNQVolumeThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max opening range (legacy)", Order = 4, GroupName = "05 Hosted Indicator")]
        public int CockpitMaxOpeningRange { get; set; }
        #endregion

        // =====================================================================
        // LIFECYCLE
        // =====================================================================

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Strategy hosting AMTradeCockpitV2_5 (L1 detection) with L2 heuristic scoring and L3 toggleable safety gates per architecture spec v25.1";
                Name        = "AMTradeStrategyV1";
                Calculate                    = Calculate.OnBarClose;
                IsExitOnSessionCloseStrategy = false;  // we manage our own time-close
                EntriesPerDirection          = 1;
                BarsRequiredToTrade          = 50;

                // Logging
                JsonlLogFolder    = @"C:\seasonals\cockpit\sessions";
                HeartbeatSeconds  = 30;

                // Scorer defaults — calibrated to be permissive on the V1 heuristic
                // since the architect spec §1.1 prime directive is "fail open."
                UseHttpScorer        = false;
                HttpScorerEndpoint   = "http://localhost:7677/score";
                HttpScorerTimeoutMs  = 2000;
                MinWinProbability    = 0.45;
                MinExpectedR         = 0.30;
                MinConfidence        = 0.40;
                MinExpectedValue     = 0.20;     // p_win * expected_R
                MaxCandidatesPerBarToTake = 1;

                // Order routing
                AccountName          = "Sim101";
                AtmTemplateNormal    = "AM_Normal_2MES";
                AtmTemplateWide      = "AM_Wide_1MES";
                AllowLiveOrderSubmit = false;

                // L3 gates — defaults per spec §2.3 + risk_architecture.md §2
                EnableRTHWindowGate          = true;
                RthOpenHourEt                = 9;
                RthOpenMinuteEt              = 30;
                RthCloseHourEt               = 15;
                RthCloseMinuteEt             = 0;
                EntryCutoffMinutesBeforeClose = 30;

                EnableDailyLossKill          = true;
                MaxDailyLossDollars          = 500.0;

                EnableDailyLosingTradesKill  = true;
                MaxDailyLosingTrades         = 3;

                EnableCooldownAfterStop      = true;
                CooldownMinutes              = 30;

                EnableMaxSignalsPerDay       = true;
                MaxSignalsPerDay             = 5;

                EnablePositionStateGuard     = true;
                EnableMarginGuard            = true;
                EnableHolidayGate            = true;
                EnableManualKillSwitch       = true;

                EnableConnectionGuard        = true;
                ConnectionStaleSeconds       = 60;

                EnableHeartbeatSelfCheck     = true;
                HeartbeatStaleSeconds        = 90;

                EnableDailyLossPercent       = false;
                MaxDailyLossPercent          = 5.0;

                // Hosted indicator passthrough
                CockpitDaysOfHistory       = 5;
                CockpitESVolumeThreshold   = 12000;
                CockpitNQVolumeThreshold   = 6000;
                CockpitMaxOpeningRange     = 10;
            }
            else if (State == State.Configure)
            {
                // Hosted indicators cannot AddDataSeries themselves — strategy must
                // pre-load every series the indicator will use. Pattern proven by
                // AMShadowObserverV1 (V2_3) and architect spec §5.1.
                try
                {
                    AddDataSeries(Instrument.FullName,
                        new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 30 });
                    // Primary series IS 1-minute (chart attachment); idx1Min=0.
                    // BarsArray[1] = 30-min secondary -> idx30Min=1.
                }
                catch (Exception ex)
                {
                    Print("[L2L3] Configure AddDataSeries FAILED: " + ex.Message);
                    throw;
                }
            }
            else if (State == State.DataLoaded)
            {
                idx1Min = 0;
                idx30Min = 1;
                instrumentRoot = (Instrument != null && Instrument.MasterInstrument != null)
                    ? Instrument.MasterInstrument.Name : "UNKNOWN";

                // Establish session date and log paths.
                sessionDate = Times[idx1Min][0].ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                EnsureSessionLogPaths();

                // Restore state.json (architect §8.4).
                TryRestoreStateFromJson();

                // Instantiate hosted L1 indicator using V2_5's signature
                // (architect spec §3 / §7). V2_5 is L1-pure: NO order/sound/
                // ATM-template params (those moved to L2/L3). Parameters here
                // mirror AMTradeCockpitV2_5's NinjaScriptProperty list exactly.
                try
                {
                    cockpit = AMTradeCockpitV2_5(
                        /* detailLevel               */ CockpitDetailLevel.Full,
                        /* showOnlyCurrentSession    */ false,
                        /* labelPosition             */ CockpitLabelPosition.Right,
                        /* institutionalCorner       */ CockpitCornerPosition.TopRight,
                        /* showCandidateMarkers      */ true,
                        /* daysOfHistory             */ CockpitDaysOfHistory,
                        /* maxLookbackDaysForLevels  */ 3,
                        /* enablePatternA            */ true,
                        /* enablePatternB            */ true,
                        /* emitVwapAsPermissionLevel */ true,
                        /* newsVolumeMultiplierThreshold */ 1.0,
                        /* show50SMA                 */ true,
                        /* show200SMA                */ true,
                        /* legendXOffset             */ 8,
                        /* legendYOffset             */ 25,
                        /* prePlacePanelX            */ 10,
                        /* prePlacePanelY            */ 65,
                        /* enableJsonlLog            */ true,
                        /* jsonlLogFolder            */ JsonlLogFolder,
                        /* heartbeatSeconds          */ HeartbeatSeconds,
                        /* enableStatePersistence    */ true);

                    // Subscribe to L1 events. Architect spec §7.1: OnCandidate
                    // is the canonical channel; OnBoxCapture provides cross-
                    // layer master-candle anchor sync; OnAbstain mirrors the
                    // L1 RTH-window / warmup skips. The legacy OnTouch /
                    // OnSignal bridge is retained as defensive fallback only.
                    SubscribeToCockpitEvents();
                }
                catch (Exception ex)
                {
                    Print("[L2L3] DataLoaded host indicator FAILED: " + ex.Message);
                    EmitError("dataloaded_indicator_init_failed", ex);
                    throw;
                }

                // NT8 surfaces connection state through OnConnectionStatusUpdate
                // (override below). Account-level connection is polled in
                // OnBarUpdate via Account.ConnectionStatus, so no event hookup
                // is needed here — keeps the subscription footprint minimal.
            }
            else if (State == State.Realtime)
            {
                EmitInfoEvent("strategy_realtime", "msg", "Strategy entered Realtime; gates active.");
            }
            else if (State == State.Terminated)
            {
                try
                {
                    UnsubscribeFromCockpitEvents();
                    PersistStateToJson("terminated");
                }
                catch (Exception ex)
                {
                    Print("[L2L3] Terminated cleanup error: " + ex.Message);
                }
            }
        }

        // =====================================================================
        // OnBarUpdate — drives heartbeat, reconciliation, time-cutoff
        // =====================================================================

        protected override void OnBarUpdate()
        {
            // Don't react to warmup bars before BarsRequiredToTrade.
            if (CurrentBars[idx1Min] < BarsRequiredToTrade) return;
            if (BarsInProgress != idx1Min) return;

            // Update heartbeat timestamp (used by gate 11).
            lastBarUpdateTime = Times[idx1Min][0];

            try
            {
                // Detect daily rollover. Reset counters at session boundary.
                string newDate = Times[idx1Min][0].ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                if (newDate != sessionDate)
                {
                    OnDailyRollover(newDate);
                }

                // Periodic state persistence + heartbeat.
                if ((Times[idx1Min][0] - lastHeartbeatEmit).TotalSeconds >= HeartbeatSeconds)
                {
                    EmitHeartbeat();
                    lastHeartbeatEmit = Times[idx1Min][0];
                    PersistStateToJson("heartbeat");
                }

                // Reconciliation: every bar, compare broker position vs internal
                // state (architect spec INV-L3-4).
                ReconcileBrokerVsInternal();

                // Time-close cutoff: if Active and we are inside last 5 minutes
                // before close, close at market (limits-only is for entries; a
                // forced close is acceptable — explicitly logged).
                CheckTimeCloseCutoff();

                // Cooldown / lockout expiry.
                CheckCooldownExpiry();

                // Flush per-bar candidate batch into ranking decision now that
                // the bar is closed.
                FlushCurrentBarCandidatesIfDue();
            }
            catch (Exception ex)
            {
                EmitError("on_bar_update_exception", ex);
                // Architect §1.4 invariant 6: re-throw in production so the
                // harness sees it; here we swallow only after logging because
                // NT8 disables the strategy on uncaught exception in OnBarUpdate.
                Print("[L2L3] OnBarUpdate exception (swallowed after log): " + ex.Message);
            }
        }

        private void OnDailyRollover(string newDate)
        {
            EmitInfoEvent("daily_rollover",
                "from", sessionDate,
                "to",   newDate);
            sessionDate = newDate;
            EnsureSessionLogPaths();

            // Lockout check: if today's date equals state.json's session_date
            // we already restored. Otherwise rollover resets counters.
            signalsToday = 0;
            fillsToday = 0;
            losingTradesToday = 0;
            winningTradesToday = 0;
            consecutiveStops = 0;
            realizedPnlDollarsToday = 0.0;

            // Lockout resets each session unless it was set to "permanent" -
            // which V1 does not support; everything resets daily.
            if (lockoutActive)
            {
                EmitEvent("lockout_reset",
                    "trigger_that_was_active", lockoutTrigger,
                    "reset_at", FormatTime(Times[idx1Min][0]),
                    "reason", "session_rollover");
                lockoutActive = false;
                lockoutTrigger = null;
            }

            PersistStateToJson("daily_rollover");
        }

        // =====================================================================
        // L2 — DECISION FLOW (architect spec §7)
        // =====================================================================

        /// <summary>
        /// Top-level entry from L1's OnCandidate event. Buffers candidates per
        /// bar; flushes & ranks at bar close. Per architect §7.5: ranking is
        /// SCORE-based, not distance-based.
        /// </summary>
        private void OnL1Candidate(CandidateEvent ev)
        {
            if (ev == null) return;

            // Bar-bucket the candidate. The flush happens in OnBarUpdate after
            // all candidates for a given bar have been emitted.
            if (currentBarBucketTime != ev.BarTime)
            {
                FlushCurrentBarCandidatesIfDue();
                currentBarBucketTime = ev.BarTime;
            }
            currentBarCandidates.Add(ev);
        }

        private void FlushCurrentBarCandidatesIfDue()
        {
            if (currentBarCandidates.Count == 0) return;

            // Score every candidate. Rank by composite (p_win * E[R] * confidence).
            var scored = new List<KeyValuePair<CandidateEvent, ScorerDecision>>(currentBarCandidates.Count);
            foreach (var c in currentBarCandidates)
            {
                ScorerDecision d;
                try { d = ScoreCandidate(c); }
                catch (Exception ex)
                {
                    EmitError("scorer_exception", ex);
                    d = new ScorerDecision
                    {
                        PWin = 0, ExpectedR = 0, Confidence = 0,
                        AbstainReason = "scorer_exception",
                        SizeBucket = "SKIP",
                        ScorerMode = "Heuristic",
                        TargetChoice = "level_to_level"
                    };
                }
                scored.Add(new KeyValuePair<CandidateEvent, ScorerDecision>(c, d));

                // Always emit decision_response for audit (architect INV-L2-5).
                EmitDecisionResponse(c, d);
            }

            // Rank descending by composite score.
            scored.Sort((a, b) =>
            {
                double sa = a.Value.PWin * a.Value.ExpectedR * a.Value.Confidence;
                double sb = b.Value.PWin * b.Value.ExpectedR * b.Value.Confidence;
                return sb.CompareTo(sa);
            });

            int taken = 0;
            for (int i = 0; i < scored.Count; i++)
            {
                var c = scored[i].Key;
                var d = scored[i].Value;

                if (i >= MaxCandidatesPerBarToTake)
                {
                    EmitAbstain(c, "L2", "rank_too_low",
                        string.Format(CultureInfo.InvariantCulture,
                            "rank {0} of {1}; max_per_bar={2}",
                            i + 1, scored.Count, MaxCandidatesPerBarToTake),
                        d, /*recoverableUntil*/ null);
                    continue;
                }

                if (!ShouldTake(ref d))
                {
                    EmitAbstain(c, "L2", d.AbstainReason ?? "scorer_threshold",
                        string.Format(CultureInfo.InvariantCulture,
                            "p_win={0:F2} expR={1:F2} conf={2:F2} EV={3:F2}",
                            d.PWin, d.ExpectedR, d.Confidence, d.PWin * d.ExpectedR),
                        d, /*recoverableUntil*/ null);
                    continue;
                }

                // L2 says take. Defer to L3.
                var gateResult = IsSubmissionAllowed(c, d);
                if (!gateResult.Allowed)
                {
                    EmitAbstain(c, "L3", gateResult.GateName, gateResult.Reason, d, gateResult.RecoverableUntil);
                    continue;
                }

                // L3 cleared: emit signal + submit.
                if (!SubmitSignal(c, d))
                {
                    // Submission failed; SubmitSignal already emitted error.
                    continue;
                }
                taken++;
            }

            currentBarCandidates.Clear();
            currentBarBucketTime = DateTime.MinValue;
        }

        /// <summary>
        /// V1 heuristic scorer per architect §7.2. Rule-based; deterministic
        /// function of features (architect INV-L2-2).
        ///
        /// Pseudocode (weight rationale in inline comments):
        ///   score = 0.50 baseline
        ///        + day_type bonus / penalty   (trend +0.20, sideways -0.10)
        ///        + slope alignment            (with-direction +0.15, counter -0.10)
        ///        + MOC validation             (Green +0.10, Orange +0.05, Gray -0.05)
        ///        + level priority             (institutional +0.10, confluence +0.10)
        ///        - permission level           (-0.20)
        ///        + Pattern B preference       (+0.10)
        ///        - R3/R4 exhaustion           (-0.30 for fresh long above R3)
        ///        - time-of-day late          (-0.10 if &lt;60min to RTH close)
        ///        + news-wick boost            (+0.10 if active and close)
        ///        - already-touched-today      (-0.10 latch warning)
        ///        + Friday escalation          (+0.05 if trend day + Green MOC)
        ///        + retrace_side               (+0.10)
        ///   p_win = clip(score, 0, 1)
        ///   E[R]  = (target/stop) * p_win - (1-p_win)
        /// </summary>
        public ScorerDecision ScoreCandidate(CandidateEvent c)
        {
            if (UseHttpScorer)
            {
                ScorerDecision httpResult;
                if (TryScoreHttp(c, out httpResult)) return httpResult;
                // Fall through to heuristic on HTTP failure.
                EmitInfoEvent("warning", "msg", "HTTP scorer failed; falling back to heuristic", "candidate_id", c.CandidateId);
            }
            return ScoreHeuristic(c);
        }

        private ScorerDecision ScoreHeuristic(CandidateEvent c)
        {
            double score = 0.50;
            int featuresAvailable = 0, featuresExpected = 8;

            var f = c.Features ?? new FeatureVector();
            string dir = c.Direction ?? "LONG";

            // 1) Day type strength (3-node interpretation default per architect §11.1)
            if (f.DayTypeV2_3node == "LongTrend"  || f.DayTypeV2_3node == "ShortTrend")  { score += 0.20; featuresAvailable++; }
            else if (f.DayTypeV2_3node == "CautiousLong" || f.DayTypeV2_3node == "CautiousShort") { score += 0.10; featuresAvailable++; }
            else if (f.DayTypeV2_3node == "Sideways") { score -= 0.10; featuresAvailable++; }

            // 2) SMA200 slope alignment. AM apr-9: trend > level matters more.
            if (f.Sma200SlopeAvailable)
            {
                featuresAvailable++;
                if      (f.Sma200SlopeSign == "Up"   && dir == "LONG")  score += 0.15;
                else if (f.Sma200SlopeSign == "Down" && dir == "SHORT") score += 0.15;
                else if (f.Sma200SlopeSign == "Up"   && dir == "SHORT") score -= 0.10;
                else if (f.Sma200SlopeSign == "Down" && dir == "LONG")  score -= 0.10;
            }

            // 3) MOC validation -> sizing-relevant (apr-24 lines 312-315).
            if (f.MocObservedToday)
            {
                featuresAvailable++;
                if      (f.MocState == "Green")  score += 0.10;
                else if (f.MocState == "Orange") score += 0.05;
                else if (f.MocState == "Gray")   score -= 0.05;
            }

            // 4) Level priority (architect §7.2).
            if (c.LevelName != null)
            {
                featuresAvailable++;
                string ln = c.LevelName;
                if (ln.StartsWith("PrInst") || ln.StartsWith("Close330")) score += 0.10;
                else if (ln.StartsWith("Europe") || ln.StartsWith("GlobEx")) score += 0.05;
            }

            // 5) Confluence
            if (f.IsHighestVolumeInCluster) score += 0.05;
            if (f.ConfluenceCount >= 4)     score += 0.10;
            featuresAvailable++;

            // 6) Permission-level (VWAP/AnchVWAP) penalty per spec §6.7.
            if (c.IsPermissionLevel) score -= 0.20;

            // 7) Pattern B preference (apr-24 verbatim: "I rarely take a breakdown
            //    trade; what I will take is a failed retest").
            if (c.PatternType == "B") score += 0.10;

            // 8) R3/R4 exhaustion: don't take fresh longs above R3.
            // dist_to_r3 < 0 means price is ABOVE R3.
            if (dir == "LONG" && !double.IsNaN(f.DistToR3) && f.DistToR3 < 0)
                score -= 0.30;
            else if (dir == "SHORT" && !double.IsNaN(f.DistToS3) && f.DistToS3 > 0)
                score -= 0.30;

            // 9) Time of day — late entries are lower quality.
            featuresAvailable++;
            if (f.MinutesUntilRthClose < 60) score -= 0.10;
            if (f.MinutesSinceRthOpen < 5)  score -= 0.05;  // first-bar noise

            // 10) News-wick boost
            if (f.NewsWickActiveToday && !double.IsNaN(f.NewsWickDistancePts) && Math.Abs(f.NewsWickDistancePts) < 2.0)
                score += 0.10;

            // 11) Already-touched penalty (latch warning, not block per spec §1.1).
            if (f.AlreadyTouchedToday) score -= 0.10;

            // 12) Day-of-week (Friday escalation per apr-24 lines 290-303).
            if (f.DayOfWeek == "Friday" && f.DayTypeV2_3node != "Sideways" && f.MocState == "Green")
                score += 0.05;

            // 13) Retrace-side bonus (price came back to the level — AM's preferred entry).
            if (f.RetraceSide) score += 0.10;
            else if (f.RetraceSideAtOpen) /* edge case; small penalty handled implicitly */ score -= 0.02;

            // is_permission_level is informational; we already penalized.
            featuresAvailable++;

            // Clip and convert to probability.
            double pWin = Math.Max(0.0, Math.Min(1.0, score));

            // Expected R: target/stop ratio is the upside; assume 1R risk.
            double targetPts = c.FirstTargetPts;
            double stopPts   = c.StopDistanceSuggestionPts;
            // Apply target_choice extension if slope steep enough (architect §11.3).
            string targetChoice = "level_to_level";
            if (f.Sma200SlopeAvailable && Math.Abs(f.Sma200SlopeDeltaPts) > 5.0)
            {
                if (c.RunnerTargets != null && c.RunnerTargets.Fib200PctPts > 0)
                {
                    targetPts = Math.Max(targetPts, c.RunnerTargets.Fib200PctPts);
                    targetChoice = "200";
                }
            }
            else if (c.RunnerTargets != null && c.RunnerTargets.Fib150PctPts > 0)
            {
                targetPts = Math.Max(targetPts, c.RunnerTargets.Fib150PctPts);
                targetChoice = "150";
            }

            double rr = (stopPts > 0) ? targetPts / stopPts : 1.0;
            double expectedR = pWin * rr - (1.0 - pWin) * 1.0;

            // Confidence: based on how many features were populated.
            double confidence = Math.Max(0.0, Math.Min(1.0, (double)featuresAvailable / featuresExpected));

            // Size bucket from MOC state (apr-24 §1).
            string sizeBucket = "MIN";
            if (f.MocState == "Green" && f.DayTypeV2_3node != "Sideways") sizeBucket = "FULL";
            else if (f.MocState == "Orange") sizeBucket = "HALF";
            else if (f.MocState == "Gray") sizeBucket = "MIN";

            // Sideways days reduce by one step per apr-23 (line 412-414).
            if (f.DayTypeV2_3node == "Sideways")
            {
                if (sizeBucket == "FULL") sizeBucket = "HALF";
                else if (sizeBucket == "HALF") sizeBucket = "MIN";
            }

            string abstainReason = null;
            if (sizeBucket == "MIN" && f.MocState == "Gray" && f.DayTypeV2_3node == "Sideways")
                abstainReason = "scorer_skip_sideways_gray";

            return new ScorerDecision
            {
                PWin = pWin,
                ExpectedR = expectedR,
                Confidence = confidence,
                SizeBucket = sizeBucket,
                TargetChoice = targetChoice,
                AbstainReason = abstainReason,
                ScorerMode = "Heuristic"
            };
        }

        /// <summary>
        /// Decision rule per spec §7.4 — take if BOTH (a) thresholds met AND
        /// (b) expected value (p*R) clears the floor. Configurable via params.
        /// d is passed by ref so the caller sees the assigned AbstainReason
        /// (ScorerDecision is a struct).
        /// </summary>
        private bool ShouldTake(ref ScorerDecision d)
        {
            if (d.AbstainReason != null) return false;
            if (d.PWin       < MinWinProbability) { d.AbstainReason = "scorer_min_p_win"; return false; }
            if (d.ExpectedR  < MinExpectedR)      { d.AbstainReason = "scorer_min_expected_r"; return false; }
            if (d.Confidence < MinConfidence)     { d.AbstainReason = "scorer_min_confidence"; return false; }
            if (d.PWin * d.ExpectedR < MinExpectedValue) { d.AbstainReason = "scorer_min_expected_value"; return false; }
            return true;
        }

        // =====================================================================
        // L2 HTTP SCORER — V2 hook
        // Request:  POST {endpoint} {"candidate_id":"...","features":{...}}
        // Response: {"p_win":0.58,"predicted_R":1.85,"confidence":0.72,
        //            "size_bucket":"FULL","target_choice":"200","abstain_reason":null}
        // Behavior: 2s timeout; on failure log warning and return false to fall
        // back to heuristic (architect spec §2.2 fail-open).
        // =====================================================================
        private bool TryScoreHttp(CandidateEvent c, out ScorerDecision result)
        {
            result = default(ScorerDecision);
            var sw = System.Diagnostics.Stopwatch.StartNew();
            try
            {
                EmitEvent("decision_request",
                    "candidate_id", c.CandidateId,
                    "endpoint", HttpScorerEndpoint,
                    "sent_at", FormatTime(Times[idx1Min][0]));

                var req = (HttpWebRequest)WebRequest.Create(HttpScorerEndpoint);
                req.Method = "POST";
                req.ContentType = "application/json";
                req.Timeout = HttpScorerTimeoutMs;
                req.ReadWriteTimeout = HttpScorerTimeoutMs;

                string body = BuildHttpScoreRequestBody(c);
                byte[] data = Encoding.UTF8.GetBytes(body);
                req.ContentLength = data.Length;
                using (var rs = req.GetRequestStream()) rs.Write(data, 0, data.Length);

                using (var resp = (HttpWebResponse)req.GetResponse())
                using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                {
                    string respBody = sr.ReadToEnd();
                    sw.Stop();
                    result = ParseHttpScoreResponse(respBody);
                    result.ScorerMode = "MlHttp";
                    return true;
                }
            }
            catch (Exception ex)
            {
                sw.Stop();
                EmitInfoEvent("warning",
                    "msg", "HTTP scorer error",
                    "candidate_id", c.CandidateId,
                    "exception", ex.GetType().Name,
                    "latency_ms", sw.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture));
                return false;
            }
        }

        private static string BuildHttpScoreRequestBody(CandidateEvent c)
        {
            // Minimal request — enough for the scoring service to look up the
            // pre-built feature vector keyed by (instrument, ts, level). The
            // full feature vector is logged via the events.jsonl stream.
            var sb = new StringBuilder(256);
            sb.Append('{');
            sb.Append("\"candidate_id\":"); AppendJsonString(sb, c.CandidateId); sb.Append(',');
            sb.Append("\"session_date\":"); AppendJsonString(sb, c.SessionDate); sb.Append(',');
            sb.Append("\"event_ts\":");     AppendJsonString(sb, c.BarTime.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture)); sb.Append(',');
            sb.Append("\"level_name\":");   AppendJsonString(sb, c.LevelName); sb.Append(',');
            sb.Append("\"direction\":");    AppendJsonString(sb, c.Direction);
            sb.Append('}');
            return sb.ToString();
        }

        private static ScorerDecision ParseHttpScoreResponse(string body)
        {
            // Minimal scalar extraction (avoid Newtonsoft to match V2_4 pattern).
            return new ScorerDecision
            {
                PWin       = ExtractDouble(body, "\"p_win\"", 0.0),
                ExpectedR  = ExtractDouble(body, "\"predicted_R\"", 0.0),
                Confidence = ExtractDouble(body, "\"confidence\"", 0.0),
                SizeBucket = ExtractString(body, "\"size_bucket\"") ?? "MIN",
                TargetChoice = ExtractString(body, "\"target_choice\"") ?? "level_to_level",
                AbstainReason = ExtractString(body, "\"abstain_reason\""),
                ScorerMode = "MlHttp"
            };
        }

        // =====================================================================
        // L2 — ORDER CONSTRUCTION & SUBMISSION
        // Limit-only entries (AM apr-9 line 94: "I never use market orders").
        // Stop-market for hard stop. Limit for first target. OCO sibling pair
        // is implemented via cancel-other-on-fill in OnExecutionUpdate.
        // V1: single-entry, single-exit at first target. Runner ladder -> V1.1.
        // =====================================================================

        private bool SubmitSignal(CandidateEvent c, ScorerDecision d)
        {
            // Compute size from bucket. MES contract counts.
            int qty = SizeBucketToQty(d.SizeBucket);
            if (qty <= 0)
            {
                EmitAbstain(c, "L2", "size_bucket_skip",
                    "scorer SizeBucket==SKIP/MIN with zero qty", d, null);
                return false;
            }

            // Replace older Pending if any (architect §7.6 "Pending limits replace
            // older pending limits"). Single-position model.
            if (signalState == InternalSignalState.Pending && currentSignal != null)
            {
                CancelPendingSignal("replaced_by_newer_pending");
            }
            else if (signalState == InternalSignalState.Active)
            {
                // Position state guard should have caught this; double-protect.
                EmitAbstain(c, "L3", "position_already_active",
                    "internal Active state; refusing new entry", d, null);
                return false;
            }

            // Build the active signal.
            string sigId = string.Format(CultureInfo.InvariantCulture,
                "sig_{0}_{1}_{2:D3}",
                instrumentRoot, sessionDate.Replace("-", ""), signalsToday + 1);

            double entryPrice = c.LevelPrice;
            double stopDistPts = c.StopDistanceSuggestionPts > 0 ? c.StopDistanceSuggestionPts : 3.0;
            double targetDistPts = c.FirstTargetPts > 0 ? c.FirstTargetPts : stopDistPts;

            double stopPrice, targetPrice;
            if (c.Direction == "LONG")
            {
                stopPrice   = entryPrice - stopDistPts;
                targetPrice = entryPrice + targetDistPts;
            }
            else
            {
                stopPrice   = entryPrice + stopDistPts;
                targetPrice = entryPrice - targetDistPts;
            }

            currentSignal = new ActiveSignal
            {
                SignalId = sigId,
                CandidateId = c.CandidateId,
                Direction = c.Direction,
                EntryPrice = RoundToTick(entryPrice),
                StopPrice  = RoundToTick(stopPrice),
                TargetPrice = RoundToTick(targetPrice),
                SizeQty = qty,
                SignalTime = c.BarTime,
                LevelName = c.LevelName,
                PatternType = c.PatternType,
                Decision = d
            };

            EmitSignal(currentSignal);
            signalsToday++;

            // Submit broker orders unless live submission is disabled.
            if (!AllowLiveOrderSubmit)
            {
                signalState = InternalSignalState.Pending;
                EmitInfoEvent("submit_simulated",
                    "msg", "AllowLiveOrderSubmit=false; signal logged but no broker orders submitted",
                    "signal_id", sigId);
                PersistStateToJson("signal");
                return true;
            }

            try
            {
                // Limit entry. SubmitOrderUnmanaged returns the Order; track it.
                OrderAction entryAction = (c.Direction == "LONG") ? OrderAction.Buy : OrderAction.SellShort;
                currentSignal.EntryOrder = SubmitOrderUnmanaged(
                    idx1Min,
                    entryAction,
                    OrderType.Limit,
                    qty,
                    currentSignal.EntryPrice,
                    /* stopPrice */ 0,
                    /* oco */ sigId + "_entry",
                    sigId + "_entry_name");

                signalState = InternalSignalState.Pending;
                PersistStateToJson("signal");
                return true;
            }
            catch (Exception ex)
            {
                EmitError("submit_entry_failed", ex);
                currentSignal = null;
                signalState = InternalSignalState.None;
                return false;
            }
        }

        private int SizeBucketToQty(string bucket)
        {
            switch (bucket)
            {
                case "FULL": return 2;   // 2 MES per AM apr-24 + Stage B risk_arch
                case "HALF": return 1;
                case "MIN":  return 1;
                default:     return 0;
            }
        }

        private void CancelPendingSignal(string reason)
        {
            if (currentSignal == null) return;

            try
            {
                if (currentSignal.EntryOrder != null && currentSignal.EntryOrder.OrderState == OrderState.Working)
                    CancelOrder(currentSignal.EntryOrder);
            }
            catch (Exception ex) { EmitError("cancel_entry_failed", ex); }

            EmitEvent("cancel",
                "signal_id", currentSignal.SignalId,
                "reason", reason,
                "cancelled_at", FormatTime(Times[idx1Min][0]));

            currentSignal = null;
            signalState = InternalSignalState.None;
            PersistStateToJson("cancel");
        }

        // =====================================================================
        // L2 — EXECUTION CALLBACKS
        // =====================================================================

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            try
            {
                if (execution == null || execution.Order == null) return;
                if (currentSignal == null) return;

                var order = execution.Order;
                bool isEntryFill = currentSignal.EntryOrder != null && order.OrderId == currentSignal.EntryOrder.OrderId;
                bool isStopFill  = currentSignal.StopOrder  != null && order.OrderId == currentSignal.StopOrder.OrderId;
                bool isTargetFill = currentSignal.TargetOrder != null && order.OrderId == currentSignal.TargetOrder.OrderId;

                if (isEntryFill && order.OrderState == OrderState.Filled && !currentSignal.Filled)
                {
                    currentSignal.Filled = true;
                    currentSignal.FilledPrice = price;
                    currentSignal.FilledAt = time;
                    fillsToday++;

                    EmitEvent("fill",
                        "signal_id", currentSignal.SignalId,
                        "broker_order_id", orderId,
                        "filled_at", FormatTime(time),
                        "filled_price", price.ToString("R", CultureInfo.InvariantCulture),
                        "filled_qty", quantity.ToString(CultureInfo.InvariantCulture),
                        "expected_price", currentSignal.EntryPrice.ToString("R", CultureInfo.InvariantCulture),
                        "slippage_pts", (price - currentSignal.EntryPrice).ToString("R", CultureInfo.InvariantCulture));

                    // Submit OCO stop + target.
                    SubmitExitOrders();
                    signalState = InternalSignalState.Active;
                    PersistStateToJson("fill");
                }
                else if (isStopFill && order.OrderState == OrderState.Filled)
                {
                    OnStopHit(price, quantity, time);
                }
                else if (isTargetFill && order.OrderState == OrderState.Filled)
                {
                    OnTargetHit(price, quantity, time);
                }
                else if (order.OrderState == OrderState.Rejected)
                {
                    EmitError("order_rejected",
                        new InvalidOperationException("OrderState=Rejected: " + (order.Name ?? "?")));
                    if (isEntryFill) { currentSignal = null; signalState = InternalSignalState.None; }
                }
            }
            catch (Exception ex)
            {
                EmitError("on_execution_update_exception", ex);
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice,
            int quantity, int filled, double averageFillPrice, OrderState orderState,
            DateTime time, ErrorCode error, string nativeError)
        {
            if (error != ErrorCode.NoError)
            {
                EmitInfoEvent("warning",
                    "msg", "OrderUpdate error",
                    "error", error.ToString(),
                    "native", nativeError ?? "",
                    "order_name", order != null ? order.Name : "?");
            }
        }

        private void SubmitExitOrders()
        {
            if (currentSignal == null) return;
            try
            {
                OrderAction exitAction = (currentSignal.Direction == "LONG") ? OrderAction.Sell : OrderAction.BuyToCover;
                string oco = currentSignal.SignalId + "_exit";

                currentSignal.StopOrder = SubmitOrderUnmanaged(
                    idx1Min, exitAction, OrderType.StopMarket,
                    currentSignal.SizeQty, /*limit*/ 0, currentSignal.StopPrice,
                    oco, currentSignal.SignalId + "_stop");

                currentSignal.TargetOrder = SubmitOrderUnmanaged(
                    idx1Min, exitAction, OrderType.Limit,
                    currentSignal.SizeQty, currentSignal.TargetPrice, /*stop*/ 0,
                    oco, currentSignal.SignalId + "_target");
            }
            catch (Exception ex)
            {
                EmitError("submit_exit_failed", ex);
            }
        }

        private void OnStopHit(double price, int qty, DateTime time)
        {
            if (currentSignal == null) return;
            double dirSign = (currentSignal.Direction == "LONG") ? 1.0 : -1.0;
            double pnlPts = dirSign * (price - currentSignal.FilledPrice);
            double pnlDollars = pnlPts * MesPointValue * qty;

            EmitEvent("stop_hit",
                "signal_id", currentSignal.SignalId,
                "stopped_at", FormatTime(time),
                "stop_price", price.ToString("R", CultureInfo.InvariantCulture),
                "filled_qty", qty.ToString(CultureInfo.InvariantCulture),
                "realized_pnl_dollars", pnlDollars.ToString("R", CultureInfo.InvariantCulture),
                "realized_R", "-1.0");

            realizedPnlDollarsToday += pnlDollars;
            losingTradesToday++;
            consecutiveStops++;
            lastStopTime = time;
            cooldownActive = EnableCooldownAfterStop;
            cooldownExpiresAt = time.AddMinutes(CooldownMinutes);

            EmitEvent("cooldown_active",
                "stop_time", FormatTime(time),
                "cooldown_minutes", CooldownMinutes.ToString(CultureInfo.InvariantCulture),
                "expires_at", FormatTime(cooldownExpiresAt));

            currentSignal = null;
            signalState = InternalSignalState.None;
            CheckLockoutTriggers();
            PersistStateToJson("stop_hit");
        }

        private void OnTargetHit(double price, int qty, DateTime time)
        {
            if (currentSignal == null) return;
            double dirSign = (currentSignal.Direction == "LONG") ? 1.0 : -1.0;
            double pnlPts = dirSign * (price - currentSignal.FilledPrice);
            double pnlDollars = pnlPts * MesPointValue * qty;

            EmitEvent("target_hit",
                "signal_id", currentSignal.SignalId,
                "target_kind", "first_target",
                "target_price", price.ToString("R", CultureInfo.InvariantCulture),
                "filled_at", FormatTime(time),
                "filled_qty", qty.ToString(CultureInfo.InvariantCulture),
                "remaining_qty", "0",
                "realized_pnl_dollars", pnlDollars.ToString("R", CultureInfo.InvariantCulture),
                "realized_R", pnlPts > 0 ? "1.0" : "-1.0");

            realizedPnlDollarsToday += pnlDollars;
            if (pnlDollars > 0) { winningTradesToday++; consecutiveStops = 0; }
            else                { losingTradesToday++; }

            currentSignal = null;
            signalState = InternalSignalState.None;
            CheckLockoutTriggers();
            PersistStateToJson("target_hit");
        }

        private void CheckTimeCloseCutoff()
        {
            if (signalState != InternalSignalState.Active || currentSignal == null) return;
            DateTime t = Times[idx1Min][0];
            int closeMins = RthCloseHourEt * 60 + RthCloseMinuteEt;
            int curMins = t.Hour * 60 + t.Minute;
            if (curMins >= closeMins - 5 && curMins <= closeMins)
            {
                // Force flat. Cancel target order, submit market exit.
                try
                {
                    if (currentSignal.TargetOrder != null && currentSignal.TargetOrder.OrderState == OrderState.Working)
                        CancelOrder(currentSignal.TargetOrder);
                    if (currentSignal.StopOrder != null && currentSignal.StopOrder.OrderState == OrderState.Working)
                        CancelOrder(currentSignal.StopOrder);

                    OrderAction exitAction = (currentSignal.Direction == "LONG") ? OrderAction.Sell : OrderAction.BuyToCover;
                    SubmitOrderUnmanaged(idx1Min, exitAction, OrderType.Market,
                        currentSignal.SizeQty, 0, 0, "", currentSignal.SignalId + "_timeclose");
                }
                catch (Exception ex) { EmitError("time_close_failed", ex); }

                EmitEvent("time_close",
                    "signal_id", currentSignal.SignalId,
                    "closed_at", FormatTime(t),
                    "close_price", Closes[idx1Min][0].ToString("R", CultureInfo.InvariantCulture),
                    "filled_qty", currentSignal.SizeQty.ToString(CultureInfo.InvariantCulture));

                signalState = InternalSignalState.Closing;
                PersistStateToJson("time_close");
            }
        }

        private void CheckCooldownExpiry()
        {
            if (cooldownActive && Times[idx1Min][0] >= cooldownExpiresAt)
            {
                EmitEvent("cooldown_reset",
                    "reset_at", FormatTime(Times[idx1Min][0]));
                cooldownActive = false;
            }
        }

        private void CheckLockoutTriggers()
        {
            if (lockoutActive) return;
            if (EnableDailyLossKill && realizedPnlDollarsToday <= -MaxDailyLossDollars)
            {
                lockoutActive = true;
                lockoutTrigger = "daily_loss_dollars";
                EmitEvent("lockout_active",
                    "trigger", lockoutTrigger,
                    "value", realizedPnlDollarsToday.ToString("R", CultureInfo.InvariantCulture),
                    "threshold", (-MaxDailyLossDollars).ToString("R", CultureInfo.InvariantCulture),
                    "expires_at", "next_session");
            }
            else if (EnableDailyLosingTradesKill && losingTradesToday >= MaxDailyLosingTrades)
            {
                lockoutActive = true;
                lockoutTrigger = "max_losing_trades";
                EmitEvent("lockout_active",
                    "trigger", lockoutTrigger,
                    "value", losingTradesToday.ToString(CultureInfo.InvariantCulture),
                    "threshold", MaxDailyLosingTrades.ToString(CultureInfo.InvariantCulture),
                    "expires_at", "next_session");
            }
        }

        private double RoundToTick(double price)
        {
            double tick = MesTickSize;
            return Math.Round(price / tick) * tick;
        }

        // =====================================================================
        // L3 — SAFETY GATES (architect spec §8)
        // Each gate is an independently toggleable method returning GateResult.
        // First-veto-wins ordering per architect §8.2.
        // =====================================================================

        public GateResult IsSubmissionAllowed(CandidateEvent c, ScorerDecision d)
        {
            // Gate 10: connection state guard — first because nothing matters
            // when disconnected.
            if (EnableConnectionGuard)
            {
                var r = GateConnection();
                if (!r.Allowed) return r;
            }

            // Gate 9: manual kill switch — operator override outranks scoring.
            if (EnableManualKillSwitch && manualKillSwitchActive)
                return MakeGate(false, "manual_kill_switch",
                    "operator pressed kill; press F12 to resume", null,
                    "{\"manual_kill_switch_active\":true}");

            // Divergence halt overrides all (architect INV-L3-4).
            if (haltDueToDivergence)
                return MakeGate(false, "divergence_halt",
                    "broker vs internal position mismatch; manual reconcile required", null, null);

            // Gate 8: holiday gate.
            if (EnableHolidayGate)
            {
                var r = GateHoliday();
                if (!r.Allowed) return r;
            }

            // Gate 1: RTH window.
            if (EnableRTHWindowGate)
            {
                var r = GateRthWindow();
                if (!r.Allowed) return r;
            }

            // Gate 7: margin guard (HARD - cannot be silently skipped).
            if (EnableMarginGuard)
            {
                var r = GateMargin(d);
                if (!r.Allowed) return r;
            }

            // Gate 6: position state guard.
            if (EnablePositionStateGuard)
            {
                var r = GatePositionState();
                if (!r.Allowed) return r;
            }

            // Gate 2: daily $ loss.
            if (EnableDailyLossKill)
            {
                var r = GateDailyLossDollars();
                if (!r.Allowed) return r;
            }

            // Gate 12: daily % loss.
            if (EnableDailyLossPercent)
            {
                var r = GateDailyLossPercent();
                if (!r.Allowed) return r;
            }

            // Gate 3: daily losing trades count.
            if (EnableDailyLosingTradesKill)
            {
                var r = GateDailyLosingTrades();
                if (!r.Allowed) return r;
            }

            // Gate 4: cooldown after stop.
            if (EnableCooldownAfterStop)
            {
                var r = GateCooldown();
                if (!r.Allowed) return r;
            }

            // Gate 5: max signals per day.
            if (EnableMaxSignalsPerDay)
            {
                var r = GateMaxSignals();
                if (!r.Allowed) return r;
            }

            // Gate 11: heartbeat self-check.
            if (EnableHeartbeatSelfCheck)
            {
                var r = GateHeartbeat();
                if (!r.Allowed) return r;
            }

            // Catch-all: lockout flag (set by daily loss / max losing trades).
            if (lockoutActive)
                return MakeGate(false, "lockout_active", lockoutTrigger ?? "lockout", null,
                    "{\"lockout_trigger\":\"" + (lockoutTrigger ?? "?") + "\"}");

            return MakeGate(true, "all_clear", "all gates passed", null, null);
        }

        // ---- individual gates ------------------------------------------------

        private GateResult GateRthWindow()
        {
            DateTime t = Times[idx1Min][0];
            int curMins = t.Hour * 60 + t.Minute;
            int openMins = RthOpenHourEt * 60 + RthOpenMinuteEt;
            int closeMins = RthCloseHourEt * 60 + RthCloseMinuteEt;
            int cutoffMins = closeMins - EntryCutoffMinutesBeforeClose;

            if (curMins < openMins)
            {
                DateTime recover = t.Date.AddHours(RthOpenHourEt).AddMinutes(RthOpenMinuteEt);
                return MakeGate(false, "rth_window_closed",
                    string.Format(CultureInfo.InvariantCulture,
                        "before RTH open {0:D2}:{1:D2} ET", RthOpenHourEt, RthOpenMinuteEt),
                    recover, null);
            }
            if (curMins > cutoffMins)
            {
                DateTime recover = t.Date.AddDays(1).AddHours(RthOpenHourEt).AddMinutes(RthOpenMinuteEt);
                return MakeGate(false, "rth_window_closed",
                    string.Format(CultureInfo.InvariantCulture,
                        "past entry cutoff (close-{0}min)", EntryCutoffMinutesBeforeClose),
                    recover, null);
            }
            return MakeGate(true, "rth_window", null, null, null);
        }

        private GateResult GateDailyLossDollars()
        {
            if (realizedPnlDollarsToday <= -MaxDailyLossDollars)
                return MakeGate(false, "daily_loss_kill",
                    string.Format(CultureInfo.InvariantCulture,
                        "realized PnL {0:F2} <= -{1:F2}", realizedPnlDollarsToday, MaxDailyLossDollars),
                    null,
                    "{\"realized_pnl\":" + realizedPnlDollarsToday.ToString("R", CultureInfo.InvariantCulture) + "}");
            return MakeGate(true, "daily_loss_kill", null, null, null);
        }

        private GateResult GateDailyLossPercent()
        {
            double accountValue = 10000.0; // V1 placeholder
            try { if (Account != null) accountValue = Account.Get(AccountItem.CashValue, Currency.UsDollar); }
            catch { /* fall back to placeholder */ }
            double pct = accountValue > 0 ? (-realizedPnlDollarsToday / accountValue) * 100.0 : 0.0;
            if (pct >= MaxDailyLossPercent)
                return MakeGate(false, "daily_loss_pct_kill",
                    string.Format(CultureInfo.InvariantCulture,
                        "loss {0:F2}% of {1:F2} >= {2:F2}%", pct, accountValue, MaxDailyLossPercent),
                    null, null);
            return MakeGate(true, "daily_loss_pct_kill", null, null, null);
        }

        private GateResult GateDailyLosingTrades()
        {
            if (losingTradesToday >= MaxDailyLosingTrades)
                return MakeGate(false, "max_losing_trades",
                    string.Format(CultureInfo.InvariantCulture,
                        "{0} losing trades today >= max {1}", losingTradesToday, MaxDailyLosingTrades),
                    null,
                    "{\"losing_trades_today\":" + losingTradesToday + "}");
            return MakeGate(true, "max_losing_trades", null, null, null);
        }

        private GateResult GateCooldown()
        {
            if (cooldownActive && Times[idx1Min][0] < cooldownExpiresAt)
            {
                int mins = (int)(cooldownExpiresAt - Times[idx1Min][0]).TotalMinutes;
                return MakeGate(false, "cooldown_after_stop",
                    string.Format(CultureInfo.InvariantCulture, "{0} min remaining", mins),
                    cooldownExpiresAt,
                    "{\"last_stop_time\":\"" + FormatTime(lastStopTime) + "\",\"cooldown_minutes\":" + CooldownMinutes + "}");
            }
            return MakeGate(true, "cooldown_after_stop", null, null, null);
        }

        private GateResult GateMaxSignals()
        {
            if (signalsToday >= MaxSignalsPerDay)
                return MakeGate(false, "max_signals_per_day",
                    string.Format(CultureInfo.InvariantCulture,
                        "{0} signals today >= max {1}", signalsToday, MaxSignalsPerDay),
                    null,
                    "{\"signals_today\":" + signalsToday + "}");
            return MakeGate(true, "max_signals_per_day", null, null, null);
        }

        private GateResult GatePositionState()
        {
            if (signalState == InternalSignalState.Active)
                return MakeGate(false, "position_already_active",
                    "internal Active state; one-position policy", null, null);

            // Cross-check with broker for safety.
            try
            {
                if (Account != null)
                {
                    var pos = Account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == Instrument.FullName);
                    if (pos != null && pos.MarketPosition != MarketPosition.Flat)
                        return MakeGate(false, "position_already_active",
                            "broker position " + pos.MarketPosition + " qty " + pos.Quantity,
                            null, null);
                }
            }
            catch (Exception ex) { EmitError("gate_position_query_failed", ex); }

            return MakeGate(true, "position_state", null, null, null);
        }

        private GateResult GateMargin(ScorerDecision d)
        {
            int qty = SizeBucketToQty(d.SizeBucket);
            double estMargin = qty * MarginPerMesContractDollars;
            double available = double.MaxValue;
            try
            {
                if (Account != null)
                    available = Account.Get(AccountItem.BuyingPower, Currency.UsDollar);
            }
            catch { available = double.MaxValue; }
            if (available < estMargin)
                return MakeGate(false, "insufficient_margin",
                    string.Format(CultureInfo.InvariantCulture,
                        "available {0:F2} < est {1:F2}", available, estMargin),
                    null, null);
            return MakeGate(true, "margin_guard", null, null, null);
        }

        private GateResult GateHoliday()
        {
            DateTime today = Times[idx1Min][0].Date;
            if (FullCloseHolidays2026.Contains(today))
                return MakeGate(false, "holiday_blackout",
                    "full-close holiday: " + today.ToString("yyyy-MM-dd"), null, null);
            if (EarlyCloseHolidays2026.Contains(today))
            {
                // Override close time effectively: emit warning + tighten gate.
                int curMins = Times[idx1Min][0].Hour * 60 + Times[idx1Min][0].Minute;
                int earlyClose = 13 * 60;   // 13:00 ET typical
                if (curMins > earlyClose - EntryCutoffMinutesBeforeClose)
                    return MakeGate(false, "early_close_window",
                        "early-close day; past 13:00 cutoff", null, null);
            }
            return MakeGate(true, "holiday", null, null, null);
        }

        private GateResult GateConnection()
        {
            if (!dataFeedConnected || !orderFeedConnected)
                return MakeGate(false, "connection_error",
                    "data=" + dataFeedConnected + " order=" + orderFeedConnected, null, null);

            // Stale check on data feed.
            DateTime now = Times[idx1Min][0];
            if (lastBarUpdateTime != DateTime.MinValue &&
                (now - lastBarUpdateTime).TotalSeconds > ConnectionStaleSeconds)
                return MakeGate(false, "connection_stale",
                    string.Format(CultureInfo.InvariantCulture,
                        "data feed stale {0}s", (int)(now - lastBarUpdateTime).TotalSeconds),
                    null, null);

            return MakeGate(true, "connection", null, null, null);
        }

        private GateResult GateHeartbeat()
        {
            DateTime now = Times[idx1Min][0];
            if (lastBarUpdateTime != DateTime.MinValue &&
                (now - lastBarUpdateTime).TotalSeconds > HeartbeatStaleSeconds)
                return MakeGate(false, "heartbeat_gap",
                    string.Format(CultureInfo.InvariantCulture,
                        "no bar update for {0}s", (int)(now - lastBarUpdateTime).TotalSeconds),
                    null, null);
            return MakeGate(true, "heartbeat", null, null, null);
        }

        private GateResult MakeGate(bool allowed, string name, string reason, DateTime? recoverable, string snapshot)
        {
            return new GateResult
            {
                Allowed = allowed,
                GateName = name,
                Reason = reason,
                RecoverableUntil = recoverable,
                StateSnapshotJson = snapshot
            };
        }

        // =====================================================================
        // L3 — Reconciliation (architect INV-L3-4)
        // =====================================================================
        private void ReconcileBrokerVsInternal()
        {
            try
            {
                if (Account == null) return;
                var pos = Account.Positions.FirstOrDefault(p => p.Instrument != null && p.Instrument.FullName == Instrument.FullName);
                int brokerQty = (pos != null && pos.MarketPosition != MarketPosition.Flat) ? pos.Quantity : 0;

                int expectedQty = (signalState == InternalSignalState.Active && currentSignal != null)
                    ? currentSignal.SizeQty : 0;

                if (brokerQty != expectedQty)
                {
                    if (!haltDueToDivergence)
                    {
                        EmitEvent("divergence",
                            "internal_state", signalState.ToString(),
                            "broker_position_qty", brokerQty.ToString(CultureInfo.InvariantCulture),
                            "expected_qty", expectedQty.ToString(CultureInfo.InvariantCulture),
                            "detected_at", FormatTime(Times[idx1Min][0]),
                            "action", "halt_new_submissions");
                        haltDueToDivergence = true;
                        PersistStateToJson("divergence");
                    }
                }
            }
            catch (Exception ex) { EmitError("reconcile_exception", ex); }
        }

        // =====================================================================
        // L3 — STATE PERSISTENCE (architect §8.4)
        // Atomic write: write tmp + rename. On read failure: defaults + warning.
        // =====================================================================

        private void EnsureSessionLogPaths()
        {
            try
            {
                string folder = Path.Combine(JsonlLogFolder ?? @"C:\seasonals\cockpit\sessions", sessionDate);
                Directory.CreateDirectory(folder);
                strategyEventsPath = Path.Combine(folder, instrumentRoot + "_strategy_events.jsonl");
                strategyStatePath  = Path.Combine(folder, instrumentRoot + "_strategy_state.json");
            }
            catch (Exception ex)
            {
                Print("[L2L3] EnsureSessionLogPaths failed: " + ex.Message);
            }
        }

        private void PersistStateToJson(string trigger)
        {
            if (string.IsNullOrEmpty(strategyStatePath)) return;
            try
            {
                var sb = new StringBuilder(2048);
                sb.Append('{');
                AppendField(sb, "schema_version", "v25.1", first: true);
                AppendField(sb, "session_date", sessionDate ?? "");
                AppendField(sb, "instrument", instrumentRoot ?? "");
                AppendField(sb, "last_updated", FormatTime(SafeBarTime()));
                AppendField(sb, "trigger", trigger ?? "");
                sb.Append(",\"counters\":{");
                AppendField(sb, "signals_today", signalsToday, first: true);
                AppendField(sb, "fills_today", fillsToday);
                AppendField(sb, "losing_trades_today", losingTradesToday);
                AppendField(sb, "winning_trades_today", winningTradesToday);
                AppendField(sb, "consecutive_stops", consecutiveStops);
                AppendField(sb, "realized_pnl_dollars_today", realizedPnlDollarsToday);
                sb.Append('}');
                sb.Append(",\"lockout\":{");
                AppendField(sb, "active", lockoutActive, first: true);
                AppendField(sb, "trigger", lockoutTrigger);
                AppendField(sb, "expires_at", lockoutActive ? FormatTime(lockoutExpiresAt) : null);
                sb.Append('}');
                sb.Append(",\"cooldown\":{");
                AppendField(sb, "active", cooldownActive, first: true);
                AppendField(sb, "last_stop_time", lastStopTime == DateTime.MinValue ? null : FormatTime(lastStopTime));
                AppendField(sb, "expires_at", cooldownActive ? FormatTime(cooldownExpiresAt) : null);
                sb.Append('}');
                sb.Append(",\"signal_state\":{");
                AppendField(sb, "current", signalState.ToString(), first: true);
                if (currentSignal != null)
                {
                    AppendField(sb, "signal_id", currentSignal.SignalId);
                    AppendField(sb, "direction", currentSignal.Direction);
                    AppendField(sb, "entry", currentSignal.EntryPrice);
                    AppendField(sb, "stop", currentSignal.StopPrice);
                    AppendField(sb, "target", currentSignal.TargetPrice);
                    AppendField(sb, "qty", currentSignal.SizeQty);
                    AppendField(sb, "filled", currentSignal.Filled);
                }
                sb.Append('}');
                AppendField(sb, "manual_kill_switch_active", manualKillSwitchActive);
                AppendField(sb, "halt_due_to_divergence", haltDueToDivergence);
                sb.Append('}');

                string tmp = strategyStatePath + ".tmp";
                File.WriteAllText(tmp, sb.ToString(), Encoding.UTF8);
                if (File.Exists(strategyStatePath)) File.Delete(strategyStatePath);
                File.Move(tmp, strategyStatePath);

                EmitEvent("state_persisted",
                    "path", strategyStatePath,
                    "trigger", trigger,
                    "size_bytes", sb.Length.ToString(CultureInfo.InvariantCulture));
            }
            catch (Exception ex)
            {
                Print("[L2L3] PersistStateToJson failed: " + ex.Message);
            }
        }

        private void TryRestoreStateFromJson()
        {
            if (string.IsNullOrEmpty(strategyStatePath) || !File.Exists(strategyStatePath))
            {
                EmitInfoEvent("warning", "msg", "state.json not found; defaults used");
                return;
            }
            try
            {
                string body = File.ReadAllText(strategyStatePath, Encoding.UTF8);
                string sd = ExtractString(body, "\"session_date\"");
                if (sd != null && sd != sessionDate)
                {
                    EmitInfoEvent("info", "msg",
                        "state.json from a previous session; not restoring counters",
                        "stored_date", sd, "current_date", sessionDate);
                    return;
                }
                signalsToday = (int)ExtractDouble(body, "\"signals_today\"", 0);
                fillsToday = (int)ExtractDouble(body, "\"fills_today\"", 0);
                losingTradesToday = (int)ExtractDouble(body, "\"losing_trades_today\"", 0);
                winningTradesToday = (int)ExtractDouble(body, "\"winning_trades_today\"", 0);
                consecutiveStops = (int)ExtractDouble(body, "\"consecutive_stops\"", 0);
                realizedPnlDollarsToday = ExtractDouble(body, "\"realized_pnl_dollars_today\"", 0);
                lockoutActive = ExtractBool(body, "\"active\"");   // first 'active' is lockout
                manualKillSwitchActive = body.IndexOf("\"manual_kill_switch_active\":true", StringComparison.Ordinal) >= 0;
                EmitInfoEvent("info", "msg", "state.json restored",
                    "signals_today", signalsToday.ToString(CultureInfo.InvariantCulture),
                    "fills_today", fillsToday.ToString(CultureInfo.InvariantCulture));
            }
            catch (Exception ex)
            {
                EmitInfoEvent("warning", "msg", "state.json restore failed",
                    "exception", ex.GetType().Name);
            }
        }

        // =====================================================================
        // L3 — MANUAL KILL SWITCH (UI button + F12 hotkey, architect §8.7)
        // The keyboard hook lives on the chart's UI thread; we register it
        // in DataLoaded via ChartControl.Dispatcher and unregister in Terminated.
        // =====================================================================

        public void ActivateManualKillSwitch()
        {
            // 1. Cancel all live orders.
            if (currentSignal != null)
            {
                try
                {
                    if (currentSignal.EntryOrder != null && currentSignal.EntryOrder.OrderState == OrderState.Working)
                        CancelOrder(currentSignal.EntryOrder);
                    if (currentSignal.StopOrder != null && currentSignal.StopOrder.OrderState == OrderState.Working)
                        CancelOrder(currentSignal.StopOrder);
                    if (currentSignal.TargetOrder != null && currentSignal.TargetOrder.OrderState == OrderState.Working)
                        CancelOrder(currentSignal.TargetOrder);
                }
                catch (Exception ex) { EmitError("kill_cancel_failed", ex); }
            }

            // 2. Set persistent kill flag.
            manualKillSwitchActive = true;

            // 3. Emit abstain (architect 8.7).
            EmitEvent("manual_kill_switch_activated",
                "activated_at", FormatTime(Times[idx1Min][0]),
                "operator", Environment.UserName ?? "unknown");

            // 4. Banner: drawn via Draw API on the chart.
            try
            {
                Draw.TextFixed(this, "AM_KILL_BANNER",
                    "MANUAL KILL ACTIVE — F12 to resume",
                    TextPosition.TopRight,
                    Brushes.White, new SimpleFont("Arial", 14) { Bold = true },
                    Brushes.Black, Brushes.DarkRed, 90);
            }
            catch (Exception ex) { EmitInfoEvent("warning", "msg", "banner draw failed", "exception", ex.Message); }

            PersistStateToJson("manual_kill");
        }

        public void ResumeAfterKillSwitch()
        {
            manualKillSwitchActive = false;
            EmitEvent("manual_kill_switch_resumed",
                "resumed_at", FormatTime(Times[idx1Min][0]),
                "operator", Environment.UserName ?? "unknown");
            try { RemoveDrawObject("AM_KILL_BANNER"); }
            catch { /* swallow */ }
            PersistStateToJson("manual_resume");
        }

        // =====================================================================
        // EVENT EMISSION (architect §3 + INV-L1-1 / INV-L2-1)
        // Single emitter for: signals, abstains, fills, exits, errors.
        // Format: one JSONL record per event, schema_version v25.1.
        // =====================================================================

        private void EmitSignal(ActiveSignal s)
        {
            EmitEvent("signal",
                "signal_id", s.SignalId,
                "candidate_id", s.CandidateId,
                "direction", s.Direction,
                "entry_price", s.EntryPrice.ToString("R", CultureInfo.InvariantCulture),
                "stop_price",  s.StopPrice.ToString("R", CultureInfo.InvariantCulture),
                "first_target_price", s.TargetPrice.ToString("R", CultureInfo.InvariantCulture),
                "pattern_type", s.PatternType,
                "level_name", s.LevelName,
                "size_qty", s.SizeQty.ToString(CultureInfo.InvariantCulture),
                "p_win", s.Decision.PWin.ToString("R", CultureInfo.InvariantCulture),
                "expected_R", s.Decision.ExpectedR.ToString("R", CultureInfo.InvariantCulture),
                "confidence", s.Decision.Confidence.ToString("R", CultureInfo.InvariantCulture),
                "size_bucket", s.Decision.SizeBucket,
                "target_choice", s.Decision.TargetChoice,
                "scorer_mode", s.Decision.ScorerMode);

            // Visual marker on chart (architect: green triangle for fired signals).
            try
            {
                string tag = "AM_SIG_" + s.SignalId;
                if (s.Direction == "LONG")
                    Draw.TriangleUp(this, tag, true, 0, s.EntryPrice - 0.5, Brushes.LimeGreen);
                else
                    Draw.TriangleDown(this, tag, true, 0, s.EntryPrice + 0.5, Brushes.LimeGreen);
            }
            catch (Exception ex) { EmitInfoEvent("warning", "msg", "signal marker failed", "exception", ex.Message); }
        }

        private void EmitAbstain(CandidateEvent c, string layer, string gate, string reason,
            ScorerDecision d, DateTime? recoverableUntil)
        {
            EmitEvent("abstain",
                "candidate_id", c != null ? c.CandidateId : "?",
                "layer", layer,
                "gate_name", gate,
                "reason", reason,
                "recoverable_until_time", recoverableUntil.HasValue ? FormatTime(recoverableUntil.Value) : null,
                "p_win", d.PWin.ToString("R", CultureInfo.InvariantCulture),
                "expected_R", d.ExpectedR.ToString("R", CultureInfo.InvariantCulture),
                "confidence", d.Confidence.ToString("R", CultureInfo.InvariantCulture),
                "scorer_mode", d.ScorerMode);

            // Red triangle for L3 abstains (visible on chart so operator sees blocks).
            if (layer == "L3" && c != null)
            {
                try
                {
                    string tag = "AM_ABSTAIN_" + (c.CandidateId ?? Guid.NewGuid().ToString("N"));
                    if (c.Direction == "LONG")
                        Draw.TriangleUp(this, tag, true, 0, c.LevelPrice - 0.25, Brushes.Red);
                    else
                        Draw.TriangleDown(this, tag, true, 0, c.LevelPrice + 0.25, Brushes.Red);
                }
                catch { /* draw best-effort */ }
            }
        }

        private void EmitDecisionResponse(CandidateEvent c, ScorerDecision d)
        {
            EmitEvent("decision_response",
                "candidate_id", c.CandidateId,
                "predicted_R", d.ExpectedR.ToString("R", CultureInfo.InvariantCulture),
                "p_win", d.PWin.ToString("R", CultureInfo.InvariantCulture),
                "confidence", d.Confidence.ToString("R", CultureInfo.InvariantCulture),
                "size_bucket", d.SizeBucket,
                "target_choice", d.TargetChoice,
                "scorer_mode", d.ScorerMode,
                "abstain_reason", d.AbstainReason);
        }

        private void EmitHeartbeat()
        {
            EmitEvent("heartbeat",
                "signals_today", signalsToday.ToString(CultureInfo.InvariantCulture),
                "fills_today", fillsToday.ToString(CultureInfo.InvariantCulture),
                "realized_pnl_dollars_today", realizedPnlDollarsToday.ToString("R", CultureInfo.InvariantCulture),
                "in_lockout", lockoutActive ? "true" : "false",
                "in_cooldown", cooldownActive ? "true" : "false",
                "signal_state", signalState.ToString(),
                "manual_kill", manualKillSwitchActive ? "true" : "false",
                "halt_due_to_divergence", haltDueToDivergence ? "true" : "false");
        }

        private void EmitError(string msg, Exception ex)
        {
            EmitEvent("error",
                "msg", msg,
                "exception", ex != null ? ex.GetType().Name : "?",
                "exception_msg", ex != null ? ex.Message : "",
                "stack_trace", ex != null ? (ex.StackTrace ?? "") : "",
                "bar_time", FormatTime(SafeBarTime()));
        }

        /// <summary>
        /// Returns Times[idx1Min][0] when the bar buffer is populated; falls
        /// back to DateTime.UtcNow during early lifecycle states (SetDefaults,
        /// State.Configure) when bar arrays are not yet available. NT8's
        /// `Times[idx][0]` access throws if the bar series isn't ready.
        /// </summary>
        private DateTime SafeBarTime()
        {
            try
            {
                if (Times != null && Times.Length > idx1Min &&
                    BarsArray != null && BarsArray.Length > idx1Min &&
                    BarsArray[idx1Min] != null && BarsArray[idx1Min].Count > 0 &&
                    CurrentBars != null && idx1Min < CurrentBars.Length && CurrentBars[idx1Min] >= 0)
                {
                    return Times[idx1Min][0];
                }
            }
            catch { /* swallow — return UtcNow fallback */ }
            return DateTime.UtcNow;
        }

        private void EmitInfoEvent(string type, params object[] kv)
        {
            EmitEvent(type, kv);
        }

        /// <summary>
        /// Single emit point. Builds a JSONL line with the standard envelope
        /// (architect §3 envelope: t, type, schema_version, instrument,
        /// session_date, payload). All event payload fields are passed as
        /// alternating (key, value) varargs.
        /// </summary>
        private void EmitEvent(string type, params object[] kv)
        {
            if (string.IsNullOrEmpty(strategyEventsPath)) return;
            try
            {
                DateTime t = SafeBarTime();
                var sb = new StringBuilder(384);
                sb.Append('{');
                AppendField(sb, "t", FormatTime(t), first: true);
                AppendField(sb, "type", type);
                AppendField(sb, "schema_version", "v25.1");
                AppendField(sb, "instrument", Instrument != null ? Instrument.FullName : "?");
                AppendField(sb, "session_date", sessionDate ?? "");
                sb.Append(",\"payload\":{");
                bool firstKv = true;
                for (int i = 0; i + 1 < kv.Length; i += 2)
                {
                    string k = kv[i] != null ? kv[i].ToString() : "";
                    object v = kv[i + 1];
                    AppendKvAuto(sb, k, v, firstKv);
                    firstKv = false;
                }
                sb.Append('}');
                sb.Append('}');
                sb.Append('\n');

                File.AppendAllText(strategyEventsPath, sb.ToString(), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Print("[L2L3] EmitEvent failed: " + ex.Message);
            }
        }

        private static void AppendKvAuto(StringBuilder sb, string key, object value, bool first)
        {
            if (!first) sb.Append(',');
            AppendJsonString(sb, key);
            sb.Append(':');
            if (value == null) { sb.Append("null"); return; }
            if (value is bool)        { sb.Append((bool)value ? "true" : "false"); return; }
            if (value is int)         { sb.Append(((int)value).ToString(CultureInfo.InvariantCulture)); return; }
            if (value is long)        { sb.Append(((long)value).ToString(CultureInfo.InvariantCulture)); return; }
            if (value is double)
            {
                double dv = (double)value;
                if (double.IsNaN(dv) || double.IsInfinity(dv)) sb.Append("null");
                else sb.Append(dv.ToString("R", CultureInfo.InvariantCulture));
                return;
            }
            AppendJsonString(sb, value.ToString());
        }

        // =====================================================================
        // EVENT SUBSCRIPTION TO HOSTED INDICATOR
        // ---------------------------------------------------------------------
        // Architect spec §7.1: L2 subscribes to L1's OnCandidate (canonical
        // channel) for the full feature-vector payload, plus OnBoxCapture for
        // master-candle anchor synchronization, plus OnAbstain for L1's
        // fail-open visibility into RTH-window and warmup skips.
        //
        // We translate AMTradeCockpitV2_5.CandidateEventArgs → strategy-side
        // CandidateEvent so the existing scorer + ranker + L3 gate code path
        // remains untouched (architect §7.5 ranking logic preserved).
        //
        // The OnTouch / OnSignal bridge (V2_4 era) is retained ONLY as a
        // defensive fallback in case a future V2_5 build re-exposes those
        // events. V2_5 today emits OnCandidate exclusively; the legacy hooks
        // wire up but never fire.
        // =====================================================================

        private void SubscribeToCockpitEvents()
        {
            if (cockpit == null) return;

            // Canonical V2_5 events (architect §3.3, §7.1).
            cockpit.OnCandidate  += HandleCockpitCandidate;
            cockpit.OnBoxCapture += HandleCockpitBoxCapture;
            cockpit.OnAbstain    += HandleCockpitAbstain;

            // Defensive legacy bridge — see method header. V2_5 marks these
            // [Obsolete] and never fires them; still wire so a downgraded
            // indicator wouldn't silently lose candidates.
            #pragma warning disable 0618 // intentional use of obsolete event
            cockpit.OnTouch  += HandleLegacyTouch;
            cockpit.OnSignal += HandleLegacySignal;
            #pragma warning restore 0618
        }

        private void UnsubscribeFromCockpitEvents()
        {
            if (cockpit == null) return;
            try { cockpit.OnCandidate  -= HandleCockpitCandidate;  } catch { }
            try { cockpit.OnBoxCapture -= HandleCockpitBoxCapture; } catch { }
            try { cockpit.OnAbstain    -= HandleCockpitAbstain;    } catch { }
            #pragma warning disable 0618
            try { cockpit.OnTouch  -= HandleLegacyTouch;  } catch { }
            try { cockpit.OnSignal -= HandleLegacySignal; } catch { }
            #pragma warning restore 0618
        }

        // -------------------------------------------------------------------
        // CANONICAL V2_5 EVENT HANDLERS
        // -------------------------------------------------------------------

        /// <summary>
        /// Translates V2_5's CandidateEventArgs (full feature vector dict)
        /// into the strategy-side CandidateEvent / FeatureVector struct that
        /// the heuristic scorer expects. Field mapping mirrors architect §3.3.
        /// </summary>
        private void HandleCockpitCandidate(AMTradeCockpitV2_5.CandidateEventArgs args)
        {
            try
            {
                var c = TranslateCandidate(args);
                if (c != null) OnL1Candidate(c);
            }
            catch (Exception ex)
            {
                EmitError("on_l1_candidate_translate_exception", ex);
            }
        }

        /// <summary>
        /// Mirror of L1 box_capture for downstream state sync (architect §7).
        /// V1 logs only; future V2 may use this to invalidate stale anchors
        /// or to propagate MOC validation into L3 sizing decisions in real
        /// time without re-reading the JSONL stream.
        /// </summary>
        private void HandleCockpitBoxCapture(AMTradeCockpitV2_5.BoxCaptureEventArgs e)
        {
            try
            {
                EmitInfoEvent("l1_box_capture",
                    "name", e.Name,
                    "subtype", e.Subtype ?? "",
                    "instance_day_offset", e.InstanceDayOffset.ToString(CultureInfo.InvariantCulture),
                    "high", e.High.ToString("R", CultureInfo.InvariantCulture),
                    "low",  e.Low.ToString("R",  CultureInfo.InvariantCulture),
                    "is_institutional_now", e.IsInstitutionalNow ? "true" : "false",
                    "moc_state", e.MocState ?? "");
            }
            catch (Exception ex) { EmitError("on_l1_box_capture_exception", ex); }
        }

        /// <summary>
        /// Mirror of L1's pre-warmup / outside-RTH abstain. We do not propagate
        /// this to L3 (it's an L1 self-abstain, not a candidate-triggered
        /// abstain); we just log so the JSONL stream is complete.
        /// </summary>
        private void HandleCockpitAbstain(AMTradeCockpitV2_5.AbstainEventArgs e)
        {
            try
            {
                EmitInfoEvent("l1_abstain",
                    "layer",       e.Layer ?? "L1",
                    "reason",      e.Reason ?? "",
                    "bar_time",    FormatTime(e.BarTime),
                    "candidate_id", e.CandidateId ?? "",
                    "gate_name",   e.GateName ?? "");
            }
            catch (Exception ex) { EmitError("on_l1_abstain_exception", ex); }
        }

        /// <summary>
        /// Build a strategy-side CandidateEvent from V2_5's CandidateEventArgs.
        /// V2_5's Features dict is keyed by the architect-§3.3 names ("day_type_v2_3node",
        /// "moc_ratio", etc.). We project the subset the scorer reads into
        /// the strongly-typed FeatureVector. Missing keys leave defaults.
        /// </summary>
        private CandidateEvent TranslateCandidate(AMTradeCockpitV2_5.CandidateEventArgs a)
        {
            if (a == null) return null;
            var c = new CandidateEvent
            {
                CandidateId       = a.CandidateId,
                LevelName         = a.LevelName,
                LevelPrice        = a.LevelPrice,
                IsPermissionLevel = a.IsPermissionLevel,
                Direction         = a.Direction,
                PatternType       = a.PatternType,
                LwsState          = a.LwsState,
                BarTime           = a.BarTime,
                BarOpen           = a.BarOpen,
                BarHigh           = a.BarHigh,
                BarLow            = a.BarLow,
                BarClose          = a.BarClose,
                BarVolume         = (long)a.BarVolume,
                SessionDate       = a.SessionDate
            };

            var f = a.Features;
            // Stop / target proposals from feature vector (V2_5 BuildFeatureVector §3.3).
            double stopProp = ReadDouble(f, "stop_dist_proposal_pts", double.NaN);
            double tgt100   = ReadDouble(f, "target_fib_100_pts",     double.NaN);
            double tgt150   = ReadDouble(f, "target_fib_150_pts",     double.NaN);
            double tgt200   = ReadDouble(f, "target_fib_200_pts",     double.NaN);
            double tgt250   = ReadDouble(f, "target_fib_250_pts",     double.NaN);
            double anchorWidth = Math.Max(0.5, Math.Abs(a.BarHigh - a.BarLow));
            c.StopDistanceSuggestionPts = !double.IsNaN(stopProp) && stopProp > 0 ? stopProp : anchorWidth;
            c.FirstTargetPts            = !double.IsNaN(tgt100) && tgt100 > 0 ? tgt100 : anchorWidth;
            c.RunnerTargets = new RunnerTargetOptions
            {
                LevelToLevelNextPts = !double.IsNaN(tgt200) ? tgt200 : c.FirstTargetPts * 2.0,
                Fib150PctPts = !double.IsNaN(tgt150) ? tgt150 : c.FirstTargetPts * 1.5,
                Fib200PctPts = !double.IsNaN(tgt200) ? tgt200 : c.FirstTargetPts * 2.0,
                Fib250PctPts = !double.IsNaN(tgt250) ? tgt250 : c.FirstTargetPts * 2.5
            };

            var fv = c.Features;
            // Day-type
            fv.DayTypeV2_3node = ReadString(f, "day_type_v2_3node", "Unknown");
            fv.DayTypeV2_4node = ReadString(f, "day_type_v2_4node", "Unknown");
            fv.BodyOverlapAB   = ReadBool(f, "body_overlap_AB");
            fv.BodyOverlapBC   = ReadBool(f, "body_overlap_BC");
            fv.BodyOverlapCD   = ReadBool(f, "body_overlap_CD");
            fv.LargeWickA      = ReadBool(f, "large_wick_flag_A");
            fv.LargeWickB      = ReadBool(f, "large_wick_flag_B");
            fv.LargeWickC      = ReadBool(f, "large_wick_flag_C");
            fv.LargeWickD      = ReadBool(f, "large_wick_flag_D");

            // SMA200 slope
            fv.Sma200SlopeAvailable = ReadBool(f, "sma200_slope_available");
            fv.Sma200SlopeDeltaPts  = ReadDouble(f, "sma200_slope_delta_pts", double.NaN);
            fv.Sma200SlopeSign      = ReadString(f, "sma200_slope_sign", "Flat");

            // SMA50_30
            fv.Sma50_30SlopeAvailable = ReadBool(f, "sma50_30_slope_available");
            fv.Sma50_30SlopePts       = ReadDouble(f, "sma50_30_slope_pts", double.NaN);

            // MOC
            fv.MocRatio         = ReadDouble(f, "moc_ratio", double.NaN);
            fv.MocState         = ReadString(f, "moc_state", "Pending");
            fv.MocObservedToday = ReadBool(f, "moc_observed_today");

            // VWAP
            fv.VwapPrice         = ReadDouble(f, "vwap_price",        double.NaN);
            fv.VwapSlope         = ReadString(f, "vwap_slope",        "Flat");
            fv.DistToVwapPts     = ReadDouble(f, "dist_to_vwap_pts",  double.NaN);
            fv.DistToAnchVwapPts = ReadDouble(f, "dist_to_anchvwap_pts", double.NaN);

            // R3/R4/S3/S4 distances
            fv.DistToR3 = ReadDouble(f, "dist_to_r3", double.NaN);
            fv.DistToR4 = ReadDouble(f, "dist_to_r4", double.NaN);
            fv.DistToS3 = ReadDouble(f, "dist_to_s3", double.NaN);
            fv.DistToS4 = ReadDouble(f, "dist_to_s4", double.NaN);

            // Cluster / confluence
            fv.NumLevelsInCluster      = ReadInt(f,  "num_levels_in_cluster", 1);
            fv.IsHighestVolumeInCluster = ReadBool(f, "is_highest_volume_in_cluster");
            fv.ConfluenceCount         = ReadInt(f,  "confluence_count", 0);

            // Bar shape
            fv.BodyPct         = ReadDouble(f, "body_pct", double.NaN);
            fv.CandleDirection = ReadString(f, "candle_direction", "Up");

            // Latch / retrace
            fv.RetraceSide         = ReadBool(f, "retrace_side");
            fv.RetraceSideAtOpen   = ReadBool(f, "retrace_side_at_open");
            fv.AlreadyTouchedToday = ReadBool(f, "already_touched_today");

            // Time / DOW
            fv.MinutesSinceRthOpen  = ReadInt(f, "minutes_since_rth_open", 0);
            fv.MinutesUntilRthClose = ReadInt(f, "minutes_until_rth_close", 0);
            fv.HourEt               = ReadInt(f, "hour_et", a.BarTime.Hour);
            fv.DayOfWeek            = ReadString(f, "day_of_week", a.BarTime.DayOfWeek.ToString());

            // Volume context
            fv.VolZScoreVsSession        = ReadDouble(f, "vol_zscore_vs_session", 0);
            fv.FirstMinVolumePctOfNormal = ReadDouble(f, "first_1min_volume_pct_of_normal", 1.0);

            // ADR / volatility
            fv.Adr20dPts      = ReadDouble(f, "adr_20d_pts",       double.NaN);
            fv.EuropeWidthPts = ReadDouble(f, "europe_width_pts",  double.NaN);

            // News-wick
            fv.NewsWickActiveToday = ReadBool(f, "news_wick_active_today");
            fv.NewsWickDistancePts = ReadDouble(f, "news_wick_distance_pts", double.NaN);

            return c;
        }

        // -------------------------------------------------------------------
        // FEATURE-DICT SAFE READERS
        //   V2_5 emits Dictionary<string,object> with values that may be null
        //   (architect §3.3 sentinel for unavailable). These accessors clamp
        //   to typed defaults so the scorer never NPEs on missing keys.
        // -------------------------------------------------------------------

        private static double ReadDouble(IDictionary<string, object> d, string key, double fallback)
        {
            if (d == null) return fallback;
            object v;
            if (!d.TryGetValue(key, out v) || v == null) return fallback;
            try
            {
                if (v is double)  return (double)v;
                if (v is float)   return (double)(float)v;
                if (v is int)     return (double)(int)v;
                if (v is long)    return (double)(long)v;
                if (v is decimal) return (double)(decimal)v;
                double parsed;
                return double.TryParse(v.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out parsed)
                    ? parsed : fallback;
            }
            catch { return fallback; }
        }

        private static int ReadInt(IDictionary<string, object> d, string key, int fallback)
        {
            if (d == null) return fallback;
            object v;
            if (!d.TryGetValue(key, out v) || v == null) return fallback;
            try
            {
                if (v is int)    return (int)v;
                if (v is long)   return (int)(long)v;
                if (v is double) return (int)(double)v;
                int parsed;
                return int.TryParse(v.ToString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed)
                    ? parsed : fallback;
            }
            catch { return fallback; }
        }

        private static bool ReadBool(IDictionary<string, object> d, string key)
        {
            if (d == null) return false;
            object v;
            if (!d.TryGetValue(key, out v) || v == null) return false;
            if (v is bool) return (bool)v;
            string s = v.ToString();
            return string.Equals(s, "true", StringComparison.OrdinalIgnoreCase)
                || s == "1";
        }

        private static string ReadString(IDictionary<string, object> d, string key, string fallback)
        {
            if (d == null) return fallback;
            object v;
            if (!d.TryGetValue(key, out v) || v == null) return fallback;
            return v.ToString();
        }

        // -------------------------------------------------------------------
        // DEPRECATED LEGACY BRIDGE (V2_4 OnTouch / OnSignal)
        //
        // V2_5 [Obsolete]-marks OnTouch / OnSignal and never fires them. This
        // shim lives on as defensive code in case a downgraded indicator is
        // hosted; it forwards into the same OnL1Candidate() entry point. New
        // development should target HandleCockpitCandidate() above.
        // -------------------------------------------------------------------

        #pragma warning disable 0618 // legacy types kept for fallback
        private void HandleLegacyTouch(AMTradeCockpitV2_5.TouchEventArgs e)
        {
            // Build a synthetic CandidateEvent. Populates only the features the
            // legacy event carries; the scorer uses fail-open weighting for
            // missing fields (architect §2.2). PREFER HandleCockpitCandidate.
            var c = new CandidateEvent
            {
                CandidateId = string.Format(CultureInfo.InvariantCulture,
                    "{0}_{1:yyyyMMdd}_{1:HHmm}_{2}_{3}_LEGACY",
                    instrumentRoot, e.EventTs, e.Level, e.Direction),
                LevelName = e.Level,
                LevelPrice = e.LevelPrice,
                IsPermissionLevel = (e.Level == "VWAP" || e.Level == "AnchVWAP"),
                Direction = e.Direction,
                PatternType = "A",  // legacy emits Pattern A only
                LwsState = null,
                BarTime = e.EventTs,
                BarOpen = e.BarOpen, BarHigh = e.BarHigh, BarLow = e.BarLow, BarClose = e.BarClose,
                BarVolume = 0,
                StopDistanceSuggestionPts = Math.Max(0.5, Math.Abs(e.BarHigh - e.BarLow)),
                FirstTargetPts = Math.Max(0.5, Math.Abs(e.BarHigh - e.BarLow)),
                SessionDate = e.SessionDate
            };
            c.RunnerTargets = new RunnerTargetOptions
            {
                LevelToLevelNextPts = c.FirstTargetPts * 2.0,
                Fib150PctPts = c.FirstTargetPts * 1.5,
                Fib200PctPts = c.FirstTargetPts * 2.0,
                Fib250PctPts = c.FirstTargetPts * 2.5
            };
            // Best-effort feature population from legacy event payload.
            c.Features.RetraceSide = e.RetraceSide;
            c.Features.AlreadyTouchedToday = e.AlreadyLatched;
            c.Features.HourEt = e.EventTs.Hour;
            c.Features.DayOfWeek = e.EventTs.DayOfWeek.ToString();
            c.Features.MinutesSinceRthOpen = Math.Max(0,
                (e.EventTs.Hour - RthOpenHourEt) * 60 + (e.EventTs.Minute - RthOpenMinuteEt));
            c.Features.MinutesUntilRthClose = Math.Max(0,
                (RthCloseHourEt - e.EventTs.Hour) * 60 + (RthCloseMinuteEt - e.EventTs.Minute));

            OnL1Candidate(c);
        }

        private void HandleLegacySignal(AMTradeCockpitV2_5.SignalEventArgs e)
        {
            // Legacy L1 'signal' — informational only; we score via candidates.
            EmitInfoEvent("l1_legacy_signal",
                "level", e.Level,
                "direction", e.Direction,
                "entry", e.Entry.ToString("R", CultureInfo.InvariantCulture),
                "stop", e.Stop.ToString("R", CultureInfo.InvariantCulture),
                "phase", e.Phase,
                "day_type", e.DayType);
        }
        #pragma warning restore 0618

        // =====================================================================
        // CONNECTION STATUS HOOKS
        // =====================================================================

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs connectionStatusUpdate)
        {
            try
            {
                // Track price/data feed status. PriceStatus is the futures data
                // feed; Status is the broker connection. Treat either drop as
                // a stop-trading signal — gate 10 evaluates them.
                bool wasDataConnected  = dataFeedConnected;
                bool wasOrderConnected = orderFeedConnected;
                dataFeedConnected  = (connectionStatusUpdate.PriceStatus == ConnectionStatus.Connected);
                orderFeedConnected = (connectionStatusUpdate.Status      == ConnectionStatus.Connected);

                if (wasDataConnected != dataFeedConnected)
                    EmitEvent(dataFeedConnected ? "connection_restored" : "connection_error",
                        "feed", "data",
                        "status", connectionStatusUpdate.PriceStatus.ToString());
                if (wasOrderConnected != orderFeedConnected)
                    EmitEvent(orderFeedConnected ? "connection_restored" : "connection_error",
                        "feed", "order",
                        "status", connectionStatusUpdate.Status.ToString());
            }
            catch (Exception ex) { EmitError("on_connection_status_exception", ex); }
        }

        // =====================================================================
        // JSON HELPERS (StringBuilder-based, no Newtonsoft — match V2_4 pattern)
        // =====================================================================

        private static void AppendField(StringBuilder sb, string name, string value, bool first = false)
        {
            if (!first) sb.Append(',');
            AppendJsonString(sb, name);
            sb.Append(':');
            if (value == null) sb.Append("null");
            else AppendJsonString(sb, value);
        }
        private static void AppendField(StringBuilder sb, string name, double value, bool first = false)
        {
            if (!first) sb.Append(',');
            AppendJsonString(sb, name);
            sb.Append(':');
            if (double.IsNaN(value) || double.IsInfinity(value)) sb.Append("null");
            else sb.Append(value.ToString("R", CultureInfo.InvariantCulture));
        }
        private static void AppendField(StringBuilder sb, string name, int value, bool first = false)
        {
            if (!first) sb.Append(',');
            AppendJsonString(sb, name);
            sb.Append(':');
            sb.Append(value.ToString(CultureInfo.InvariantCulture));
        }
        private static void AppendField(StringBuilder sb, string name, bool value, bool first = false)
        {
            if (!first) sb.Append(',');
            AppendJsonString(sb, name);
            sb.Append(':');
            sb.Append(value ? "true" : "false");
        }
        private static void AppendJsonString(StringBuilder sb, string s)
        {
            if (s == null) { sb.Append("null"); return; }
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"':  sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n");  break;
                    case '\r': sb.Append("\\r");  break;
                    case '\t': sb.Append("\\t");  break;
                    default:
                        if (c < ' ') sb.AppendFormat("\\u{0:X4}", (int)c);
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }

        private static double ExtractDouble(string body, string quotedName, double fallback)
        {
            if (string.IsNullOrEmpty(body)) return fallback;
            int i = body.IndexOf(quotedName, StringComparison.Ordinal);
            if (i < 0) return fallback;
            i = body.IndexOf(':', i);
            if (i < 0) return fallback;
            i++;
            while (i < body.Length && (body[i] == ' ' || body[i] == '\t')) i++;
            int j = i;
            while (j < body.Length)
            {
                char ch = body[j];
                if (ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\n' || ch == '\r' || ch == '\t') break;
                j++;
            }
            string token = body.Substring(i, j - i);
            if (token == "null" || token.Length == 0) return fallback;
            double v;
            return double.TryParse(token, NumberStyles.Float, CultureInfo.InvariantCulture, out v) ? v : fallback;
        }
        private static bool ExtractBool(string body, string quotedName)
        {
            if (string.IsNullOrEmpty(body)) return false;
            int i = body.IndexOf(quotedName, StringComparison.Ordinal);
            if (i < 0) return false;
            i = body.IndexOf(':', i);
            if (i < 0) return false;
            i++;
            while (i < body.Length && (body[i] == ' ' || body[i] == '\t')) i++;
            return i + 4 <= body.Length && string.Compare(body, i, "true", 0, 4, StringComparison.Ordinal) == 0;
        }
        private static string ExtractString(string body, string quotedName)
        {
            if (string.IsNullOrEmpty(body)) return null;
            int i = body.IndexOf(quotedName, StringComparison.Ordinal);
            if (i < 0) return null;
            i = body.IndexOf(':', i);
            if (i < 0) return null;
            i++;
            while (i < body.Length && (body[i] == ' ' || body[i] == '\t')) i++;
            if (i >= body.Length || body[i] != '"') return null;
            int end = body.IndexOf('"', i + 1);
            if (end < 0) return null;
            return body.Substring(i + 1, end - i - 1);
        }

        private static string FormatTime(DateTime t)
        {
            return t.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);
        }
    }
}

