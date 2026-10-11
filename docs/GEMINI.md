# Add Gemini after receiving the ZIP

## 1. Obtain a key

Create/select a project and API key in https://aistudio.google.com/apikey. Do not paste the key in chat or put it in frontend code. Review the project's available models, quotas and billing settings.

## 2. Edit backend/.env

```dotenv
AI_MODE=gemini
GEMINI_API_KEY=your_real_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-2
```

These are configurable defaults, not a guarantee that your project has access to these model IDs. Choose an available image-capable generation model and compatible embedding model if necessary. Restart the backend after changing configuration. The ZIP already includes the Google GenAI SDK dependency.

## 3. Call the item-analysis endpoint

Create your own report, optionally upload its photos, then POST `/api/listings/{id}/analyze` with a session cookie, X-CSRF-Token and:

```json
{"consent_to_ai":true,"image_ids":[1]}
```

For text-only analysis use `image_ids: []`. Live mode sends the selected photos and the report's title/description to Google; it does not send stored private location trails. Show that disclosure before consent in the future frontend. The endpoint returns suggestions, not an automatic edit. Demo/fallback output is explicitly labeled.

Review, correct, then POST `/api/analyses/{analysis_id}/apply`:

```json
{"confirm":true,"corrections":{"title":"Blue bottle"}}
```

Analysis is tied to a listing revision; stale results cannot overwrite newer edits. A suggested sensitive category may require setting the report PRIVATE before reanalysis or applying through a manual edit. Identifying features are creator-only in API responses.

## 4. Semantic matching

POST `/api/listings/{id}/semantic-index` with `{"consent_to_ai":true}` after reviewing/editing a report. It sends that report's title, description and category to the embedding model. It does not send private fields or the movement trail. Each owner opts in separately. When BOTH reports have current vectors from the same model, matching adds semantic similarity to the deterministic score. Editing a report invalidates its old vector; re-index to restore semantic matching. There is no automatic recurring API spend.

Generation analysis and semantic indexing are independent so outages do not prevent reporting. Indexing errors leave deterministic matching active. Scores are prototype ranking signals, not ownership probabilities.

## 5. Classroom matching

The reference catalog is `backend/data/classrooms.json`. Use `classrooms.example.json` as a format example. Add local photos under `data/reference_images/` that you have permission to use. Retain accurate labels/source URLs. Do not point entries outside the data directory.

Start with 10–20 actual rooms, use an optional building filter to compare at most 12 reference rooms per request, and test with independently taken photos from different angles. Include unknown rooms and look-alike rooms. Source discovery: https://dcs.rutgers.edu/learning-spaces/ and https://dcs.rutgers.edu/learning-spaces/general-purpose-classrooms/ . Rutgers photos are not copied into this package.

POST `/api/listings/{id}/recognize-room`:

```json
{"consent_to_ai":true,"image_id":1,"building":"Your building"}
```

Results are limited to configured room IDs, with evidence/conflicts. They always require confirmation. Confirm by editing the report's `location` or `private_location`; suggestions are never automatically published. Demo mode returns no invented candidates. Empty catalogs return an explanatory result.

## 6. Multi-item scan drafts

POST `/api/listings/{id}/scan-items` with `consent_to_ai` and `image_id`. The caller must own the source report/photo. Live mode can propose up to eight drafts. Review each draft and create separate reports; nothing is auto-posted. Demo mode returns no invented objects. This is a stretch workflow, not an evaluated object detector.

## Evaluate honestly

`python benchmark.py` evaluates a small supplied synthetic dataset without API calls. `python benchmark.py --gemini` explicitly sends the synthetic examples to Google to compare semantic assistance. It uses real calls and may incur charges. Replace/add representative examples before claiming real-world performance. No live Gemini benchmark was performed when producing this ZIP.

Official references:
- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/image-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/embeddings
