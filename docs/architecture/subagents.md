# Subagent Boundary

## Motivation

Lexora needs one legal Supervisor to delegate bounded case framing, legal research, and material
analysis without encoding those product roles in North or building one large fixed workflow. This is
a concrete host requirement for a small reusable delegation primitive.

## Runtime Contract

```text
Host Run
  -> lead agent
      -> delegation tool
          -> stateless subagent
              -> host-selected skills and tools
          <- structured result or final text
      <- tool result
  -> one final lead-agent response
```

North owns agent construction, delegation execution, callback propagation, timeout, generic event
attribution, and result serialization. The host owns role prompts, task schemas, tool implementations,
authorization, business memory, persistence, budgets beyond the per-call limits, and the final answer.
North graphs and delegation tools declare a dictionary runtime context schema so the host's parent
Run context can pass to subagent tools without becoming graph state or producing serializer ambiguity.
Each delegation carries a short user-facing `description` separately from its bounded `task`, matching
DeerFlow's observable task contract. An `AgentDefinition.input_builder` may attach an
exact, host-owned context projection to the child input. North invokes that callback but never chooses,
stores, or interprets the business data it returns.

## Invariants

- A subagent invocation remains inside the parent Run and does not create a product Run or message.
- A subagent has no Checkpointer in the first version and cannot mutate the lead agent's graph state.
- Only tools explicitly assigned to the subagent are visible to it.
- Skills are explicitly selected per subagent and remain prompt/runtime scope rather than thread state.
- Parent callbacks and runtime context propagate so model usage and errors remain observable.
- The lead model does not need to reproduce lossless host context inside the task when an input builder
  is configured; the model still decides whether to delegate and states the specialist objective.
- Subagent model calls carry `subagent:<name>` attribution.
- Cancellation propagates naturally; a host-selected timeout bounds each delegation.
- The tool result contains only the subagent's structured response or final assistant text.

## Non-goals

- Nested subagents
- A generic multi-agent topology or workflow DSL
- Shared scratchpad or business memory
- Automatic business-data commits
- A second event, message, thread, or Run persistence model
- Automatic tool gating inferred from Skill metadata

Those capabilities require separate host evidence and contracts.
