# Runtime Observability

`north` follows DeerFlow's separation between live transport, durable event storage,
and product presentation without copying the DeerFlow Gateway into the harness.

## Boundaries

- `RuntimeJournal` translates LangChain callbacks into product-neutral events.
- `RuntimeEventSink` is an async integration boundary owned by the caller.
- `north` does not choose a database, SSE server, tenant policy, or user-facing text.
- Product applications sanitize and persist events, then project them into their UI.
- Live stream fanout and durable history are separate concerns. A live stream may be
  Redis-backed while the durable source of truth remains PostgreSQL.

## Event Contract

The initial contract covers:

- `model.started`, `model.completed`, `model.error`
- `tool.started`, `tool.completed`, `tool.error`

Model events include a call ID, caller classification, latency, and usage metadata.
Tool events include a call ID, tool name, inputs or output, latency, and errors. Call
IDs let products correlate a tool start with its terminal event.

Subagent events use the delegation tool call ID as `task_id`. Model and tool events
executed inside a subagent also carry that `task_id`, in addition to their own
`call_id`. This gives host products an explicit hierarchy without inferring ownership
from timestamps or actor names:

```text
subagent task_id
  -> model call_id
  -> tool call_id
```

Start and terminal events for one invocation always retain the same identifier. North
does not combine separate calls merely because they use the same tool or subagent type.
Consumers may collapse detail for presentation, but correlation remains call-accurate.

`north` normalizes model usage to `input_tokens`, `output_tokens`, and `total_tokens`
across common LangChain and provider field names. `RuntimeUsageAccumulator` aggregates
the normalized events once per model call, including intermediate tool-selection calls.
Products own pricing, budgets, tenant attribution, and durable usage storage.

This is callback-based observability, not agent middleware. `RuntimeJournal` is a
LangChain callback handler that observes completed provider calls without changing agent
state or control flow. `RuntimeUsageAccumulator` consumes those runtime events and
deduplicates usage by `call_id`. Middleware remains reserved for behavior that participates
in agent execution, such as clarification, compaction, loop protection, or tool-error policy.

## Security

The journal does not persist model prompts. Event payloads can still contain sensitive
tool arguments or results, so every product sink must apply an allowlist before storage
or display. Raw provider reasoning is not synthesized by `north`; provider-supplied
reasoning may be carried in a model message and products decide whether it is safe to
show.

Never emit credentials, system prompts, database connection strings, hidden tenant
context, or unrestricted tool output to a user-facing stream.

## Product Presentation Contract

North events are execution facts, not ready-made user interface rows. A host-owned
projector must:

- merge one start and terminal pair by `call_id` or `task_id`;
- preserve separate invocations of the same tool;
- use `task_id` for subagent parentage instead of temporal inference;
- allowlist any tool input used as a user-facing detail;
- omit raw model output, hidden reasoning, unrestricted tool results, and provider
  exception text;
- map technical names to product language outside North.

This deliberately follows DeerFlow's call and task identity model. North does not
standardize one visual component: a general assistant may use expandable task cards,
while a focused product may use a compact activity timeline.

## Tool Message Artifacts

North's canonical `messages` stream preserves JSON-compatible
`ToolMessage.artifact` separately from model-visible `ToolMessage.content`.
Host products may use this to carry a complete validated presentation snapshot
while keeping model context compact. North transports the artifact without
interpreting product fields; the host owns validation, durable projection,
redaction, and UI semantics.

Checkpoint artifacts are runtime transport/state, not product conversation
history. A host must durably project an artifact before later compaction removes
it. Artifact preservation does not authorize North to include it in model input.

## Invocation

`invoke_agent_once(..., event_sink=...)` appends a `RuntimeJournal` to existing runnable
callbacks. With no sink, invocation behavior is unchanged.

`RunExecutor.execute(...)` is the only production owner of the Agent's canonical
`astream` loop. It normalizes graph chunks and publishes selected modes directly to an
asynchronous `StreamBridge`. Hosts use lifecycle hooks to durably settle product state
before the executor publishes the end sentinel. `RuntimeJournal` remains the separate
audit and usage boundary.
