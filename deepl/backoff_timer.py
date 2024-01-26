# Copyright 2022 DeepL SE (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.
import random
import time

from . import http_client


class BackoffTimer:
    """Implements exponential-backoff strategy.
    This strategy is based on the GRPC Connection Backoff Protocol:
    https://github.com/grpc/grpc/blob/master/doc/connection-backoff.md"""

    BACKOFF_INITIAL = 1.0
    BACKOFF_MAX = 120.0
    BACKOFF_JITTER = 0.23
    BACKOFF_MULTIPLIER = 1.6

    def __init__(self):
        self._num_retries = 0
        self._backoff = self.BACKOFF_INITIAL
        self._deadline = time.time() + self._backoff

    def get_num_retries(self) -> int:
        return self._num_retries

    def get_timeout(self) -> float:
        return max(
            self.get_time_until_deadline(), http_client.min_connection_timeout
        )

    def get_time_until_deadline(self) -> float:
        return max(self._deadline - time.time(), 0.0)

    def get_time_until_wakeup(self) -> float:
        deadline = self.get_time_until_deadline()
        self._update_deadline()
        return deadline

    def _update_deadline(self):
        # Apply multiplier to current backoff time
        self._backoff = min(
            self._backoff * self.BACKOFF_MULTIPLIER, self.BACKOFF_MAX
        )

        # Get deadline by applying jitter as a proportion of backoff:
        # if jitter is 0.1, then multiply backoff by random value in [0.9, 1.1]
        self._deadline = time.time() + self._backoff * (
            1 + self.BACKOFF_JITTER * random.uniform(-1, 1)
        )
        self._num_retries += 1
