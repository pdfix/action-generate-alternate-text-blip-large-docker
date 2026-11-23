import argparse
import json
import logging
import re
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from constants import CONFIG_FILE, IMAGE_FILE_EXT_REGEX, SUPPORTED_IMAGE_EXT
from exceptions import (
    EC_ARG_GENERAL,
    MESSAGE_ARG_GENERAL,
    ArgumentException,
    ArgumentInputNotImageException,
    ArgumentInputNotPdfException,
    ArgumentOutputExtensionException,
    ArgumentOutputFolderNotExistsException,
    ArgumentZoomException,
    ExpectedException,
    InvalidRegexOrTemplateException,
)
from image_update import DockerImageContainerUpdateChecker
from logger import get_logger
from params_parser import ParamsParser
from process_image import generate_alt_text_into_txt
from process_pdf import GenerateAltTextsInPdf

logger: logging.Logger = get_logger("app_logger")

DEFAULT_TAGS: str = "Figure"


def str2bool(value: Any) -> bool:
    """
    Helper function to convert argument to boolean.

    Args:
        value (Any): The value to convert to boolean.

    Returns:
        Parsed argument as boolean.
    """
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "0"):
        return False
    else:
        raise ArgumentException(f"{MESSAGE_ARG_GENERAL} Boolean value expected.")


def set_arguments(
    parser: argparse.ArgumentParser,
    names: list,
    required_output: bool = True,
    output_help: str = "",
) -> None:
    """
    Set arguments for the parser based on the provided names and options.

    Args:
        parser (argparse.ArgumentParser): The argument parser to set arguments for.
        names (list): List of argument names to set.
        required_output (bool): Whether the output argument is required. Defaults to True.
        output_help (str): Help shown for --output argument. Defaults to "".
    """
    for name in names:
        match name:
            case "input":
                parser.add_argument("--input", "-i", type=str, required=True, help="The input PDF file")
            case "key":
                parser.add_argument("--key", type=str, default="", nargs="?", help="PDFix license key")
            case "model":
                parser.add_argument(
                    "--model",
                    type=str,
                    default="model",
                    help='Path to local model directory. It cannot contain "..". Default value is "model".',
                )
            case "name":
                parser.add_argument("--name", type=str, default="", nargs="?", help="PDFix license name")
            case "output":
                parser.add_argument("--output", "-o", type=str, required=required_output, help=output_help)
            case "overwrite":
                parser.add_argument(
                    "--overwrite",
                    type=str2bool,
                    default=False,
                    help="Overwrite alternate text if already present in the tag",
                )
            case "params":
                parser.add_argument(
                    "--params",
                    type=str,
                    required=False,
                    help="Path to JSON file with tag filter parameters (required for PDF → PDF).",
                )
            case "zoom":
                parser.add_argument(
                    "--zoom", type=float, default=2.0, help="Zoom level for the PDF page rendering (default: 2.0)."
                )


def run_config_subcommand(args) -> None:
    get_pdfix_config(args.output)


def get_pdfix_config(path: str) -> None:
    """
    If Path is not provided, output content of config.
    If Path is provided, copy config to destination path.

    Args:
        path (string): Destination path for config.json file
    """
    config_path: Path = Path(__file__).parent.parent.joinpath(CONFIG_FILE).resolve()

    with open(config_path, "r", encoding="utf-8") as file:
        if path is None:
            print(file.read())
        else:
            with open(path, "w") as out:
                out.write(file.read())


def check_output_file(output_path: str) -> str:
    """
    Check the output file extension and that its folder exists before any processing.

    Args:
        output_path (str): Path to the output PDF or TXT file.

    Returns:
        Output extension, ".pdf" or ".txt", which selects the mode.
    """
    extension: str = Path(output_path).suffix.lower()
    if extension not in (".pdf", ".txt"):
        raise ArgumentOutputExtensionException()

    output_folder: Path = Path(output_path).resolve().parent
    if not output_folder.is_dir():
        raise ArgumentOutputFolderNotExistsException(output_folder.as_posix())

    return extension


def check_input_file(input_path: str, output_extension: str) -> None:
    """
    Check that the input is an existing file of the type the mode needs.

    Args:
        input_path (str): Path to the input PDF or image.
        output_extension (str): ".pdf" for PDF to PDF, ".txt" for image to TXT.
    """
    path: Path = Path(input_path)
    if output_extension == ".pdf":
        if path.suffix.lower() != ".pdf" or not path.is_file():
            raise ArgumentInputNotPdfException(input_path)
    elif not re.search(IMAGE_FILE_EXT_REGEX, input_path, re.IGNORECASE) or not path.is_file():
        raise ArgumentInputNotImageException(input_path)


