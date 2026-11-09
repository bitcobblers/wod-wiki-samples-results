#!/usr/bin/env python3
"""Build seed notebooks from a converted dataset JSONL.

Usage:
  build-notebooks.py <dataset.jsonl> --category <name> [--out markdown/notebooks]
                     [--max-per-group N] [--slug <notebook-slug>]

The dataset is the pipeline's `execution-log` JSONL: one line per recorded
session, each with `data.logs[]` segment rows carrying absolute `timeSpan`
instants. One session becomes one notebook item — a markdown note with a
`time` block, one line per segment, prefixed with the segment's clock time —
plus the provenance of the source row.

Sessions are grouped into notebook items by the group key each category uses
(the race edition, the event, the meet, the athlete, the training week), and
the groups become one notebook per category. The fastest `--max-per-group`
sessions are kept per group, because a seed chunk is published to GitHub
Pages and every item costs bytes.

Frontmatter uses the corpus vocabulary: domain, format, intent, level.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Callable, Iterator

FENCE_OPEN = '```time'
FENCE_CLOSE = '```'

# The Whiteboard Language grammar accepts identifiers, digits, and a small
# symbol set (`.,@!$%^*=&-()[]/:`). Source text from race results carries
# characters it does not: an em dash, an apostrophe, and bracketed annotations.
# Those are rewritten for the block, and the dropped annotation is kept in the
# note prose so no source detail is silently lost.
ANNOTATION = re.compile(r'\[([^\]]*)\]')
DASHES = {'—': '-', '–': '-', '−': '-'}
# Labels keep only what the grammar reads as words, digits and separators.
# A colon or a plus inside a label breaks the parse; the clock prefix this
# script adds in front of the label is a separate token and stays intact.
SAFE = re.compile(r'[^A-Za-z0-9 .,/\-]')


def split_annotation(text: str) -> tuple[str, list[str]]:
    """Split a source label into block-safe text and its bracketed notes."""
    notes = [note.strip() for note in ANNOTATION.findall(text)]
    cleaned = ANNOTATION.sub('', text)
    for dash, plain in DASHES.items():
        cleaned = cleaned.replace(dash, plain)
    cleaned = SAFE.sub(' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -')
    return cleaned, notes


def safe_text(text: str) -> str:
    """Block-safe label, without the bracketed annotations."""
    return split_annotation(text)[0]

# Frontmatter vocabulary (mirrors templates/taxonomy.yaml in wod-wiki-sources).
CATEGORY_META: dict[str, dict[str, Any]] = {
    'hyrox': {
        'domain': 'hyrox',
        'format': 'race',
        'intent': 'competition',
        'level': 'expert',
        'slug': 'hyrox-races',
        'label': 'HYROX Race Results',
        'summary': 'Real HYROX race runs, station by station, from the public Pyrox results.',
    },
    'athletics': {
        'domain': 'track',
        'format': 'for-time',
        'intent': 'competition',
        'level': 'expert',
        'slug': 'athletics-results',
        'label': 'Athletics Results',
        'summary': 'Track-and-field performances with 100 m splits, from the AthTech Challenge results.',
    },
    'crossfit': {
        'domain': 'crossfit',
        'format': 'for-time',
        'intent': 'competition',
        'level': 'expert',
        'slug': 'crossfit-leaderboards',
        'label': 'CrossFit Leaderboard Results',
        'summary': 'CrossFit Games event-by-event scores from the official leaderboards.',
    },
    'swimming-results': {
        'domain': 'swimming',
        'format': 'for-time',
        'intent': 'competition',
        'level': 'advanced',
        'slug': 'swimming-results',
        'label': 'Swimming Race Results',
        'summary': 'Swimming race times from World Aquatics rankings.',
    },
    'swimming-training': {
        'domain': 'swimming',
        'format': 'intervals',
        'intent': 'training',
        'level': 'advanced',
        'slug': 'swimming-training',
        'label': 'Swimming Training Load',
        'summary': 'Twelve weeks of pool training load, one note per week.',
    },
}


def read_sessions(path: str) -> Iterator[dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def segment_lines(logs: list[dict]) -> tuple[list[str], list[str]]:
    """One line per timed segment: clock time, then the segment text.

    Returns the block lines and the bracketed source annotations that were
    rewritten out of the block.
    """
    lines: list[str] = []
    notes: list[str] = []
    for log in logs:
        if log.get('outputType') == 'analytics':
            continue
        raw = str(log.get('text', '')).strip()
        if not raw:
            continue
        text, annotations = split_annotation(raw)
        if not text:
            continue
        for note in annotations:
            notes.append(f'{text}: {note}')
        span = log.get('timeSpan')
        if isinstance(span, dict) and isinstance(span.get('ended'), (int, float)):
            seconds = (span['ended'] - span['started']) / 1000
            minutes = int(seconds // 60)
            remainder = seconds - minutes * 60
            lines.append(f'{minutes}:{remainder:05.2f} {text}')
        else:
            lines.append(text)
    return lines, notes


def clock(ms: float) -> str:
    total = int(round(ms / 1000))
    return f'{total // 60}:{total % 60:02d}'


# --- per-category grouping -------------------------------------------------
#
# Each group key is a tuple; the first element names the group, the rest
# describe it for the item title and the notebook index.

def hyrox_group(session_id: str) -> tuple[str, ...]:
    parts = session_id.split('-')
    race = parts[1] if len(parts) > 1 else 'race'
    return (f'Race {race}', race)


def athletics_group(session_id: str) -> tuple[str, ...]:
    parts = session_id.split('-')
    event = parts[4] if len(parts) > 4 else 'event'
    gender = parts[5] if len(parts) > 5 else ''
    return (f'{event} {gender}'.strip(), event, gender)


def crossfit_group(session_id: str) -> tuple[str, ...]:
    parts = session_id.split('-')
    kind = parts[1] if len(parts) > 1 else 'leaderboard'
    year = parts[2] if len(parts) > 2 else ''
    division = parts[3] if len(parts) > 3 else ''
    label = 'Games' if kind == 'games' else 'Open'
    return (f'{label} {year} — Division {division}', kind, year, division)


def swimming_results_group(session_id: str) -> tuple[str, ...]:
    parts = session_id.split('-')
    meet = '-'.join(parts[3:-2]) if len(parts) > 4 else 'meet'
    return (meet, meet)


def swimming_training_group(session_id: str) -> tuple[str, ...]:
    parts = session_id.split('-')
    participant = parts[2] if len(parts) > 2 else 'participant'
    mesocycle = parts[3] if len(parts) > 3 else ''
    week = parts[4] if len(parts) > 4 else ''
    return (f'Participant {participant}', participant, mesocycle, week)


GROUPS: dict[str, Callable[[str], tuple[str, ...]]] = {
    'hyrox': hyrox_group,
    'athletics': athletics_group,
    'crossfit': crossfit_group,
    'swimming-results': swimming_results_group,
    'swimming-training': swimming_training_group,
}


def title_for(category: str, group: tuple[str, ...], session_id: str, duration_ms: float) -> str:
    label = group[0]
    # A leaderboard row can carry per-event scores but no session total; the
    # clock is then meaningless and only clutters the title.
    elapsed = f' — {clock(duration_ms)}' if duration_ms > 0 else ''
    if category == 'hyrox':
        run = session_id.split('-')[-1]
        return f'HYROX {label} — Run {run}{elapsed}'
    if category == 'athletics':
        return f'{label} — Athlete {session_id.rsplit("-", 1)[-1]}{elapsed}'
    if category == 'crossfit':
        return f'{label} — Athlete {session_id.rsplit("-", 1)[-1]}{elapsed}'
    if category == 'swimming-results':
        athlete = session_id.rsplit('-', 1)[-1].replace('-', ' ').title()
        return f'{label} — {athlete}{elapsed}'
    if category == 'swimming-training':
        return f'{label} — Cycle {group[2]}, Week {group[3]}{elapsed}'
    return f'{label} — {session_id}{elapsed}'


def slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return slug or 'item'


def item_markdown(
    meta: dict[str, Any],
    title: str,
    lines: list[str],
    notes: list[str],
    session: dict[str, Any],
) -> str:
    source = session.get('source', {})
    results = session['data']['results']
    front = [
        '---',
        f'domain: {meta["domain"]}',
        f'format: {meta["format"]}',
        f'intent: {meta["intent"]}',
        f'level: {meta["level"]}',
        '---',
        '',
    ]
    body = [
        f'# {title}',
        '',
        f"**Source:** {source.get('dataset', 'unknown dataset')} "
        f"({source.get('license', 'unknown license')}). "
        f"Session `{results.get('sessionId', 'unknown')}`, "
        f"retrieved {source.get('retrievedAt', 'unknown')}.",
        '',
    ]
    if notes:
        body += ['**Source notes:**', *[f'- {note}' for note in notes], '']
    body += [FENCE_OPEN, *lines, FENCE_CLOSE, '']
    return '\n'.join(front + body)


def notebook_readme(meta: dict[str, Any], groups: list[str], count: int, source: dict[str, Any]) -> str:
    front = [
        '---',
        'template: canvas',
        'collection: true',
        'category:',
        f'  - {meta["domain"]}',
        '---',
        f'# {meta["label"]}',
        '',
        meta['summary'],
        '',
        f"Dataset: `{source.get('dataset', 'unknown')}` — {source.get('license', 'unknown license')}. "
        f"Retrieved {source.get('retrievedAt', 'unknown')}. "
        f'Converted from the public source by the solar-system dataset pipeline; '
        f'{count} recorded sessions in {len(groups)} groups.',
        '',
        '## Groups',
        '',
    ]
    for group in groups:
        front.append(f'- {group}')
    front.append('')
    return '\n'.join(front)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', help='dataset JSONL produced by the pipeline')
    parser.add_argument('--category', required=True, choices=sorted(CATEGORY_META))
    parser.add_argument('--out', default='markdown/notebooks')
    parser.add_argument('--slug', help='notebook slug (defaults to the category slug)')
    parser.add_argument('--max-per-group', type=int, default=40,
                        help='sessions kept per group, fastest first')
    parser.add_argument('--max-items', type=int, default=600,
                        help='items kept per notebook, fastest first overall')
    args = parser.parse_args()

    meta = CATEGORY_META[args.category]
    slug = args.slug or meta['slug']
    group_of = GROUPS[args.category]

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    source: dict[str, Any] = {}
    total = 0
    for session in read_sessions(args.dataset):
        total += 1
        source = source or session.get('source', {})
        results = session['data']['results']
        session_id = str(results.get('sessionId') or f'session-{total}')
        groups[group_of(session_id)].append({
            'session': session,
            'sessionId': session_id,
            'duration': float(results.get('duration') or 0),
        })

    out_dir = os.path.join(args.out, slug)
    os.makedirs(out_dir, exist_ok=True)
    for stale in os.listdir(out_dir):
        if stale.endswith('.md'):
            os.remove(os.path.join(out_dir, stale))

    kept = 0
    group_names: list[str] = []
    written: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    for group in sorted(groups):
        rows = sorted(groups[group], key=lambda row: row['duration'])
        group_names.append(group[0])
        for row in rows[:args.max_per_group]:
            written.append((group, row))

    # Notebook-wide cap: keep the fastest sessions across every group.
    written.sort(key=lambda pair: pair[1]['duration'])
    written = written[:args.max_items]

    for group, row in written:
        session = row['session']
        lines, notes = segment_lines(session['data']['logs'])
        if not lines:
            continue
        title = title_for(args.category, group, row['sessionId'], row['duration'])
        markdown = item_markdown(meta, title, lines, notes, session)
        name = f'{slugify(group[0])}-{slugify(row["sessionId"])}.md'
        with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as handle:
            handle.write(markdown)
        kept += 1

    with open(os.path.join(out_dir, 'README.md'), 'w', encoding='utf-8') as handle:
        handle.write(notebook_readme(meta, sorted(set(group_names)), kept, source))

    print(f'{args.category}: {total} sessions in {len(groups)} groups -> {kept} items in {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
