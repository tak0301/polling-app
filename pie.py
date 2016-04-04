import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


pieVotes = [12, 10, 3, 1]
pieLabels = ["Leia Reisner", "Hillary Clinton", "Bernie Sanders", "Martin O'Malley"]
pieColors = ['blue', 'red', 'yellow', 'purple']
plt.pie(pieVotes, labels=pieLabels, colors=pieColors)
plt.axis('equal')
plt.savefig("static/pie")
