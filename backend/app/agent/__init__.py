"""Voice-purchase agent: the decision layer around the LLM.

The LLM does one narrow job (turn a transcript into a structured purchase).
Everything that decides what happens next is deterministic code in this package:

- ``output_parsing``  strict parsing of the model's JSON against the schema
- ``grounding``       checks that the numbers the model returned were actually spoken
- ``quality_gate``    routes each extraction to "ready", "needs_attention" or "manual_entry"
- ``approval``        decides whether a confirmed purchase needs a manager's approval
"""
