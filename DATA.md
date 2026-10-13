# Data

`data/catalogue.json` lists remotes as protocol, address and a map from button
name to command number. It holds no user data: nothing in it comes from people
using the app.

## Sources

| Source | Licence | What it requires |
|---|---|---|
| [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB) | CC0 1.0 | Nothing |
| [irdb](https://github.com/probonopd/irdb) | irdb License | Tell the project before use, show the notice below, and provide up to three copies on request |

Contains/accesses irdb by Simon Peter and contributors, used under permission.
For licensing details and for information on how to contribute to the database,
see https://github.com/probonopd/irdb

## How it was made

The two sources were parsed, their button names mapped to one vocabulary, and
only the protocols REMOTE DNA can transmit were kept. Raw captures were decoded
where they were valid frames of a known protocol.

## Format

```
{"v": 1, "brands": [{"b": "<brand>", "s": [{"p": "<protocol>", "a": <address>, "c": {"<button>": <command>}}]}]}
```
