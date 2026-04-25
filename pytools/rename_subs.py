#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import re
import shutil

parser = argparse.ArgumentParser(
    description="Copy and rename subtitle files to match film filenames"
)
parser.add_argument(
    "-f", "--films", type=str, required=True, help="the films directory path"
)
parser.add_argument(
    "-s", "--subs", type=str, required=True, help="the subtitles directory path"
)
parser.add_argument(
    "--dry-run", action="store_true", help="preview changes without copying"
)
parser.add_argument(
    "--offset",
    type=int,
    default=0,
    help="offset to subtract from subtitle episode numbers (e.g. --offset 12 maps sub 13->EP01)",
)
parser.add_argument(
    "--exclude",
    type=str,
    action="append",
    default=[],
    help="regex pattern to exclude subtitle files (repeatable, e.g. --exclude OAD)",
)
parser.add_argument("--debug", action="store_true", help="debug mode")
args = parser.parse_args()

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts"}
SUB_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}

EPISODE_PATTERNS = [
    re.compile(r"S\d+E(\d+)", re.IGNORECASE),
    re.compile(r"EP\s*(\d+)", re.IGNORECASE),
    re.compile(r"(?<![a-zA-Z])E(\d+)(?!\d)", re.IGNORECASE),
    re.compile(r"第(\d+)[話话集]"),
    re.compile(r"[-–]\s*(\d+)(?:\s|$|[(\[])"),
]


def extract_episode_number(filename):
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            return int(match.group(1))
    return None


def main():
    if not os.path.isdir(args.films):
        print(f"ERROR: films directory not found: {args.films}")
        return
    if not os.path.isdir(args.subs):
        print(f"ERROR: subs directory not found: {args.subs}")
        return

    films = {}
    for f in sorted(os.listdir(args.films)):
        ext = os.path.splitext(f)[1].lower()
        if ext not in VIDEO_EXTENSIONS:
            continue
        ep = extract_episode_number(f)
        if ep is not None:
            films[ep] = f
            if args.debug:
                print(f"Film EP{ep:02d}: {f}")
        else:
            print(f"SKIP film (no episode number): {f}")

    exclude_patterns = [re.compile(p, re.IGNORECASE) for p in args.exclude]

    subs = {}
    for f in sorted(os.listdir(args.subs)):
        ext = os.path.splitext(f)[1].lower()
        if ext not in SUB_EXTENSIONS:
            continue
        if any(p.search(f) for p in exclude_patterns):
            if args.debug:
                print(f"Excluded: {f}")
            continue
        ep = extract_episode_number(f)
        if ep is not None:
            adjusted_ep = ep - args.offset
            subs.setdefault(adjusted_ep, []).append(f)
            if args.debug:
                offset_info = f" (raw {ep})" if args.offset else ""
                print(f"Sub  EP{adjusted_ep:02d}{offset_info}: {f}")
        else:
            print(f"SKIP sub (no episode number): {f}")

    matched = 0
    skipped = 0
    for ep in sorted(films.keys()):
        if ep not in subs:
            print(f"WARNING: no subtitle found for EP{ep:02d}")
            continue
        if len(subs[ep]) > 1:
            print(f"WARNING: multiple subtitles for EP{ep:02d}, skipping:")
            for s in subs[ep]:
                print(f"  - {s}")
            skipped += len(subs[ep])
            continue
        film_stem = os.path.splitext(films[ep])[0]
        sub_file = subs[ep][0]
        sub_ext = os.path.splitext(sub_file)[1]
        new_name = f"{film_stem}{sub_ext}"
        src = os.path.join(args.subs, sub_file)
        dst = os.path.join(args.films, new_name)
        if args.dry_run:
            print(f"[DRY RUN] {sub_file} -> {new_name}")
        else:
            shutil.copy2(src, dst)
            print(f"Copied: {sub_file} -> {new_name}")
        matched += 1

    print(f"\nTotal: {matched} subtitle(s) {'would be ' if args.dry_run else ''}copied")
    if skipped:
        print(f"Skipped: {skipped} subtitle(s) due to duplicate matches")

    unmatched_subs = set(subs.keys()) - set(films.keys())
    if unmatched_subs:
        print(f"Unmatched subtitle episodes: {sorted(unmatched_subs)}")


if __name__ == "__main__":
    main()
