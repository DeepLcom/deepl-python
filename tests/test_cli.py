# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from click.testing import CliRunner
from .conftest import example_text, needs_real_server

# flake8: noqa: F401
from deepl import __main__
import deepl
import pathlib
import pytest
import re


main_function = deepl.__main__


@pytest.fixture
def runner(server):
    env = {
        "DEEPL_SERVER_URL": server.server_url,
        "DEEPL_AUTH_KEY": server.auth_key,
    }
    return CliRunner(env=env)


def test_help(runner):
    result = runner.invoke(main_function, "--help")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "usage" in result.output


def test_version(runner):
    result = runner.invoke(main_function, "--version")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "deepl-python v" in result.output
    version_regex = re.compile(r"deepl-python v\d+\.\d+\.\d+")
    assert version_regex.match(result.output) is not None


def test_verbose(runner):
    # verbose = info
    result = runner.invoke(main_function, "--verbose usage")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Request to DeepL API" in result.output

    # verbose = debug
    result = runner.invoke(main_function, "-vv usage")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Request to DeepL API" in result.output
    assert "Request details" in result.output


def test_no_auth(runner):
    result = runner.invoke(
        main_function, "usage", env={"DEEPL_AUTH_KEY": None}
    )
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "DEEPL_AUTH_KEY" in result.output


def test_no_command(runner):
    result = runner.invoke(main_function, "")
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "command is required" in result.output


def test_usage(runner):
    result = runner.invoke(main_function, "usage")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Usage this billing period" in result.output


def test_languages(runner):
    result = runner.invoke(main_function, "languages")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Source languages" in result.output
    assert "Target languages" in result.output
    assert "DE: German" in result.output
    assert "EN: English" in result.output

    result = runner.invoke(deepl.__main__, "languages --glossary")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "supported for glossaries" in result.output
    assert "de, en" in result.output


