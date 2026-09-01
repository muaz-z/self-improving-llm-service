# Self-Improving LLM Service

A FastAPI service that processes customer-support messages into validated
structured outputs and automatically improves its prompt using LLM-based
evaluation and regression testing.

Rather than immediately deploying an AI-generated prompt, the service treats
prompt improvement as a controlled deployment process:

1. Process real requests using the active prompt.
2. Store outputs for later evaluation.
3. Review outputs using a stronger evaluator model.
4. Generate a candidate prompt from failed cases.
5. Regression-test the candidate against historical successes and current failures.
6. Promote the candidate only if it improves failing cases without breaking
   previously successful ones.

This makes automated prompt improvement measurable, traceable, and safer than
blindly replacing prompts based on individual failures.

## Example Task

The service uses customer-support classification as its example workload.

The `/process` endpoint classifies a customer-support message into a structured
schema containing:

- intent
- sentiment
- urgency
- entities
- whether human intervention is needed

This workload was chosen because the fields require semantic interpretation,
creating useful failure cases for demonstrating the automated prompt-improvement
and regression-testing pipeline.

## Tech Stack

-   Python 3.12+
-   FastAPI
-   asyncio
-   Pydantic
-   SQLite
-   OpenAI API


## Models

| Role | Model | Used for |
| --- | --- | --- |
| Processing | `gpt-5-mini` | `/process` structured classification and candidate reprocessing during regression |
| Review / improvement | `gpt-5.4` | Sample review, prompt improvement, and candidate output review |

A smaller model handles the core task so the prompt-improvement loop has meaningful failures to learn from. A stronger model acts as the reviewer and prompt author.

## Setup

### 1. Create and activate a virtual environment

``` bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

``` bash
pip install -r requirements.txt
```

For development and testing:

``` bash
pip install -r requirements-dev.txt
```

### 3. Configure environment variables

Create a `.env` file and provide the required OpenAI API key:

``` env
OPENAI_API_KEY=your_key_here
```

### 4. Run the application

``` bash
python -m uvicorn app.main:app --reload
```

FastAPI's interactive API documentation is then available through the
application's `/docs` route.

## API

### `POST /process`

Processes a message using the currently active prompt version and
returns a Pydantic-validated structured result.

Example request:

``` json
{
  "message": "I was charged twice and I want a refund."
}
```

A processed sample is persisted together with its input, structured
output, and the prompt version that produced it.

### `GET /prompts`

Returns the current and historical prompt versions, including:

-   version
-   reason for the change
-   active/inactive state
-   regression outcome
-   creation timestamp
-   prompt content from the versioned `.txt` file

The response also includes `active_version` for quick inspection of
which prompt `/process` is currently using.

### `GET /samples`

Browse processed samples and their review status.

Supports optional query filters:

-   `review_status` — e.g. `pending` or `reviewed`
-   `prompt_version` — samples produced by a specific prompt
-   `limit` — max rows returned (default 50, max 200)

Each sample includes the input message, structured output, prompt
version used, review status/result/feedback, review run association,
and timestamps.

### `POST /review`

Runs the automated review and prompt-improvement workflow.

The endpoint:

1.  Loads samples associated with the active prompt version.
2.  Uses a stronger reviewer LLM to evaluate the structured outputs
    against the closed `ProcessResult` schema.
3.  Persists pass/fail results and reviewer feedback.
4.  Generates an improved candidate prompt when failures are found.
5.  Builds a regression set from up to 100 randomly sampled historical
    passes plus the current review batch.
6.  Reprocesses that set using the candidate prompt.
7.  Reviews the candidate outputs and checks for regressions.
8.  Persists the regression outcome on the candidate prompt version.
9.  Promotes the candidate only when the regression criteria pass.

## Review and Improvement Flow

``` text
POST /process
      |
      v
 Active Prompt
      |
      v
 Processing LLM
      |
      v
Structured Output
      |
      v
 Store Sample
      |
      v
 POST /review
      |
      v
 Reviewer LLM
      |
      v
   Failures?
   /      \
 no        yes
 |          |
done        v
       Generate Candidate
             |
             v
       Regression Test
             |
       +-----+-----+
       |           |
     pass         fail
       |           |
       v           v
   Activate     Keep Current
   Candidate       Prompt
