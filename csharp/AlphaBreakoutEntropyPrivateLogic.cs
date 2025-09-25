using System;
using NinjaTrader.NinjaScript.Strategies;

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>
    /// Proprietary logic for AlphaBreakoutEntropy_v1_1. These implementations
    /// are intentionally simplified placeholders to keep sensitive logic out of
    /// the public reference build.
    /// </summary>
    public partial class AlphaBreakoutEntropy_v1_1
    {
        private double CalculatePrivateEntropy()
        {
            // Placeholder implementation—replace with proprietary entropy logic
            // in internal builds. The public reference only exposes a stable
            // surface area for integration and testing.
            if (CurrentBar <= EntropyLookback)
                return 0.0;

            int lookback = Math.Min(EntropyLookback, CurrentBar);
            double[] returns = new double[lookback];
            for (int i = 0; i < lookback; i++)
            {
                returns[i] = Close[i] - Close[i + 1];
            }

            return PrivateLogic.CalculatePrivateEntropy(returns, lookback);
        }

        private void InitializePrivateResonance()
        {
            PrivateLogic.InitializeResonance();
            lastEntropy = 0.0;
        }

        private bool IsPrivateEntryValid()
        {
            return PrivateLogic.IsEntryValid();
        }

        private bool IsPrivateExitValid()
        {
            return PrivateLogic.IsExitValid();
        }
    }
}
