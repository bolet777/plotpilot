# Research: Remove Inside

## Decision: complement of the existing inside span

Keep inside already finds the one interval of a segment that lies in a rectangle (`clip_segment`) or an ellipse (`clip_segment_to_ellipse`). Remove inside keeps the prefix and the suffix of that interval. A tangent is a zero-length interval and does not open a hole. The two kept pieces are flushed apart so the plot SVG gets two paths and no pen-down across the hole.

The printable clip stays first. A shape that misses the printable area removes nothing. A shape that covers it removes the artwork.

## Decision: mode on the session, not a second shape

`ClipMode` is `keep_inside` or `remove_inside`. The default is keep inside, including when an old project omits the key. The rectangle fast path runs only for keep inside.
