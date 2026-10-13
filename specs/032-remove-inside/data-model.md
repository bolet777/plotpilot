# Data Model: Remove Inside

`ClipMode`: `keep_inside` (default) or `remove_inside`.

Project JSON, version 1. The clipping object is unchanged except for an optional `mode` string. It is written only when the mode is remove-inside and a shape exists. A missing `mode` loads as keep inside. An unknown mode is a project error.
