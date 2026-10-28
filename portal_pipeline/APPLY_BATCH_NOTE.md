
## /apply --batch

Author: Yazad Madan. Date: 2026-10-28.

Prepare 2 or 3 queue items through the existing build, audit, and prepare steps. From `portal_pipeline`, run `py batch_apply.py --folders "F1" "F2" "F3" --workers 3`. Edge is checked once; each application uses a separate process and tab. Login is manual and serialized per host. The current driver never types credentials or verification codes.

After the batch, review `data/learning_queue.md`, fill the answer values in `data/learning_queue.json`, and run `py answer_memory.py --import-answers data/learning_queue.json`. Reviewed answers are shared and queued jobs resume only in their original tabs. Blank, protected, immigration, and history-row answers stay pending. `py batch_apply.py --learn-only` rebuilds the latest batch sheet without a browser. Add `--store-only` to the import to store answers without resuming tabs. Batch `--dry` only scans existing matching tabs.

Yazad handles login, CAPTCHA, verification codes, signatures, attestations, and final submission. Tracker status remains To Apply. Shared-profile cookies, popups, and focus changes can still interfere across tabs. Synthetic checks do not establish live compatibility.
