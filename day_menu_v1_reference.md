# Day-Menu v1 — The Rider-Composition Key Vocabulary

**Frozen 2026-08-09** · artifact `models/production/day_menu_v1.json` · fit on all labeled stage days 2016 → 2026-06 (signature artifact 2026-06-11) · **v1.1 refit scheduled after the post-Tour data refresh, before the Vuelta** (item identities are expected to be stable; the refit adds ~2 months of days and the full TdF 2026).

This is the serve-time vocabulary for the retrieval channel: each morning you key the stage to one item (or a weighted set), the kernod ranking model uses that key to decide **who is in the top-15 conversation**, and the untouched production heads price the pool. A wrong key can cost pool composition; it cannot corrupt prices (gate 6, 2026-08-09).

## What a key is (and isn't)

A key is a point in **contesting-composition space**: the 6-archetype mix (sprint / mountain / hilly / rolling / breakaway / time_trial) of the riders you expect to contest the front ~15. Finishing-time shape is **not** part of the matching — it enters only as (a) the macro routing below and (b) a canonical winner-group-proportion value each item carries as a descriptor. This split is deliberate: who contests is roughly twice as forward-predictable as how the gaps shape up (June: r .739 vs .452).

**Macro routing (mechanical — you rarely key these by judgment):**

| macro item | rule | n | note |
|---|---|---|---|
| `itt` | winning time < 75 min | 368 | format is public; always known |
| `bunch` | mass sprint, or bunch sprint with winner group ≥ 20% of field | 1,664 | ~72% sprinter-won |
| `gc_day` | winner or front-5 median inside morning GC top-10 | 968 | mountain/TT-archetype front; the GC filter, not composition, defines it |
| *residual* | everything else | **951** | → the 8 analogs below; ~8 per GT edition |

## The two families

The 8 analogs organize into two sharply distinct families (cross-family similarity as low as 0.17) with graded variants inside each. **At serve, pick the family first** — "does this end with a small escape/select group of climbers-puncheurs, or with a reduced sprint of fast men?" — then grade within it.

```
ESCAPE / CLIMB family            POWER-SPRINT family          bridges
res_2 mountain escape            res_3 survivor gallop        res_1 fast-survivor
res_4 hard puncheur              res_7 split sprint           res_0 chaos (rare)
res_6 rouleur power              (res_5 = degenerate res_7)
```

---

## The 8 analogs

### `res_2` — **Mountain escape** *(the Lombardia day)* — n=360, 34% in GTs
- **Composition:** mountain .42 · time_trial .24 · rolling .20 · breakaway .08 · hilly .06 · **sprint .00**
- **Shape payload:** solo or tiny-group wins (median winner group **1**)
- **Winners:** mountain 34%, time_trial 31%, rolling 21%
- **WT anchors:** Il Lombardia 0.97 · Liège–Bastogne–Liège 0.94 · San Sebastián 0.91
- **Exemplars:** Itzulia mountain stages; Andalucía st2; **TdF 2026 st4 (Pedersen — on the res_4 boundary), st9 (van der Poel), st13 (Schmid), st18 (Carapaz)**
- **Pick when:** real climbing, and the GC group lets the move go — break of climbers/attackers stays away, or a late solo from outside GC control. The escape composition is terrain-independent (mountain and rolling breaks share this signature); what makes it res_2 rather than gc_day is *who is allowed to win*, not the profile.
- **This is the single most GT-relevant item.**

### `res_4` — **Hard puncheur day** *(the Montréal / Liège day)* — n=181, 19% in GTs
- **Composition:** mountain .30 · rolling .21 · time_trial .21 · breakaway .11 · hilly .09 · sprint .07
- **Shape payload:** solo/small-group (median winner group 1)
- **Winners:** mountain 32%, time_trial 31%
- **WT anchors:** GP Montréal 0.96 · Liège–Bastogne–Liège 0.95 · San Sebastián 0.94
- **Exemplars:** Paris–Nice st3; Oman st2. **TdF 2026 st4 (Pedersen) — the founding example of this CLASS of day — sits on the res_4/res_2 boundary (canonical label res_2; similarity 0.97)**; key torn cases as a weighted pair.
- **Pick when:** repeated hard climbs but power men survive — the front is climber-rouleurs and hard classics types, not pure climbers; sprinters gone, but the winner can be a Pedersen-class hard man.
- **Distinguish from res_2:** more rolling/power, a trace of sprint survives, less pure mountain. Similarity 0.97 — these are graded neighbors; when torn, weight both.

### `res_6` — **Rouleur power group** *(the Amstel / Montréal day)* — n=114, 18% in GTs
- **Composition:** mountain .24 · time_trial .22 · rolling .17 · sprint .13 · breakaway .13 · hilly .12
- **Shape payload:** small group (median winner group 2)
- **Winners:** time_trial 32%, mountain 25%
- **WT anchors:** GP Montréal 0.95 · Cadel Evans GORR 0.91 · Amstel 0.89
- **Exemplars:** Paris–Nice st6; Andalucía st5; Dunkerque st4
- **Pick when:** selective but balanced — a powerful mixed group of ~2–6 decides it; TT-shaped engines are the modal winners. The "everyone strong survives" day.

