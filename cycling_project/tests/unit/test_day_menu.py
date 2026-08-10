"""
Day-menu production module (prediction_tools/day_menu.py) — the retrieval-only
ranking channel wired for the Vuelta 2026 (Option A, 2026-08-09).

Covers the load-bearing invariants:
  - stored-parameter GMM assignment matches sklearn's predict exactly
  - as-of-then kernel discipline (a ride on the target date never feeds its
    own kernels; strictly-prior rides do)
  - exponential decay honors the 730-day half-life
  - unkeyed comps get NaN in every dtm_* column; one-day self-keyed comps
    get kernels but no fills
  - attachment is deterministic
  - board mixing blends ranking scores per-comp (never features) and a
    singleton key equals the direct single-key score
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.mixture import GaussianMixture

from cycling_project.prediction_tools.day_menu import (
    ARCH,
    DAY_MENU_FEATURE_COLS,
    DTM_FILL_COLS,
    DTM_KERNEL_COLS,
    EPOCH,
    GAMMA,
    HALF_LIFE_DAYS,
    DayMenu,
    assign_residual_items,
    attach_day_menu_features,
    attach_day_menu_serving,
    kernel_cumulants,
    mixed_ranking_scores,
    self_key_oneday,
    serving_board_scores,
)

pytestmark = pytest.mark.unit

SH15 = [f"top15_{a}" for a in ARCH]
SIGC = [f"sig_{a}" for a in ARCH]


def make_menu(canon_rows: dict) -> DayMenu:
    """Menu with the given canonicals and a trivial (unused) GMM."""
    canon = pd.DataFrame.from_dict(canon_rows, orient="index")
    canon.index.name = "item"
    for col in SIGC + ["sig_wg_prop"]:
        if col not in canon:
            canon[col] = 0.0
    canon["n_members"] = 10
    k = 2
    return DayMenu(
        version="test",
        canonicals=canon,
        gmm_means=np.zeros((k, 6)),
        gmm_covariances=np.stack([np.eye(6)] * k),
        gmm_weights=np.full(k, 0.5),
        labeler={"itt_seconds": 4500.0, "wide_bs_prop": 0.20,
                 "gc_top": 10, "unknown_junk": 0.20},
    )


@pytest.fixture
def menu():
    # Two sharply distinct composition items (a res_2-like and a res_3-like).
    return make_menu({
        "res_a": dict(zip(SIGC, [0.0, 0.5, 0.1, 0.2, 0.1, 0.1]),
                      sig_wg_prop=0.02),
        "res_b": dict(zip(SIGC, [0.6, 0.0, 0.1, 0.1, 0.1, 0.1]),
                      sig_wg_prop=0.10),
    })


def make_hist(rows):
    """rows: (rider_id, date, place_n, shares6)."""
    recs = []
    for rid, d, place, shares in rows:
        rec = {"rider_id": rid, "competition_id": 0, "comp_id": 0,
               "date": pd.Timestamp(d), "place_n": float(place),
               "top15": float(place <= 15), "top3": float(place <= 3)}
        rec.update(dict(zip(SH15, shares)))
        recs.append(rec)
    return pd.DataFrame(recs)


def make_frame(rows):
    """rows: (competition_id, rider_id, date, best_profile)."""
    recs = []
    for cid, rid, d, bp in rows:
        rec = {"competition_id": cid, "rider_id": rid,
               "competition_date": pd.Timestamp(d), "best_profile": bp}
        for a in ARCH:
            rec[f"{a}_avg_bucket"] = 3.0
        recs.append(rec)
    return pd.DataFrame(recs)


def field_shares_for(comp_ids):
    return pd.DataFrame(
        [{"comp_id": c, **{f"field_share_{a}": 1.0 / 6 for a in ARCH}}
         for c in comp_ids])


MOUNTAIN_DAY = [0.0, 0.5, 0.1, 0.2, 0.1, 0.1]   # == res_a canonical


class TestGMMAssignment:
    def test_matches_sklearn_predict(self):
        rng = np.random.default_rng(7)
        x = rng.dirichlet(np.ones(6), size=400)
        gm = GaussianMixture(3, covariance_type="full", random_state=0,
                             reg_covar=1e-5).fit(x)
        menu = DayMenu(
            version="t", canonicals=pd.DataFrame(),
            gmm_means=gm.means_, gmm_covariances=gm.covariances_,
            gmm_weights=gm.weights_, labeler={})
        test = rng.dirichlet(np.ones(6), size=200)
        got = assign_residual_items(test, menu)
        want = np.array([f"res_{i}" for i in gm.predict(test)])
        assert (got == want).all()


class TestKernels:
    def test_no_same_day_leak_strictly_prior_counts(self, menu):
        hist = make_hist([
            (1, "2024-05-01", 1, MOUNTAIN_DAY),
            (1, "2024-06-01", 1, MOUNTAIN_DAY),
        ])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([
            (100, 1, "2024-06-01", "mountain"),   # same day as 2nd ride
            (101, 1, "2024-06-02", "mountain"),   # strictly after
        ])
        key = pd.Series({100: "res_a", 101: "res_a"})
        out = attach_day_menu_features(
            frame, key, menu, cum, field_shares_for([100, 101]))
        e_same, e_after = out.dtm_k_expos.to_numpy()
        # same-day comp sees only the 2024-05-01 ride; the 06-01 ride is
        # excluded (allow_exact_matches=False)
        assert e_same < e_after
        assert e_same == pytest.approx(
            np.exp(-np.log(2) / HALF_LIFE_DAYS
                   * (pd.Timestamp("2024-06-01") - pd.Timestamp("2024-05-01")).days),
            rel=1e-9)

    def test_decay_half_life(self, menu):
        d0 = pd.Timestamp("2022-01-01")
        hist = make_hist([(1, d0, 1, MOUNTAIN_DAY)])
        cum = kernel_cumulants(hist, menu)
        target = d0 + pd.Timedelta(days=int(HALF_LIFE_DAYS))
        frame = make_frame([(100, 1, target, "mountain")])
        out = attach_day_menu_features(
            frame, pd.Series({100: "res_a"}), menu, cum,
            field_shares_for([100]))
        # perfect cosine (shares == canonical) so w = 1; one ride, half-life out
        assert out.dtm_k_expos.iloc[0] == pytest.approx(0.5, rel=1e-9)

    def test_thin_history_ratios_nan(self, menu):
        # expos < MIN_EFF_N -> ratio features masked
        hist = make_hist([(1, "2024-05-01", 1, MOUNTAIN_DAY)])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(100, 1, "2024-06-01", "mountain")])
        out = attach_day_menu_features(
            frame, pd.Series({100: "res_a"}), menu, cum,
            field_shares_for([100]))
        assert out.dtm_k_expos.iloc[0] > 0
        assert out[["dtm_k_attend", "dtm_k_top3", "dtm_k_perf_place"]] \
            .iloc[0].isna().all()


class TestAttachment:
    def test_unkeyed_comps_all_nan(self, menu):
        hist = make_hist([(1, "2024-05-01", 1, MOUNTAIN_DAY)] * 4)
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(100, 1, "2024-06-01", "mountain"),
                            (200, 1, "2024-06-01", "mountain")])
        out = attach_day_menu_features(
            frame, pd.Series({100: "res_a"}), menu, cum,
            field_shares_for([100, 200]))
        unkeyed = out[out.competition_id == 200]
        assert unkeyed[DAY_MENU_FEATURE_COLS].isna().all().all()
        keyed = out[out.competition_id == 100]
        assert keyed[DTM_FILL_COLS].notna().all().all()

    def test_oneday_self_key_kernels_only(self, menu):
        hist = make_hist([(1, f"2024-0{m}-01", 1, MOUNTAIN_DAY)
                          for m in range(1, 6)])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(300, 1, "2024-06-01", "mountain")])
        # comp 300 keyed (self-key) but NOT in stage_comps -> kernels, no fills
        out = attach_day_menu_features(
            frame, pd.Series({300: "res_a"}), menu, cum,
            field_shares_for([300]), stage_comps=set())
        row = out.iloc[0]
        assert row[DTM_FILL_COLS].isna().all()
        assert row["dtm_k_expos"] > 0

    def test_fill_values_are_canonical(self, menu):
        hist = make_hist([(1, "2024-05-01", 1, MOUNTAIN_DAY)])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(100, 1, "2024-06-01", "sprint")])
        out = attach_day_menu_features(
            frame, pd.Series({100: "res_b"}), menu, cum,
            field_shares_for([100]))
        row = out.iloc[0]
        assert row["dtm_sig_sprint"] == pytest.approx(0.6)
        assert row["dtm_sig_wg_prop"] == pytest.approx(0.10)
        # rider is a sprinter on a sprint-heavy item: share - field share
        assert row["dtm_rider_sig_share"] == pytest.approx(0.6)
        assert row["dtm_rider_sig_vs_field"] == pytest.approx(0.6 - 1 / 6)

    def test_deterministic(self, menu):
        hist = make_hist([(r, f"2024-0{m}-01", m, MOUNTAIN_DAY)
                          for r in (1, 2) for m in range(1, 6)])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(100, 1, "2024-06-01", "mountain"),
                            (100, 2, "2024-06-01", "sprint")])
        key = pd.Series({100: "res_a"})
        fs = field_shares_for([100])
        a = attach_day_menu_features(frame, key, menu, cum, fs)
        b = attach_day_menu_features(frame, key, menu, cum, fs)
        pd.testing.assert_frame_equal(a, b)


class TestSelfKey:
    def test_exact_canonical_maps_to_item(self, menu):
        od = pd.DataFrame([
            {"comp_id": 500, **dict(zip(SIGC, [0.0, 0.5, 0.1, 0.2, 0.1, 0.1]))},
            {"comp_id": 501, **dict(zip(SIGC, [0.6, 0.0, 0.1, 0.1, 0.1, 0.1]))},
        ])
        km = self_key_oneday(od, menu)
        assert km.loc[500] == "res_a"
        assert km.loc[501] == "res_b"

    def test_nan_signature_rows_dropped(self, menu):
        od = pd.DataFrame([{"comp_id": 502,
                            **dict(zip(SIGC, [np.nan] * 6))}])
        assert self_key_oneday(od, menu).empty


class _LinearBucket:
    """Ranking stub: score = 5 - dtm_sig_sprint (item-sensitive), NaN -> 5."""

    def predict_continuous(self, frame):
        v = frame["dtm_sig_sprint"].fillna(0.0).to_numpy(dtype=float)
        return 5.0 - v


class TestBoardMixing:
    def _setup(self, menu):
        hist = make_hist([(1, f"2024-0{m}-01", 1, MOUNTAIN_DAY)
                          for m in range(1, 6)])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(100, 1, "2024-06-10", "mountain"),
                            (200, 1, "2024-06-11", "mountain")])
        return cum, frame, field_shares_for([100, 200])

    def test_weighted_mix_blends_scores(self, menu):
        cum, frame, fs = self._setup(menu)
        bucket = _LinearBucket()
        mixed = mixed_ranking_scores(
            frame, bucket, {100: {"res_a": 0.6, "res_b": 0.4}},
            menu, cum, fs, stage_comps={100, 200})
        s_a = mixed_ranking_scores(frame, bucket, {100: {"res_a": 1.0}},
                                   menu, cum, fs, stage_comps={100, 200})
        s_b = mixed_ranking_scores(frame, bucket, {100: {"res_b": 1.0}},
                                   menu, cum, fs, stage_comps={100, 200})
        row = frame.competition_id == 100
        assert mixed[row.to_numpy()] == pytest.approx(
            0.6 * s_a[row.to_numpy()] + 0.4 * s_b[row.to_numpy()])
        # comp 200 has no key: identical (unkeyed) score in every run
        other = ~row.to_numpy()
        assert mixed[other] == pytest.approx(s_a[other])
        assert mixed[other] == pytest.approx(s_b[other])

    def test_weights_normalized_and_validated(self, menu):
        cum, frame, fs = self._setup(menu)
        bucket = _LinearBucket()
        a = mixed_ranking_scores(frame, bucket, {100: {"res_a": 2.0, "res_b": 2.0}},
                                 menu, cum, fs, stage_comps={100, 200})
        b = mixed_ranking_scores(frame, bucket, {100: {"res_a": 0.5, "res_b": 0.5}},
                                 menu, cum, fs, stage_comps={100, 200})
        np.testing.assert_allclose(a, b)
        with pytest.raises(ValueError):
            mixed_ranking_scores(frame, bucket, {100: {"nope": 1.0}},
                                 menu, cum, fs, stage_comps={100, 200})


class TestServing:
    """Serve-time attach must be feature-identical to the training attach —
    the train/serve skew guard for the retrieval channel."""

    FIELD_FEATURES = {  # 6 riders, one per archetype -> shares 1/6 each,
        "field_size": 6,  # matching field_shares_for in the training attach
        "sprinter_count": 1, "climber_count": 1, "hilly_specialist_count": 1,
        "rolling_specialist_count": 1, "breakaway_specialist_count": 1,
        "time_trialist_count": 1,
    }

    def _setup(self, menu):
        hist = make_hist([(1, f"2024-0{m}-01", 1, MOUNTAIN_DAY)
                          for m in range(1, 6)]
                         + [(2, "2024-03-01", 8, MOUNTAIN_DAY)])
        cum = kernel_cumulants(hist, menu)
        frame = make_frame([(100, 1, "2024-06-10", "mountain"),
                            (100, 2, "2024-06-10", "sprint")])
        return cum, frame

    def test_serve_attach_matches_training_attach(self, menu):
        cum, frame = self._setup(menu)
        trained = attach_day_menu_features(
            frame, pd.Series({100: "res_a"}), menu, cum,
            field_shares_for([100]))
        served = attach_day_menu_serving(
            frame, "res_a", menu, cum, self.FIELD_FEATURES, "2024-06-10")
        for col in DAY_MENU_FEATURE_COLS:
            np.testing.assert_allclose(
                trained[col].to_numpy(dtype=float),
                served[col].to_numpy(dtype=float),
                equal_nan=True, err_msg=col)

    def test_serving_scores_singleton_and_blend(self, menu):
        cum, frame = self._setup(menu)
        bucket = _LinearBucket()
        s_a = serving_board_scores(frame, bucket, {"res_a": 1.0}, menu, cum,
                                   self.FIELD_FEATURES, "2024-06-10")
        fr_a = attach_day_menu_serving(frame, "res_a", menu, cum,
                                       self.FIELD_FEATURES, "2024-06-10")
        np.testing.assert_allclose(s_a, bucket.predict_continuous(fr_a))
        s_b = serving_board_scores(frame, bucket, {"res_b": 1.0}, menu, cum,
                                   self.FIELD_FEATURES, "2024-06-10")
        mix = serving_board_scores(frame, bucket,
                                   {"res_a": 0.6, "res_b": 0.4}, menu, cum,
                                   self.FIELD_FEATURES, "2024-06-10")
        np.testing.assert_allclose(mix, 0.6 * s_a + 0.4 * s_b)
        with pytest.raises(ValueError):
            serving_board_scores(frame, bucket, {"nope": 1.0}, menu, cum,
                                 self.FIELD_FEATURES, "2024-06-10")
