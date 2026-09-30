import numpy as np
print("=== CR-0009 item 1's NEW gate: |ME>=0.8 - NH>=0.8| <= 5 pp ===")
print("   Accepted baselines (INVESTIGATION_REPORT_errol_map.md:334-337):")
rows=[("gap3 before",67.93,5.05),("gap3 AFTER (accepted)",10.24,4.88),
      ("bce before",45.68,0.11),("bce AFTER (accepted)",0.18,0.10)]
for nm,me,nh in rows:
    dd=abs(me-nh)
    print(f"     {nm:24s} ME>=0.8={me:6.2f}%  NH>=0.8={nh:5.2f}%  |diff|={dd:6.2f} pp  "
          f"{'PASS' if dd<=5 else '*** FAILS the new +-5 pp gate ***'}")
print("   Reviewer's bimodal attack: ME 45.0%, NH 4.9% -> |diff|=40.1 pp -> FAILS  (break CLOSED)")

print("\n=== CR-0009 item 2 gates vs PA-0021(c) (quantile over >=50 draws) ===")
rd=np.array([-549.,-185.,490.,1154.,203.,-155.,835.,-171.])   # report :204
pr=np.array([-0.119,0.204,0.168,-0.056,0.197,-0.018,0.119,0.367]) # report :206
for nm,x,gate in (("road_dist m",rd,500.0),("mean probability",pr,0.15)):
    n=len(x); m=x.mean(); sd=x.std(ddof=1); sem=sd/np.sqrt(n)
    print(f"   {nm}: n={n} (NPAIRS=8, SEED=0 -> ONE draw) mean={m:.4f} sd={sd:.4f} SEM={sem:.4f}")
    print(f"      gate {gate}: point estimate is {(gate-m)/sem:.2f} SEM below the gate")
    # bootstrap the sampling distribution of the mean at n=8
    rng=np.random.default_rng(0)
    bs=np.array([rng.choice(x,n,replace=True).mean() for _ in range(20000)])
    print(f"      bootstrap P(next 8-pair draw breaches the gate | unchanged truth) = {(np.abs(bs)>gate).mean():.3f}")
    print(f"      bootstrap 95th pct of |mean| = {np.percentile(np.abs(bs),95):.4f}  "
          f"(a PA-0021(c)-conformant gate would sit here or above)")