### `res_1` — **Fast-finisher power day** *(the Cadel day)* — n=124, 11% in GTs
- **Composition:** sprint .24 · time_trial .21 · rolling .17 · mountain .17 · hilly .12
- **Shape payload:** small group (median 2)
- **Winners:** time_trial 30%, rolling 17%, sprint 17%
- **WT anchors:** Cadel Evans GORR 0.95 · Eschborn-Frankfurt 0.91 · Bretagne 0.91
- **Exemplars:** Tour Auvergne-Rhône-Alpes st2; Rwanda hill stages
- **Pick when:** enough climbing to shed pure sprinters, but the finish suits quick men who climbed — a fast finisher wins from a small hard group.

### `res_7` — **Split sprint** *(the Sanremo run-in)* — n=140, 15% in GTs
- **Composition:** sprint .37 · time_trial .21 · hilly .16 · breakaway .14 · mountain .07
- **Shape payload:** small-to-mid group (median 3)
- **Winners:** time_trial 33%, sprint 31%, breakaway 17%
- **WT anchors:** In Flanders Fields 0.97 · Eschborn-Frankfurt 0.97 · Milano-Sanremo 0.97
- **Exemplars:** La Provence st3; Giro 2026 st12; Hainan st3; **TdF 2026 st5 (Kooij), st17 (Philipsen) — canonical labels here, on the res_3 border**
- **Pick when:** a hard, fast finale splits the bunch — sprinters-who-climb and power men contest a fractured sprint. *(`res_5`, n=10, is a degenerate twin of this item — never select it; it folds in here.)*

### `res_3` — **Survivor gallop** *(the Cyclassics day)* — n=73, 10% in GTs
- **Composition:** sprint .62 · hilly .10 · breakaway .09 · time_trial .11
- **Shape payload:** reduced bunch (median winner group 4; the low-wg_prop `res_wide` class)
- **Winners:** sprint 55%
- **WT anchors:** Tour of Bruges 0.99 · BEMER Cyclassics 0.99
- **Exemplars:** Coppi e Bartali st2; Hongrie st2. **TdF 2026 st5 (Kooij) and st17 (Philipsen) live on this item's border with res_7** (canonical labels res_7; both under the 20% bunch bar — st17 = 26 of 158). Key reduced-sprint days as res_3/res_7 weighted when torn.
- **Pick when:** attrition (wind, climbs, chaos) cuts the bunch but the fastest man present still wins — a sprint, just not a full one.
- **Distinguish from `bunch`:** the winner group is under ~20% of the field; the model's bunch board would over-credit the shelled pure sprinters.

### `res_0` — **Chaos day** *(rare, weak identity)* — n=31, 6% in GTs
- **Composition:** mountain .25 · breakaway .25 · sprint .21 — an unresolved break-vs-bunch mix
- **Winners:** scattered (sprint 26%, mountain 23%, breakaway 19%)
- **Anchors:** none strong (best WT 0.87)
- **Pick when:** genuinely torn between a break surviving and a reduced bunch catching it — or better, don't: weight the two family candidates instead. Kept for completeness; ~3 days/season.

---

## Serve guidance

1. **Route the macros mechanically** — ITT from the road book; bunch vs survivor-gallop by expected winner-group size; gc_day when you expect the GC group to contest the win.
2. **Family question first:** escape/select group (res_2/4/6) or fractured fast finish (res_3/7, res_1 between)?
3. **Grade within family** by who survives: pure climbers (res_2) → hard puncheurs (res_4) → balanced engines (res_6); full-ish sprint (res_3) → split sprint (res_7) → small fast group (res_1).
4. **When uncertain, weight 2–3 items** — the ranking channel mixes boards under your weights (never average the descriptions themselves). Wrong keys cost pool composition only; prices are structurally untouched.
5. Log the key (item + weights) with each read — the Vuelta 2026 archive is the prospective tier-3 evaluation of judgment accuracy.

## TdF 2026, keyed under this menu (CANONICAL — migrated DB, 2026-08-09)

| class | stages |
|---|---|
| bunch | 7, 8, 11, 12, 21 |
| gc_day | 2, 3, 6, 10, 14, 15, 19, 20 |
| itt | 1 (TTT, 21'47), 16 |
| res_2 mountain escape | **4**, 9, 13, 18 |
| res_7 split sprint | 5, 17 |

**Label sensitivity (important for keying):** within-family neighbors flip
under small share differences — the survey-era table had st4→res_4 and
st5/17→res_3; canonical as-of-then snapshots put them in the res_2 / res_7
neighbors. No day has ever crossed families. Key the FAMILY with
confidence; when the grade is uncertain, weight 2 neighbors — the kernels
overlap heavily between neighbors (cos⁸ ≈ 0.8), so a one-grade miss costs
little. Oracle scoring (`score_day_keys.py`) counts set-coverage for
exactly this reason.

## Version notes

- v1 = this freeze (data through 2026-06; GMM k=8, seed 42, junk filter top15_unknown > 0.20 — the exact config the step-3/4 gates ran).
- v1.1 (pre-Vuelta): refit after post-Tour scrape + signature rebuild; check canonical drift vs v1 (report cosine per item); kernels/cumulants rebuilt so riders' Tour rides count in their Vuelta-time histories.
- The GMM parameters are stored in the artifact — assignment of any new day is a stored-parameter predict, never a refit.