```

## Prompt Versioning

Prompt content is stored as versioned `.txt` files. Prompt metadata is
stored separately in SQLite.

Each prompt version tracks information such as:

-   version
-   reason for the change
-   active/inactive state
-   whether regression checks passed (`regression_passed`)
-   creation timestamp

`/process` resolves the active prompt version so that a successfully
promoted candidate is used by subsequent requests.

## Regression Protection

Before a candidate can be promoted, it is evaluated against a regression
set built from:

-   up to 100 historical samples that previously passed review
-   the current review batch (including failures that should improve)

Historical passes are sampled with `ORDER BY RANDOM() LIMIT 100` so
regression cost stays bounded as successful production traffic grows.
The current review batch is always included in full.

Each sample's previous result is compared with the candidate result:

  Previous result   Candidate result   Meaning
  ----------------- ------------------ -----------------
  Passed            Passed             Unchanged
  Passed            Failed             Regression
  Failed            Passed             Improvement
  Failed            Failed             Still incorrect

The current promotion rule is:

``` python
regressions == 0 and improvements > 0
```

A candidate therefore needs to fix at least one previously failing case
from the current review batch without breaking any historically
successful case, or any case that passed in the current review.

The regression outcome is stored on the candidate prompt version so
prompt history remains queryable.

## Storage and Traceability

SQLite is used as a lightweight persistent store.

### `samples`

Stores the processed input and its review state, including:

-   input message
-   structured output
-   prompt version used
-   review status
-   review result
-   reviewer feedback
-   review run association
-   timestamps

### `prompt_versions`

Tracks prompt history and metadata, including the reason a candidate was
created, whether it is active, and whether it passed regression checks.

### `prompt_evaluations`

Stores candidate regression comparisons for individual samples:

-   candidate prompt version
-   sample ID
-   previous result
-   candidate result
-   reviewer feedback
-   timestamp

This provides a history of which cases improved or regressed for each
candidate.

### `review_runs`

Tracks an individual review/improvement workflow and its state.

A run can be:

-   `running`
-   `failed`
-   `completed`

Samples are associated with the review run so that a failed workflow can
be retried using the same sample set.

## Retry Behaviour

Failures can occur after a review run has already started, for example
during:

-   reviewer LLM calls
-   candidate generation
-   regression testing
-   persistence

When the workflow fails, its review run is marked as `failed`.

A later `/review` request can find that resumable run and retry it with
the same associated samples rather than losing the original review set.

The current implementation retries the workflow for that run rather than
resuming from the exact stage where execution stopped. Stage-level
checkpoints would be a natural production improvement.

## Error Handling

The service distinguishes external LLM failures from internal
workflow/persistence failures.

LLM failures return HTTP 502; internal persistence/workflow failures return HTTP 500.

Candidate prompt persistence also includes cleanup so that a prompt file
is removed if its corresponding metadata cannot be persisted.

## Logging

The application logs important workflow metadata such as:

-   active prompt version
-   review run ID
-   sample count
-   failed sample count
-   candidate prompt version
-   regression result
-   candidate promotion

The intent is to make the improvement workflow observable without
relying on full user-message or prompt contents in logs.

## Testing

Install development dependencies:

``` bash
pip install -r requirements-dev.txt
```

Run the test suite with:

``` bash
pytest -v
```

Development tooling is kept in `requirements-dev.txt`, including pytest
and Ruff.

Lint and format with:

``` bash
ruff check .
ruff format .
```

## Design Decisions and Trade-offs

The implementation prioritizes the core prompt-improvement lifecycle,
regression safety, and traceability while keeping the infrastructure lightweight.

### Must-haves

The implementation prioritizes:

-   validated structured output from `/process`
-   persistent samples and prompt versions
-   automated review with a stronger model
-   prompt generation from failed cases
-   regression protection before promotion
-   automatic activation of successful candidates
-   traceability of prompt evaluations
-   recoverable review runs

### SQLite

SQLite keeps the demo lightweight and easy to run while satisfying the
persistence requirements.

For a high-traffic production system, I would move the persistent state
to a database designed for concurrent workloads, such as PostgreSQL.

### Prompt files and database metadata

Prompt content is kept in versioned `.txt` files, while mutable metadata
and evaluation history are stored in SQLite.

This keeps prompt text easy to inspect while allowing activation state
and evaluation history to remain queryable.

The trade-off is coordination between filesystem and database state. The
implementation performs cleanup when prompt metadata persistence fails
after writing a candidate file.

### Synchronous SQLite access

LLM work is asynchronous, while the lightweight SQLite persistence uses
synchronous database access.

This keeps the demo implementation straightforward. For heavier
workloads I would use an async-capable persistence layer or move
long-running review work into workers.

### Explicit `/review` endpoint

An explicit `/review` endpoint makes the self-improvement lifecycle easy to
trigger, inspect, and demonstrate.

For a production system, this workflow would be better suited to asynchronous
background execution.

## Current Limitations

The current implementation intentionally keeps the infrastructure lightweight.

Potential extensions include:

- metrics and monitoring dashboard
- stage-level workflow checkpoints
- distributed/background job processing
- curated golden/held-out evaluation datasets

## Production and Scaling Considerations

For a production system with heavy usage, I would:

- run review/improvement workflows as background jobs
- use PostgreSQL instead of SQLite
- replace random historical sampling with a curated, bounded regression set
  combining golden cases and recent production passes
- add locking around prompt creation and activation
- add provider retries, metrics, and alerting around failed reviews and prompt
  promotions

The current implementation bounds regression cost with
`ORDER BY RANDOM() LIMIT 100` for historical passes and uses a concurrency
semaphore for candidate reprocessing.

## TLDR

The core design treats prompt improvement as a controlled deployment
process rather than immediately replacing a prompt whenever the reviewer
finds a mistake:

1.  collect real processed samples,
2.  review them against the closed output schema,
3.  generate a candidate from failures,
4.  regression-test against historical successes plus the current batch,
5.  record the comparison and regression outcome,
6.  promote only when the candidate improves performance without
    introducing regressions.

This keeps the automated improvement mechanism traceable and provides a
clear path toward a more scalable production implementation.
