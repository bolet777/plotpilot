# Research: Ellipse Keep-Inside

## Decision: unit-circle map

An axis-aligned ellipse becomes the unit circle by dividing offsets from the center by the radii. The segment is a quadratic in that space. Hits map back with `x = cx + u * rx`. A circle is the same function with equal radii.

Liang–Barsky stays the printable-area cut and the rectangle fast path. The ellipse cut sees only segments that are already inside the printable rectangle, so a circle drawn across a margin cannot emit points in the margin.

## Decision: one span

An ellipse is convex. Each segment contributes at most one inside span. A tangent is a zero-length span and is dropped with the existing 0.01 mm tolerance. A path that leaves and re-enters is already split by the walker; the pieces are not joined.

## Decision: no new shape tools

Square and circle are Shift constraints on rectangle and ellipse. The choice is two buttons on the clip tool, shown only while that tool is on.
