"""CR-0012 d6 test plan: standing checks on the accepted scratch tree A.
(64, 8, True) must be refused (window), the others accepted."""
import sys

sys.path.insert(0, "/home/ec2-user/grouse2")
import acceptance_split as a  # noqa: E402

A = sys.argv[1]
expect = {(64, 0, False): True, (64, 8, False): True, (64, 0, True): True,
          (64, 8, True): False, (62, 1, True): True, (66, 0, False): False}
allok = True
for args, want in expect.items():
    try:
        a.standing_checks(*args, data_root=A)
        got, msg = True, "accepted"
    except a.AcceptanceError as e:
        got, msg = False, "REFUSED: " + " | ".join(str(e).splitlines()[1:])
    ok = got == want
    allok &= ok
    print(f"standing_checks{args}: {msg}  [expected {'accept' if want else 'refuse'}] {'PASS' if ok else 'FAIL'}")
print("ALL AS EXPECTED" if allok else "UNEXPECTED RESULT")