def test_text(runner):
    result = runner.invoke(
        main_function, 'text --to DE "proton beam" --show-detected-source'
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"] in result.output
    assert "Detected source" in result.output


def test_text_stdin(runner):
    result = runner.invoke(
        main_function,
        "text --to DE --show-detected-source -",
        input=example_text["EN"],
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"] in result.output
    assert "Detected source" in result.output


@needs_real_server
def test_text_preserve_formatting(runner):
    result = runner.invoke(
        main_function, 'text --to DE --preserve-formatting "proton beam"'
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"].lower() in result.output


def test_text_split_sentences(runner):
    result = runner.invoke(
        main_function,
        '-vv text --to DE --split-sentences nonewlines "proton beam"',
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    # Check split_sentences parameter is sent in HTTP request
    regex = re.compile("Request details.*split_sentences.*nonewlines.*")
    assert any(
        regex.match(line) is not None for line in result.output.split("\n")
    ), f"output:\n{result.output}"


def test_text_tags(runner):
    result = runner.invoke(
        main_function,
        "-vv text --to DE --tag-handling xml --splitting-tags split "
        '--ignore-tags a,b --ignore-tags c --ignore-tags d "proton beam"',
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    # Check ignore_tags parameter is sent in HTTP request
    regex = re.compile("Request details.*'ignore_tags': 'a,b,c,d'")
    assert any(
        regex.match(line) is not None for line in result.output.split("\n")
    ), f"output:\n{result.output}"
    # Check splitting_tags parameter is sent in HTTP request
    regex = re.compile("Request details.*'splitting_tags': 'split'")
    assert any(
        regex.match(line) is not None for line in result.output.split("\n")
    ), f"output:\n{result.output}"


def test_document(runner, tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    output_dir = tmpdir / "output"
    input_document = tmpdir / "document.txt"
    input_document.write_text(example_text["EN"])
    output_document = output_dir / "document.txt"

    result = runner.invoke(
        main_function, f"-vv document --to DE {input_document} {output_dir}"
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"] == output_document.read_text()


def test_document_occupied_output(runner, tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    output_dir = tmpdir / "output"
    input_document = tmpdir / "document.txt"
    input_document.write_text(example_text["EN"])
    # Create a file in place of the output directory
    output_dir.touch()

    result = runner.invoke(
        main_function, f"-vv document --to DE {input_document} {output_dir}"
    )
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "already exists" in result.output


def test_invalid_document(runner, tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    output_dir = tmpdir / "output"
    input_document = tmpdir / "document.invalid"
    input_document.write_text(example_text["EN"])

    result = runner.invoke(
        main_function, f"-vv document --to DE {input_document} {output_dir}"
    )
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "Invalid file" in result.output or "file extension" in result.output


def test_glossary_no_subcommand(runner):
    result = runner.invoke(main_function, "glossary")
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "subcommand is required" in result.output


def test_glossary_create(
    runner, glossary_name, tmpdir, cleanup_matching_glossaries
):
    name_cli = f"{glossary_name}-cli"
    name_stdin = f"{glossary_name}-stdin"
    name_file = f"{glossary_name}-file"
    entries = {"Hallo": "Hello", "Maler": "Artist"}
    entries_tsv = deepl.convert_dict_to_tsv(entries)
    entries_cli = "\n".join(f"{s}={t}" for s, t in entries.items())
    file = tmpdir / "glossary_entries"
    file.write(entries_tsv)

    try:
        result = runner.invoke(
            main_function,
            f'-vv glossary create --name "{name_cli}" --from DE --to EN '
            f"{entries_cli}",
        )
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        result = runner.invoke(
            main_function,
            f'-vv glossary create --name "{name_stdin}" --from DE --to EN -',
            input=entries_tsv,
        )
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        result = runner.invoke(
            main_function,
            f'-vv glossary create --name "{name_file}" --from DE --to EN '
            f"--file {file}",
        )
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"

        result = runner.invoke(main_function, "-vv glossary list")
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        assert name_cli in result.output
        assert name_stdin in result.output
        assert name_file in result.output

        # Cannot use --file option together with entries
        result = runner.invoke(
            main_function,
            f'-vv glossary create --name "{name_file}" --from DE --to EN '
            f"--file {file} {entries_cli}",
        )
        assert (
            result.exit_code == 1
        ), f"exit: {result.exit_code}\n {result.output}"
        assert "--file argument" in result.output

    finally:
        cleanup_matching_glossaries(
            lambda glossary: glossary.name in [name_file, name_cli, name_stdin]
        )


def test_glossary_get(translator, runner, glossary_manager):
    with glossary_manager() as created_glossary:
        created_id = created_glossary.glossary_id

        result = runner.invoke(main_function, f"-vv glossary get {created_id}")
        print(result.output)
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        assert created_id in result.output
        assert created_glossary.name in result.output


def test_glossary_list(translator, runner, glossary_manager):
    with glossary_manager(glossary_name_suffix="1") as g1, glossary_manager(
        glossary_name_suffix="2"
    ) as g2, glossary_manager(glossary_name_suffix="3") as g3:
        glossary_list = [g1, g2, g3]

        result = runner.invoke(main_function, "-vv glossary list")
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        for glossary in glossary_list:
            assert glossary.name in result.output


def test_glossary_entries(translator, runner, glossary_manager):
    entries = {"Hallo": "Hello", "Maler": "Artist"}
    with glossary_manager(entries=entries) as created_glossary:
        created_id = created_glossary.glossary_id
        result = runner.invoke(
            main_function, f"-vv glossary entries {created_id}"
        )
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        for source, target in entries.items():
            assert f"{source}\t{target}" in result.output


def test_glossary_delete(translator, runner, glossary_manager):
    with glossary_manager() as created_glossary:
        created_id = created_glossary.glossary_id
        result = runner.invoke(main_function, "glossary list")
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        assert created_id in result.output

        # Remove the created glossary
        result = runner.invoke(
            main_function, f'glossary delete "{created_id}"'
        )
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"

        result = runner.invoke(main_function, "glossary list")
        assert (
            result.exit_code == 0
        ), f"exit: {result.exit_code}\n {result.output}"
        assert created_id not in result.output
