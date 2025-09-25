from pathlib import Path

from lab.adaptive.persistence import save_pickle, load_pickle
from lab.adaptive.online_learner import OnlineLearnerState


def test_pickled_state_roundtrip(tmp_path: Path):
    path = tmp_path / "state.pkl"
    state = OnlineLearnerState(
        params={"tilt": 0.5, "vol_target": 0.1},
        adapt_rate=0.02,
        bounds={"tilt": (0, 1), "vol_target": (0, 1)},
    )
    save_pickle(str(path), state)
    reloaded = load_pickle(str(path))
    assert reloaded.params == state.params

    reloaded.params["tilt"] = 0.6
    save_pickle(str(path), reloaded)
    mutated = load_pickle(str(path))
    assert mutated.params["tilt"] == 0.6
