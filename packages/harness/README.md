# North Runtime

The reusable runtime package behind North Agent. It provides agent assembly, tools, skills,
middleware, runtime events, usage normalization, and configurable checkpointers for host products.
Its opt-in title middleware generates `ThreadState.title` inside the first Agent run so hosts can
project the checkpointed title into their own conversation metadata without creating another run.

The distribution and import name remain `north`:

```python
from north import AppClient, RuntimeJournal, invoke_agent_once
```

See the [repository README](../../README.md) for installation and integration examples.
