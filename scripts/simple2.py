import pypistats

print(pypistats.recent("googletrans-curl", format="json"))
print(pypistats.overall("googletrans-curl", format="json"))
print(pypistats.python_minor("googletrans-curl", format="json"))
print(pypistats.system("googletrans-curl", format="json"))
