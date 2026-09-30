from regions import BOXES
import itertools
def area(b): return (b[2]-b[0])*(b[3]-b[1])
for a,bn in itertools.combinations(BOXES,2):
    A,B = BOXES[a],BOXES[bn]
    ox0,ox1 = max(A[0],B[0]), min(A[2],B[2])
    oy0,oy1 = max(A[1],B[1]), min(A[3],B[3])
    if ox1>ox0 and oy1>oy0:
        ov=(ox1-ox0)*(oy1-oy0)
        print(f"{a} INTER {bn}: lon {ox0:.3f}..{ox1:.3f} ({ox1-ox0:.3f} deg), lat {oy0:.3f}..{oy1:.3f} ({oy1-oy0:.3f} deg)")
        print(f"   overlap area {ov:.4f} deg^2 = {100*ov/area(A):.1f}% of {a} box, {100*ov/area(B):.1f}% of {bn} box")
    else:
        print(f"{a} INTER {bn}: EMPTY")
print()
for k,v in BOXES.items():
    print(k, v, "width_deg", round(v[2]-v[0],3), "height_deg", round(v[3]-v[1],3))
print()
pt=(-71.14,44.78)
print("Errol", pt, "-> boxes containing it:", [k for k,v in BOXES.items() if v[0]<=pt[0]<=v[2] and v[1]<=pt[1]<=v[3]])
# fraction of NH box area covered by union of ME+VT boxes (they don't overlap each other? check)
