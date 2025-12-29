#
# Copyright (c) 2024-2025 Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import unittest

from bot_engine.utils.text.simple_text_aggregator import SimpleTextAggregator


class TestSimpleTextAggregator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.aggregator = SimpleTextAggregator()

    async def test_reset_aggregations(self):
        assert await self.aggregator.aggregate("Hello ") == None
        assert self.aggregator.text == "Hello "
        await self.aggregator.reset()
        assert self.aggregator.text == ""

    async def test_simple_sentence(self):
        assert await self.aggregator.aggregate("Hello ") == None
        assert await self.aggregator.aggregate("Bot Engine!") == "Hello Bot Engine!"
        assert self.aggregator.text == ""

    async def test_multiple_sentences(self):
        assert await self.aggregator.aggregate("Hello Bot Engine! How are ") == "Hello Bot Engine!"
        assert await self.aggregator.aggregate("you?") == " How are you?"
