import argparse
import os
import shutil
import sys
from pathlib import Path

from autotag import autotag_pdf, autotag_folder


def get_config(path: str) -> None:
    if path is None:
        with open(
            os.path.join(Path(__file__).parent.absolute(), "../config.json"),
            "r",
            encoding="utf-8",
        ) as f:
            print(f.read())
    else:
        src = os.path.join(Path(__file__).parent.absolute(), "../config.json")
        dst = path
        shutil.copyfile(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a PDF file using Paddle layout recognition",
    )

    parser.add_argument("--name", type=str, default="", help="Pdfix license name")
    parser.add_argument("--key", type=str, default="", help="Pdfix license key")

    subparsers = parser.add_subparsers(dest="subparser")

    # config subparser
    pars_config = subparsers.add_parser(
        "config",
        help="Extract config file for integration",
    )
    pars_config.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output to save the config JSON file. Application output\
              is used if not provided",
    )

    pars_tag = subparsers.add_parser(
        "tag",
        help="Run autotag",
    )

    pars_tag.add_argument("-i", "--input", type=str, help="The input PDF file")
    pars_tag.add_argument(
        "-o",
        "--output",
        type=str,
        help="The output PDF file",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:  # This happens when --help is used, exit gracefully
            sys.exit(0)
        print("Failed to parse arguments. Please check the usage and try again.")
        sys.exit(1)

    if args.subparser == "config":
        get_config(args.output)
        sys.exit(0)

    elif args.subparser == "tag":
        if not args.input or not args.output:
            parser.error(
                "The following arguments are required: -i/--input, -o/--output",
            )

        input_file = args.input
        output_file = args.output

        # if not os.path.isfile(input_file):
        #     sys.exit(f"Error: The input file '{input_file}' does not exist")
        #     return

        if input_file.lower().endswith(".pdf") and output_file.lower().endswith(".pdf"):
            try:                
                autotag_pdf(input_file, output_file)
            except Exception as e:
                sys.exit("Failed to run Paddle {}".format(e))
        elif Path(input_file).is_dir():
            try:                
                autotag_folder(input_file, output_file)
            except Exception as e:
                sys.exit("Failed to run Paddle {}".format(e))
        else:
            print("Input and output file must be PDF")


if __name__ == "__main__":
    main()
