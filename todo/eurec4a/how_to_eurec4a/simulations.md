---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.12
    jupytext_version: 1.7.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Simulations

The wealth of EUREC4A observations is increasingly complemented by simulations on different scales and different amount of realism.
The following pages give an overview on some of the details of these simulations and how to access them.

The currently available simulations and their outputs are:

```{code-cell} ipython3
import eurec4a
cat = eurec4a.get_intake_catalog()

def tree(cat, level=0):
    prefix = " " * (3*level)
    try:
        for child in list(cat):
            parameters = [p["name"] for p in cat[child].describe().get("user_parameters", [])]
            if len(parameters) > 0:
                parameter_str = " (" + ", ".join(parameters) + ")"
            else:
                parameter_str = ""
            print(prefix + str(child) + parameter_str)
            tree(cat[child], level+1)
    except:
        pass

tree(cat.simulations)
```
