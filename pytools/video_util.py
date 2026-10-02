#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import shutil
import subprocess
import sys
import unicodedata

parser = argparse.ArgumentParser(
    description="Inspect the audio and subtitle tracks of a video file, "
    "optionally remove or keep selected tracks, shift the audio, video or "
    "subtitle tracks or add an external subtitle file"
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
    "-sa",
    "--shift-audio",
    type=int,
    metavar="MS",
    help="shift all audio tracks by MS milliseconds: positive values delay "
    "the audio, negative values advance it",
)
parser.add_argument(
    "-sv",
    "--shift-video",
    type=int,
    metavar="MS",
    help="shift all video tracks by MS milliseconds: positive values delay "
    "the video, negative values advance it",
)
parser.add_argument(
    "-as",
    "--add-subtitle",
    type=str,
    metavar="FILE",
    help="add an external subtitle file as a new subtitle track",
)
parser.add_argument(
    "-sl",
    "--subtitle-language",
    type=str,
    metavar="LANG",
    help="set the language of the subtitle added with --add-subtitle, "
    "e.g. eng or jpn",
)
parser.add_argument(
    "-ss",
    "--shift-subtitle",
    type=int,
    metavar="MS",
    help="shift all subtitle tracks by MS milliseconds: positive values delay "
    "them, negative values advance them (also applies to the subtitle added "
    "with --add-subtitle)",
)
parser.add_argument(
    "-o",
    "--output",
    type=str,
    help="output filename for track changes "
    "(default: <video> plus a suffix describing them, "
    "e.g. no_audio_2 or shift_audio_<MS>ms)",
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


def display_width(text):
    return sum(
        2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in text
    )


def print_table(label, headers, rows):
    print(f"{label} ({len(rows)}):")
    if not rows:
        print()
        return
    table = [headers] + rows
    widths = [max(display_width(row[i]) for row in table) for i in range(len(headers))]
    for row in table:
        line = "  ".join(
            cell + " " * (width - display_width(cell))
            for cell, width in zip(row[:-1], widths[:-1])
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


def apply_changes(video_path, streams, output):
    for stream_type, shift in (
        ("audio", args.shift_audio),
        ("video", args.shift_video),
        ("subtitle", args.shift_subtitle),
    ):
        if shift is None:
            continue
        # the added subtitle is shifted even when the file has no subtitle track
        if stream_type == "subtitle" and args.add_subtitle:
            continue
        if not any(stream.get("codec_type") == stream_type for stream in streams):
            print(
                f"ERROR: {video_path} has no {stream_type} tracks to shift",
                file=sys.stderr,
            )
            sys.exit(1)

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

    drop_indexes = [index for _, _, _, drops in changes for index in drops]

    shifted_types = set()
    for stream_type, shift in (
        ("audio", args.shift_audio),
        ("video", args.shift_video),
        ("subtitle", args.shift_subtitle),
    ):
        if shift is None:
            continue
        kept = any(
            stream.get("codec_type") == stream_type
            and stream["index"] not in drop_indexes
            for stream in streams
        )
        if kept or (stream_type == "subtitle" and args.add_subtitle):
            shifted_types.add(stream_type)

    if output is None:
        stem, extension = os.path.splitext(video_path)
        parts = []
        for mode, stream_type, indexes, _ in changes:
            prefix = "keep" if mode == "keep" else "no"
            joined = "_".join(str(index) for index in indexes)
            parts.append(f"{prefix}_{stream_type}_{joined}")
        if "audio" in shifted_types:
            parts.append(f"shift_audio_{args.shift_audio}ms")
        if "video" in shifted_types:
            parts.append(f"shift_video_{args.shift_video}ms")
        if args.add_subtitle:
            parts.append("add_subtitle")
        if "subtitle" in shifted_types:
            parts.append(f"shift_subtitle_{args.shift_subtitle}ms")
        output = f"{stem}_{'_'.join(parts)}{extension}"

    if os.path.exists(output):
        print(f"ERROR: output already exists: {output}", file=sys.stderr)
        sys.exit(1)

    # Shifts are relative, not absolute: the muxer's avoid_negative_ts
    # normalization absorbs any global timestamp offset, so -sv -N is
    # equivalent to -sa +N on the same file.
    command = ["ffmpeg", "-i", video_path]
    offset_inputs = {}
    for stream_type, shift in (
        ("audio", args.shift_audio),
        ("video", args.shift_video),
        ("subtitle", args.shift_subtitle),
    ):
        if shift is None:
            continue
        if not any(
            stream.get("codec_type") == stream_type
            and stream["index"] not in drop_indexes
            for stream in streams
        ):
            continue
        command += ["-itsoffset", f"{shift / 1000:g}", "-i", video_path]
        offset_inputs[stream_type] = len(offset_inputs) + 1
    subtitle_input = len(offset_inputs) + 1
    if args.add_subtitle:
        if args.shift_subtitle is not None:
            command += ["-itsoffset", f"{args.shift_subtitle / 1000:g}"]
        command += ["-i", args.add_subtitle]

    if offset_inputs:
        for stream in streams:
            if stream["index"] in drop_indexes:
                continue
            source = offset_inputs.get(stream.get("codec_type"), 0)
            command += ["-map", f"{source}:{stream['index']}"]
    else:
        command += ["-map", "0"]
        for index in drop_indexes:
            command += ["-map", f"-0:{index}"]
    if args.add_subtitle:
        command += ["-map", f"{subtitle_input}:s"]
        if args.subtitle_language:
            kept_subs = sum(
                1
                for stream in streams
                if stream.get("codec_type") == "subtitle"
                and stream["index"] not in drop_indexes
            )
            command += [
                f"-metadata:s:s:{kept_subs}",
                f"language={args.subtitle_language}",
            ]
    command += ["-c", "copy", output]
    result = run_command(command)
    if result.returncode != 0:
        print(
            f"ERROR: ffmpeg failed with exit code {result.returncode}", file=sys.stderr
        )
        # discard the partial output so the same name can be retried
        if os.path.exists(output):
            os.remove(output)
        sys.exit(1)

    for mode, stream_type, indexes, _ in changes:
        listed = ", ".join(str(index) for index in indexes)
        verb = "Kept" if mode == "keep" else "Removed"
        print(f"{verb} {stream_type} tracks: {listed}.")
    if "audio" in shifted_types:
        print(f"Shifted audio tracks by {args.shift_audio} ms.")
    if "video" in shifted_types:
        print(f"Shifted video tracks by {args.shift_video} ms.")
    if "subtitle" in shifted_types:
        print(f"Shifted subtitle tracks by {args.shift_subtitle} ms.")
    if args.add_subtitle:
        language = (
            f" (language {args.subtitle_language})" if args.subtitle_language else ""
        )
        print(f"Added subtitle: {args.add_subtitle}{language}.")
    print(f"Output: {output}")


def main():
    if not os.path.isfile(args.video):
        print(f"ERROR: file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    if args.add_subtitle and not os.path.isfile(args.add_subtitle):
        print(f"ERROR: file not found: {args.add_subtitle}", file=sys.stderr)
        sys.exit(1)

    if args.subtitle_language is not None and not args.add_subtitle:
        print(
            "ERROR: --subtitle-language can only be used together with "
            "--add-subtitle",
            file=sys.stderr,
        )
        sys.exit(1)

    has_changes = any(
        (
            args.remove_audio,
            args.keep_audio,
            args.remove_subtitle,
            args.keep_subtitle,
            args.shift_audio is not None,
            args.shift_video is not None,
            args.shift_subtitle is not None,
            args.add_subtitle,
        )
    )

    if args.output and not has_changes:
        print(
            "ERROR: --output can only be used together with a track "
            "removal, keep, shift or subtitle add option",
            file=sys.stderr,
        )
        sys.exit(1)

    require_tool("ffprobe")
    streams = run_ffprobe(args.video)

    if has_changes:
        require_tool("ffmpeg")
        apply_changes(args.video, streams, args.output)
    else:
        list_tracks(args.video, streams)


if __name__ == "__main__":
    main()
