#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import re
import shutil

parser = argparse.ArgumentParser(
    description="Rename bangumi (anime) files in a directory to a clean format: \
                <Name><Season><Episode>.<ext>"
)
parser.add_argument(
    "-v",
    "--video",
    type=str,
    required=True,
    help="the directory containing bangumi video files",
)
parser.add_argument("-n", "--name", type=str, required=True, help="bangumi name")
parser.add_argument(
    "-s", "--season", type=str, required=True, help="season identifier (e.g. S03)"
)
parser.add_argument(
    "--subs",
    type=str,
    help="directory containing subtitle files to rename and copy into the video directory",
)
parser.add_argument(
    "-l",
    "--lang",
    type=str,
    help="case-insensitive language filter for subtitle filenames (e.g. SC); "
    "only matching files are copied, and the tag is dropped from the output name",
)
parser.add_argument(
    "--start", type=int, default=1, help="starting episode number (default: 1)"
)
parser.add_argument(
    "-d", "--dry-run", action="store_true", help="preview changes without renaming"
)
parser.add_argument("--verbose", action="store_true", help="verbose output")
args = parser.parse_args()

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts"}
SUB_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}


def natural_sort_key(s):
    return [
        int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", s)
    ]


def extract_sub_parts(filename):
    """Split subtitle filename into (base, tag, ext).

    e.g. "foo.HYSUB-SC.ass" -> ("foo", ".HYSUB-SC", ".ass")
         "foo.ass"          -> ("foo", "", ".ass")
    """
    name, ext = os.path.splitext(filename)
    name2, tag = os.path.splitext(name)
    if tag:
        return name2, tag, ext
    return name, "", ext


def rename_videos(directory_path):
    entries = []
    for f in os.listdir(directory_path):
        ext = os.path.splitext(f)[1].lower()
        if ext not in VIDEO_EXTENSIONS:
            if args.verbose:
                print(f"SKIP (not video): {f}")
            continue
        entries.append(f)

    entries.sort(key=natural_sort_key)

    renamed = 0
    for idx, filename in enumerate(entries):
        new_ep = args.start + idx
        ext = os.path.splitext(filename)[1]
        new_name = f"{args.name}{args.season}E{new_ep:02d}{ext}"
        old_path = os.path.join(directory_path, filename)
        new_path = os.path.join(directory_path, new_name)

        if os.path.exists(new_path) and old_path != new_path:
            print(f"WARNING: target already exists, skipping: {new_name}")
            continue

        if args.dry_run:
            print(f"[DRY RUN] {filename} -> {new_name}")
        else:
            os.rename(old_path, new_path)
            print(f"Renamed: {filename} -> {new_name}")
        renamed += 1

    print(f"\nTotal: {renamed} video(s) {'would be ' if args.dry_run else ''}renamed")
    return len(entries)


def rename_subs(sub_dir, video_dir, num_episodes):
    sub_filter = args.lang.lower() if args.lang else None

    sub_files = []
    for f in os.listdir(sub_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext not in SUB_EXTENSIONS:
            if args.verbose:
                print(f"SKIP (not subtitle): {f}")
            continue
        if sub_filter and sub_filter not in f.lower():
            if args.verbose:
                print(f"SKIP (lang filter '{args.lang}'): {f}")
            continue
        sub_files.append(f)

    sub_files.sort(key=natural_sort_key)

    groups = {}
    for f in sub_files:
        base, tag, ext = extract_sub_parts(f)
        groups.setdefault(base, []).append((f, tag, ext))

    sorted_bases = sorted(groups.keys(), key=natural_sort_key)

    if len(sorted_bases) != num_episodes:
        print(
            f"WARNING: found {len(sorted_bases)} subtitle episode(s) "
            f"but {num_episodes} video(s)"
        )

    copied = 0
    for idx, base in enumerate(sorted_bases):
        new_ep = args.start + idx
        for orig_file, tag, ext in groups[base]:
            if sub_filter:
                new_name = f"{args.name}{args.season}E{new_ep:02d}{ext}"
            else:
                new_name = f"{args.name}{args.season}E{new_ep:02d}{tag}{ext}"
            src = os.path.join(sub_dir, orig_file)
            dst = os.path.join(video_dir, new_name)

            if os.path.exists(dst):
                print(f"WARNING: target already exists, skipping: {new_name}")
                continue

            if args.dry_run:
                print(f"[DRY RUN] {orig_file} -> {new_name}")
            else:
                shutil.copy2(src, dst)
                print(f"Copied: {orig_file} -> {new_name}")
            copied += 1

    print(f"\nTotal: {copied} subtitle(s) {'would be ' if args.dry_run else ''}copied")


def main():
    if not os.path.isdir(args.video):
        print(f"ERROR: directory not found: {args.video}")
        return

    num_episodes = rename_videos(args.video)

    if args.subs:
        if not os.path.isdir(args.subs):
            print(f"ERROR: subs directory not found: {args.subs}")
            return
        print()
        rename_subs(args.subs, args.video, num_episodes)


if __name__ == "__main__":
    main()
