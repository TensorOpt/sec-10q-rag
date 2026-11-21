#!/usr/bin/env bash
# Downloads the EDGAR documents behind eval/expected.jsonl into the directory given as $1.
# Reads the declared User-Agent from SEC_USER_AGENT (set by the person running it).
set -u
: "${SEC_USER_AGENT:?set SEC_USER_AGENT to 'name email' as the SEC requires}"
OUT="${1:?usage: fetch_sources.sh OUT_DIR}"; mkdir -p "$OUT"
get() { curl -sS -A "$SEC_USER_AGENT" --compressed -o "$OUT/$1" -w "$1 %{http_code} %{size_download}\n" "$2"; sleep 0.5; }
A=https://www.sec.gov/Archives/edgar/data
get msft.htm  $A/789019/000119312526436133/msft-20260930.htm
get amzn.htm  $A/1018724/000101872426000040/amzn-20260930.htm
get jpm.htm   $A/19617/000162828026069523/jpm-20260930.htm
get csv.htm   $A/1016281/000101628126000070/csv-20260930.htm
get nrc.htm   $A/70487/000143774926034887/nrc20260930_10q.htm
get googl.htm $A/1652044/000165204426000084/goog-20260930.htm
# 8-K folders (earnings releases outside the corpus): NVIDIA 2026-11-17, Microsoft 2026-10-28 (two)
for f in nvda8k:1045810/000104581026000088 msft8k_a:789019/000119312526436122 msft8k_b:789019/000119312526436149; do
  n=${f%%:*}; p=${f##*:}
  get $n.index.json $A/$p/index.json
  python3 -I - "$OUT/$n.index.json" <<'PY' | while read name; do get "$n.$name" "$A/$p/$name"; done
import json,sys
try:
    for it in json.load(open(sys.argv[1]))['directory']['item']:
        nm=it['name']
        if nm.endswith('.htm') and 'index' not in nm and '/' not in nm: print(nm)
except Exception as e:
    sys.stderr.write(f'index parse failed: {e}\n')
PY
done
ls -la "$OUT" | tail -n +2
