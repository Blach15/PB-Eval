import highspy
import numpy as np

h = highspy.Highs()

x0 = h.addVariable(lb = 0, ub = 4)
x1 = h.addVariable(lb = 1, ub = 7)

h.addConstr(5 <=   x0 + 2*x1 <= 15)
h.addConstr(6 <= 3*x0 + 2*x1)

h.minimize(x0 + x1)