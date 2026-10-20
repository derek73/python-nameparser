# D1 — the segmenterless-activation warning

**When:** a parser is built that activates division for a script no surname vocabulary it holds covers and no segmenter divides.

**Then:** constructing a parser that activates division for scripts with no covering surnames and no segmenter warns at construction, naming the dead scripts and each way out.

**Because:** a parser whose activated scripts nothing can divide behaves like a working parser minus a feature, silently — the one misconfiguration a caller cannot see in output.

```
[segmenterless-ja]  →  warns="deactivate with Policy(segment_scripts=frozenset())"
```

---
no-boundary: any covering surname vocabulary, configured segmenter, or deactivation silences it — the default parser and the zh pack never warn, which every other example in this document exercises.
**Signal:** none in the name: the configuration's activated scripts against its surnames and segmenter
**history:** decisions/D1 · **implemented:** nameparser/_parser.py
