#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os

# https://sylikc.github.io/pyexiftool/installation.html
import exiftool

parser = argparse.ArgumentParser(
    description="Process films in a directory and rename them by their date and time"
)
parser.add_argument(
    "-d", "--directory", type=str, required=True, help="the directory to process"
)
parser.add_argument("--debug", action="store_true", help="debug mode")
args = parser.parse_args()


def get_photo_datetime(photo_path):
    date_time = None

    with exiftool.ExifToolHelper() as et:
        if args.debug:
            print("--- photo metadata ---")
            for metadata in et.get_metadata(photo_path):
                for k, v in metadata.items():
                    print(f"{k} = {v}")
            print("--- photo metadata ---")

        for metadata in et.get_metadata(photo_path):
            if "EXIF:DateTimeOriginal" in metadata:
                date_time = metadata.get("EXIF:DateTimeOriginal")

            if date_time is not None:
                break

    return date_time


def get_video_datetime(video_path):
    date_time = None

    with exiftool.ExifToolHelper() as et:
        if args.debug:
            print("--- video metadata ---")
            for metadata in et.get_metadata(video_path):
                for k, v in metadata.items():
                    print(f"{k} = {v}")
            print("--- video metadata ---")

        for metadata in et.get_metadata(video_path):
            if "QuickTime:CreationDate" in metadata:
                date_time = metadata.get("QuickTime:CreationDate")
            if date_time is None and "QuickTime:CreateDate" in metadata:
                date_time = metadata.get("QuickTime:CreateDate")

            if date_time is not None:
                break

    return date_time


def format_datetime(date_time):
    date_part, time_part = str(date_time).split()
    date_part = date_part.replace(":", "")
    time_part = time_part.replace(":", "")
    return f"{date_part}_{time_part}"


def get_unique_filename(directory, base_name, suffix):
    increment = 1
    new_name = f"{base_name}{suffix}"

    while os.path.exists(os.path.join(directory, new_name)):
        new_name = f"{base_name}_{increment}{suffix}"
        increment += 1

    return new_name


def rename_films(directory_path):
    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            if args.debug:
                print(f"Processing File = {file_path}")

            date_time = None
            if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".heic")):
                date_time = get_photo_datetime(file_path)
            elif file_path.lower().endswith((".mov", ".mp4")):
                date_time = get_video_datetime(file_path)

            if date_time is None:
                print(f"File = {file_path} does not have DateTime")
                continue
            if args.debug:
                print(f"DateTime = {date_time}")

            formatted_date_time = format_datetime(date_time)
            if args.debug:
                print(f"Formatted DateTime = {formatted_date_time}")

            file_extension = os.path.splitext(file)[1]
            new_file_name = get_unique_filename(
                root, formatted_date_time, file_extension
            )
            if args.debug:
                print(f"New unique file name = {new_file_name}")

            new_file_path = os.path.join(root, new_file_name)
            os.rename(file_path, new_file_path)
            print(f"Rename {file_path} to {new_file_path}")


def main():
    if not os.path.isdir(args.directory):
        print(f"ERROR directory path {args.directory}")
        return

    rename_films(args.directory)


if __name__ == "__main__":
    main()
