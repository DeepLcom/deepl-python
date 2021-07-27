import argparse
import deepl
import logging
import os
import sys
from typing import List


# Program name for integration with click.testing
name = "python -m deepl"

env_auth_key = "DEEPL_AUTH_KEY"
env_server_url = "DEEPL_SERVER_URL"


def usage(translator: deepl.Translator):
    """Action function for the usage command."""
    usage_result = translator.get_usage()
    print(usage_result)


def languages(translator: deepl.Translator):
    """Action function for the languages command."""
    source_languages = translator.get_source_languages()
    target_languages = translator.get_target_languages()

    print("Source languages available:")
    for language in source_languages:
        print(f"{language.code}: {language.name}")
    print("Target languages available:")
    for language in target_languages:
        print(
            f"{language.code}: {language.name}{' (supports formality)' if language.supports_formality else ''}"
        )


def document(
    translator: deepl.Translator, file: List[str], dest: str, **kwargs
):
    """Action function for the document command."""
    if not os.path.exists(dest):
        os.makedirs(dest, exist_ok=True)
    elif not os.path.isdir(dest):
        raise Exception("Destination already exists, and is not a directory")

    for this_file in file:
        output_path = os.path.join(dest, os.path.basename(this_file))
        translator.translate_document_from_filepath(
            this_file, output_path, **kwargs
        )


def text(
    translator: deepl.Translator,
    show_detected_source: bool = False,
    **kwargs,
):
    """Action function for the text command."""
    output_list = translator.translate_text(**kwargs)
    for output in output_list:
        if show_detected_source:
            print(f"Detected source language: {output.detected_source_lang}")
        print(output.text)


def get_parser(prog_name):
    """Constructs and returns the argument parser for all commands."""
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Translate text using the DeepL API "
        "(https://www.deepl.com/docs-api).",
        epilog="If you encounter issues while using this program, please "
        "report them at https://github.com/DeepLcom/deepl-python/issues",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"deepl-python v{deepl.__version__}",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        dest="verbose",
        default=0,
        help="print additional information, can be supplied multiple times "
        "for more verbose output",
    )

    parser.add_argument(
        "--auth-key",
        default=None,
        help="authentication key as given in your DeepL account; the "
        f"{env_auth_key} environment variable is used as secondary fallback",
    )
    parser.add_argument(
        "--server-url",
        default=None,
        metavar="URL",
        help=f"alternative server URL for testing; the {env_server_url} "
        f"environment variable may be used as secondary fallback",
    )

    # Note: add_subparsers param 'required' is not available in py36
    subparsers = parser.add_subparsers(metavar="command", dest="command")

    def add_common_arguments(subparser: argparse.ArgumentParser):
        """Adds arguments shared between text and document commands to the
        subparser."""
        subparser.add_argument(
            "--from",
            "--source-lang",
            dest="source_lang",
            help="language of the text to be translated; if omitted, DeepL will "
            "auto-detect the language",
        )
        subparser.add_argument(
            "--to",
            "--target-lang",
            dest="target_lang",
            required=True,
            help="language into which the text should be translated",
        )
        subparser.add_argument(
            "--formality",
            type=str,
            choices=[enum.value for enum in deepl.Formality],
            default=deepl.Formality.DEFAULT.value,
            help="desired formality for translation",
        )

    # create the parser for the "text" command
    parser_text = subparsers.add_parser(
        "text", help="translate text(s)", description="translate text(s)"
    )
    add_common_arguments(parser_text)
    parser_text.add_argument(
        "--split-sentences",
        type=str,
        choices=[enum.value for enum in deepl.SplitSentences],
        default=deepl.SplitSentences.DEFAULT.value,
        help="control sentence splitting before translation, see API for information",
    )
    parser_text.add_argument(
        "--preserve-formatting",
        action="store_true",
        help="leave original formatting unchanged during translation",
    )
    parser_text.add_argument(
        "text",
        nargs="+",
        type=str,
        help="text to be translated. Wrap text in quotes to prevent the shell "
        'from splitting sentences into words. Use "-" to read from standard-input.',
    )
    parser_text.add_argument(
        "--show-detected-source",
        action="store_true",
        help="print detected source language for each text",
    )

    tag_handling_group = parser_text.add_argument_group(
        "tag-handling",
        description="Arguments controlling tag handling, for example XML. "
        "The -tags arguments can have multiple tags specified, as comma-"
        "separated lists or as repeated arguments.",
    )
    tag_handling_group.add_argument(
        "--tag-handling",
        type=str,
        choices=["xml"],
        default=None,
        help="activate processing of formatting tags, for example 'xml'",
    )
    tag_handling_group.add_argument(
        "--outline-detection-off",
        dest="outline_detection",
        default=True,
        action="store_false",
        help="disable automatic tag selection",
    )
    tag_handling_group.add_argument(
        "--non-splitting-tags",
        type=str,
        action="append",
        metavar="tag",
        help="specify tags that may occur within sentences",
    )
    tag_handling_group.add_argument(
        "--splitting-tags",
        type=str,
        action="append",
        metavar="tag",
        help="specify tags that separate text into sentences",
    )
    tag_handling_group.add_argument(
        "--ignore-tags",
        type=str,
        action="append",
        metavar="tag",
        help="specify tags containing text that should not be translated",
    )

    # create the parser for the "document" command
    parser_document = subparsers.add_parser(
        "document",
        help="translate document(s)",
        description="translate document(s)",
    )
    add_common_arguments(parser_document)
    parser_document.add_argument(
        "file", nargs="+", help="file(s) to be translated."
    )
    parser_document.add_argument(
        "dest", help="destination directory to store translated files."
    )

    # create the parser for the "usage" command
    usage_help_str = "print usage information for the current billing period"
    subparsers.add_parser(
        "usage", help=usage_help_str, description=usage_help_str
    )

    # create the parser for the "languages" command
    languages_help_str = "print available languages"
    subparsers.add_parser(
        "languages", help=languages_help_str, description=languages_help_str
    )

    return parser


def main(args=None, prog_name=None):
    parser = get_parser(prog_name)
    args = parser.parse_args(args)

    if args.command is None:
        # Support for Python 3.6 - subcommands cannot be required
        sys.stderr.write(f"Error: command is required\n")
        parser.print_help(sys.stderr)
        sys.exit(1)

    logger = logging.getLogger("deepl")
    if args.verbose == 1:
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())
    elif args.verbose >= 2:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler())
    else:
        logger.setLevel(logging.WARNING)

    server_url = args.server_url or os.getenv(env_server_url)
    auth_key = args.auth_key or os.getenv(env_auth_key)

    try:
        if auth_key is None:
            raise Exception(
                f"Please provide authentication key via the {env_auth_key} "
                "environment variable or --auth_key option"
            )

        # Note: the get_languages() call to verify language codes is skipped
        #       because the CLI makes one API call per execution.
        translator = deepl.Translator(
            auth_key=auth_key, server_url=server_url, skip_language_check=True
        )

        if args.command == "text":
            if len(args.text) == 1 and args.text[0] == "-":
                args.text = [sys.stdin.read()]

        # Remove global args so they are not unrecognised in action functions
        del args.verbose, args.server_url, args.auth_key
        args = vars(args)
        # Call action function corresponding to command with remaining args
        globals()[args.pop("command")](translator, **args)

    except Exception as exception:
        sys.stderr.write(f"Error: {exception}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
