"""BUG-0067 (CR-0018 C3) repro: the name bound by `except ... as NAME`
is deleted at the end of the clause (Python 3), so a later reference to
it raises UnboundLocalError. Same shape as ee_init in
download_tcc_nlcd.py / download_treemap.py before the fix. No network.

Run: python docs/quality/evidence/CR-0018-candidates/c3_repro.py
"""
import sys


def ee_init_shape():
    try:
        raise RuntimeError("path 1 failed")
    except Exception as persistent_err:
        pass
    try:
        raise ValueError("path 2 failed")
    except Exception as adc_err:
        raise SystemExit(f"both failed: {persistent_err} / {adc_err}")


if __name__ == "__main__":
    print("python", sys.version.split()[0])
    try:
        ee_init_shape()
    except BaseException as e:
        print("raised :", type(e).__name__, "-", e)
        print("context:", type(e.__context__).__name__, "-", e.__context__)
