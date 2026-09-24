#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(
    description="Inspect the audio and subtitle tracks of a video file "
    "and optionally remove or keep selected tracks"
)
parser.add_argument("video", type=str, help="the video file to process")
parser.add_argument("-a", "--audio", action="store_true", help="list audio tracks")
parser.add_argument(
    "-s", "--subtitle", action="store_true", help="list subtitle tracks"
)
parser.add_argument(
    "-ra",
    "--remove-audio",
    type=int,
    action="append",
    metavar="N",
    help="remove the audio track with stream index N (repeatable, e.g. -ra 2 -ra 4)",
)
parser.add_argument(
    "-rs",
    "--remove-subtitle",
    type=int,
    action="append",
    metavar="N",
    help="remove the subtitle track with stream index N (repeatable)",
)
parser.add_argument(
    "-ka",
    "--keep-audio",
    type=int,
    action="append",
    metavar="N",
    help="keep only the audio tracks with these stream indexes and remove the rest "
    "(repeatable)",
)
parser.add_argument(
    "-ks",
    "--keep-subtitle",
    type=int,
    action="append",
    metavar="N",
    help="keep only the subtitle tracks with these stream indexes and remove the rest "
    "(repeatable)",
)
parser.add_argument(
    "-o",
    "--output",
    type=str,
    help="output filename for track changes "
    "(default: <video> with a no_<type>_<N>/keep_<type>_<N> suffix)",
)
parser.add_argument("--debug", action="store_true", help="debug mode")
args = parser.parse_args()

FFPROBE_ENTRIES = (
    "stream=index,codec_type,codec_name,channels,channel_layout,sample_rate"
    ":stream_tags=language,title"
    ":stream_disposition=default,forced"
)


def require_tool(name):
    if shutil.which(name) is None:
        print(f"ERROR: {name} is not installed", file=sys.stderr)
        sys.exit(1)


def run_command(command, capture=False):
    if args.debug:
        print(f"Running: {' '.join(command)}")
    if capture:
        return subprocess.run(command, capture_output=True, text=True)
    return subprocess.run(command)


def run_ffprobe(video_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        FFPROBE_ENTRIES,
        "-of",
        "json",
        video_path,
    ]
    result = run_command(command, capture=True)
    if result.returncode != 0:
        print(
            f"ERROR: could not read stream information from {video_path}",
            file=sys.stderr,
        )
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout).get("streams", [])


def stream_flags(stream):
    disposition = stream.get("disposition", {})
    flags = [name for name in ("default", "forced") if disposition.get(name)]
    return ",".join(flags) if flags else "-"


def audio_rows(streams):
    rows = []
    for stream in streams:
        if stream.get("codec_type") != "audio":
            continue
        tags = stream.get("tags", {})
        rate = stream.get("sample_rate", "")
        rate = f"{int(rate) / 1000:g} kHz" if rate.isdigit() else "-"
        channels = stream.get("channel_layout") or str(stream.get("channels", "-"))
        rows.append(
            [
                str(stream["index"]),
                stream.get("codec_name", "-"),
                tags.get("language", "-"),
                channels,
                rate,
                stream_flags(stream),
                tags.get("title", "-"),
            ]
        )
    return rows


def subtitle_rows(streams):
    rows = []
    for stream in streams:
        if stream.get("codec_type") != "subtitle":
            continue
        tags = stream.get("tags", {})
        rows.append(
            [
                str(stream["index"]),
                stream.get("codec_name", "-"),
                tags.get("language", "-"),
                stream_flags(stream),
                tags.get("title", "-"),
            ]
        )
    return rows


def print_table(label, headers, rows):
    print(f"{label} ({len(rows)}):")
    if not rows:
        print()
        return
    table = [headers] + rows
    widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
    for row in table:
        line = "  ".join(
            cell.ljust(width) for cell, width in zip(row[:-1], widths[:-1])
        )
        print("  " + line + "  " + row[-1])
    print()


