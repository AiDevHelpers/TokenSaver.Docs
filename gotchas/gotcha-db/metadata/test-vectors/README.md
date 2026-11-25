# Validator test vectors

Shared conformance suite for the two validator implementations (`validate.py` here,
`Gotcha.Core` in gotcha-mcp). Both must accept everything in `valid/` and reject
everything in `invalid/` (each invalid file's name states the rule it violates).
Add a vector whenever a validation rule is added or a bug slips past one
implementation. These paths are outside the record shards, so `validate.py`'s normal
scan ignores them.
