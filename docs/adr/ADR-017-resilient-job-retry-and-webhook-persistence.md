# ADR-017: Resilient Job Retry, Webhook Persistence, and Forwarded Media Preservation

## Status
Accepted

## Context
When investigating why incoming posts were occasionally not ingested after service reboots or following recoverable errors (e.g., API quota exhausted HTTP 402, transient network drops):
1. **Lost Updates on Startup**: `main.py` previously invoked `await bot.delete_webhook(drop_pending_updates=True)`. During any PM2 reload or server reboot, messages sent by users during the restart window were deleted permanently from Telegram's servers.
2. **Blocked Resubmission of Failed Jobs**: The deduplication logic in `submit_content` treated any existing hash as a duplicate. If a job previously failed (status `FAILED` due to expired API balance or network timeout), resending the same post returned the failed job without resetting its status or clearing the error, blocking subsequent processing.
3. **Observability Gap**: `handle_incoming_content` lacked structured reception logging, making it hard to trace message arrival in production logs.
4. **Forwarded Media Ingestion**: When users forwarded posts containing existing photos from channels (e.g., `[ Фотография ]`), the photo file ID was ignored and discarded, forcing fallback to AI image generation. If the AI gateway lacked image generation models, the post became text-only despite having an existing cover image.
5. **Unified Message Bubble Assurance**: Strict verification that all photo posts in preview and channel publication are delivered as a single cohesive message bubble (`send_photo` with `caption <= 1024` chars and inline keyboard), preventing separate detached photo and text bubbles.

## Decision
1. **Preserve Pending Updates**: Change to `delete_webhook(drop_pending_updates=False)` on application startup so messages sent during deploys or restarts are faithfully dequeued and processed.
2. **Automatic Retry for Failed Jobs in Ingestion**:
   - If `submit_content` encounters an existing job whose status is `FAILED` (or interrupted in `EXTRACTING`, `REWRITING`, `GENERATING_IMAGE`), the orchestrator resets the job status to `JobStatus.PENDING`, clears previous error messages (`error_message = None`), updates timestamps and tone, saves it, and marks `is_duplicate = False`.
   - The user immediately receives `⏳ Принял в работу!` and the pipeline executes with the updated configuration.
3. **Structured Incoming Logging**:
   - Add explicit INFO log on message entry in `handle_incoming_content`: user ID, chat ID, message ID, content length, presence of media/photos, and extracted target URL.
4. **Forwarded Media Preservation**:
   - When an incoming message contains a photo (`message.photo`), download the highest resolution photo to `storage/images/fwd_{job_id}.jpg` and store it in `job.image` as a valid non-placeholder `ImageAsset`.
   - In `process_pipeline`, if `job.image` is already set and not a placeholder, retain the existing photo instead of attempting redundant AI generation.
5. **Unified Message Presentation**:
   - Both in DM preview (`send_draft_preview`) and channel publication (`publish_to_channel`), photo and text are sent in a single `bot.send_photo` call with `caption=draft.render_post(max_length=1024)`.

## Consequences
- Zero message drop across restarts and deployment updates.
- Transparent recovery: fixing an API key allows users to immediately re-send previously failed posts without manual database intervention.
- Immediate traceability in PM2 production logs.
- Native cover photos in forwarded posts are seamlessly preserved.
- Posts remain unified in a single message bubble adhering to Telegram's 1024-character caption limit.
