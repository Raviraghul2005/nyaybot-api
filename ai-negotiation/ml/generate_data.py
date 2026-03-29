import pandas as pd
import random

data = []

types = ["refund", "service", "delivery", "fraud"]

for _ in range(500):
    claim = random.randint(5000, 100000)
    dtype = random.choice(types)

    severity = random.randint(1, 5)
    evidence = random.randint(1, 5)
    aggressiveness = random.randint(1, 5)
    flexibility = random.randint(1, 5)

    # BASE settlement ratio depending on dispute type
    if dtype == "refund":
        ratio = random.uniform(0.6, 0.85)
    elif dtype == "service":
        ratio = random.uniform(0.4, 0.7)
    elif dtype == "delivery":
        ratio = random.uniform(0.3, 0.6)
    else:  # fraud
        ratio = random.uniform(0.2, 0.4)

    base = claim * ratio

    # Adjustments (realistic behavior)
    base += severity * 1500          # more severe → higher payout
    base += evidence * 2500          # strong proof → higher payout
    base -= aggressiveness * 2500    # aggressive → worse deal
    base += (6-flexibility) * 1500       # flexible opponent → better deal

    # Clamp values
    settlement = max(0, min(base, claim))

    data.append([
        dtype,
        claim,
        severity,
        evidence,
        aggressiveness,
        flexibility,
        int(settlement)
    ])

df = pd.DataFrame(data, columns=[
    "type",
    "claim",
    "severity",
    "evidence",
    "aggressiveness",
    "flexibility",
    "settlement"
])

df.to_csv("data.csv", index=False)

print("Better dataset created!")