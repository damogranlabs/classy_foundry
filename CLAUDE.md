
Never run any git commands. I'll commit/merge manually unless specifically stated so. Also don't suggest to "commit this" in prompts.

The package relies on classy_blocks; its source (so no python introspection is needed) lies in right next to this repo in ../classy_blocks. You can always read from that with no extra permission from me. You can also always read from any file in this repository.

Take special care not to repeat code (the DRY principle).
An 'if' sentence is a bad thing unless there's no other way - everything else, utilize object-oriented stuff, patterns and so on.

When a bunch of code is needed to do something, triple-check that there really is no other way - reuse everything the Polyscope platform offers. If there's something really difficult to implement, discuss about changing the user interface/workflow. The less code, the better.

Separate GUI from the logic as much as possible.

Prefer dataclasses over dictionaries (for more than 2 fields, let's say). It's less transparent.

Use typing wherever possible and specifically ignore where it isn't possible.