def list_tracks(video_path, streams):
    show_audio = args.audio or not args.subtitle
    show_subtitle = args.subtitle or not args.audio

    print(f"File: {video_path}")
    print()

    if show_audio:
        print_table(
            "Audio tracks",
            ["#", "CODEC", "LANGUAGE", "CHANNELS", "SAMPLE RATE", "FLAGS", "TITLE"],
            audio_rows(streams),
        )

    if show_subtitle:
        print_table(
            "Subtitle tracks",
            ["#", "CODEC", "LANGUAGE", "FLAGS", "TITLE"],
            subtitle_rows(streams),
        )


def apply_track_changes(video_path, streams, output):
    changes = []

    selections = (
        ("audio", args.remove_audio, args.keep_audio),
        ("subtitle", args.remove_subtitle, args.keep_subtitle),
    )

    for stream_type, requested_remove, requested_keep in selections:
        if requested_remove and requested_keep:
            print(
                f"ERROR: --remove-{stream_type} and --keep-{stream_type} "
                "cannot be used together",
                file=sys.stderr,
            )
            sys.exit(1)
        if not requested_remove and not requested_keep:
            continue

        indexes = list(dict.fromkeys(requested_remove or requested_keep))
        available = [s["index"] for s in streams if s.get("codec_type") == stream_type]

        missing = [index for index in indexes if index not in available]
        if missing:
            missing_list = ", ".join(str(index) for index in missing)
            print(
                f"ERROR: {video_path} has no {stream_type} track "
                f"with stream index {missing_list}",
                file=sys.stderr,
            )
            if available:
                available_list = " ".join(str(index) for index in available)
                print(
                    f"{stream_type.capitalize()} track indexes: {available_list}",
                    file=sys.stderr,
                )
            sys.exit(1)

        if requested_keep:
            drops = [index for index in available if index not in indexes]
            changes.append(("keep", stream_type, indexes, drops))
        else:
            changes.append(("remove", stream_type, indexes, indexes))

    if output is None:
        stem, extension = os.path.splitext(video_path)
        parts = []
        for mode, stream_type, indexes, _ in changes:
            prefix = "keep" if mode == "keep" else "no"
            joined = "_".join(str(index) for index in indexes)
            parts.append(f"{prefix}_{stream_type}_{joined}")
        output = f"{stem}_{'_'.join(parts)}{extension}"

    if os.path.exists(output):
        print(f"ERROR: output already exists: {output}", file=sys.stderr)
        sys.exit(1)

    drop_indexes = [index for _, _, _, drops in changes for index in drops]

    command = ["ffmpeg", "-i", video_path, "-map", "0"]
    for index in drop_indexes:
        command += ["-map", f"-0:{index}"]
    command += ["-c", "copy", output]
    result = run_command(command)
    if result.returncode != 0:
        print(
            f"ERROR: ffmpeg failed with exit code {result.returncode}", file=sys.stderr
        )
        sys.exit(1)

    for mode, stream_type, indexes, _ in changes:
        listed = ", ".join(str(index) for index in indexes)
        verb = "Kept" if mode == "keep" else "Removed"
        print(f"{verb} {stream_type} tracks: {listed}.")
    print(f"Output: {output}")


def main():
    if not os.path.isfile(args.video):
        print(f"ERROR: file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    has_changes = any(
        (args.remove_audio, args.keep_audio, args.remove_subtitle, args.keep_subtitle)
    )

    if args.output and not has_changes:
        print(
            "ERROR: --output can only be used together with a track "
            "removal or keep option",
            file=sys.stderr,
        )
        sys.exit(1)

    require_tool("ffprobe")
    streams = run_ffprobe(args.video)

    if has_changes:
        require_tool("ffmpeg")
        apply_track_changes(args.video, streams, args.output)
    else:
        list_tracks(args.video, streams)


if __name__ == "__main__":
    main()
