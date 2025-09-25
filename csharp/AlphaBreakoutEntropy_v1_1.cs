using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui.NinjaScript;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>
    /// Public facing portion of the Alpha Breakout Entropy strategy. The
    /// proprietary entropy and resonance logic lives in a companion partial
    /// class so that sensitive details can be omitted from public builds.
    /// </summary>
    public partial class AlphaBreakoutEntropy_v1_1 : Strategy
    {
        private RSI rsi;
        private VWAP vwap;
        private EMA fastEma;
        private EMA slowEma;
        private ATR atr;
        private double lastEntropy;

        #region Parameters

        [Range(0.0, double.MaxValue)]
        public double EntryEntropyThreshold { get; set; } = 0.35;

        [Range(0.0, double.MaxValue)]
        public double ExitEntropyThreshold { get; set; } = 0.60;

        [Range(1, int.MaxValue)]
        public int EntropyLookback { get; set; } = 14;

        [Range(1, int.MaxValue)]
        public int RsiPeriod { get; set; } = 14;

        [Range(0.0, 100.0)]
        public double RsiLower { get; set; } = 35.0;

        [Range(0.0, 100.0)]
        public double RsiUpper { get; set; } = 65.0;

        [Range(1, int.MaxValue)]
        public int FastEmaPeriod { get; set; } = 21;

        [Range(1, int.MaxValue)]
        public int SlowEmaPeriod { get; set; } = 55;

        [Range(0.0, double.MaxValue)]
        public double VwapProximityATRs { get; set; } = 1.5;

        [Range(0.0, 100.0)]
        public double BaseRiskPct { get; set; } = 1.0;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "AlphaBreakoutEntropy_v1_1";
                Description = "Alpha breakout strategy with entropy-based gating.";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 50;
            }
            else if (State == State.DataLoaded)
            {
                rsi = RSI(Close, RsiPeriod, 3);
                vwap = VWAP(14);
                fastEma = EMA(Close, FastEmaPeriod);
                slowEma = EMA(Close, SlowEmaPeriod);
                atr = ATR(14);

                AddChartIndicator(rsi);
                AddChartIndicator(vwap);
                AddChartIndicator(fastEma);
                AddChartIndicator(slowEma);
                AddChartIndicator(atr);

                InitializePrivateResonance();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            lastEntropy = CalculatePrivateEntropy();

            // Entry Logic (delegating sensitive checks to private helpers)
            if (Position.MarketPosition == MarketPosition.Flat && lastEntropy <= EntryEntropyThreshold)
            {
                bool momentumAligned = fastEma[0] > slowEma[0];
                bool rsiWithinBand = rsi[0] >= RsiLower && rsi[0] <= RsiUpper;
                double vwapDelta = Math.Abs(Close[0] - vwap[0]);
                bool nearVwap = vwapDelta <= VwapProximityATRs * atr[0];

                if (momentumAligned && rsiWithinBand && nearVwap && IsPrivateEntryValid())
                {
                    int quantity = CalculatePositionSize();
                    if (quantity > 0)
                        EnterLong(quantity, "LongEntry");
                }
            }

            // Exit Logic (delegating to private validation for sensitive gates)
            if (Position.MarketPosition == MarketPosition.Long && lastEntropy >= ExitEntropyThreshold)
            {
                if (IsPrivateExitValid())
                    ExitLong("ExitEntropy");
            }
        }

        private int CalculatePositionSize()
        {
            double accountCash = 0.0;

            try
            {
                accountCash = Account?.Get(AccountItem.CashValue, Currency.UsDollar) ?? 0.0;
            }
            catch (Exception)
            {
                // Ignore account retrieval issues in public reference build.
            }

            if (accountCash <= 0.0 || atr == null)
                return 0;

            double riskPerContract = atr[0] * 1.5;
            if (riskPerContract <= 0.0)
                return 0;

            double capitalAtRisk = accountCash * (BaseRiskPct / 100.0);
            int quantity = (int)Math.Floor(capitalAtRisk / riskPerContract);
            return Math.Max(1, quantity);
        }
    }
}
