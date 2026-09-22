"""Single source of truth for the project's state bounding boxes.
(min_lon, min_lat, max_lon, max_lat), ~0.1 deg buffer around each state's
observed sighting extent. See BUG-0001 for why this exists as its own
module instead of being duplicated per-script (it previously drifted to
two different NH max_lon values across 7 files).

NOTE: the NH max_lon value below (-70.600) was chosen as the majority
value across the prior duplicated copies, not verified against the real
sighting-data extent (no data/ tree was available in the environment that
made this fix). Confirm against real NH sighting data before relying on
this for a production run; update here (one place) if it needs to change.
"""
BOXES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.600, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}
