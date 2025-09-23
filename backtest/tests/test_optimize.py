import pandas as pd

from backtest.core.strategy import BarStrategy
from backtest.optimize import grid_search, walk_forward


class ToyStrategy(BarStrategy):
    def warmup(self) -> int:  # pragma: no cover - trivial override
        return 0

    def on_bar(self, timestamp, row, index, broker):  # pragma: no cover - constant behaviour
        return 0


def test_grid_search_and_walk_forward_smoke():
    index = pd.date_range("2022-01-03", periods=780, freq="B")
    frame = pd.DataFrame({"close": 100.0}, index=index)

    grid = {"x": [1, 2]}
    Strat = lambda params: ToyStrategy(params)

    result = grid_search(frame, Strat, grid)
    assert not result.empty

    wf = walk_forward(frame, Strat, grid, train_years=1, test_years=1, step_years=1)
    assert not wf.empty
