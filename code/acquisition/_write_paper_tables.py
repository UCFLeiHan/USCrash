import pandas as pd
from pathlib import Path

s = pd.read_csv(
    r"F:\LH_Research\USCrash\Crash\Paper\us_crash_dataset\tables\state_geography_summary.csv"
)
top = s[s.n_rows_file > 0].sort_values("n_rows_file", ascending=False).head(12)
lines = [
    r"\begin{tabular}{lrrc}",
    r"\toprule",
    r"State & Primary rows & Sampled pts & Coords \\",
    r"\midrule",
]
for _, r in top.iterrows():
    lines.append(
        f"{r.abbr} & {int(r.n_rows_file):,} & {int(r.n_sampled):,} & "
        f"{'Y' if r.ok else 'N'} \\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
out = Path(
    r"F:\LH_Research\USCrash\Crash\Paper\us_crash_dataset\tables\top_states.tex"
)
out.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out)

# missing coords list
miss = s[~s.ok & (s.n_rows_file > 0)]
lines = [
    r"\begin{tabular}{ll}",
    r"\toprule",
    r"State & Issue \\",
    r"\midrule",
]
for _, r in miss.iterrows():
    err = str(r.error).replace("&", r"\&")[:60]
    lines.append(f"{r.abbr} & {err} \\\\")
lines += [r"\bottomrule", r"\end{tabular}"]
out2 = Path(
    r"F:\LH_Research\USCrash\Crash\Paper\us_crash_dataset\tables\missing_coords.tex"
)
out2.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out2)
print("total rows", int(s.n_rows_file.sum()), "ok", int(s.ok.sum()))
