# wod-wiki-samples-results

A Wod.Wiki community seed source — notebooks built from the public sports
datasets converted by the [solar-system](https://github.com/bitcobblers/solar-system)
dataset pipeline, validated and compiled into versioned seed artifacts by the
`wod` CLI
([@bitcobblers/wod-wiki-tools](https://www.npmjs.com/package/@bitcobblers/wod-wiki-tools)),
published via GitHub Pages, and imported by the
[wod-wiki](https://github.com/bitcobblers/wod-wiki) app as an independent
seed source (own manifest, version, and sync checkpoint).

Every item is a **recorded session** from a public competition dataset, not
programming: one note per session, with the segment splits as a `time` block.

## Notebooks

| notebook | kind | items |
|---|---|---:|
| `hyrox-races` | collection | 200 |
| `athletics-results` | collection | 400 |
| `crossfit-leaderboards` | collection | 119 |
| `swimming-results` | collection | 400 |
| `swimming-training` | collection | 228 |

## Where the data comes from

| notebook | source | sessions in the dataset | items kept |
|---|---|---:|---:|
| `hyrox-races` | Pyrox Parquet on CloudFront — public HYROX race results | 9,000 | 200 |
| `athletics-results` | AthTech Challenge (Rome 2024) — Tilastopaja + IsoLynx tracking | 945 | 400 |
| `crossfit-leaderboards` | CrossFit Games leaderboard API | 329 | 119 |
| `swimming-results` | World Aquatics rankings CSV | 2,185 | 400 |
| `swimming-training` | Mendeley Data — 12 weeks of pool training load | 228 | 228 |

The pipeline converts each source to the dataset contract (one
`execution-log` JSON line per session) and validates it before publishing.
The published datasets live on the NFS volume at
`/srv/nfs/helios/datasets/<category>/` on Helios.

## Regenerating the notebooks

The notebooks are generated, not hand-written:

```sh
D=/path/to/datasets      # holds <category>/<category>.jsonl
for c in hyrox athletics crossfit swimming-results swimming-training; do
  python3 scripts/build-notebooks.py "$D/$c/$c.jsonl" \
    --category "$c" --out markdown/notebooks \
    --max-per-group 40 --max-items 400
done
```

`--max-per-group` keeps the fastest sessions in each group (a race, an event,
a meet, a participant) and `--max-items` caps the notebook overall, because a
seed chunk is published to GitHub Pages and every item costs bytes.

The generator rewrites source labels into Whiteboard Language: the grammar
reads identifiers, digits and a small symbol set, so an em dash, an
apostrophe, a colon or a plus inside a source label is rewritten, and any
bracketed source annotation is moved into the note prose instead of the block.

## Layout

```
markdown/            the corpus (the only thing most PRs touch)
  notebooks/         one directory per notebook — README.md + items
scripts/             the generator that turns a dataset into notebooks
dist/                build output (gitignored)
```

## Build & publish

```
npm install
npx wod build --out dist   # validate + compile (same gate the CI runs)
```

Pushes to `main` publish `dist/` to GitHub Pages
(.github/workflows/main.yml); PRs get a validation build + sticky report
(.github/workflows/pull-request.yml). The seed dir URL is
`https://<owner>.github.io/<repo>/` — `manifest.json` plus content-hashed
chunk files.