def check_zoom(zoom: float) -> None:
    """
    Check the rendering zoom level.

    Args:
        zoom (float): Zoom level for rendering the page.
    """
    if zoom < 1.0 or zoom > 4.0:
        raise ArgumentZoomException()


def resolve_regex_template(params_path: Optional[str]) -> str | Path | dict:
    """
    Resolve tag filter from --params (regex or template) or the default Figure regex.

    Args:
        params_path (Optional[str]): Path to params JSON, or None.

    Returns:
        Either a regex string or a template dict.
    """
    if not params_path:
        return DEFAULT_TAGS

    params_parser = ParamsParser(params_path)
    params_parser.parse()
    tag_names: Any = params_parser.get("tag_names")
    if isinstance(tag_names, str):
        return tag_names
    if isinstance(tag_names, dict):
        return tag_names
    raise InvalidRegexOrTemplateException()


# @KA:action pdfix_generate_alternate_text_blip_large
# @KA:desc Writes alternate text to Figure tags of a tagged PDF using the BLIP large AI model. The area of every
# selected tag is rendered as an image, BLIP describes the image in one English sentence, and the sentence is saved as
# the tag's alternate text. The input file is not changed; the PDF with the alternate texts is saved as the output file.
# @KA:context Run on a **tagged** PDF whose figures have no alternate text, for example after autotagging, to get a
# first description of photos and pictures. Check and correct the texts afterwards, especially for charts, diagrams and
# logos. Runs locally in Docker and nothing leaves your computer; the first run downloads the image and takes longer.
# @KA:param input_pdf
# @KA:desc Tagged PDF document. It is only read, never changed.
# @KA:problem "Input file must be an existing PDF document." (error 14)
# @KA:solution The file shown in the message was not found or does not have the `.pdf` extension. Select an existing PDF
# file.
# @KA:problem "PDF document has no tags." (error 26)
# @KA:solution The PDF is not tagged. Tag it first, for example with an autotagging action, and run the action again.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 30" (error 24)
# @KA:solution The file is not a valid PDF. Open and save it again in a PDF editor and run the action again.
# @KA:problem "Failed to open PDF document." and the next log line shows "PDFix SDK error 34" (error 24)
# @KA:solution The PDF is password-protected. Remove the password and run the action again.
# @KA:param output_pdf
# @KA:desc Where the PDF with the alternate texts is saved, a file with the `.pdf` extension. The folder must already
# exist; an existing file with the same name is overwritten. Both are checked before the document is processed.
# @KA:problem "Output file must be PDF document or TXT file." (error 16)
# @KA:solution Select an output file with the `.pdf` extension.
# @KA:problem "Output folder does not exist." (error 13)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:problem "Failed to save PDF document." (error 25)
# @KA:solution The PDF could not be written. Check that the output folder is writable and that the file is not open in
# another application.
# @KA:param overwrite
# @KA:desc When on, tags that already have alternate text get a new one from BLIP. When off (default), their alternate
# text is kept; the log shows the kept text.
# @KA:problem A figure kept its old alternate text.
# @KA:solution The tag already had alternate text and **Overwrite** is off. Turn **Overwrite** on to replace it.
# @KA:param zoom
# @KA:desc Zoom level used to render the area of each tag into an image, from 1.0 to 4.0 (default 2.0). A higher zoom
# gives BLIP more detail of small figures but takes longer.
# @KA:problem "Zoom level must be between 1.0 and 4.0." (error 17)
# @KA:solution Enter a zoom level from 1.0 to 4.0.
# @KA:param tag_names
# @KA:desc Which tags get alternate text: a regular expression of tag types (default `Figure`), or a template
# `tag_update` that selects tags by their properties. The regular expression is tested against the tag type and its
# standard type after role mapping.
# @KA:problem "Missing or invalid parameters." (error 12)
# @KA:solution The parameters from PDFix Desktop could not be read or do not contain **Tags**. Select the tags again and
# run the action again.
# @KA:problem "Invalid regex or template. Please check the usage and try again." (error 11)
# @KA:solution **Tags** is neither a regular expression nor a template. Enter a regular expression such as `Figure`, or
# a template.
# @KA:problem No tag got alternate text and the log shows no tag.
# @KA:solution No tag matches **Tags**. An invalid regular expression is not reported and matches nothing. Check the
# expression, for example use `Figure`.
# @KA:logic Which area is described
# @KA:desc The area of a tag is taken from its BBox attribute; when the tag has no BBox attribute, the area of its
# content on the page is used. Tags whose area is empty or whose page cannot be found are skipped with a warning in the
# log. An area of one colour, for example an empty white frame, is not sent to BLIP and gets no alternate text, because
# BLIP would invent a scene for it. Every new alternate text is written to the log with the tag type and page number.
# @KA:problem A figure got no alternate text and the log says it is empty.
# @KA:solution The figure area renders as one colour, so there is nothing to describe. Check the figure in the document;
# if it is decorative, mark it as an artifact.
# @KA:problem A figure got no alternate text and the log shows a Python error.
# @KA:solution Rendering or describing this figure failed; the action skips it and continues with the other tags. Open
# and save the PDF again in a PDF editor and run the action again, or write the alternate text manually.
# @KA:logic Quality of the descriptions
# @KA:desc BLIP writes one short English sentence in lowercase without a final period, for example "a field full of red
# and white flowers with trees in the background". It describes what it sees in general: photos usually get a good
# description, but charts, diagrams, maps and logos often get an invented or very general one, text in the image is not
# read, and the meaning of the image in the document is not known. The meaningless word "arafed" that BLIP sometimes
# generates is removed.
# @KA:problem The description of a chart or diagram is wrong or says something the chart does not show.
# @KA:solution BLIP is not made for charts and diagrams. Write the alternate text of such figures manually.
# @KA:problem The description is in English although the document is in another language.
# @KA:solution BLIP writes English only. Translate the alternate text or write it manually.
# @KA:logic Only selected tags
# @KA:desc Alternate text is meant for figures. It replaces the content of the tag for screen readers, so giving it to
# text tags such as paragraphs or tables would hide their text.
# @KA:logic PDFix license
# @KA:desc PDFix Desktop passes your PDFix license to the action automatically. Without a license the action runs in
# trial mode, which adds watermarks and may redact random content in the output PDF.
# @KA:problem The output PDF has watermarks or randomly redacted content.
# @KA:solution Trial mode is active. Activate your PDFix license in PDFix Desktop and run the action again.
# @KA:problem "Failed to authorize PDFix SDK account." and the next log line shows "PDFix SDK error 420" (error 22)
# @KA:solution The license name or key is not valid. Check the license in PDFix Desktop settings.
# @KA:problem "Failed to activate PDFix SDK account." and the next log line shows "PDFix SDK error 1205" (error 21)
# @KA:solution The license key is not valid. Check the license in PDFix Desktop settings.
# @KA:action pdfix_generate_alternate_text_from_image_to_text_blip_large
# @KA:desc Describes an image file in one English sentence using the BLIP large AI model and saves the sentence to a
# text file, so it can be used as alternate text. The image is not changed.
# @KA:context Run when you need a first alternate text for a picture, for example before you place it into a document.
# Check and correct the text afterwards. Runs locally in Docker and nothing leaves your computer; the first run
# downloads the image and takes longer.
# @KA:param input_jpg
# @KA:desc Image to describe. PDFix Desktop offers only `.jpg` files (one extension per input field; more extensions are
# planned in PDFix Desktop); the action itself also accepts `.jpeg`, `.png` and `.bmp`.
# @KA:problem "Input file must be an existing image file (JPG, JPEG, PNG or BMP)." (error 15)
# @KA:solution The file shown in the message was not found or is not a supported image. Select an existing JPG file.
# @KA:param output_txt
# @KA:desc Text file where the description is saved, a file with the `.txt` extension. The folder must already exist; an
# existing file with the same name is overwritten. The description is also written to the log.
# @KA:problem "Output file must be PDF document or TXT file." (error 16)
# @KA:solution Select an output file with the `.txt` extension.
# @KA:problem "Output folder does not exist." (error 13)
# @KA:solution Create the folder shown in the message or select another output file.
# @KA:param zoom
# @KA:desc Not used for image files; the image is described as it is.
# @KA:param overwrite
# @KA:desc Not used for image files; the output text file is always overwritten.
# @KA:logic Quality of the descriptions
# @KA:desc BLIP writes one short English sentence in lowercase without a final period, for example "a field full of red
# and white flowers with trees in the background". It describes what it sees in general: photos usually get a good
# description, but charts, diagrams, maps and logos often get an invented or very general one, text in the image is not
# read, and the meaning of the image in the document is not known. The meaningless word "arafed" that BLIP sometimes
# generates is removed.
# @KA:problem The description of a chart or diagram is wrong or says something the chart does not show.
# @KA:solution BLIP is not made for charts and diagrams. Write the alternate text of such figures manually.
# @KA:problem The description is in English although the document is in another language.
# @KA:solution BLIP writes English only. Translate the alternate text or write it manually.
def run_generate_alt_text_subcommand(args) -> None:
    output_extension: str = check_output_file(args.output)
    check_input_file(args.input, output_extension)
    check_zoom(args.zoom)

    if output_extension == ".txt":
        generate_alt_text_into_txt(args.input, args.output, args.model)
        return

    tag_filter: str | Path | dict = resolve_regex_template(getattr(args, "params", None))
    if isinstance(tag_filter, dict):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json") as template_file:
            with open(template_file.name, "w", encoding="utf-8") as template_file_write:
                json.dump(tag_filter, template_file_write)
            generate_alt_text_in_pdf(args, Path(template_file.name))
    else:
        generate_alt_text_in_pdf(args, tag_filter)


