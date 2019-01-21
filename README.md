# chpy
A wrapper for the UK Companies House API, with tools for network analysis built on networkx.

# Notes
This tool enables users to build a corporate network from information on the UK Companies House API.

It's still a very early version, full of cheap bug-fixes, debugging print-outs, and poorly-documented and thoroughly un-PEP8 code, but it's published. Please feel free to mess around with what you have here, and provide feedback on anything you encounter. Although please note it's undergoing a fairly substantial re-write with a big new update due in late January.

# Installation
```
pip install chpy
```

# Dependencies
Users will require the following dependencies:
- networkx
- pandas
- fuzzywuzzy
- progressbar2

# Usage
This tool is currently intended for use alongside a Jupyter notebook, and I've provided a sample in the "example" directory.

```
from chpy.build import *

# You'll need your own API key from Companies House and to load
# it as a variable in Python.
with open('API_KEY.txt') as f:
    api_key = f.read().strip()

get_company_network("01467092", api_key)
```

chpy outputs three objects to ./data/you_company_number:
- One node list in csv format
- One edge list in csv format
- One graph in gexf format, for use with gephy or similar

# A word of warning
This is very much still in development, and due to the way Companies House (CH) data is maintained and structured a degree of caution is required when using this tool. Notably:
- CH does not maintain information on companies that have been wound up for a certain (I think five years) period of time.
- Similarly, inactive officers are not always available.
- This software makes extensive use of fuzzy matching to build links between companies and officers, due to the limitations of the unique identifier system used by the CH API.
- The system is designed to be conservative with the relationships it builds, requiring date of birth (if available) and location matches, and as such may miss relationships if a strong match isn't found. Testing has shown that the current version misses quite a few links, an issue which has been resolved in the pending update.
