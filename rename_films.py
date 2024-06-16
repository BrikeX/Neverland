import os
import argparse

# https://sylikc.github.io/pyexiftool/installation.html
import exiftool


def get_photo_datetime(photo_path):
    date_time = None

    with exiftool.ExifToolHelper() as et:
        for metadata in et.get_metadata(photo_path):
            for k, v in metadata.items():
                # print(f"{k} = {v}")
                if k == "EXIF:DateTimeOriginal":
                    date_time = v
                    # print(f"{date_time}")
                    break
            if date_time is not None:
                break

    return date_time


def get_video_datetime(video_path):
    date_time = None

    with exiftool.ExifToolHelper() as et:
        for metadata in et.get_metadata(video_path):
            for k, v in metadata.items():
                # print(f"{k} = {v}")
                if k == "QuickTime:CreateDate":
                    date_time = v
                    # print(f"{date_time}")
                    break
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

            date_time = None
            video_type = False
            if file_path.lower().endswith((".jpg", ".jpeg")):
                date_time = get_photo_datetime(file_path)
            elif file_path.lower().endswith((".mov", ".mp4")):
                date_time = get_video_datetime(file_path)
                video_type = True

            if date_time is None:
                print(f"File = {file_path} does not have DateTime")
                continue
            # print(f"File = {file_path}, DateTime = {date_time}")

            formatted_date_time = format_datetime(date_time)
            # print(f"File = {file_path}, formatted DateTime = {formatted_date_time}")

            file_extension = os.path.splitext(file)[1]
            new_base_name = (
                f"VID_{formatted_date_time}"
                if video_type
                else f"IMG_{formatted_date_time}"
            )
            new_file_name = get_unique_filename(root, new_base_name, file_extension)
            # print(f"File = {file_path}, new name = {new_file_name}")

            new_file_path = os.path.join(root, new_file_name)
            os.rename(file_path, new_file_path)
            print(f"Rename {file_path} to {new_file_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Process films in a directory and rename them by their date and time"
    )
    parser.add_argument(
        "-d", "--directory", type=str, required=True, help="the directory to process"
    )
    args = parser.parse_args()
    directory_path = args.directory

    if not os.path.isdir(directory_path):
        print(f"ERROR directory path {directory_path}")
        return

    rename_films(directory_path)


if __name__ == "__main__":
    main()
