# Copyright 2024 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import pytest
import deepl

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_async(server):
    async with deepl.TranslatorAsync(
        server.auth_key, server_url=server.server_url
    ) as async_translator:
        text_result = await async_translator.translate_text(
            "Hello, world!", target_lang="de"
        )
        print(text_result.text)

    # async def async_func():
    #     async with deepl.TranslatorAsync(
    #         server.auth_key, server_url=server.server_url
    #     ) as async_translator:
    #         text_result = await async_translator.translate_text(
    #             "Hello, world!", target_lang="de"
    #         )
    #         print(text_result.text)
    #
    # asyncio.run(async_func())


@pytest.mark.asyncio
async def test_translate_text(async_translator_factory):
    async with async_translator_factory() as async_translator:
        text_result = await async_translator.translate_text(
            "Hello, world!", target_lang="de"
        )
        print(text_result.text)
