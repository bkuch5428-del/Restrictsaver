---
name: Telegram history pagination
description: Durable constraints for reading sparse Telegram channel history.
---

Telegram message IDs are not contiguous. Deleted or inaccessible posts create
gaps, so a missing individual ID is not evidence that channel history has
ended. Use Telegram's paginated history iterator and advance from the last
actual message ID.

**Why:** Probing sequential IDs caused the forwarder to stop at the first hole
and made an empty result indistinguishable from a completed history scan.

**How to apply:** Treat empty history as a retryable condition, log diagnostic
reasons, and keep the worker alive when polling for newly available messages.