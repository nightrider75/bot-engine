#
# Copyright (c) 2024-2025 Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import unittest

from bot_engine.utils.text.skip_tags_aggregator import SkipTagsAggregator


class TestSkipTagsAggregator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.aggregator = SkipTagsAggregator([("<spell>", "</spell>")])

    async def test_no_tags(self):
        await self.aggregator.reset()

        # No tags involved, aggregate at end of sentence.
        result = await self.aggregator.aggregate("Hello Bot Engine!")
        self.assertEqual(result, "Hello Bot Engine!")
        self.assertEqual(self.aggregator.text, "")

    async def test_basic_tags(self):
        await self.aggregator.reset()

        # Tags involved, avoid aggregation during tags.
        result = await self.aggregator.aggregate("My email is <spell>foo@example.com</spell>.")
        self.assertEqual(result, "My email is <spell>foo@example.com</spell>.")
        self.assertEqual(self.aggregator.text, "")

    async def test_streaming_tags(self):
        await self.aggregator.reset()

        # Tags involved, stream small chunk of texts.
        result = await self.aggregator.aggregate("My email is <sp")
        self.assertIsNone(result)
        self.assertEqual(self.aggregator.text, "My email is <sp")

        result = await self.aggregator.aggregate("ell>foo.")
        self.assertIsNone(result)
        self.assertEqual(self.aggregator.text, "My email is <spell>foo.")

        result = await self.aggregator.aggregate("bar@example.")
        self.assertIsNone(result)
        self.assertEqual(self.aggregator.text, "My email is <spell>foo.bar@example.")

        result = await self.aggregator.aggregate("com</spe")
        self.assertIsNone(result)
        self.assertEqual(self.aggregator.text, "My email is <spell>foo.bar@example.com</spe")

        result = await self.aggregator.aggregate("ll>.")
        self.assertEqual(result, "My email is <spell>foo.bar@example.com</spell>.")
        self.assertEqual(self.aggregator.text, "")