def generate_alt_text_in_pdf(args, regex_template: str | Path) -> None:
    """
    Generate alternate texts for selected tags in PDF document.

    Args:
        args: Parsed command line arguments.
        regex_template (str | Path): Regex or path to template JSON for matching tags.
    """
    processor: GenerateAltTextsInPdf = GenerateAltTextsInPdf(
        args.input, args.output, args.name, args.key, args.overwrite, args.zoom, args.model, regex_template
    )
    processor.generate_alt_texts_in_pdf()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a PDF file with Vission to generate alt text",
    )

    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)

    # Config subparser
    config_subparser = subparsers.add_parser(
        "config",
        help="Extract config file for integration",
    )
    set_arguments(
        config_subparser,
        ["output"],
        False,
        "Output to save the config JSON file. Application output is used if not provided",
    )
    config_subparser.set_defaults(func=run_config_subcommand)

    # Generate alternate text images subparser
    generate_alt_text_help = "Run alternate text description."
    generate_alt_text_help += " Runs in 2 modes. First mode is PDF -> PDF."
    generate_alt_text_help += " Second mode is image file -> TXT."
    generate_alt_text_help += f" Allowed image types: {SUPPORTED_IMAGE_EXT}"
    generate_alt_text_subparser = subparsers.add_parser("generate-alt-text", help=generate_alt_text_help)
    set_arguments(
        generate_alt_text_subparser,
        ["name", "key", "input", "output", "overwrite", "zoom", "model", "params"],
        True,
        "The output PDF or TXT file",
    )
    generate_alt_text_subparser.set_defaults(func=run_generate_alt_text_subcommand)

    # Parse arguments
    try:
        args = parser.parse_args()
    except ExpectedException as e:
        logger.error(e.message)
        sys.exit(e.error_code)
    except SystemExit as e:
        if e.code != 0:
            logger.error(MESSAGE_ARG_GENERAL)
            sys.exit(EC_ARG_GENERAL)
        # This happens when --help is used, exit gracefully
        sys.exit(0)
    except Exception as e:
        logger.error("Failed to run the program:")
        logger.exception(e)
        sys.exit(1)

    if hasattr(args, "func"):
        # Check for updates only when help is not checked
        update_checker = DockerImageContainerUpdateChecker()
        # Check it in separate thread not to be delayed when there is slow or no internet connection
        update_thread = threading.Thread(target=update_checker.check_for_image_updates)
        update_thread.start()

        # Measure the time it takes to process the input
        start_time: float = time.time()
        current_time: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger.info(f"Processing started at: {current_time}")

        # Run subcommand
        try:
            args.func(args)
        except ExpectedException as e:
            logger.error(e.message)
            if e.sdk_error:
                logger.error(e.sdk_error)
            sys.exit(e.error_code)
        except Exception as e:
            # not expected exception -> print stack trace and what exception happened
            logger.error("Failed to run the program:")
            logger.exception(e)
            sys.exit(1)
        finally:
            elapsed_time: float = time.time() - start_time
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logger.info(f"Processing finished at: {current_time}. Elapsed time: {elapsed_time:.2f} seconds")

            # Make sure to let update thread finish before exiting
            update_thread.join()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
